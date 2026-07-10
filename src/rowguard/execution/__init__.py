"""Execution engines and per-row processing."""

from rowguard.execution.async_ import AsyncExecutionEngine
from rowguard.execution.context import AsyncExecutionContext, SyncExecutionContext
from rowguard.execution.observer import BaseStreamObserver, StreamObserver
from rowguard.execution.processor import ProcessedRow, process_row
from rowguard.execution.streaming import AsyncStreamEngine, SyncStreamEngine
from rowguard.execution.sync import SyncExecutionEngine

__all__ = [
    "AsyncExecutionContext",
    "AsyncExecutionEngine",
    "AsyncStreamEngine",
    "AsyncStreamResult",
    "BaseStreamObserver",
    "ProcessedRow",
    "StreamObserver",
    "StreamResult",
    "SyncExecutionContext",
    "SyncExecutionEngine",
    "SyncStreamEngine",
    "process_row",
]


def __getattr__(name: str) -> object:
    if name == "StreamResult":
        from rowguard.results.stream_result import StreamResult

        return StreamResult
    if name == "AsyncStreamResult":
        from rowguard.results.async_stream_result import AsyncStreamResult

        return AsyncStreamResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
