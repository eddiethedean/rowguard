from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select, text

import rowguard
from rowguard.errors import (
    ConfigurationError,
    PlanningError,
    QueryExecutionError,
    RowValidationError,
)
from rowguard.execution.async_ import AsyncExecutionEngine, aclose_result
from rowguard.execution.context import AsyncExecutionContext
from rowguard.execution.observer import BaseStreamObserver
from rowguard.execution.state import ExecutionState
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import PushdownConfig, RejectionConfig, StreamingConfig
from rowguard.planning.request import QueryRequest
from rowguard.results.async_stream_result import AsyncStreamResult
from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _table():
    from sqlalchemy import Column, Integer, MetaData, String, Table

    metadata = MetaData()
    return Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )


def _plan(*, policy: str = "skip", parameters: dict[str, object] | None = None):
    return QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=_table(),
            pushdown=PushdownConfig(enabled=False),
            rejection=RejectionConfig(policy=policy),
            parameters=parameters or {},
        )
    )


async def test_astream_config_errors(async_session, users_table) -> None:
    with pytest.raises(ConfigurationError, match="table= or statement="):
        rowguard.astream(session=async_session, model=UserRead)
    with pytest.raises(ConfigurationError, match="table= or source="):
        rowguard.astream(
            session=async_session,
            table=users_table,
            source=users_table,
            model=UserRead,
        )
    with pytest.raises(ConfigurationError, match="yield_per"):
        rowguard.astream(
            session=async_session,
            table=users_table,
            model=UserRead,
            yield_per=0,
        )


async def test_async_execution_context_requires_one_handle() -> None:
    with pytest.raises(ConfigurationError, match="session or connection"):
        AsyncExecutionContext()
    with pytest.raises(ConfigurationError, match="session or connection"):
        AsyncExecutionContext(session=object(), connection=object())


async def test_aclose_result_sync_and_async() -> None:
    class SyncClose:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class AsyncClose:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    sync_obj = SyncClose()
    await aclose_result(sync_obj)
    assert sync_obj.closed

    async_obj = AsyncClose()
    await aclose_result(async_obj)
    assert async_obj.closed

    await aclose_result(object())


async def test_async_engine_execute_failure() -> None:
    class BoomSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        await AsyncExecutionEngine[UserRead]().execute(
            _plan(),
            AsyncExecutionContext(session=BoomSession()),
        )


async def test_async_engine_async_iterable_and_params() -> None:
    class AsyncRows:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows
            self.closed = False

        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for row in self._rows:
                yield row

        async def close(self) -> None:
            self.closed = True

    class ParamSession:
        def __init__(self) -> None:
            self.seen_params: object | None = None

        async def execute(self, _statement, params=None):
            self.seen_params = params
            return AsyncRows([{"id": 1, "name": "Ada", "age": 37}])

    session = ParamSession()
    result = await AsyncExecutionEngine[UserRead]().execute(
        _plan(parameters={"uid": 1}),
        AsyncExecutionContext(session=session),
    )
    assert session.seen_params == {"uid": 1}
    assert len(result.models) == 1


async def test_async_engine_connection_path_and_raise() -> None:
    class Conn:
        async def execute(self, *_args, **_kwargs):
            return iter(
                [
                    {"id": 1, "name": "Ada", "age": 37},
                    {"id": 2, "name": "Legacy", "age": 12},
                ]
            )

        async def close(self) -> None:
            return None

    with pytest.raises(RowValidationError):
        await AsyncExecutionEngine[UserRead]().execute(
            _plan(policy="raise"),
            AsyncExecutionContext(connection=Conn()),
        )


async def test_async_engine_connection_with_params() -> None:
    class Conn:
        def __init__(self) -> None:
            self.params: object | None = None

        async def execute(self, _statement, params=None):
            self.params = params
            return iter([{"id": 1, "name": "Ada", "age": 37}])

    conn = Conn()
    result = await AsyncExecutionEngine[UserRead]().execute(
        _plan(parameters={"x": 1}),
        AsyncExecutionContext(connection=conn),
    )
    assert conn.params == {"x": 1}
    assert len(result.models) == 1


