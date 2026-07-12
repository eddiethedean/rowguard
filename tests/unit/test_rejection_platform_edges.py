from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

import rowguard
from rowguard.errors import CallbackError, ConfigurationError, RejectionThresholdError
from rowguard.rejection.base import empty_rejection_context
from rowguard.rejection.callback import CallbackDecision, CallbackPolicy
from rowguard.rejection.log import LogPolicy
from rowguard.rejection.quarantine import (
    InMemoryQuarantineProvider,
    JSONLQuarantineProvider,
    QuarantineContext,
    QuarantinePolicy,
    build_quarantine_record,
)
from rowguard.rejection.redaction import REDACTED, json_safe, prepare_rejected_for_handoff
from rowguard.results.rejected_row import RejectedRow


class UserRead(BaseModel):
    id: int
    name: str
    secret: str = "x"


class FixtureUser(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _rejected() -> RejectedRow:
    try:
        UserRead.model_validate({"id": "bad", "name": "Ada"})
    except ValidationError as error:
        return RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad", "name": "Ada", "secret": "ssn"},
            validation_error=error,
        )
    raise AssertionError("expected failure")


def test_callback_drop_does_not_retain() -> None:
    def drop(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        return CallbackDecision.DROP

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=drop,
    )
    assert result.rejected_count == 0
    assert result.rejected == ()
    assert result.statistics.rows_rejected == 1
    assert result.has_rejections is True


def test_callback_none_does_not_retain() -> None:
    def silent(rejected: object, context: object) -> None:
        del rejected, context

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=silent,
    )
    assert result.rejected_count == 0
    assert result.statistics.rows_rejected == 1


def test_callback_continue_does_not_retain() -> None:
    def cont(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        return CallbackDecision.CONTINUE

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=cont,
    )
    assert result.rejected_count == 0
    assert result.rejected == ()
    assert result.statistics.rows_rejected == 1


def test_callback_error_continue_and_log(caplog: pytest.LogCaptureFixture) -> None:
    def boom(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("nope")

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=boom,
        on_callback_error="continue",
    )
    assert result.rejected_count == 1
    assert result.rejected[0].index == 0

    with caplog.at_level("ERROR", logger="rowguard.rejection"):
        result2 = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=boom,
            on_callback_error="log",
        )
    assert result2.rejected_count == 1
    assert any("callback failed" in r.message.lower() for r in caplog.records)


def test_reject_handler_error_mode_aliases_raise() -> None:
    def boom(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("alias boom")

    with pytest.raises(CallbackError, match="alias boom") as raise_exc:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=boom,
            on_callback_error="raise",
        )
    with pytest.raises(CallbackError, match="alias boom") as alias_exc:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=boom,
            on_callback_error="reject_handler",
        )
    assert raise_exc.value.rejected is not None
    assert alias_exc.value.rejected is not None
    assert raise_exc.value.rejected.index == alias_exc.value.rejected.index


def test_callback_invalid_decision() -> None:
    def bad(rejected: object, context: object) -> object:
        del rejected, context
        return "nope"

    with pytest.raises(CallbackError, match="Invalid callback decision") as excinfo:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=bad,
        )
    assert excinfo.value.rejected is not None
    assert excinfo.value.rejected.index == 0


def test_callback_async_on_sync_api() -> None:
    async def cb(rejected: object, context: object) -> None:
        del rejected, context

    with pytest.raises(ConfigurationError, match=r"Async reject_callback|aselect"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=cb,
        )


def test_callback_values_redacted_at_api() -> None:
    seen: list[object] = []

    def cb(rejected: RejectedRow, context: object) -> CallbackDecision:
        del context
        seen.append(dict(rejected.mapping or {}))
        assert rejected.raw_row is None
        return CallbackDecision.DROP

    rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada", "secret": "ssn"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
        callback_values="redacted",
        redact_fields={"secret"},
    )
    assert seen == [{"id": "bad", "name": "Ada", "secret": REDACTED}]


def test_callback_values_metadata_only_at_api() -> None:
    seen: list[object] = []

    def cb(rejected: RejectedRow, context: object) -> None:
        del context
        seen.append(dict(rejected.mapping or {}))
        assert rejected.raw_row is None

    rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada", "secret": "ssn"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
        callback_values="metadata_only",
    )
    assert seen == [{}]


def test_callback_ordering_and_context_counters() -> None:
    events: list[tuple[int, int, int, int]] = []

    def cb(rejected: RejectedRow, context: object) -> CallbackDecision:
        events.append(
            (
                rejected.index,
                context.rejection_count,
                context.rows_accepted,
                context.rows_rejected,
            )
        )
        return CallbackDecision.DROP

    result = rowguard.validate_rows(
        rows=[
            {"id": "a", "name": "Ada"},
            {"id": 2, "name": "Bob"},
            {"id": "c", "name": "Cara"},
        ],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
    )
    assert [e[0] for e in events] == [0, 2]
    assert events[0] == (0, 1, 0, 0)
    assert events[1] == (2, 2, 1, 1)
    assert result.valid_count == 1
    assert result.statistics.rows_rejected == 2


