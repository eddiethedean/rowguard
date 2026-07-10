from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.fixture
def users_table() -> Table:
    metadata = MetaData()
    return Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("age", Integer, nullable=False),
    )


@pytest.fixture
async def async_engine(users_table: Table) -> AsyncIterator[object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(users_table.metadata.create_all)
        await connection.execute(
            users_table.insert(),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
                {"id": 3, "name": "Grace", "age": 45},
            ],
        )
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(async_engine) as session:
        yield session


@pytest.fixture
async def async_connection(async_engine) -> AsyncIterator[AsyncConnection]:
    async with async_engine.connect() as connection:
        yield connection
