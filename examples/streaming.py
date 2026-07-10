from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

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

engine = create_engine("sqlite+pysqlite:///:memory:")
metadata.create_all(engine)

with engine.begin() as connection:
    connection.execute(
        users.insert(),
        [
            {"id": 1, "name": "Ada", "age": 37},
            {"id": 2, "name": "Legacy", "age": 12},
            {"id": 3, "name": "Grace", "age": 45},
        ],
    )

with Session(engine) as session, rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,
) as stream:
    for model in stream:
        print("accepted:", model)

print("rejected:", stream.rejected)
print("stats:", stream.statistics)
