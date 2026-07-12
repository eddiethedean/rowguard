from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

import rowguard
from rowguard.errors import CallbackError, QuarantineError, RejectionThresholdError
from rowguard.rejection.callback import CallbackDecision
from rowguard.rejection.quarantine import InMemoryQuarantineProvider, JSONLQuarantineProvider
from rowguard.rejection.redaction import REDACTED, redact_mapping


class UserRead(BaseModel):
    id: int
    name: str
    secret: str = "x"


def test_callback_retain_and_context() -> None:
    seen: list[int] = []

    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected
        seen.append(context.rejection_count)
        return CallbackDecision.RETAIN

    result = rowguard.validate_rows(
        rows=[{"id": "bad", "name": "Ada"}, {"id": 2, "name": "Bob"}],
        model=UserRead,
        on_reject="callback",
        reject_callback=cb,
    )
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert seen == [1]


def test_callback_stop() -> None:
    def cb(rejected: object, context: object) -> CallbackDecision:
        del rejected, context
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
    assert result.statistics.rows_read == 1
    assert result.valid_count == 0


def test_callback_error_raises() -> None:
    def cb(rejected: object, context: object) -> None:
        del rejected, context
        raise RuntimeError("boom")

    with pytest.raises(CallbackError, match="boom"):
        rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}],
            model=UserRead,
            on_reject="callback",
            reject_callback=cb,
        )


def test_log_policy(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="rowguard.rejection"):
        result = rowguard.validate_rows(
            rows=[{"id": "bad", "name": "Ada"}, {"id": 1, "name": "Ada"}],
            model=UserRead,
            on_reject="log",
        )
    assert result.valid_count == 1
    assert result.rejected_count == 0
    assert result.statistics.rows_rejected == 1
    assert any("rejected row" in r.message.lower() for r in caplog.records)


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
    assert len(provider.records) == 1
    assert provider.records[0].schema_version == "1"
    assert provider.records[0].rejection_type == "validation_error"


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
    assert len(result.quarantine_receipts) == 1


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
    assert excinfo.value.rejected is not None
    assert excinfo.value.rejected.index == 0


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
    line = path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["mapping"]["secret"] == REDACTED
    assert payload["mapping"]["name"] == "Ada"


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
    assert excinfo.value.rows_rejected == 2
    assert excinfo.value.max_rejections == 1


def test_max_rejection_rate_threshold() -> None:
    with pytest.raises(RejectionThresholdError, match="rate"):
        rowguard.validate_rows(
            rows=[
                {"id": "a", "name": "Ada"},
                {"id": 2, "name": "Bob"},
            ],
            model=UserRead,
            on_reject="skip",
            max_rejection_rate=0.4,
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
        del rejected
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
    assert result.rejected_count == 1
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
    assert len(provider.records) == 1
