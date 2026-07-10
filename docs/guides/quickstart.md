# Quickstart

Validate every row from a SQLAlchemy Core table against a Pydantic model.

:::{admonition} About `use_sqlrules=False`
:class: tip

This walkthrough disables SQLRules pushdown so invalid rows reach Pydantic and
appear in `rejected`. Production defaults use `use_sqlrules=True`. See
[SQLRules pushdown](sqlrules-pushdown.md).
:::

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
