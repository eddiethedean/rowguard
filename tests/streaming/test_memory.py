from __future__ import annotations

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

    with Session(engine) as session, rowguard.stream(
        session=session,
        table=users,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        count = 0
        for _model in stream:
            count += 1
            # Accepted models must not accumulate on the stream object.
            assert not hasattr(stream, "_accepted")
            assert not hasattr(stream, "models")

    assert count == 5_000
    assert stream.statistics.rows_accepted == 5_000
    assert stream.rejected == ()
