from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from time import perf_counter_ns
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.errors import QueryExecutionError, RowGuardError
from rowguard.execution.async_ import aclose_result
from rowguard.execution.context import AsyncExecutionContext
from rowguard.execution.guards import require_session_for_entity_plan
from rowguard.execution.observer import StreamObserver
from rowguard.execution.processor import process_row
from rowguard.execution.state import MutableStatistics
from rowguard.planning.config import StreamingConfig
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics

T = TypeVar("T", bound=BaseModel)


class AsyncStreamResult(Generic[T]):
    """Async incremental validated-row iterator with context-managed DB cleanup.

    Accepted models are yielded and never retained. Prefer
    ``async with rowguard.astream(...) as stream:`` or ``async for model in stream``.
    """

    def __init__(
        self,
        *,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
        streaming: StreamingConfig | None = None,
        observers: Sequence[StreamObserver] = (),
    ) -> None:
        self._plan = plan
        self._context = context
        self._streaming = streaming or StreamingConfig()
        self._observers: tuple[StreamObserver, ...] = tuple(observers)
        self._statistics = MutableStatistics()
        self._rejected: list[RejectedRow] = []
        self._diagnostics: list[Diagnostic] = list(plan.diagnostics)
        self._db_result: Any | None = None
        self._row_aiter: AsyncIterator[Any] | None = None
        self._index = 0
        self._started = False
        self._closed = False
        self._completed = False
        self._started_ns = 0
        self._primary_error: BaseException | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def statistics(self) -> QueryStatistics:
        return self._statistics.snapshot()

    @property
    def rejected(self) -> tuple[RejectedRow, ...]:
        return tuple(self._rejected)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)

    @property
    def statement(self) -> Any:
        return self._plan.statement

    @property
    def has_rejections(self) -> bool:
        return self._statistics.rows_rejected > 0

    @property
    def is_clean(self) -> bool:
        return not self.has_rejections

    @property
    def rejected_count(self) -> int:
        return len(self._rejected)

    @property
    def execution_time(self) -> float:
        return self._statistics.execution_time_ns / 1_000_000_000

    def __aiter__(self) -> AsyncIterator[T]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[T]:
        await self._ensure_started()
        try:
            while True:
                yield await self._next_model()
        except StopAsyncIteration:
            return
        finally:
            await self.close()

    async def __aenter__(self) -> AsyncStreamResult[T]:
        await self._ensure_started()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        if exc is not None and self._primary_error is None:
            self._primary_error = exc
            self._notify_failed(exc)
        await self.close()

    async def __anext__(self) -> T:
        await self._ensure_started()
        return await self._next_model()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stamp_execution_time()

        close_error: BaseException | None = None
        if self._db_result is not None:
            try:
                await aclose_result(self._db_result)
            except Exception as error:
                close_error = error
            self._db_result = None
            self._row_aiter = None

        self._notify_closed()

        if close_error is not None and self._primary_error is None:
            self._primary_error = close_error
            raise close_error

    async def _next_model(self) -> T:
        if self._closed:
            raise StopAsyncIteration

        assert self._row_aiter is not None
        while True:
            try:
                row = await self._row_aiter.__anext__()
            except StopAsyncIteration:
                await self._finish_complete()
                raise

            index = self._index
            self._index += 1
            try:
                processed = process_row(row=row, index=index, plan=self._plan)
            except RowGuardError as error:
                self._primary_error = error
                self._notify_failed(error)
                await self.close()
                raise
            except Exception as error:
                wrapped = QueryExecutionError(f"Query execution failed: {error}")
                wrapped.__cause__ = error
                self._primary_error = wrapped
                self._notify_failed(wrapped)
                await self.close()
                raise wrapped from error

            self._statistics.record_processed(processed)

            if processed.model is not None:
                self._notify_accepted(index, processed.model)
                return processed.model

            if processed.rejected is not None:
                self._notify_rejected(processed.rejected)
                if processed.retain_rejection:
                    self._rejected.append(processed.rejected)

            if processed.raise_error is not None:
                self._primary_error = processed.raise_error
                self._notify_failed(processed.raise_error)
                await self.close()
                raise processed.raise_error

            if not processed.continue_processing:
                await self._finish_complete()
                raise StopAsyncIteration

    async def _finish_complete(self) -> None:
        if self._completed:
            await self.close()
            return
        self._completed = True
        self._stamp_execution_time()
        self._notify_complete()
        await self.close()

    def _stamp_execution_time(self) -> None:
        if self._started_ns:
            self._statistics.execution_time_ns = perf_counter_ns() - self._started_ns

    async def _ensure_started(self) -> None:
        if self._closed:
            raise QueryExecutionError("AsyncStreamResult is closed and cannot be reused")
        if self._started:
            return
        self._started = True
        self._started_ns = perf_counter_ns()
        self._notify_start()
        try:
            self._db_result = await self._stream_statement()
            self._row_aiter = self._db_result.__aiter__()
        except RowGuardError as error:
            self._primary_error = error
            self._notify_failed(error)
            await self.close()
            raise
        except Exception as error:
            wrapped = QueryExecutionError(f"Query execution failed: {error}")
            wrapped.__cause__ = error
            self._primary_error = wrapped
            self._notify_failed(wrapped)
            await self.close()
            raise wrapped from error

    async def _stream_statement(self) -> Any:
        require_session_for_entity_plan(self._plan, session=self._context.session)
        statement = self._plan.statement
        options: dict[str, Any] = {}
        if self._streaming.stream_results:
            options["stream_results"] = True
        if self._streaming.yield_per is not None:
            options["yield_per"] = self._streaming.yield_per
        if options:
            statement = statement.execution_options(**options)

        params = dict(self._plan.parameters) if self._plan.parameters else {}
        if self._context.session is not None:
            target = self._context.session
        else:
            target = self._context.connection
        if target is None:
            raise QueryExecutionError("No session or connection available for execution")

        stream = getattr(target, "stream", None)
        if callable(stream):
            if params:
                return await stream(statement, params)
            return await stream(statement)

        # Fallback for unusual async handles that only expose execute().
        if params:
            return await target.execute(statement, params)
        return await target.execute(statement)

    def _notify_start(self) -> None:
        for observer in self._observers:
            try:
                observer.on_stream_start(execution_id=self._plan.execution_id)
            except Exception as error:
                self._handle_observer_error(error)

    def _notify_accepted(self, index: int, model: T) -> None:
        for observer in self._observers:
            try:
                observer.on_row_accepted(index=index, model=model)
            except Exception as error:
                self._handle_observer_error(error)

    def _notify_rejected(self, rejected: RejectedRow) -> None:
        for observer in self._observers:
            try:
                observer.on_row_rejected(rejected=rejected)
            except Exception as error:
                self._handle_observer_error(error)

    def _notify_complete(self) -> None:
        stats = self._statistics.snapshot()
        for observer in self._observers:
            try:
                observer.on_stream_complete(statistics=stats)
            except Exception as error:
                self._handle_observer_error(error)

    def _notify_failed(self, error: BaseException) -> None:
        for observer in self._observers:
            try:
                observer.on_stream_failed(error=error)
            except Exception as observer_error:
                self._handle_observer_error(observer_error)

    def _notify_closed(self) -> None:
        for observer in self._observers:
            try:
                observer.on_stream_closed()
            except Exception as error:
                if self._primary_error is None:
                    self._handle_observer_error(error)
                else:
                    with suppress(Exception):
                        self._handle_observer_error(error)

    def _handle_observer_error(self, error: Exception) -> None:
        self._diagnostics.append(
            Diagnostic(
                code="streaming.observer_error",
                severity="warning",
                execution_id=self._plan.execution_id,
                metadata={"error": str(error), "error_type": type(error).__name__},
            )
        )
