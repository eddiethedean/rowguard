"""Execution engines and per-row processing."""

from rowguard.execution.processor import ProcessedRow, process_row
from rowguard.execution.sync import SyncExecutionEngine

__all__ = ["ProcessedRow", "SyncExecutionEngine", "process_row"]
