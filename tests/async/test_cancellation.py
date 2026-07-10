from __future__ import annotations

import asyncio
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

import rowguard


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.mark.integration
async def test_astream_cancellation_closes(async_session, users_table) -> None:
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )

    async def consume() -> None:
        try:
            async for _model in stream:
                await asyncio.sleep(0)
                raise asyncio.CancelledError
        finally:
            await stream.close()

    task = asyncio.create_task(consume())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed
