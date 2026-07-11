"""Production-default path: SQLRules pushdown on (use_sqlrules=True).

Invalid candidates are filtered in SQL, so rejected stays empty even when the
table still contains rows that would fail Pydantic. Compare with basic.py.
"""

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
        ],
    )

with Session(engine) as session:
    result = rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="collect",
        # Default is True; shown explicitly for the demo.
        use_sqlrules=True,
    )
    print("accepted:", result.models)
    print("rejected:", result.rejected)
    print("rows_read:", result.statistics.rows_read)
