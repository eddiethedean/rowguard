from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

import rowguard
from rowguard.errors import (
    CallbackError,
    ConfigurationError,
    QuarantineError,
    RejectionThresholdError,
    RowValidationError,
)
from rowguard.rejection.callback import CallbackDecision
from rowguard.rejection.quarantine import InMemoryQuarantineProvider, JSONLQuarantineProvider
from rowguard.rejection.redaction import REDACTED, redact_mapping


class UserRead(BaseModel):
    id: int
    name: str
    secret: str = "x"


def test_callback_retain_and_context() -> None:
    seen: list[tuple[int, int, int, int]] = []

    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected
        seen.append(
            (
                context.rejection_count,
                context.rows_read,
                context.rows_accepted,
                context.rows_rejected,
            )
        )
        return CallbackDecision.RETAIN

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}, {"id": 2, "name": "Bob"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
    )
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert result.rejected[0].index == 0
    assert result.rejected[0].mapping == {"id": "bad", "name": "Ada"}
    # Pre-increment snapshot: first rejection sees rows_rejected=0, rejection_count=1
    assert seen == [(1, 0, 0, 0)]


def test_callback_stop_does_not_retain_and_stops() -> None:
    calls = 0

    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
        nonlocal calls
        calls += 1
        return CallbackDecision.STOP

    result = rowguard.validate_rows(
        rows=[
            {"id": "bad", "name": "Ada"},
            {"id": "worse", "name": "Bob"},
            {"id": 3, "name": "Cara"},
        ],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
    )
    assert calls == 1
    assert result.statistics.rows_read == 1
    assert result.statistics.rows_rejected == 1
    assert result.valid_count == 0
    assert result.rejected_count == 0
    assert result.rejected == ()


def test_callback_error_raises() -> None:
    def cb(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("boom")

    with pytest.raises(CallbackError, match="boom") as excinfo:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=cb,
        )
    err = excinfo.value
    assert err.rejected is not None
    assert err.rejected.index == 0
    assert err.rejected.mapping == {"id": "bad", "name": "Ada"}
    assert isinstance(err.original_error, RuntimeError)
    assert err.__cause__ is err.original_error


def test_log_policy(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="rowguard.rejection"):
        result = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}, {"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="log",
        )
    assert result.valid_count == 1
    assert result.rejected_count == 0
    assert result.rejected == ()
    assert result.has_rejections is True
    assert result.statistics.rows_rejected == 1
    assert any("rejected row" in r.message.lower() for r in caplog.records)


def test_log_has_rejections_without_retained() -> None:
    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="log",
    )
    assert result.has_rejections is True
    assert result.rejected == ()
    assert result.rejected_count == 0


def test_quarantine_memory_receipt_retention() -> None:
    provider = InMemoryQuarantineProvider()
    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}, {"id": 1, "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
    )
    assert result.valid_count == 1
    assert result.rejected_count == 0
    assert len(result.quarantine_receipts) == 1
    receipt = result.quarantine_receipts[0]
    assert receipt.provider == "memory"
    assert receipt.record_id
    assert receipt.location == f"memory:{receipt.record_id}"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.schema_version == "1"
    assert record.rejection_type == "validation_error"
    assert record.row_index == 0
    assert record.mapping == {"id": "bad", "name": "Ada"}
    assert record.errors
    assert record.errors[0]["type"]
    assert "loc" in record.errors[0]
    assert record.errors[0]["msg"]


def test_quarantine_both_retention() -> None:
    provider = InMemoryQuarantineProvider()
    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
        quarantine_retention="both",
    )
    assert result.rejected_count == 1
    assert result.rejected[0].index == 0
    assert len(result.quarantine_receipts) == 1
    assert provider.records[0].row_index == result.rejected[0].index


def test_quarantine_provider_failure_preserves_rejection() -> None:
    class Boom:
        def write(self, record: object, context: object) -> object:
            del record, context
            raise RuntimeError("disk full")

    with pytest.raises(QuarantineError, match="disk full") as excinfo:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=Boom(),
        )
    err = excinfo.value
    assert err.rejected is not None
    assert err.rejected.index == 0
    assert err.rejected.mapping == {"id": "bad", "name": "Ada"}
    assert isinstance(err.original_error, RuntimeError)
    assert err.__cause__ is err.original_error


