# Examples

Runnable scripts from the repository. Copy them locally or browse on GitHub:

- [examples/basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/basic.py) — buffered `select` with `collect`
- [examples/streaming.py](https://github.com/eddiethedean/rowguard/blob/main/examples/streaming.py) — sync `stream`
- [examples/async_basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/async_basic.py) — `aselect` + `astream` (needs `rowguard[async]`)
- [examples/orm_projected.py](https://github.com/eddiethedean/rowguard/blob/main/examples/orm_projected.py) — ORM column projection
- [examples/orm_entity.py](https://github.com/eddiethedean/rowguard/blob/main/examples/orm_entity.py) — single-entity ORM select
- [examples/sqlmodel_basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/sqlmodel_basic.py) — SQLModel table source (needs `rowguard[sqlmodel]`)

## Run locally

```bash
pip install -e ".[dev,async,sqlmodel]"
python examples/basic.py
python examples/streaming.py
python examples/async_basic.py
python examples/orm_projected.py
python examples/orm_entity.py
python examples/sqlmodel_basic.py
```

## Minimal buffered example

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
```

## Next

- [Quickstart](../guides/quickstart.md)
- [Async guide](../guides/async.md)
- [Streaming guide](../guides/streaming.md)
