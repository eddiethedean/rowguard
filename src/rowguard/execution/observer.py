from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from rowguard.results.rejected_row import RejectedRow
from rowguard.statistics import QueryStatistics


@runtime_checkable
class StreamObserver(Protocol):
    """First-party streaming lifecycle hooks (plugin registry deferred to 0.7)."""

    def on_stream_start(self, *, execution_id: str) -> None:  # pragma: no cover
        ...

    def on_row_accepted(self, *, index: int, model: BaseModel) -> None:  # pragma: no cover
        ...

    def on_row_rejected(self, *, rejected: RejectedRow) -> None:  # pragma: no cover
        ...

    def on_stream_complete(self, *, statistics: QueryStatistics) -> None:  # pragma: no cover
        ...

    def on_stream_failed(self, *, error: BaseException) -> None:  # pragma: no cover
        ...

    def on_stream_closed(self) -> None:  # pragma: no cover
        ...


class BaseStreamObserver:
    """No-op observer base; subclass and override only the hooks you need."""

    def on_stream_start(self, *, execution_id: str) -> None:
        return None

    def on_row_accepted(self, *, index: int, model: BaseModel) -> None:
        return None

    def on_row_rejected(self, *, rejected: RejectedRow) -> None:
        return None

    def on_stream_complete(self, *, statistics: QueryStatistics) -> None:
        return None

    def on_stream_failed(self, *, error: BaseException) -> None:
        return None

    def on_stream_closed(self) -> None:
        return None
