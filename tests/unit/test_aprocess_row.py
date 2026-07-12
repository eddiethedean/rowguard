from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard
from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import PlanningError, QueryExecutionError
from rowguard.execution.processor import aprocess_row
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ValidationPlan,
)
from rowguard.rejection.callback import CallbackDecision, CallbackPolicy
from rowguard.rejection.policies import CollectPolicy
from rowguard.rejection.quarantine import InMemoryQuarantineProvider, QuarantinePolicy
from rowguard.rejection.redaction import json_safe
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str
    age: int = Field(ge=0)


class FixtureUser(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _plan(policy: object | None = None) -> ExecutionPlan[UserRead]:
    return ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(
            policy=policy or CollectPolicy(),
            policy_name="collect",
        ),
        use_sqlrules=False,
        execution_id="exec-1",
    )


@pytest.mark.asyncio
async def test_aprocess_row_accept_and_reject() -> None:
    accepted = await aprocess_row(
        row={"id": 1, "name": "Ada", "age": 30},
        index=0,
        plan=_plan(),
    )
    assert accepted.model is not None

    rejected = await aprocess_row(
        row={"id": "bad", "name": "Ada", "age": 30},
        index=1,
        plan=_plan(),
    )
    assert rejected.rejected is not None
    assert rejected.retain_rejection


@pytest.mark.asyncio
async def test_aprocess_row_adaptation_failure() -> None:
    processed = await aprocess_row(row=object(), index=2, plan=_plan())
    assert processed.model is None
    assert processed.rejected is not None
    assert processed.rejected.adaptation_error is not None


@pytest.mark.asyncio
async def test_aprocess_row_async_callback() -> None:
    seen: list[str] = []

    async def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected
        seen.append(context.execution_id)
        return CallbackDecision.RETAIN

    plan = _plan(CallbackPolicy(callback=cb, async_mode=True))
    processed = await aprocess_row(
        row={"id": "bad", "name": "Ada", "age": 1},
        index=0,
        plan=plan,
    )
    assert processed.retain_rejection
    assert seen == ["exec-1"]


@pytest.mark.asyncio
async def test_aprocess_row_async_quarantine() -> None:
    provider = InMemoryQuarantineProvider()
    plan = _plan(QuarantinePolicy(provider=provider, quarantine_retention="receipt"))
    processed = await aprocess_row(
        row={"id": "bad", "name": "Ada", "age": 1},
        index=0,
        plan=plan,
    )
    assert processed.quarantine_receipt is not None
    assert len(provider.records) == 1
    await provider.aclose()


@pytest.mark.asyncio
async def test_quarantine_aclose_and_async_only_provider() -> None:
    from pydantic import ValidationError

    from rowguard.errors import QuarantineError
    from rowguard.rejection.base import empty_rejection_context
    from rowguard.results.rejected_row import RejectedRow

    class AsyncOnly:
        async def awrite(self, record: object, context: object) -> object:
            from rowguard.results.quarantine import QuarantineReceipt

            del record, context
            return QuarantineReceipt(
                provider="async-only",
                record_id="1",
                location=None,
                written_at=datetime.now(tz=timezone.utc),
            )

        async def aclose(self) -> None:
            return None

    policy = QuarantinePolicy(provider=AsyncOnly(), async_mode=True)
    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "age": 1})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )
    with pytest.raises(QuarantineError, match="Async quarantine"):
        policy.handle(rejected, empty_rejection_context(model=UserRead))

    decision = await policy.ahandle(rejected, empty_rejection_context(model=UserRead))
    assert decision.quarantine_receipt is not None
    await policy.aclose()


@pytest.mark.asyncio
async def test_quarantine_ahandle_sync_write_fallback() -> None:
    from pydantic import ValidationError

    from rowguard.rejection.base import empty_rejection_context
    from rowguard.results.rejected_row import RejectedRow

    class SyncOnly:
        def __init__(self) -> None:
            self.closed = False

        def write(self, record: object, context: object) -> object:
            from rowguard.results.quarantine import QuarantineReceipt

            del record, context
            return QuarantineReceipt(
                provider="sync-only",
                record_id="1",
                location=None,
                written_at=datetime.now(tz=timezone.utc),
            )

        def close(self) -> None:
            self.closed = True

    provider = SyncOnly()
    policy = QuarantinePolicy(provider=provider)
    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "age": 1})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )
    decision = await policy.ahandle(rejected, empty_rejection_context(model=UserRead))
    assert decision.quarantine_receipt is not None
    await policy.aclose()
    assert provider.closed


