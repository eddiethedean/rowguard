from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session


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
def engine(users_table: Table):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    users_table.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            users_table.insert(),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
                {"id": 3, "name": "Grace", "age": 45},
            ],
        )
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]
