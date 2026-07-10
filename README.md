# RowGuard

Validation-first database queries for SQLAlchemy and Pydantic.

[![Documentation Status](https://readthedocs.org/projects/rowguard/badge/?version=latest)](https://rowguard.readthedocs.io/en/latest/?badge=latest)

RowGuard executes SQLAlchemy queries, validates every returned row against a
Pydantic model, and explicitly handles rows that fail validation.

## Status

**0.4.0** — first-class async APIs (`aselect` / `aexecute` / `astream`) over
`AsyncSession` / `AsyncConnection`, with streaming lifecycle parity to sync.
ORM remains deferred to 0.5.0; async callback/quarantine handlers to 0.6.0.

## Install

```bash
pip install rowguard
```

Requires Python 3.10+, Pydantic v2, SQLAlchemy 2.x, and SQLRules.

## Quickstart

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

With `use_sqlrules=True` (the default), supported constraints such as `age >= 18`
are pushed into SQL, so invalid candidate rows may never be returned.

## Public API (0.4.0)

| Function | Purpose |
| --- | --- |
| `select(...)` | Build and execute a table query with validation |
| `execute(...)` | Validate rows from an existing `Select` |
| `validate_rows(...)` | Validate mappings without SQL |
| `compile_plan(...)` | Compile an `ExecutionPlan` without executing |
| `stream(...)` | Stream validated models without buffering accepted rows |
| `aselect(...)` | Async `select` for `AsyncSession` / `AsyncConnection` |
| `aexecute(...)` | Async `execute` for `AsyncSession` / `AsyncConnection` |
| `astream(...)` | Async stream (`AsyncStreamResult`) without buffering accepted rows |

Rejection policies: `raise` (default), `collect`, `skip`.

Optional planning knobs: `compiled_rules=` (precompiled SQLRules), `strict=`
(Pydantic), `field_map=` / `column_map=` (validated at plan time).

Streaming knobs: `yield_per=`, `observers=` (`StreamObserver` / `BaseStreamObserver`).
Observers remain sync callables in 0.4.

Async note: only DB I/O is awaited. Pydantic validation runs on the event loop;
heavy models can block. Prefer `async with rowguard.astream(...)` for cleanup.
Install async extras with `pip install rowguard[async]`.

## Architecture

```text
Pydantic Model
      │
      ▼
SQLRules
      │
      ▼
SQLAlchemy Query
      │
      ▼
Database
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ├── Accepted Model
      └── Rejected Row
```

## Documentation

- [Online docs](https://rowguard.readthedocs.io) — Read the Docs
- [SPEC.md](SPEC.md) — product specification
- [API.md](API.md) — public API
- [ARCHITECTURE.md](ARCHITECTURE.md) — layered design
- [ROADMAP.md](ROADMAP.md) — release plan
- [docs/](docs/) — detailed design notes

Build docs locally:

```bash
pip install -e ".[docs]"
make docs
# open docs/_build/html/index.html
```

## Development

```bash
pip install -e ".[dev,async]"
make all          # ruff + mypy + pytest --cov
python examples/basic.py
python examples/streaming.py
python examples/async_basic.py
```

## License

MIT
