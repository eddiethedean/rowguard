from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel

from rowguard.execution.context import AsyncExecutionContext, SyncExecutionContext
from rowguard.execution.observer import StreamObserver
from rowguard.planning.config import StreamingConfig
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.results.async_stream_result import AsyncStreamResult
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


class AsyncStreamEngine(Generic[T]):
    """Open an async context-managed streaming result for an execution plan."""

    def open(
        self,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
        *,
        streaming: StreamingConfig | None = None,
        observers: Sequence[StreamObserver] = (),
    ) -> AsyncStreamResult[T]:
        return AsyncStreamResult(
            plan=plan,
            context=context,
            streaming=streaming,
            observers=observers,
        )


__all__ = ["AsyncStreamEngine", "AsyncStreamResult", "StreamResult", "SyncStreamEngine"]
