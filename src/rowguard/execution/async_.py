from __future__ import annotations

import inspect
from time import perf_counter_ns
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.errors import QueryExecutionError, ResultAssemblyError, RowGuardError
from rowguard.execution.context import AsyncExecutionContext
from rowguard.execution.processor import ProcessedRow, process_row
from rowguard.execution.state import ExecutionState
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.query_result import QueryResult

T = TypeVar("T", bound=BaseModel)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def aclose_result(result: Any) -> None:
    close = getattr(result, "close", None)
    if callable(close):
        await _maybe_await(close())


class AsyncExecutionEngine(Generic[T]):
    async def execute(
        self,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
    ) -> QueryResult[T]:
        state = ExecutionState(plan=plan)
        state.diagnostics.extend(plan.diagnostics)
        started = perf_counter_ns()
        result: Any | None = None
        primary_error: BaseException | None = None

        try:
            result = await self._execute_statement(plan, context)
            index = 0
            # AsyncResult supports async iteration; CursorResult is sync-iterable.
            if hasattr(result, "__aiter__"):
                async for row in result:
                    processed = process_row(row=row, index=index, plan=plan)
                    index += 1
                    if not self._consume_processed(state, processed):
                        break
            else:
                for row in result:
                    processed = process_row(row=row, index=index, plan=plan)
                    index += 1
                    if not self._consume_processed(state, processed):
                        break
        except RowGuardError as exc:
            primary_error = exc
            raise
        except Exception as exc:
            primary_error = QueryExecutionError(f"Query execution failed: {exc}")
            raise primary_error from exc
        finally:
            if result is not None:
                try:
                    await aclose_result(result)
                except Exception:
                    if primary_error is None:
                        raise
            state.statistics.execution_time_ns = perf_counter_ns() - started

        return self._assemble(state)

    def _consume_processed(
        self,
        state: ExecutionState[T],
        processed: ProcessedRow[T],
    ) -> bool:
        state.statistics.record_processed(processed)

        if processed.model is not None:
            state.accepted.append(processed.model)
            return True

        if processed.retain_rejection and processed.rejected is not None:
            state.rejected.append(processed.rejected)
        if processed.raise_error is not None:
            raise processed.raise_error
        return processed.continue_processing

    async def _execute_statement(
        self,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
    ) -> Any:
        params = dict(plan.parameters) if plan.parameters else {}
        if context.session is not None:
            if params:
                return await context.session.execute(plan.statement, params)
            return await context.session.execute(plan.statement)
        if context.connection is not None:
            if params:
                return await context.connection.execute(plan.statement, params)
            return await context.connection.execute(plan.statement)
        raise QueryExecutionError("No session or connection available for execution")

    def _assemble(self, state: ExecutionState[T]) -> QueryResult[T]:
        stats = state.statistics.snapshot()
        if stats.rows_accepted != len(state.accepted):
            raise ResultAssemblyError("Accepted count does not match models")
        if stats.rows_rejected < len(state.rejected):
            raise ResultAssemblyError("Rejected count is less than retained rejections")
        if stats.rows_accepted + stats.rows_rejected != stats.rows_read:
            raise ResultAssemblyError("Read rows are not fully classified")
        if stats.rows_validated > stats.rows_read:
            raise ResultAssemblyError("Validated count exceeds rows read")

        return QueryResult(
            models=tuple(state.accepted),
            rejected=tuple(state.rejected),
            statistics=stats,
            statement=state.plan.statement,
            diagnostics=tuple(state.diagnostics),
        )
