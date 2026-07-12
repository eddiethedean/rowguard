from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.errors import RowAdaptationError
from rowguard.integrations.sqlalchemy_orm import (
    entity_source_identity,
    extract_entity,
)
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.rejection.base import RejectionContext, RejectionDecision, empty_rejection_context
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
    quarantine_receipt: Any | None = None


def _best_effort_source_identity(row: object) -> dict[str, object] | None:
    try:
        entity = extract_entity(row)
        if entity is None:
            return None
        return entity_source_identity(entity)
    except Exception:
        return None


def build_rejection_context(
    *,
    plan: ExecutionPlan[T],
    rows_read: int = 0,
    rows_accepted: int = 0,
    rows_rejected: int = 0,
) -> RejectionContext:
    source_name = None
    if plan.resolved_source is not None:
        source_name = plan.resolved_source.source_name
    return RejectionContext(
        execution_id=plan.execution_id,
        model=plan.model,
        statement=plan.statement,
        source_name=source_name,
        rejection_count=rows_rejected + 1,
        rows_read=rows_read,
        rows_accepted=rows_accepted,
        rows_rejected=rows_rejected,
    )


def process_row(
    *,
    row: object,
    index: int,
    plan: ExecutionPlan[T],
    context: RejectionContext | None = None,
) -> ProcessedRow[T]:
    """Adapt, validate, and apply rejection policy for a single row."""
    adaptation_time_ns = 0
    validation_time_ns = 0
    rejection_context = context or empty_rejection_context(
        model=plan.model,
        execution_id=plan.execution_id,
        statement=plan.statement,
        source_name=(
            plan.resolved_source.source_name if plan.resolved_source is not None else None
        ),
    )

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
            source_identity=_best_effort_source_identity(row),
        )
        return _handle_rejection(
            plan,
            rejected,
            rejection_context,
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
            source_identity=_best_effort_source_identity(row),
        )
        return _handle_rejection(
            plan,
            rejected,
            rejection_context,
            adaptation_time_ns=adaptation_time_ns,
            validated=False,
        )
    adaptation_time_ns = perf_counter_ns() - started

    started = perf_counter_ns()
    subject = (
        adapted.attributes_subject
        if adapted.attributes_subject is not None
        else adapted.mapping
    )
    outcome = plan.validator.validate(subject)
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
        source_identity=adapted.source_identity,
    )
    return _handle_rejection(
        plan,
        rejected,
        rejection_context,
        adaptation_time_ns=adaptation_time_ns,
        validation_time_ns=validation_time_ns,
        validated=True,
    )


async def aprocess_row(
    *,
    row: object,
    index: int,
    plan: ExecutionPlan[T],
    context: RejectionContext | None = None,
) -> ProcessedRow[T]:
    """Async variant: validation stays sync; only reject handlers may await."""
    adaptation_time_ns = 0
    validation_time_ns = 0
    rejection_context = context or empty_rejection_context(
        model=plan.model,
        execution_id=plan.execution_id,
        statement=plan.statement,
        source_name=(
            plan.resolved_source.source_name if plan.resolved_source is not None else None
        ),
    )

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
            source_identity=_best_effort_source_identity(row),
        )
        return await _ahandle_rejection(
            plan,
            rejected,
            rejection_context,
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
            source_identity=_best_effort_source_identity(row),
        )
        return await _ahandle_rejection(
            plan,
            rejected,
            rejection_context,
            adaptation_time_ns=adaptation_time_ns,
            validated=False,
        )
    adaptation_time_ns = perf_counter_ns() - started

    started = perf_counter_ns()
    subject = (
        adapted.attributes_subject
        if adapted.attributes_subject is not None
        else adapted.mapping
    )
    outcome = plan.validator.validate(subject)
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
        source_identity=adapted.source_identity,
    )
    return await _ahandle_rejection(
        plan,
        rejected,
        rejection_context,
        adaptation_time_ns=adaptation_time_ns,
        validation_time_ns=validation_time_ns,
        validated=True,
    )


def _handle_rejection(
    plan: ExecutionPlan[T],
    rejected: RejectedRow,
    context: RejectionContext,
    *,
    adaptation_time_ns: int = 0,
    validation_time_ns: int = 0,
    validated: bool = False,
) -> ProcessedRow[T]:
    started = perf_counter_ns()
    decision: RejectionDecision = plan.rejection_policy.handle(rejected, context)
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
        quarantine_receipt=decision.quarantine_receipt,
    )


async def _ahandle_rejection(
    plan: ExecutionPlan[T],
    rejected: RejectedRow,
    context: RejectionContext,
    *,
    adaptation_time_ns: int = 0,
    validation_time_ns: int = 0,
    validated: bool = False,
) -> ProcessedRow[T]:
    started = perf_counter_ns()
    policy = plan.rejection_policy
    ahandle = getattr(policy, "ahandle", None)
    if callable(ahandle):
        decision = await ahandle(rejected, context)
    else:
        decision = policy.handle(rejected, context)
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
        quarantine_receipt=decision.quarantine_receipt,
    )
