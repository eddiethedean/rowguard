from __future__ import annotations

import gc
import weakref
from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

import rowguard


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def test_stream_does_not_retain_accepted_models() -> None:
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("age", Integer, nullable=False),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    rows = [{"id": i, "name": f"User{i}", "age": 20 + (i % 50)} for i in range(5_000)]
    with engine.begin() as connection:
        connection.execute(users.insert(), rows)

    def _consume(
        stream: rowguard.StreamResult[UserRead],
    ) -> tuple[list[weakref.ref[UserRead]], int]:
        refs: list[weakref.ref[UserRead]] = []
        count = 0
        for model in stream:
            refs.append(weakref.ref(model))
            count += 1
            assert not hasattr(stream, "_accepted")
            assert not hasattr(stream, "models")
        return refs, count

    with Session(engine) as session, rowguard.stream(
        session=session,
        table=users,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        refs, count = _consume(stream)

    assert count == 5_000
    assert stream.statistics.rows_accepted == 5_000
    assert stream.rejected == ()

    gc.collect()
    alive = sum(1 for ref in refs if ref() is not None)
    assert alive == 0, f"stream retained {alive} accepted models after iteration"
