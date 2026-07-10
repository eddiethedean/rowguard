from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import rowguard


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.mark.integration
async def test_sync_async_select_parity(async_engine, users_table) -> None:
    sync_engine = create_engine("sqlite+pysqlite:///:memory:")
    users_table.metadata.create_all(sync_engine)
    with sync_engine.begin() as connection:
        connection.execute(
            users_table.insert(),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
                {"id": 3, "name": "Grace", "age": 45},
            ],
        )

    with Session(sync_engine) as session:
        sync_result = rowguard.select(
            session=session,
            table=users_table,
            model=UserRead,
            on_reject="collect",
            use_sqlrules=False,
        )

    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(async_engine) as async_session:
        async_result = await rowguard.aselect(
            session=async_session,
            table=users_table,
            model=UserRead,
            on_reject="collect",
            use_sqlrules=False,
        )

    assert async_result.models == sync_result.models
    assert async_result.statistics.rows_read == sync_result.statistics.rows_read
    assert async_result.statistics.rows_accepted == sync_result.statistics.rows_accepted
    assert async_result.statistics.rows_rejected == sync_result.statistics.rows_rejected
    assert len(async_result.rejected) == len(sync_result.rejected)