def test_jsonl_quarantine(tmp_path: Path) -> None:
    path = tmp_path / "rejects.jsonl"
    provider = JSONLQuarantineProvider(path)
    try:
        result = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada", "secret": "ssn"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=provider,
            quarantine_values="redacted",
            redact_fields={"secret"},
        )
    finally:
        provider.close()
    assert len(result.quarantine_receipts) == 1
    assert result.quarantine_receipts[0].provider == "jsonl"
    assert result.quarantine_receipts[0].location == str(path)
    line = path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["schema_version"] == "1"
    assert payload["rejection_type"] == "validation_error"
    assert payload["mapping"]["secret"] == REDACTED
    assert payload["mapping"]["name"] == "Ada"
    assert payload["errors"]


def test_redact_mapping_modes() -> None:
    mapping = {"id": 1, "secret": "x"}
    assert redact_mapping(mapping, redact_fields={"secret"}, mode="full") == {
        "id": 1,
        "secret": REDACTED,
    }
    assert redact_mapping(mapping, redact_fields=None, mode="metadata_only") == {}
    assert redact_mapping(mapping, redact_fields=None, mode="redacted") == {
        "id": REDACTED,
        "secret": REDACTED,
    }


def test_max_rejections_threshold() -> None:
    ok = rowguard.validate_rows(
        rows=[{"id": "a", "name": "Ada"}, {"id": 2, "name": "Bob"}],
        model=UserRead,
        on_reject="skip",
        max_rejections=1,
    )
    assert ok.statistics.rows_rejected == 1
    assert ok.valid_count == 1

    with pytest.raises(RejectionThresholdError) as excinfo:
        rowguard.validate_rows(
            rows=[
                {"id": "a", "name": "Ada"},
                {"id": "b", "name": "Bob"},
                {"id": 3, "name": "Cara"},
            ],
            model=UserRead,
            on_reject="skip",
            max_rejections=1,
        )
    err = excinfo.value
    assert err.rows_rejected == 2
    assert err.max_rejections == 1
    assert err.last_rejection is not None
    assert err.last_rejection.index == 1


def test_max_rejection_rate_threshold() -> None:
    # Thresholds check after each rejection. Valid-first so rate is 1/2 when checked.
    # Equality does not trip (strict >): 1/2 == 0.5
    ok = rowguard.validate_rows(
        rows=[
            {"id": 2, "name": "Bob"},
            {"id": "a", "name": "Ada"},
        ],
        model=UserRead,
        on_reject="skip",
        max_rejection_rate=0.5,
    )
    assert ok.statistics.rows_rejected == 1
    assert ok.valid_count == 1

    with pytest.raises(RejectionThresholdError, match="rate") as excinfo:
        rowguard.validate_rows(
            rows=[
                {"id": 2, "name": "Bob"},
                {"id": "a", "name": "Ada"},
            ],
            model=UserRead,
            on_reject="skip",
            max_rejection_rate=0.4,
        )
    assert excinfo.value.last_rejection is not None
    assert abs(excinfo.value.rows_rejected / excinfo.value.rows_read - 0.5) < 1e-9


def test_quarantine_transaction_must_be_separate() -> None:
    with pytest.raises(ConfigurationError, match="quarantine_transaction"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=InMemoryQuarantineProvider(),
            quarantine_transaction="same",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_async_callback() -> None:
    from pydantic import Field
    from sqlalchemy import Column, Integer, MetaData, String, Table, insert
    from sqlalchemy.ext.asyncio import create_async_engine

    metadata = MetaData()
    users = Table(
        "async_cb_users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )

    class Read(BaseModel):
        id: int
        name: str
        age: int = Field(ge=0)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            insert(users),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Bad", "age": -1},
            ],
        )

    seen: list[int] = []

    async def cb(rejected: object, context: object) -> CallbackDecision:
        assert isinstance(rejected, rowguard.RejectedRow)
        assert rejected.index == 1
        seen.append(context.rejection_count)
        return CallbackDecision.RETAIN

    async with engine.connect() as connection:
        result = await rowguard.aselect(
            connection=connection,
            table=users,
            model=Read,
            on_reject="callback",
            reject_callback=cb,
            use_sqlrules=False,
        )
    await engine.dispose()
    assert result.valid_count == 1
    assert result.models[0].id == 1
    assert result.rejected_count == 1
    assert result.rejected[0].index == 1
    assert seen == [1]


