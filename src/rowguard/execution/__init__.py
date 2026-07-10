"""Execution engines and per-row processing."""

from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.observer import BaseStreamObserver, StreamObserver
from rowguard.execution.processor import ProcessedRow, process_row
from rowguard.execution.streaming import SyncStreamEngine
from rowguard.execution.sync import SyncExecutionEngine

__all__ = [
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