async def test_async_engine_no_handle() -> None:
    ctx = SimpleNamespace(session=None, connection=None)
    with pytest.raises(QueryExecutionError, match="No session or connection"):
        await AsyncExecutionEngine[UserRead]()._execute_statement(_plan(), ctx)  # type: ignore[arg-type]


async def test_async_engine_close_failure_masks_only_when_clean() -> None:
    class BoomClose:
        def __iter__(self):
            return iter([{"id": 1, "name": "Ada", "age": 37}])

        async def close(self) -> None:
            raise RuntimeError("close failed")

    class Session:
        async def execute(self, *_args, **_kwargs):
            return BoomClose()

    with pytest.raises(RuntimeError, match="close failed"):
        await AsyncExecutionEngine[UserRead]().execute(
            _plan(),
            AsyncExecutionContext(session=Session()),
        )


async def test_async_engine_close_failure_does_not_mask_primary() -> None:
    class BoomClose:
        def __iter__(self):
            return iter([{"id": 1, "name": "Legacy", "age": 12}])

        async def close(self) -> None:
            raise RuntimeError("close failed")

    class Session:
        async def execute(self, *_args, **_kwargs):
            return BoomClose()

    with pytest.raises(RowValidationError):
        await AsyncExecutionEngine[UserRead]().execute(
            _plan(policy="raise"),
            AsyncExecutionContext(session=Session()),
        )


async def test_async_engine_assembly_guards() -> None:
    from rowguard.errors import ResultAssemblyError

    engine = AsyncExecutionEngine[UserRead]()
    plan = _plan()
    state = ExecutionState(plan=plan)
    state.statistics.rows_read = 1
    state.statistics.rows_accepted = 1
    state.statistics.rows_rejected = 0
    state.statistics.rows_validated = 1
    with pytest.raises(ResultAssemblyError, match="Accepted count"):
        engine._assemble(state)

    state.accepted.append(UserRead(id=1, name="Ada", age=37))
    state.rejected.append(
        RejectedRow(index=0, model=UserRead, mapping=None, validation_error=None)
    )
    with pytest.raises(ResultAssemblyError, match="Rejected count"):
        engine._assemble(state)

    state.rejected.clear()
    state.statistics.rows_read = 2
    with pytest.raises(ResultAssemblyError, match="not fully classified"):
        engine._assemble(state)

    state.statistics.rows_read = 1
    state.statistics.rows_validated = 2
    with pytest.raises(ResultAssemblyError, match="Validated count"):
        engine._assemble(state)


async def test_astream_observer_errors_do_not_abort(async_session, users_table) -> None:
    class BoomObserver(BaseStreamObserver):
        def on_stream_start(self, *, execution_id: str) -> None:
            raise RuntimeError("start")

        def on_row_accepted(self, *, index: int, model: BaseModel) -> None:
            raise RuntimeError("accepted")

        def on_row_rejected(self, *, rejected: object) -> None:
            raise RuntimeError("rejected")

        def on_stream_complete(self, *, statistics: object) -> None:
            raise RuntimeError("complete")

        def on_stream_closed(self) -> None:
            raise RuntimeError("closed")

    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        observers=[BoomObserver()],
    ) as stream:
        models = [model async for model in stream]

    assert len(models) == 2
    assert any(d.code == "streaming.observer_error" for d in stream.diagnostics)


async def test_astream_skip_and_properties(async_session, users_table) -> None:
    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        yield_per=1,
    ) as stream:
        models = [model async for model in stream]
    assert [m.name for m in models] == ["Ada", "Grace"]
    assert stream.statement is not None
    assert stream.execution_time >= 0.0
    assert stream.diagnostics is not None
    assert stream.has_rejections is True  # skip still counts rejected rows
    assert stream.is_clean is False
    assert stream.rejected_count == 0
    assert stream.closed


async def test_astream_reenter_after_close(async_session, users_table) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    async for _ in stream:
        pass
    assert stream.closed
    with pytest.raises(QueryExecutionError, match="closed"):
        async with stream:
            pass