@pytest.mark.asyncio
async def test_async_quarantine_memory() -> None:
    from pydantic import Field
    from sqlalchemy import Column, Integer, MetaData, String, Table, insert
    from sqlalchemy.ext.asyncio import create_async_engine

    metadata = MetaData()
    users = Table(
        "async_q_users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )

    class Read(BaseModel):
        id: int
        name: str
        age: int = Field(ge=0)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(insert(users), [{"id": 1, "name": "Bad", "age": -1}])

    provider = InMemoryQuarantineProvider()
    async with engine.connect() as connection:
        result = await rowguard.aselect(
            connection=connection,
            table=users,
            model=Read,
            on_reject="quarantine",
            quarantine=provider,
            use_sqlrules=False,
        )
    await engine.dispose()
    assert len(result.quarantine_receipts) == 1
    assert result.quarantine_receipts[0].provider == "memory"
    assert len(provider.records) == 1
    assert provider.records[0].rejection_type == "validation_error"


@pytest.mark.asyncio
async def test_async_callback_error_raises_from_aselect() -> None:
    from pydantic import Field
    from sqlalchemy import Column, Integer, MetaData, String, Table, insert
    from sqlalchemy.ext.asyncio import create_async_engine

    metadata = MetaData()
    users = Table(
        "async_cb_err",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )

    class Read(BaseModel):
        id: int
        name: str
        age: int = Field(ge=0)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(insert(users), [{"id": 1, "name": "Bad", "age": -1}])

    async def boom(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("async boom")

    async with engine.connect() as connection:
        with pytest.raises(CallbackError, match="async boom") as excinfo:
            await rowguard.aselect(
                connection=connection,
                table=users,
                model=Read,
                on_reject="callback",
                reject_callback=boom,
                use_sqlrules=False,
            )
    await engine.dispose()
    assert excinfo.value.rejected is not None
    assert isinstance(excinfo.value.original_error, RuntimeError)


def test_policy_error_precedes_threshold() -> None:
    with pytest.raises(RowValidationError):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="raise",
            max_rejections=0,
        )

    def boom(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("cb boom")

    with pytest.raises(CallbackError, match="cb boom") as cb_exc:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=boom,
            max_rejections=0,
        )
    assert isinstance(cb_exc.value.original_error, RuntimeError)

    class Boom:
        def write(self, record: object, context: object) -> object:
            del record, context
            raise RuntimeError("q boom")

        def close(self) -> None:
            return None

    with pytest.raises(QuarantineError, match="q boom") as q_exc:
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=Boom(),
            max_rejections=0,
        )
    assert isinstance(q_exc.value.original_error, RuntimeError)


def test_buffered_policy_close_does_not_mask_validation_error() -> None:
    from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
    from rowguard.execution.sync import SyncExecutionEngine
    from rowguard.planning.execution_plan import (
        AdapterPlan,
        ExecutionPlan,
        PushdownPlan,
        RejectionPlan,
        ValidationPlan,
    )
    from rowguard.rejection.policies import RaisePolicy
    from rowguard.validation.pydantic import PydanticValidator

    class BoomCloseRaise(RaisePolicy):
        def close(self) -> None:
            raise RuntimeError("policy close boom")

    plan: ExecutionPlan[UserRead] = ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=BoomCloseRaise(), policy_name="raise"),
        use_sqlrules=False,
    )
    with pytest.raises(RowValidationError):
        SyncExecutionEngine().validate_rows(
            plan=plan,
            rows=[{"id": "bad", "name": "Ada"}],
        )


def test_redaction_strips_validation_input_and_source_identity() -> None:
    from pydantic import ValidationError

    from rowguard.rejection.redaction import prepare_rejected_for_handoff
    from rowguard.results.rejected_row import RejectedRow

    try:
        UserRead.model_validate({"id": "bad", "name": "Ada", "secret": "SSN"})
    except ValidationError as error:
        rejected = RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad", "name": "Ada", "secret": "SSN"},
            validation_error=error,
            source_identity={"secret": "111-22-3333", "id": 1},
        )
    else:
        raise AssertionError("expected validation failure")

    prepared = prepare_rejected_for_handoff(
        rejected,
        values="redacted",
        redact_fields={"secret"},
    )
    assert prepared.mapping == {"id": "bad", "name": "Ada", "secret": REDACTED}
    assert prepared.source_identity == {"secret": REDACTED, "id": 1}
    assert prepared.raw_row is None
    assert prepared.validation_error is not None
    for item in prepared.validation_error.errors():
        assert "input" not in item

    provider = InMemoryQuarantineProvider()
    rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada", "secret": "SSN"}],
        model=UserRead,
        on_reject="quarantine",
        quarantine=provider,
        quarantine_values="redacted",
        redact_fields={"secret"},
        quarantine_retention="both",
    )
    record = provider.records[0]
    assert record.mapping is not None
    assert record.mapping["secret"] == REDACTED
    for item in record.errors:
        assert "input" not in item


