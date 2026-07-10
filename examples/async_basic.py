"""Async RowGuard example using sqlite+aiosqlite."""

from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import rowguard


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("age", Integer),
)


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(
            users.insert(),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
                {"id": 3, "name": "Grace", "age": 45},
            ],
        )

    async with AsyncSession(engine) as session:
        result = await rowguard.aselect(
            session=session,
            table=users,
            model=UserRead,
            on_reject="collect",
            use_sqlrules=False,
        )
        print("buffered models:", result.models)
        print("buffered rejected:", result.rejected)

        async with rowguard.astream(
            session=session,
            table=users,
            model=UserRead,
            on_reject="skip",
            use_sqlrules=False,
        ) as stream:
            async for model in stream:
                print("streamed:", model)
        print("stream stats:", stream.statistics)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
