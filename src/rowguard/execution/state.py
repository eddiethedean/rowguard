from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.execution.processor import ProcessedRow
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics

T = TypeVar("T", bound=BaseModel)


@dataclass(slots=True)
class MutableStatistics:
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

    def record_processed(self, processed: ProcessedRow[Any]) -> None:
        self.rows_read += 1
        self.adaptation_time_ns += processed.adaptation_time_ns
        self.validation_time_ns += processed.validation_time_ns
        self.rejection_time_ns += processed.rejection_time_ns
        if processed.validated:
            self.rows_validated += 1
        if processed.model is not None:
            self.rows_accepted += 1
        else:
            self.rows_rejected += 1


@dataclass(slots=True)
class ExecutionState(Generic[T]):
    plan: ExecutionPlan[T]
    statistics: MutableStatistics = field(default_factory=MutableStatistics)
    accepted: list[T] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    quarantine_receipts: list[Any] = field(default_factory=list)