def test_irrelevant_rejection_knobs_rejected() -> None:
    with pytest.raises(ConfigurationError, match="callback_values"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="skip",
            callback_values="redacted",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="on_callback_error"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="skip",
            on_callback_error="log",
        )
    with pytest.raises(ConfigurationError, match="on_quarantine_error"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="skip",
            on_quarantine_error="log",
        )
    with pytest.raises(ConfigurationError, match="quarantine_values"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="skip",
            quarantine_values="redacted",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="quarantine_retention"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="skip",
            quarantine_retention="both",
        )
    with pytest.raises(ConfigurationError, match="redact_fields"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="collect",
            redact_fields={"secret"},
        )
    with pytest.raises(ConfigurationError, match="quarantine_retention"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=InMemoryQuarantineProvider(),
            quarantine_retention="nope",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="Unsupported on_callback_error"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=lambda *_a: None,
            on_callback_error="nope",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="Unsupported callback_values"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=lambda *_a: None,
            callback_values="nope",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="Unsupported on_quarantine_error"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=InMemoryQuarantineProvider(),
            on_quarantine_error="nope",  # type: ignore[arg-type]
        )
    with pytest.raises(ConfigurationError, match="Unsupported quarantine_values"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="quarantine",
            quarantine=InMemoryQuarantineProvider(),
            quarantine_values="nope",  # type: ignore[arg-type]
        )


def test_buffered_policy_close_raises_when_clean() -> None:
    from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
    from rowguard.execution.sync import SyncExecutionEngine
    from rowguard.planning.execution_plan import (
        AdapterPlan,
        ExecutionPlan,
        PushdownPlan,
        RejectionPlan,
        ValidationPlan,
    )
    from rowguard.rejection.policies import SkipPolicy
    from rowguard.validation.pydantic import PydanticValidator

    class BoomCloseSkip(SkipPolicy):
        def close(self) -> None:
            raise RuntimeError("policy close boom clean")

    plan: ExecutionPlan[UserRead] = ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=BoomCloseSkip(), policy_name="skip"),
        use_sqlrules=False,
    )
    with pytest.raises(RuntimeError, match="policy close boom clean"):
        SyncExecutionEngine().validate_rows(
            plan=plan,
            rows=[{"id": 1, "name": "Ada"}],
        )


def test_redaction_metadata_only_drops_identity() -> None:
    from rowguard.rejection.redaction import prepare_rejected_for_handoff
    from rowguard.results.rejected_row import RejectedRow

    rejected = RejectedRow(
        index=0,
        model=UserRead,
        mapping={"id": "bad", "secret": "x"},
        validation_error=None,
        source_identity={"secret": "111"},
    )
    prepared = prepare_rejected_for_handoff(
        rejected,
        values="metadata_only",
        redact_fields=None,
    )
    assert prepared.mapping == {}
    assert prepared.source_identity is None


def test_plan_cache_distinguishes_rejection_thresholds() -> None:
    from sqlalchemy import Column, Integer, MetaData, String, Table

    from rowguard.api import _build_request
    from rowguard.planning.compiler import QueryPlanner

    users = Table(
        "cache_users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )
    planner = QueryPlanner[UserRead](cache_enabled=True)
    request_a = _build_request(
        model=UserRead,
        source=users,
        on_reject="skip",
        max_rejections=1,
        async_execution=False,
    )
    request_b = _build_request(
        model=UserRead,
        source=users,
        on_reject="skip",
        max_rejections=2,
        async_execution=False,
    )
    plan1 = planner.compile(request_a)
    plan2 = planner.compile(request_b)
    assert plan1.rejection_plan.max_rejections == 1
    assert plan2.rejection_plan.max_rejections == 2
    assert planner._cache_key(request_a) != planner._cache_key(request_b)
