"""Typing smoke checks for AsyncStreamResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rowguard

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import BaseModel

    from rowguard.results.async_stream_result import AsyncStreamResult


async def _check_async_stream_result(
    stream: AsyncStreamResult[BaseModel],
) -> AsyncIterator[BaseModel]:
    assert isinstance(stream, rowguard.AsyncStreamResult)
    async for model in stream:
        yield model
