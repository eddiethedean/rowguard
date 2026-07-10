# RowGuard

Validation-first database queries for SQLAlchemy and Pydantic.

RowGuard executes SQLAlchemy queries, validates every returned row against a
Pydantic model, and explicitly handles rows that fail validation.

## Status

**0.1.0** — sync Core foundation with SQLRules pushdown and raise/collect/skip
rejection policies.

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

with Session(engine) as session:
    result = rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="collect",
    )
    print(result.models)
    print(result.rejected)
```

## Public API (0.1.0)

| Function | Purpose |
| --- | --- |
| `select(...)` | Build and execute a table query with validation |
| `execute(...)` | Validate rows from an existing `Select` |
| `validate_rows(...)` | Validate mappings without SQL |
| `stream(...)` | Deferred to 0.3.0 |

Rejection policies: `raise` (default), `collect`, `skip`.

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
