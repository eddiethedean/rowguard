"""Typing smoke checks for StreamResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rowguard

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic import BaseModel

    from rowguard.results.stream_result import StreamResult


def _check_stream_result(stream: StreamResult[BaseModel]) -> Iterator[BaseModel]:
    assert isinstance(stream, rowguard.StreamResult)
    yield from stream
