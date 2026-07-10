# Quickstart

Validate every row from a SQLAlchemy Core table against a Pydantic model.

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
    # Disable SQLRules pushdown so invalid rows reach Pydantic and appear in rejected.
    result = rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    print(result.models)
    print(result.rejected)
```

## What happened

1. RowGuard planned a `SELECT` from `users`.
2. With `use_sqlrules=False`, both rows were fetched.
3. Ada validated; Legacy failed `age >= 18`.
4. Under `collect`, both outcomes are retained on `QueryResult`.

With `use_sqlrules=True` (default), supported constraints such as `age >= 18`
may be pushed into SQL so invalid candidates never leave the database.

## Streaming

```python
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

Accepted models are yielded and not buffered. Prefer `with` / `async with` for
cursor cleanup. See [Streaming](streaming.md).

## Async

```python
result = await rowguard.aselect(
    session=async_session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,
)
```

See [Async](async.md).

## Next

- [Rejection policies](rejection-policies.md)
- [Public API](../api.md)
- Runnable examples: `examples/basic.py`, `examples/streaming.py`, `examples/async_basic.py`
