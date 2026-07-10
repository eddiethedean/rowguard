from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard
from rowguard.errors import ConfigurationError, QueryExecutionError, RowValidationError
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
        self.events.append("complete")

    def on_stream_failed(self, *, error: BaseException) -> None:
        self.events.append(f"failed:{type(error).__name__}")

    def on_stream_closed(self) -> None:
        self.events.append("closed")


def test_stream_table_collect(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        models = list(stream)

    assert [m.name for m in models] == ["Ada", "Grace"]
    assert stream.statistics.rows_read == 3
    assert stream.statistics.rows_accepted == 2
    assert stream.statistics.rows_rejected == 1
    assert stream.rejected_count == 1
    assert stream.rejected[0].mapping is not None
    assert stream.rejected[0].mapping["name"] == "Legacy"
    assert stream.closed
    assert stream.has_rejections
    assert not stream.is_clean


def test_stream_statement_parity_with_select(session, users_table) -> None:
    buffered = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    with rowguard.stream(
        session=session,
        statement=select(users_table),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        streamed = list(stream)

    assert streamed == list(buffered.models)
    assert stream.statistics.rows_read == buffered.statistics.rows_read
    assert stream.statistics.rows_accepted == buffered.statistics.rows_accepted
    assert stream.statistics.rows_rejected == buffered.statistics.rows_rejected
    assert len(stream.rejected) == len(buffered.rejected)


def test_stream_skip_policy(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        models = list(stream)

    assert [m.name for m in models] == ["Ada", "Grace"]
    assert stream.rejected_count == 0
    assert stream.statistics.rows_rejected == 1
    assert stream.has_rejections


def test_stream_raise_policy_closes(session, users_table) -> None:
    stream = rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="raise",
        use_sqlrules=False,
    )
    with pytest.raises(RowValidationError), stream:
        list(stream)
    assert stream.closed
    assert stream.statistics.rows_rejected >= 1
    assert not stream.is_clean


def test_stream_early_break_without_with_closes(session, users_table) -> None:
    stream = rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    for model in stream:
        assert model.name == "Ada"
        break
    assert stream.closed


def test_stream_complete_observer_sees_execution_time(session, users_table) -> None:
    class TimingObserver(BaseStreamObserver):
        def __init__(self) -> None:
            self.complete_ns: int | None = None

        def on_stream_complete(self, *, statistics: object) -> None:
            self.complete_ns = getattr(statistics, "execution_time_ns", None)

    observer = TimingObserver()
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        observers=[observer],
    ) as stream:
        list(stream)
    assert observer.complete_ns is not None
    assert observer.complete_ns > 0


def test_stream_with_connection(engine, users_table) -> None:
    with engine.connect() as connection, rowguard.stream(
        connection=connection,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    assert len(models) == 2


def test_stream_early_break_closes(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        for model in stream:
            assert model.name == "Ada"
            break
    assert stream.closed


def test_stream_manual_close(session, users_table) -> None:
    stream = rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    first = next(stream)
    assert first.name == "Ada"
    stream.close()
    assert stream.closed
    with pytest.raises(QueryExecutionError, match="closed"):
        next(stream)


def test_stream_observers(session, users_table) -> None:
    observer = RecordingObserver()
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        observers=[observer],
    ) as stream:
        list(stream)

    assert observer.events[0].startswith("start:")
    assert "accepted:0:Ada" in observer.events
    assert "rejected:1" in observer.events
    assert "accepted:2:Grace" in observer.events
    assert "complete" in observer.events
    assert observer.events[-1] == "closed"


def test_stream_observer_failure_does_not_abort(session, users_table) -> None:
    class BoomObserver(BaseStreamObserver):
        def on_row_accepted(self, *, index: int, model: BaseModel) -> None:
            raise RuntimeError("observer boom")

    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        observers=[BoomObserver()],
    ) as stream:
        models = list(stream)

    assert len(models) == 2
    assert any(d.code == "streaming.observer_error" for d in stream.diagnostics)


def test_stream_requires_table_or_statement(session, users_table) -> None:
    with pytest.raises(ConfigurationError, match="table= or statement="):
        rowguard.stream(session=session, model=UserRead)
    with pytest.raises(ConfigurationError, match="table= or statement="):
        rowguard.stream(
            session=session,
            table=users_table,
            statement=select(users_table),
            model=UserRead,
        )


def test_stream_invalid_yield_per(session, users_table) -> None:
    with pytest.raises(ConfigurationError, match="yield_per"):
        rowguard.stream(
            session=session,
            table=users_table,
            model=UserRead,
            on_reject="skip",
            use_sqlrules=False,
            yield_per=0,
        )


def test_stream_yield_per(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        yield_per=1,
    ) as stream:
        models = list(stream)
    assert [m.name for m in models] == ["Ada", "Grace"]


def test_stream_ordering_preserved(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        names = [m.name for m in stream]
    assert names == ["Ada", "Grace"]


def test_stream_sqlrules_pushdown(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    ) as stream:
        models = list(stream)
    assert len(models) == 2
    assert stream.statistics.rows_rejected == 0
    assert any(d.code == "sqlrules.pushdown_applied" for d in stream.diagnostics)