def test_quarantine_error_collect_and_log(caplog: pytest.LogCaptureFixture) -> None:
    class Boom:
        def write(self, record: object, context: object) -> object:
            del record, context
            raise RuntimeError("fail")

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=Boom(),
        on_quarantine_error="collect",
    )
    assert result.rejected_count == 1
    assert result.rejected[0].mapping == {"id": "bad", "name": "Ada"}

    with caplog.at_level("ERROR", logger="rowguard.rejection"):
        result2 = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=Boom(),
            on_quarantine_error="log",
        )
    assert result2.rejected_count == 1
    assert any("quarantine provider failed" in r.message.lower() for r in caplog.records)


def test_quarantine_retention_none_and_rejection() -> None:
    provider = InMemoryQuarantineProvider()
    none_result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
        quarantine_retention="none",
    )
    assert none_result.rejected_count == 0
    assert none_result.quarantine_receipts == ()
    assert len(provider.records) == 1

    provider2 = InMemoryQuarantineProvider()
    rej = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider2,
        quarantine_retention="rejection",
    )
    assert rej.rejected_count == 1
    assert rej.quarantine_receipts == ()


def test_quarantine_metadata_only_and_adaptation() -> None:
    provider = InMemoryQuarantineProvider()
    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada", "secret": "ssn"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
        quarantine_values="metadata_only",
    )
    assert provider.records[0].mapping == {}
    assert len(result.quarantine_receipts) == 1

    rejected = RejectedRow(
        index=1,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=ValueError("shape"),
    )
    record = build_quarantine_record(
        rejected,
        context=empty_rejection_context(model=UserRead, execution_id="e1"),
        values="full",
        redact_fields=None,
    )
    assert record.rejection_type == "adaptation_error"
    assert record.errors[0]["msg"] == "shape"


def test_quarantine_record_errors_and_schema() -> None:
    provider = InMemoryQuarantineProvider()
    rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
    )
    record = provider.records[0]
    assert record.schema_version == "1"
    assert record.model_name == "UserRead"
    assert record.rejection_type == "validation_error"
    assert isinstance(record.errors, tuple)
    assert record.errors
    err0 = record.errors[0]
    assert set(err0) >= {"type", "loc", "msg"}
    assert isinstance(err0["loc"], list)


def test_jsonl_close_and_closed_write(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    provider = JSONLQuarantineProvider(path)
    provider.close()
    provider.close()  # idempotent
    with pytest.raises(RuntimeError, match="closed"):
        provider.write(
            build_quarantine_record(
                _rejected(),
                context=empty_rejection_context(model=UserRead),
                values="full",
                redact_fields=None,
            ),
            QuarantineContext(
                execution_id="",
                source_name=None,
                model_name="UserRead",
            ),
        )


def test_memory_closed_write() -> None:
    provider = InMemoryQuarantineProvider()
    provider.close()
    with pytest.raises(RuntimeError, match="closed"):
        provider.write(
            build_quarantine_record(
                _rejected(),
                context=empty_rejection_context(model=UserRead),
                values="full",
                redact_fields=None,
            ),
            QuarantineContext(
                execution_id="",
                source_name=None,
                model_name="UserRead",
            ),
        )


def test_prepare_rejected_and_json_safe() -> None:
    rejected = _rejected()
    prepared = prepare_rejected_for_handoff(
        rejected,
        values="redacted",
        redact_fields={"secret"},
    )
    assert prepared.mapping is not None
    assert prepared.mapping["secret"] == REDACTED
    assert prepared.raw_row is None
    assert json_safe(b"hi") == "hi"
    assert json_safe({"a": (1, 2)}) == {"a": [1, 2]}
    assert sorted(json_safe({1, 2})) == [1, 2]


def test_stream_quarantine_and_threshold(session, users_table, tmp_path: Path) -> None:
    path = tmp_path / "stream_rejects.jsonl"
    provider = JSONLQuarantineProvider(path)
    with rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        on_reject="quarantine",
        quarantine=provider,
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    # Stream close should have closed the provider (no manual close needed for durability).
    assert len(models) == 2
    assert {m.id for m in models} == {1, 3}
    assert len(stream.quarantine_receipts) == 1
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["row_index"] == 1
    with pytest.raises(RuntimeError, match="closed"):
        provider.write(
            build_quarantine_record(
                _rejected(),
                context=empty_rejection_context(model=UserRead),
                values="full",
                redact_fields=None,
            ),
            QuarantineContext(
                execution_id="",
                source_name=None,
                model_name="UserRead",
            ),
        )

    with pytest.raises(RejectionThresholdError), rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        on_reject="skip",
        max_rejections=0,
        use_sqlrules=False,
    ) as stream2:
        list(stream2)


