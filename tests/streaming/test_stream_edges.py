from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, select, text

import rowguard
from rowguard.errors import ConfigurationError, QueryExecutionError, RowValidationError
from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.observer import BaseStreamObserver
from rowguard.execution.streaming import SyncStreamEngine
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import PushdownConfig, RejectionConfig, StreamingConfig
from rowguard.planning.request import QueryRequest
from rowguard.results.stream_result import StreamResult


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _table() -> Table:
    metadata = MetaData()
    return Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )


def test_stream_table_and_source_rejected(session, users_table) -> None:
    with pytest.raises(ConfigurationError, match="table= or source="):
        rowguard.stream(
            session=session,
            table=users_table,
            source=users_table,
            model=UserRead,
        )


def test_stream_execution_time_and_statement(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        list(stream)
    assert stream.statement is not None
    assert stream.execution_time >= 0.0
    assert stream.statistics.rows_accepted == 2
    assert stream.rejected_count == 0


def test_stream_getattr_exports() -> None:
    assert rowguard.execution.StreamResult is StreamResult
    from rowguard import results as results_pkg

    assert results_pkg.StreamResult is StreamResult


def test_stream_close_failure_does_not_mask_validation(session, users_table) -> None:
    class BoomResult:
        def __iter__(self):
            return iter([{"id": 1, "name": "Legacy", "age": 12}])

        def close(self) -> None:
            raise RuntimeError("close failed")

    class BoomSession:
        def execute(self, *_args, **_kwargs):
            return BoomResult()

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=_table(),
            pushdown=PushdownConfig(enabled=False),
            rejection=RejectionConfig(policy="raise"),
        )
    )
    stream = SyncStreamEngine[UserRead]().open(
        plan,
        SyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(RowValidationError):
        list(stream)
    assert stream.closed


def test_stream_close_failure_surfaces_when_clean() -> None:
    class BoomResult:
        def __iter__(self):
            return iter([])

        def close(self) -> None:
            raise RuntimeError("close failed")

    class BoomSession:
        def execute(self, *_args, **_kwargs):
            return BoomResult()

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=_table(),
            pushdown=PushdownConfig(enabled=False),
            rejection=RejectionConfig(policy="skip"),
        )
    )
    stream = SyncStreamEngine[UserRead]().open(
        plan,
        SyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(RuntimeError, match="close failed"):
        list(stream)


def test_stream_execute_failure_wraps() -> None:
    class BoomSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=_table(),
            pushdown=PushdownConfig(enabled=False),
        )
    )
    stream = SyncStreamEngine[UserRead]().open(
        plan,
        SyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        next(stream)
    assert stream.closed


def test_stream_observer_failures_on_all_hooks(session, users_table) -> None:
    class BoomAll(BaseStreamObserver):
        def on_stream_start(self, *, execution_id: str) -> None:
            raise RuntimeError("start")

        def on_row_rejected(self, *, rejected: object) -> None:
            raise RuntimeError("rejected")

        def on_stream_complete(self, *, statistics: object) -> None:
            raise RuntimeError("complete")

        def on_stream_failed(self, *, error: BaseException) -> None:
            raise RuntimeError("failed")

        def on_stream_closed(self) -> None:
            raise RuntimeError("closed")

    with rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        observers=[BoomAll()],
    ) as stream:
        list(stream)

    codes = [d.code for d in stream.diagnostics]
    assert codes.count("streaming.observer_error") >= 3


def test_stream_failed_observer_on_raise(session, users_table) -> None:
    class BoomFailed(BaseStreamObserver):
        def on_stream_failed(self, *, error: BaseException) -> None:
            raise RuntimeError("failed hook")

    stream = rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="raise",
        use_sqlrules=False,
        observers=[BoomFailed()],
    )
    with pytest.raises(RowValidationError), stream:
        list(stream)
    assert stream.closed


def test_stream_with_parameters(session, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == text(":uid")).params(uid=1)
    with rowguard.stream(
        session=session,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={"uid": 1},
    ) as stream:
        models = list(stream)
    assert len(models) == 1
    assert models[0].name == "Ada"


def test_stream_connection_with_parameters(engine, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == text(":uid")).params(uid=1)
    with engine.connect() as connection, rowguard.stream(
        connection=connection,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={"uid": 1},
    ) as stream:
        models = list(stream)
    assert len(models) == 1


def test_stream_consumer_exception_notifies_failed(session, users_table) -> None:
    events: list[str] = []

    class Obs(BaseStreamObserver):
        def on_stream_failed(self, *, error: BaseException) -> None:
            events.append(type(error).__name__)

    stream = rowguard.stream(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        observers=[Obs()],
    )
    with pytest.raises(RuntimeError, match="consumer boom"), stream:
        for _model in stream:
            raise RuntimeError("consumer boom")
    assert "RuntimeError" in events
    assert stream.closed


def test_streaming_config_disables_stream_results() -> None:
    class CaptureSession:
        def __init__(self) -> None:
            self.options: object | None = None

        def execute(self, statement: object, *_args, **_kwargs):
            self.options = getattr(statement, "_execution_options", {})
            return iter([])

    session = CaptureSession()
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=_table(),
            pushdown=PushdownConfig(enabled=False),
        )
    )
    stream = StreamResult(
        plan=plan,
        context=SyncExecutionContext(session=session),
        streaming=StreamingConfig(stream_results=False),
    )
    list(stream)
    assert session.options == {} or "stream_results" not in (session.options or {})


def test_base_stream_observer_noop() -> None:
    observer = BaseStreamObserver()
    observer.on_stream_start(execution_id="x")
    observer.on_row_accepted(index=0, model=UserRead(id=1, name="Ada", age=37))
    from rowguard.results.rejected_row import RejectedRow

    observer.on_row_rejected(
        rejected=RejectedRow(
            index=0,
            model=UserRead,
            mapping=None,
            validation_error=None,
        )
    )
    from rowguard.statistics import QueryStatistics

    observer.on_stream_complete(
        statistics=QueryStatistics(
            rows_read=0,
            rows_validated=0,
            rows_accepted=0,
            rows_rejected=0,
        )
    )
    observer.on_stream_failed(error=RuntimeError("x"))
    observer.on_stream_closed()
