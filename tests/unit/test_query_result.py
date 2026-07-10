from __future__ import annotations

from pydantic import BaseModel

from rowguard.results.query_result import QueryResult
from rowguard.statistics import QueryStatistics


class UserRead(BaseModel):
    id: int


def test_clean_result() -> None:
    result = QueryResult(
        models=(UserRead(id=1),),
        rejected=(),
        statistics=QueryStatistics(
            rows_read=1,
            rows_validated=1,
            rows_accepted=1,
            rows_rejected=0,
        ),
    )
    assert result.is_clean
    assert not result.has_rejections
    assert result.valid_count == 1
    assert result.rejected_count == 0
    assert result.execution_time == 0.0


def test_result_with_rejections() -> None:
    stats = QueryStatistics(
        rows_read=2,
        rows_validated=2,
        rows_accepted=1,
        rows_rejected=1,
        execution_time_ns=1_000_000_000,
    )
    result = QueryResult(
        models=(UserRead(id=1),),
        rejected=(),
        statistics=stats,
        statement=object(),
    )
    assert result.has_rejections
    assert not result.is_clean
    assert result.execution_time == 1.0
    assert stats.rejection_rate == 0.5


def test_rejection_rate_zero_when_empty() -> None:
    stats = QueryStatistics(
        rows_read=0,
        rows_validated=0,
        rows_accepted=0,
        rows_rejected=0,
    )
    assert stats.rejection_rate == 0.0
