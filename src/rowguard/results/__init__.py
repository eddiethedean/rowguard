"""Public result objects."""

from rowguard.results.query_result import QueryResult
from rowguard.results.rejected_row import RejectedRow

__all__ = ["AsyncStreamResult", "QueryResult", "RejectedRow", "StreamResult"]


def __getattr__(name: str) -> object:
    if name == "StreamResult":
        from rowguard.results.stream_result import StreamResult

        return StreamResult
    if name == "AsyncStreamResult":
        from rowguard.results.async_stream_result import AsyncStreamResult

        return AsyncStreamResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
