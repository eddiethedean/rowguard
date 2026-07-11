# Quickstart

Validate every row from a SQLAlchemy Core table against a Pydantic model.

:::{admonition} Defaults vs this walkthrough
:class: tip

**Default** `use_sqlrules=True` pushes supported constraints into SQL. Invalid
candidates may never be fetched, so `rejected` can be empty. That is pushdown
filtering—not silent drop-after-fetch. See [SQLRules pushdown](sqlrules-pushdown.md).

This walkthrough uses `use_sqlrules=False` so every fetched row is classified by
Pydantic and invalid rows appear in `rejected` under `on_reject="collect"`
(the API default policy is `"raise"`).
:::

## Default path (SQLRules on)

```python
result = rowguard.select(session=session, table=users, model=UserRead)
# Only rows that passed pushdown + Pydantic. rejected is often ().
```

## Explicit rejection path

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

1. RowGuard planned a `SELECT` from `users`.
2. With `use_sqlrules=False`, both rows were fetched.
3. Ada validated; Legacy failed `age >= 18`.
4. Under `collect`, both outcomes are retained on `QueryResult`.
5. The stream yields accepted models only (`skip` does not retain rejections).

## Async (complete example)

Requires `pip install "rowguard[async]"`.

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
            on_reject="collect",
            use_sqlrules=False,
        )
        print(result.models)

        async with rowguard.astream(
            session=session,
            table=users,
            model=UserRead,
            on_reject="skip",
            use_sqlrules=False,
        ) as stream:
            async for model in stream:
                print(model)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

## Next

- [SQLRules pushdown](sqlrules-pushdown.md)
- [Rejection policies](rejection-policies.md)
- [Examples gallery](../examples/index.md)
- [Public API](../api.md)
