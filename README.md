# RowGuard

Validation-first database queries for SQLAlchemy and Pydantic.

RowGuard executes SQLAlchemy queries, validates every returned row against a
Pydantic model, and explicitly handles rows that fail validation.

## Status

**0.2.0** — staged execution planning, plan inspection, precompiled SQLRules, and
clearer configuration errors. ORM remains deferred to 0.5.0.

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
```

With `use_sqlrules=True` (the default), supported constraints such as `age >= 18`
are pushed into SQL, so invalid candidate rows may never be returned.

## Public API (0.2.0)

| Function | Purpose |
| --- | --- |
| `select(...)` | Build and execute a table query with validation |
| `execute(...)` | Validate rows from an existing `Select` |
| `validate_rows(...)` | Validate mappings without SQL |
| `compile_plan(...)` | Compile an `ExecutionPlan` without executing |
| `stream(...)` | Deferred to 0.3.0 |

Rejection policies: `raise` (default), `collect`, `skip`.

Optional planning knobs: `compiled_rules=` (precompiled SQLRules), `strict=`
(Pydantic), `field_map=` / `column_map=` (validated at plan time).

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

- [SPEC.md](SPEC.md) — product specification
- [API.md](API.md) — public API
- [ARCHITECTURE.md](ARCHITECTURE.md) — layered design
- [ROADMAP.md](ROADMAP.md) — release plan
- [docs/](docs/) — detailed design notes

## Development

```bash
pip install -e ".[dev,async]"
make all          # ruff + mypy + pytest --cov
python examples/basic.py
```

## License

MIT
