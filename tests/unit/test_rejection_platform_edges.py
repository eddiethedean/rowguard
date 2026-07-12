from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

import rowguard
from rowguard.errors import CallbackError
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


def test_callback_drop_and_continue_none() -> None:
    def drop(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        return CallbackDecision.DROP

    def silent(rejected: object, context: object) -> None:
        del rejected, context

    for cb in (drop, silent):
        result = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=cb,
        )
        assert result.rejected_count == 0
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


def test_callback_invalid_decision() -> None:
    def bad(rejected: object, context: object) -> object:
        del rejected, context
        return "nope"

    with pytest.raises(CallbackError, match="Invalid callback decision"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=bad,
        )


def test_callback_async_on_sync_api() -> None:
    async def cb(rejected: object, context: object) -> None:
        del rejected, context

    with pytest.raises(Exception, match=r"Async reject_callback|aselect"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=cb,
        )


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

    with caplog.at_level("ERROR", logger="rowguard.rejection"):
        result2 = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=Boom(),
            on_quarantine_error="log",
        )
    assert result2.rejected_count == 1


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
    assert result.quarantine_receipts

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
    assert json_safe({1, 2})


def test_stream_quarantine_and_threshold(session, users_table) -> None:
    from typing import Annotated

    from pydantic import Field
    from sqlalchemy import select

    from rowguard.errors import RejectionThresholdError

    class FixtureUser(BaseModel):
        id: int
        name: str
        age: Annotated[int, Field(ge=18)]

    provider = InMemoryQuarantineProvider()
    with rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        on_reject="quarantine",
        quarantine=provider,
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    assert len(models) >= 1
    assert stream.quarantine_receipts
    provider.close()

    with pytest.raises(RejectionThresholdError), rowguard.stream(
        session=session,
        statement=select(users_table),
        model=FixtureUser,
        on_reject="skip",
        max_rejections=0,
        use_sqlrules=False,
    ) as stream2:
        list(stream2)


def test_callback_policy_async_mode_on_sync_handle() -> None:
    async def cb(rejected: object, context: object) -> None:
        del rejected, context

    policy = CallbackPolicy(callback=cb, async_mode=True)
    with pytest.raises(CallbackError, match="Async callback"):
        policy.handle(_rejected(), empty_rejection_context(model=UserRead))


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
    assert decision.retain_rejection
    assert decision.quarantine_receipt is not None
    await provider.aclose()
