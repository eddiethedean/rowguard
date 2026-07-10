from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.errors import QueryExecutionError, ResultAssemblyError
from rowguard.execution.processor import process_row
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.query_result import QueryResult
from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics

T = TypeVar("T", bound=BaseModel)


@dataclass(slots=True)
class _MutableStatistics:
    rows_read: int = 0
    rows_validated: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    execution_time_ns: int = 0
    adaptation_time_ns: int = 0
    validation_time_ns: int = 0
    rejection_time_ns: int = 0

    def snapshot(self) -> QueryStatistics:
        return QueryStatistics(
            rows_read=self.rows_read,
            rows_validated=self.rows_validated,
            rows_accepted=self.rows_accepted,
            rows_rejected=self.rows_rejected,
            execution_time_ns=self.execution_time_ns,
            adaptation_time_ns=self.adaptation_time_ns,
            validation_time_ns=self.validation_time_ns,
            rejection_time_ns=self.rejection_time_ns,
        )


@dataclass(slots=True)
class ExecutionState(Generic[T]):
    plan: ExecutionPlan[T]
    statistics: _MutableStatistics = field(default_factory=_MutableStatistics)
    accepted: list[T] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


class SyncExecutionEngine(Generic[T]):
    def execute(self, plan: ExecutionPlan[T]) -> QueryResult[T]:
        state = ExecutionState(plan=plan)
        state.diagnostics.extend(plan.diagnostics)
        started = perf_counter_ns()

        try:
            result = self._execute_statement(plan)
            rows = list(result)
        except Exception as exc:
            raise QueryExecutionError(f"Query execution failed: {exc}") from exc
        finally:
            state.statistics.execution_time_ns = perf_counter_ns() - started

        for index, row in enumerate(rows):
            state.statistics.rows_read += 1
            processed = process_row(row=row, index=index, plan=plan)
            state.statistics.adaptation_time_ns += processed.adaptation_time_ns
            state.statistics.validation_time_ns += processed.validation_time_ns
            state.statistics.rejection_time_ns += processed.rejection_time_ns
            state.statistics.rows_validated += 1

            if processed.model is not None:
                state.statistics.rows_accepted += 1
                state.accepted.append(processed.model)
                continue

            state.statistics.rows_rejected += 1
            if processed.retain_rejection and processed.rejected is not None:
                state.rejected.append(processed.rejected)
            if not processed.continue_processing:
                break

        return self._assemble(state)

    def validate_rows(
        self,
        *,
        plan: ExecutionPlan[T],
        rows: Iterable[Mapping[str, object]],
    ) -> QueryResult[T]:
        state = ExecutionState(plan=plan)
        state.diagnostics.extend(plan.diagnostics)
        started = perf_counter_ns()

        for index, row in enumerate(rows):
            state.statistics.rows_read += 1
            processed = process_row(row=row, index=index, plan=plan)
            state.statistics.adaptation_time_ns += processed.adaptation_time_ns
            state.statistics.validation_time_ns += processed.validation_time_ns
            state.statistics.rejection_time_ns += processed.rejection_time_ns
            state.statistics.rows_validated += 1

            if processed.model is not None:
                state.statistics.rows_accepted += 1
                state.accepted.append(processed.model)
                continue

            state.statistics.rows_rejected += 1
            if processed.retain_rejection and processed.rejected is not None:
                state.rejected.append(processed.rejected)
            if not processed.continue_processing:
                break

        state.statistics.execution_time_ns = perf_counter_ns() - started
        return self._assemble(state)

    def _execute_statement(self, plan: ExecutionPlan[T]) -> Any:
        params = dict(plan.parameters) if plan.parameters else {}
        if plan.session is not None:
            if params:
                return plan.session.execute(plan.statement, params)
            return plan.session.execute(plan.statement)
        if plan.connection is not None:
            if params:
                return plan.connection.execute(plan.statement, params)
            return plan.connection.execute(plan.statement)
        raise QueryExecutionError("No session or connection available for execution")

    def _assemble(self, state: ExecutionState[T]) -> QueryResult[T]:
        stats = state.statistics.snapshot()
        if stats.rows_accepted != len(state.accepted):
            raise ResultAssemblyError("Accepted count does not match models")
        if stats.rows_rejected < len(state.rejected):
            raise ResultAssemblyError("Rejected count is less than retained rejections")
        if stats.rows_accepted + stats.rows_rejected != stats.rows_validated:
            raise ResultAssemblyError("Validated rows are not fully classified")

        return QueryResult(
            models=tuple(state.accepted),
            rejected=tuple(state.rejected),
            statistics=stats,
            statement=state.plan.statement,
            diagnostics=tuple(state.diagnostics),
        )