def test_stream_callback_stop_closes_policy(session, users_table) -> None:
    closed: list[bool] = []

    class Tracking:
        def handle(self, rejected: object, context: object) -> object:
            from rowguard.rejection.base import RejectionDecision

            del rejected, context
            return RejectionDecision(continue_processing=False, retain_rejection=False)

        def close(self) -> None:
            closed.append(True)

    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        return CallbackDecision.STOP

    with rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        on_reject="callback",
        reject_callback=cb,
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    # Ada (valid) yields first; Legacy triggers STOP — Grace never processed.
    assert [m.id for m in models] == [1]
    assert stream.statistics.rows_read == 2
    assert stream.statistics.rows_accepted == 1
    assert stream.statistics.rows_rejected == 1
    assert stream.rejected == ()

    # Prove rejection-policy close is invoked on stream exit.
    from dataclasses import replace

    from rowguard.execution.context import SyncExecutionContext
    from rowguard.planning.execution_plan import RejectionPlan
    from rowguard.results.stream_result import StreamResult

    plan = rowguard.compile_plan(
        table=users_table,
        model=FixtureUser,
        on_reject="skip",
        use_sqlrules=False,
    )
    plan = replace(plan, rejection_plan=RejectionPlan(policy=Tracking(), policy_name="skip"))
    stream2 = StreamResult(plan=plan, context=SyncExecutionContext(session=session))
    with stream2:
        next(iter(stream2), None)
    assert closed == [True]


def test_buffered_jsonl_auto_close_flushes(tmp_path: Path) -> None:
    path = tmp_path / "buffered.jsonl"
    provider = JSONLQuarantineProvider(path)
    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}, {"id": 1, "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
    )
    assert len(result.quarantine_receipts) == 1
    # Engine closes the policy/provider in finally; file must already be durable.
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["schema_version"] == "1"
    with pytest.raises(RuntimeError, match="closed"):
        provider.write(
            build_quarantine_record(
                _rejected(),
                context=empty_rejection_context(model=UserRead),
                values="full",
                redact_fields=None,
            ),
            QuarantineContext(execution_id="", source_name=None, model_name="UserRead"),
        )


def test_threshold_counts_skip_and_callback_drop() -> None:
    with pytest.raises(RejectionThresholdError) as skip_exc:
        rowguard.validate_rows(
            rows=[{"id": "a", "name": "Ada"}, {"id": "b", "name": "Bob"}],
            model=UserRead,
            on_reject="skip",
            max_rejections=0,
        )
    assert skip_exc.value.rows_rejected == 1

    def drop(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        return CallbackDecision.DROP

    with pytest.raises(RejectionThresholdError) as drop_exc:
        rowguard.validate_rows(
            rows=[{"id": "a", "name": "Ada"}, {"id": "b", "name": "Bob"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=drop,
            max_rejections=0,
        )
    assert drop_exc.value.rows_rejected == 1
    assert drop_exc.value.last_rejection is not None


def test_callback_policy_async_mode_on_sync_handle() -> None:
    async def cb(rejected: object, context: object) -> None:
        del rejected, context

    policy = CallbackPolicy(callback=cb, async_mode=True)
    with pytest.raises(CallbackError, match="Async callback"):
        policy.handle(_rejected(), empty_rejection_context(model=UserRead))


def test_quarantine_requires_provider() -> None:
    with pytest.raises(ConfigurationError, match="requires quarantine"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
        )


@pytest.mark.asyncio
async def test_async_callback_invalid_decision_raises() -> None:
    async def cb(rejected: object, context: object) -> object:
        del rejected, context
        return "nope"

    policy = CallbackPolicy(callback=cb, async_mode=True)
    with pytest.raises(CallbackError, match="Invalid callback decision") as excinfo:
        await policy.ahandle(_rejected(), empty_rejection_context(model=UserRead))
    assert excinfo.value.rejected is not None


def test_log_adaptation_reason(caplog: pytest.LogCaptureFixture) -> None:
    rejected = RejectedRow(
        index=0,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=ValueError("x"),
    )
    with caplog.at_level("WARNING", logger="rowguard.rejection"):
        LogPolicy().handle(rejected, empty_rejection_context(model=UserRead))
    assert any("adaptation" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_quarantine_policy_ahandle() -> None:
    provider = InMemoryQuarantineProvider()
    policy = QuarantinePolicy(provider=provider, quarantine_retention="both")
    decision = await policy.ahandle(_rejected(), empty_rejection_context(model=UserRead))
    assert decision.retain_rejection is True
    assert decision.quarantine_receipt is not None
    assert decision.quarantine_receipt.provider == "memory"
    await provider.aclose()