async def test_astream_execute_failure_wraps() -> None:
    class BoomSession:
        async def stream(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        await stream.__anext__()
    assert stream.closed


async def test_astream_close_failure_does_not_mask_validation() -> None:
    class BoomResult:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_done", False):
                raise StopAsyncIteration
            self._done = True
            return {"id": 1, "name": "Legacy", "age": 12}

        async def close(self) -> None:
            raise RuntimeError("close failed")

    class BoomSession:
        async def stream(self, *_args, **_kwargs):
            return BoomResult()

    stream = AsyncStreamResult(
        plan=_plan(policy="raise"),
        context=AsyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(RowValidationError):
        await stream.__anext__()
    assert stream.closed


async def test_astream_close_failure_inside_with() -> None:
    class BoomResult:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def close(self) -> None:
            raise RuntimeError("close failed")

    class BoomSession:
        async def stream(self, *_args, **_kwargs):
            return BoomResult()

    events: list[str] = []

    class Obs(BaseStreamObserver):
        def on_stream_complete(self, *, statistics: object) -> None:
            events.append("complete")

        def on_stream_failed(self, *, error: BaseException) -> None:
            events.append(f"failed:{type(error).__name__}")

        def on_stream_closed(self) -> None:
            events.append("closed")

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=BoomSession()),
        observers=[Obs()],
    )
    with pytest.raises(RuntimeError, match="close failed"):
        async with stream:
            async for _ in stream:
                pass
    assert "complete" in events
    assert "closed" in events
    assert not any(e.startswith("failed:") for e in events)


async def test_astream_consumer_exception_notifies_failed(async_session, users_table) -> None:
    events: list[str] = []

    class Obs(BaseStreamObserver):
        def on_stream_failed(self, *, error: BaseException) -> None:
            events.append(type(error).__name__)

    class BoomFailed(BaseStreamObserver):
        def on_stream_failed(self, *, error: BaseException) -> None:
            raise RuntimeError("failed hook")

    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
        observers=[Obs(), BoomFailed()],
    )
    with pytest.raises(RuntimeError, match="consumer boom"):
        async with stream:
            async for _model in stream:
                raise RuntimeError("consumer boom")
    assert "RuntimeError" in events
    assert stream.closed
    assert any(d.code == "streaming.observer_error" for d in stream.diagnostics)


async def test_astream_failed_observer_on_raise(async_session, users_table) -> None:
    class BoomFailed(BaseStreamObserver):
        def on_stream_failed(self, *, error: BaseException) -> None:
            raise RuntimeError("failed hook")

    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="raise",
        use_sqlrules=False,
        observers=[BoomFailed()],
    )
    with pytest.raises(RowValidationError):
        async with stream:
            async for _ in stream:
                pass
    assert any(d.code == "streaming.observer_error" for d in stream.diagnostics)


async def test_astream_with_parameters(async_session, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == text(":uid")).params(uid=1)
    async with rowguard.astream(
        session=async_session,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={"uid": 1},
    ) as stream:
        models = [m async for m in stream]
    assert len(models) == 1
    assert models[0].name == "Ada"


async def test_astream_connection_with_parameters(async_engine, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == text(":uid")).params(uid=1)
    async with async_engine.connect() as connection, rowguard.astream(
        connection=connection,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={"uid": 1},
    ) as stream:
        models = [m async for m in stream]
    assert len(models) == 1


async def test_astream_execute_fallback_without_stream() -> None:
    class ExecOnly:
        async def execute(self, statement, params=None):
            class Rows:
                def __aiter__(self_inner):
                    return self_inner

                async def __anext__(self_inner):
                    raise StopAsyncIteration

                async def close(self_inner) -> None:
                    return None

            return Rows()

    stream = AsyncStreamResult(
        plan=_plan(parameters={"a": 1}),
        context=AsyncExecutionContext(session=ExecOnly()),
        streaming=StreamingConfig(stream_results=False, yield_per=None),
    )
    async with stream:
        models = [m async for m in stream]
    assert models == []


async def test_astream_process_row_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomResult:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_n", 0) >= 1:
                raise StopAsyncIteration
            self._n = getattr(self, "_n", 0) + 1
            return {"id": 1, "name": "Ada", "age": 37}

        async def close(self) -> None:
            return None

    class Session:
        async def stream(self, *_args, **_kwargs):
            return BoomResult()

    import rowguard.results.async_stream_result as asr

    async def boom_row(**_kwargs):
        raise RuntimeError("process boom")

    monkeypatch.setattr(asr, "aprocess_row", boom_row)
    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=Session()),
    )
    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        await stream.__anext__()
    assert stream.closed

    async def boom_rowguard(**_kwargs):
        raise PlanningError("guard boom")

    monkeypatch.setattr(asr, "aprocess_row", boom_rowguard)
    stream2 = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=Session()),
    )
    with pytest.raises(PlanningError, match="guard boom"):
        await stream2.__anext__()
    assert stream2.closed


