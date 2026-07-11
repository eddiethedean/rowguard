from __future__ import annotations

import asyncio
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.mark.integration
async def test_astream_cancellation_closes(async_session, users_table) -> None:
    """Cancel mid-iteration must close the stream without a manual close()."""
    stream = rowguard.astream(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )

    async def consume() -> None:
        async for _model in stream:
            raise asyncio.CancelledError

    task = asyncio.create_task(consume())
    with pytest.raises(asyncio.CancelledError):
        await task

    # Async-generator aclose (and thus stream.close) is scheduled on the loop.
    for _ in range(10):
        if stream.closed:
            break
        await asyncio.sleep(0)
    assert stream.closed

    # Session remains usable after cancellation cleanup.
    follow_up = await rowguard.aexecute(
        session=async_session,
        statement=select(users_table).where(users_table.c.id == 1),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert follow_up.valid_count == 1
