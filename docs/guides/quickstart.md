# Quickstart

Validate SQLAlchemy query rows against a Pydantic model.

## 1. Default path (recommended first run)

Library defaults: `use_sqlrules=True`, `on_reject="raise"`. Supported constraints
(such as `Field(ge=18)`) are pushed into SQL, so invalid candidates are often
never fetched.

```python
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
    result = rowguard.select(session=session, table=users, model=UserRead)
    print(result.models)    # Ada only
    print(result.rejected)  # ()
    print(result.statistics.rows_read)  # 1
```

## 2. Inspect rejections in Python

Turn pushdown off and use `collect` so every fetched row is classified:

```python
with Session(engine) as session:
    result = rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    print(result.models)
    print(result.rejected)

    with rowguard.stream(
        session=session,
        table=users,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    ) as stream:
        for model in stream:
            print(model)
```

## What happened

1. **Default path:** SQLRules pushed `age >= 18` into SQL; Legacy never left the DB.
2. **Inspect path:** both rows were fetched; Ada validated; Legacy became a
   `RejectedRow` under `collect`.
3. Stream with `skip` yields accepted models only (rejections counted, not retained).

See [SQLRules pushdown](sqlrules-pushdown.md) for the capability matrix.

## Async

Requires `pip install "rowguard[async]"`. Same default-vs-inspect pattern:

```python
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
            ],
        )

    async with AsyncSession(engine) as session:
        result = await rowguard.aselect(
            session=session,
            table=users,
            model=UserRead,
        )
        print(result.models)

        inspected = await rowguard.aselect(
            session=session,
            table=users,
            model=UserRead,
            on_reject="collect",
            use_sqlrules=False,
        )
        print(inspected.rejected)

    await engine.dispose()


asyncio.run(main())
```

## Next

- [SQLRules pushdown](sqlrules-pushdown.md)
- [Rejection policies](rejection-policies.md)
- [ORM and SQLModel](orm-sqlmodel.md)
- [Examples](../examples/index.md)
