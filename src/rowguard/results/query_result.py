from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class QueryResult(Generic[T]):
    models: tuple[T, ...]
    rejected: tuple[RejectedRow, ...]
    statistics: QueryStatistics
    statement: Any | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def has_rejections(self) -> bool:
        return self.statistics.rows_rejected > 0

    @property
    def is_clean(self) -> bool:
        return not self.has_rejections

    @property
    def valid_count(self) -> int:
        return len(self.models)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def execution_time(self) -> float:
        """Total execution time in seconds."""
        return self.statistics.execution_time_ns / 1_000_000_000