async def test_astream_no_handle() -> None:
    stream = AsyncStreamResult(
        plan=_plan(),
        context=SimpleNamespace(session=None, connection=None),  # type: ignore[arg-type]
    )
    with pytest.raises(QueryExecutionError, match="No session or connection"):
        await stream.__anext__()


async def test_astream_rowguard_error_on_start() -> None:
    class BoomSession:
        async def stream(self, *_args, **_kwargs):
            raise PlanningError("plan boom")

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=BoomSession()),
    )
    with pytest.raises(PlanningError):
        await stream.__anext__()
    assert stream.closed


async def test_streaming_config_async_path() -> None:
    with pytest.raises(ConfigurationError, match="yield_per"):
        StreamingConfig(yield_per=-5)


async def test_async_getattr_exports() -> None:
    assert rowguard.execution.AsyncStreamResult is rowguard.AsyncStreamResult
    from rowguard import results as results_pkg

    assert results_pkg.AsyncStreamResult is rowguard.AsyncStreamResult
    with pytest.raises(AttributeError):
        _ = results_pkg.NotAThing  # type: ignore[attr-defined]
    import rowguard.execution as execution_pkg

    with pytest.raises(AttributeError):
        _ = execution_pkg.NotAThing  # type: ignore[attr-defined]


async def test_astream_idempotent_close(async_session, users_table) -> None:
    async with rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        _ = [m async for m in stream]
    await stream.close()
    await stream.close()
    assert stream.closed
    assert isinstance(stream.rejected, tuple)
    assert isinstance(stream.statistics, QueryStatistics)


async def test_astream_anext_after_close_raises(async_session, users_table) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    async with stream:
        while True:
            try:
                await stream.__anext__()
            except StopAsyncIteration:
                break
    with pytest.raises(QueryExecutionError, match="closed"):
        await stream.__anext__()


async def test_astream_closed_next_model_stop() -> None:
    class Empty:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def close(self) -> None:
            return None

    class Session:
        async def stream(self, *_args, **_kwargs):
            return Empty()

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=Session()),
    )
    await stream._ensure_started()
    stream._closed = True
    with pytest.raises(StopAsyncIteration):
        await stream._next_model()


async def test_astream_finish_complete_idempotent() -> None:
    class Empty:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def close(self) -> None:
            return None

    class Session:
        async def stream(self, *_args, **_kwargs):
            return Empty()

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=Session()),
    )
    await stream._ensure_started()
    await stream._finish_complete()
    await stream._finish_complete()
    assert stream.closed


async def test_astream_execute_fallback_no_params() -> None:
    class ExecOnly:
        async def execute(self, statement, params=None):
            class Rows:
                def __aiter__(self_inner):
                    return self_inner

                async def __anext__(self_inner):
                    raise StopAsyncIteration

                async def close(self_inner) -> None:
                    return None

            return Rows()

    stream = AsyncStreamResult(
        plan=_plan(),
        context=AsyncExecutionContext(session=ExecOnly()),
        streaming=StreamingConfig(stream_results=False),
    )
    async with stream:
        assert [m async for m in stream] == []


async def test_astream_connection_stream_path() -> None:
    class Conn:
        async def stream(self, statement, params=None):
            class Rows:
                def __aiter__(self_inner):
                    return self_inner

                async def __anext__(self_inner):
                    if getattr(self_inner, "_done", False):
                        raise StopAsyncIteration
                    self_inner._done = True
                    return {"id": 1, "name": "Ada", "age": 37}

                async def close(self_inner) -> None:
                    return None

            return Rows()

    stream = AsyncStreamResult(
        plan=_plan(parameters={"z": 1}),
        context=AsyncExecutionContext(connection=Conn()),
        streaming=StreamingConfig(stream_results=True, yield_per=2),
    )
    async with stream:
        models = [m async for m in stream]
    assert len(models) == 1
