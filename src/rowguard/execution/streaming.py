from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel

from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.observer import StreamObserver
from rowguard.planning.config import StreamingConfig
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.stream_result import StreamResult

T = TypeVar("T", bound=BaseModel)


class SyncStreamEngine(Generic[T]):
    """Open a context-managed streaming result for an execution plan."""

    def open(
        self,
        plan: ExecutionPlan[T],
        context: SyncExecutionContext,
        *,
        streaming: StreamingConfig | None = None,
        observers: Sequence[StreamObserver] = (),
    ) -> StreamResult[T]:
        return StreamResult(
            plan=plan,
            context=context,
            streaming=streaming,
            observers=observers,
        )


# Re-export for callers that historically imported from execution.streaming.
__all__ = ["StreamResult", "SyncStreamEngine"]
