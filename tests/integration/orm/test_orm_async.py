from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import rowguard


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    age: Mapped[int]


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.fixture
async def async_orm_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                User(id=1, name="Ada", age=37),
                User(id=2, name="Legacy", age=12),
                User(id=3, name="Grace", age=45),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orm_async_projected_smoke(async_orm_session: AsyncSession) -> None:
    result = await rowguard.aexecute(
        session=async_orm_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
