from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Generic, TypeVar

from pydantic import BaseModel

from rowguard.errors import RowAdaptationError
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.rejection.base import RejectionDecision
from rowguard.results.rejected_row import RejectedRow

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ProcessedRow(Generic[T]):
    model: T | None
    rejected: RejectedRow | None
    retain_rejection: bool
    continue_processing: bool
    adaptation_time_ns: int = 0
    validation_time_ns: int = 0
    rejection_time_ns: int = 0
    validated: bool = False
    raise_error: BaseException | None = None


def process_row(
    *,
    row: object,
    index: int,
    plan: ExecutionPlan[T],
) -> ProcessedRow[T]:
    """Adapt, validate, and apply rejection policy for a single row."""
    adaptation_time_ns = 0
    validation_time_ns = 0

    started = perf_counter_ns()
    try:
        adapted = plan.adapter.adapt(row)
    except RowAdaptationError as error:
        adaptation_time_ns = perf_counter_ns() - started
        rejected = RejectedRow(
            index=index,
            model=plan.model,
            mapping=None,
            validation_error=None,
            adaptation_error=error,
            raw_row=row,
        )
        return _handle_rejection(
            plan,
            rejected,
            adaptation_time_ns=adaptation_time_ns,
            validated=False,
        )
    except Exception as error:
        adaptation_time_ns = perf_counter_ns() - started
        wrapped = RowAdaptationError(
            f"Adapter failed: {error}",
            model=plan.model,
            row_index=index,
        )
        wrapped.__cause__ = error
        rejected = RejectedRow(
            index=index,
            model=plan.model,
            mapping=None,
            validation_error=None,
            adaptation_error=wrapped,
            raw_row=row,
        )
        return _handle_rejection(
            plan,
            rejected,
            adaptation_time_ns=adaptation_time_ns,
            validated=False,
        )
    adaptation_time_ns = perf_counter_ns() - started

    started = perf_counter_ns()
    outcome = plan.validator.validate(adapted.mapping)
    validation_time_ns = perf_counter_ns() - started

    if outcome.accepted:
        assert outcome.model is not None
        return ProcessedRow(
            model=outcome.model,
            rejected=None,
            retain_rejection=False,
            continue_processing=True,
            adaptation_time_ns=adaptation_time_ns,
            validation_time_ns=validation_time_ns,
            validated=True,
        )

    rejected = RejectedRow(
        index=index,
        model=plan.model,
        mapping=adapted.mapping,
        validation_error=outcome.error,
        raw_row=adapted.raw_row,
    )
    return _handle_rejection(
        plan,
        rejected,
        adaptation_time_ns=adaptation_time_ns,
        validation_time_ns=validation_time_ns,
        validated=True,
    )


def _handle_rejection(
    plan: ExecutionPlan[T],
    rejected: RejectedRow,
    *,
    adaptation_time_ns: int = 0,
    validation_time_ns: int = 0,
    validated: bool = False,
) -> ProcessedRow[T]:
    started = perf_counter_ns()
    decision: RejectionDecision = plan.rejection_policy.handle(rejected)
    rejection_time_ns = perf_counter_ns() - started
    return ProcessedRow(
        model=None,
        rejected=rejected,
        retain_rejection=decision.retain_rejection,
        continue_processing=decision.continue_processing,
        adaptation_time_ns=adaptation_time_ns,
        validation_time_ns=validation_time_ns,
        rejection_time_ns=rejection_time_ns,
        validated=validated,
        raise_error=decision.error,
    )
