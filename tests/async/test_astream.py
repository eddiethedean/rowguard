from __future__ import annotations

import asyncio
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard
from rowguard.errors import QueryExecutionError, RowValidationError
from rowguard.execution.observer import BaseStreamObserver


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


class RecordingObserver(BaseStreamObserver):
    def __init__(self) -> None:
        self.events: list[str] = []

    def on_stream_start(self, *, execution_id: str) -> None:
        self.events.append(f"start:{execution_id}")

    def on_row_accepted(self, *, index: int, model: BaseModel) -> None:
        self.events.append(f"accepted:{index}:{model.name}")  # type: ignore[attr-defined]

    def on_row_rejected(self, *, rejected: object) -> None:
        self.events.append(f"rejected:{getattr(rejected, 'index', None)}")

    def on_stream_complete(self, *, statistics: object) -> None:
        self.events.append(f"complete:{getattr(statistics, 'execution_time_ns', 0)}")

    def on_stream_failed(self, *, error: BaseException) -> None:
        self.events.append(f"failed:{type(error).__name__}")

    def on_stream_closed(self) -> None:
        self.events.append("closed")


@pytest.mark.integration
async def test_astream_collect(async_session, users_table) -> None:
    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        models = [model async for model in stream]

    assert [m.name for m in models] == ["Ada", "Grace"]
    assert stream.statistics.rows_read == 3
    assert stream.rejected_count == 1
    assert stream.closed


@pytest.mark.integration
async def test_astream_statement_parity(async_session, users_table) -> None:
    buffered = await rowguard.aselect(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    async with rowguard.astream(
        session=async_session,
        statement=select(users_table),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        streamed = [model async for model in stream]

    assert streamed == list(buffered.models)
    assert stream.statistics.rows_accepted == buffered.statistics.rows_accepted


@pytest.mark.integration
async def test_astream_raise_records_rejection(async_session, users_table) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="raise",
        use_sqlrules=False,
    )
    seen: list[str] = []
    with pytest.raises(RowValidationError):
        async with stream:
            async for model in stream:
                seen.append(model.name)
    assert seen == ["Ada"]
    assert stream.closed
    assert stream.statistics.rows_rejected >= 1
    assert not stream.is_clean


@pytest.mark.integration
async def test_astream_early_break_closes(async_session, users_table) -> None:
    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        async for model in stream:
            assert model.name == "Ada"
            break
    assert stream.closed


@pytest.mark.integration
async def test_astream_bare_async_for_break_eventually_closes(
    async_session, users_table
) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    async for model in stream:
        assert model.name == "Ada"
        break
    # Async-generator aclose is scheduled on the event loop.
    for _ in range(5):
        if stream.closed:
            break
        await asyncio.sleep(0)
    assert stream.closed


@pytest.mark.integration
async def test_astream_manual_close(async_session, users_table) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    async with stream:
        first = await stream.__anext__()
        assert first.name == "Ada"
    assert stream.closed
    with pytest.raises(QueryExecutionError, match="closed"):
        async with stream:
            pass


@pytest.mark.integration
async def test_astream_observers(async_session, users_table) -> None:
    observer = RecordingObserver()
    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        observers=[observer],
    ) as stream:
        _ = [model async for model in stream]

    assert observer.events[0].startswith("start:")
    assert "accepted:0:Ada" in observer.events
    assert "rejected:1" in observer.events
    assert any(e.startswith("complete:") and e != "complete:0" for e in observer.events)
    assert observer.events[-1] == "closed"


@pytest.mark.integration
async def test_astream_with_connection(async_connection, users_table) -> None:
    async with rowguard.astream(
        connection=async_connection,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        names = [model.name async for model in stream]
    assert names == ["Ada", "Grace"]