@pytest.mark.asyncio
async def test_callback_async_error_modes() -> None:
    from pydantic import ValidationError

    from rowguard.errors import CallbackError
    from rowguard.rejection.base import empty_rejection_context
    from rowguard.results.rejected_row import RejectedRow

    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "age": 1})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )

    async def boom(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("async boom")

    raise_policy = CallbackPolicy(
        callback=boom,
        async_mode=True,
        on_callback_error="raise",
    )
    decision = await raise_policy.ahandle(rejected, empty_rejection_context(model=UserRead))
    assert isinstance(decision.error, CallbackError)

    cont = CallbackPolicy(callback=boom, async_mode=True, on_callback_error="continue")
    decision2 = await cont.ahandle(rejected, empty_rejection_context(model=UserRead))
    assert decision2.continue_processing
    assert decision2.retain_rejection


@pytest.mark.asyncio
async def test_jsonl_awrite(tmp_path: object) -> None:
    from pathlib import Path

    from pydantic import ValidationError

    from rowguard.rejection.base import empty_rejection_context
    from rowguard.rejection.quarantine import (
        JSONLQuarantineProvider,
        QuarantineContext,
        build_quarantine_record,
    )
    from rowguard.results.rejected_row import RejectedRow

    path = Path(str(tmp_path)) / "a.jsonl"
    provider = JSONLQuarantineProvider(path)
    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "age": 1})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )
    record = build_quarantine_record(
        rejected,
        context=empty_rejection_context(model=UserRead),
        values="full",
        redact_fields=None,
    )
    receipt = await provider.awrite(
        record,
        QuarantineContext(execution_id="", source_name=None, model_name="UserRead"),
    )
    assert receipt.provider == "jsonl"
    await provider.aclose()


@pytest.mark.asyncio
async def test_aprocess_row_generic_adapter_exception() -> None:
    class BoomAdapter:
        def adapt(self, row: object) -> object:
            del row
            raise RuntimeError("adapter exploded")

    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=BoomAdapter()),  # type: ignore[arg-type]
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=CollectPolicy(), policy_name="collect"),
        use_sqlrules=False,
    )
    processed = await aprocess_row(row={"id": 1}, index=0, plan=plan)
    assert processed.rejected is not None
    assert "adapter exploded" in str(processed.rejected.adaptation_error)


def test_stream_process_row_errors(monkeypatch: pytest.MonkeyPatch, session, users_table) -> None:
    import rowguard.results.stream_result as sr

    def boom(**_kwargs: object) -> object:
        raise RuntimeError("process boom")

    monkeypatch.setattr(sr, "process_row", boom)
    with pytest.raises(QueryExecutionError, match="Query execution failed"), rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        use_sqlrules=False,
    ) as stream:
        next(stream)

    def boom_rg(**_kwargs: object) -> object:
        raise PlanningError("guard boom")

    monkeypatch.setattr(sr, "process_row", boom_rg)
    with pytest.raises(PlanningError, match="guard boom"), rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        use_sqlrules=False,
    ) as stream:
        next(stream)


def test_api_rejection_kwarg_guards() -> None:
    from rowguard.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="reject_callback"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="raise",
            reject_callback=lambda *_a: None,
        )
    with pytest.raises(ConfigurationError, match="quarantine"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="raise",
            quarantine=InMemoryQuarantineProvider(),
        )
    with pytest.raises(ConfigurationError, match="max_rejections"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            max_rejections=-1,
        )
    with pytest.raises(ConfigurationError, match="max_rejection_rate"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            max_rejection_rate=1.5,
        )


@pytest.mark.asyncio
async def test_callback_sync_on_async_path() -> None:
    seen: list[int] = []

    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        seen.append(1)
        return CallbackDecision.DROP

    plan = _plan(CallbackPolicy(callback=cb, async_mode=False))
    processed = await aprocess_row(
        row={"id": "bad", "name": "Ada", "age": 1},
        index=0,
        plan=plan,
    )
    assert not processed.retain_rejection
    assert seen == [1]


def test_callback_returns_awaitable_on_sync() -> None:
    from pydantic import ValidationError

    from rowguard.errors import CallbackError
    from rowguard.rejection.base import empty_rejection_context
    from rowguard.results.rejected_row import RejectedRow

    def cb(rejected: object, context: object) -> object:
        del rejected, context

        async def coro() -> None:
            return None

        return coro()

    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "age": 1})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )
    policy = CallbackPolicy(callback=cb, async_mode=False)
    decision = policy.handle(rejected, empty_rejection_context(model=UserRead))
    assert isinstance(decision.error, CallbackError)


def test_json_safe_isoformat_failure() -> None:
    class BadDate:
        def isoformat(self) -> str:
            raise ValueError("nope")

        def __str__(self) -> str:
            return "bad-date"

    assert json_safe(BadDate()) == "bad-date"


def test_stream_policy_close_error(monkeypatch: pytest.MonkeyPatch, session, users_table) -> None:
    class BoomClose:
        def handle(self, rejected: object, context: object) -> object:
            from rowguard.rejection.base import RejectionDecision

            del rejected, context
            return RejectionDecision(continue_processing=True, retain_rejection=False)

        def close(self) -> None:
            raise RuntimeError("policy close failed")

    plan = rowguard.compile_plan(
        table=users_table,
        model=FixtureUser,
        on_reject="skip",
        use_sqlrules=False,
    )
    from dataclasses import replace

    from rowguard.planning.execution_plan import RejectionPlan

    plan = replace(
        plan,
        rejection_plan=RejectionPlan(policy=BoomClose(), policy_name="skip"),  # type: ignore[arg-type]
    )
    from rowguard.execution.context import SyncExecutionContext
    from rowguard.results.stream_result import StreamResult

    stream = StreamResult(plan=plan, context=SyncExecutionContext(session=session))
    with pytest.raises(RuntimeError, match="policy close failed"), stream:
        list(stream)
