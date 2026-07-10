"""Public result objects."""

from rowguard.results.query_result import QueryResult
from rowguard.results.rejected_row import RejectedRow

__all__ = ["QueryResult", "RejectedRow", "StreamResult"]


def __getattr__(name: str) -> object:
    if name == "StreamResult":
        from rowguard.results.stream_result import StreamResult

        return StreamResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
