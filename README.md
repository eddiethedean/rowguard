# RowGuard

[![CI](https://github.com/eddiethedean/rowguard/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/rowguard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rowguard.svg)](https://pypi.org/project/rowguard/)
[![Documentation](https://readthedocs.org/projects/rowguard/badge/?version=latest)](https://rowguard.readthedocs.io/en/latest/)
[![Python Versions](https://img.shields.io/pypi/pyversions/rowguard.svg)](https://pypi.org/project/rowguard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RowGuard turns SQLAlchemy query results into **validated Pydantic models**.

By default, **[SQLRules](https://pypi.org/project/sqlrules/)** (a required
dependency) pushes supported model constraints into SQL so invalid candidates
are filtered before fetch. Every row that *is* fetched is either an accepted
model or an explicit rejection—never ignored after fetch.

Need to inspect invalid rows in Python? Pass `use_sqlrules=False` and
`on_reject="collect"`.

Use it when you already have SQLAlchemy Core tables/selects or ORM / SQLModel
mapped classes and need typed reads with deterministic rejection handling. It is
**not** an ORM and does not replace SQLAlchemy, Pydantic, or SQLModel—it
validates **reads** over those stacks.

## Status

Current release: **[0.6.0](https://rowguard.readthedocs.io/en/latest/project/changelog.html)**
(Core + async + ORM/SQLModel + rejection platform). See
[Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html)
for what is shipped versus deferred.

## Install

```bash
pip install rowguard                 # Core (includes SQLRules)
pip install "rowguard[async]"        # aiosqlite + greenlet for async
pip install "rowguard[sqlmodel]"     # SQLModel table-source support
pip install "rowguard[postgresql]"   # psycopg driver helper
```

| Extra | When you need it |
| --- | --- |
| *(none)* | Sync Core / ORM reads |
| `async` | `aselect` / `astream` examples and async tests |
| `sqlmodel` | SQLModel mapped classes as `table=` / `source=` |
| `postgresql` | Optional PostgreSQL driver |
| `dev` | Contributors: pytest, ruff, mypy, … |
| `docs` | Sphinx documentation build |

Requires Python 3.10+, Pydantic v2, SQLAlchemy 2.x, and SQLRules ≥1.0
(3.10–3.12 tested in CI; 3.13 untested). See the
[installation guide](https://rowguard.readthedocs.io/en/latest/guides/installation.html).

## Quickstart

Full walkthrough: [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html).

### 1. Default path (library defaults)

Invalid candidates are filtered in SQL. `rejected` is empty.

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
    print(result.models)    # (UserRead(id=1, name='Ada', age=37),)
    print(result.rejected)  # ()
```

### 2. Inspect rejections in Python

```python
with Session(engine) as session:
    result = rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="collect",      # default is "raise"
        use_sqlrules=False,       # default is True
    )
    print(result.models)    # Ada
    print(result.rejected)  # Legacy failed age >= 18
```

See [SQLRules pushdown](https://rowguard.readthedocs.io/en/latest/guides/sqlrules-pushdown.html)
and the [FAQ](https://rowguard.readthedocs.io/en/latest/guides/faq.html).

## Public API (0.6.0)

| Function | Purpose |
| --- | --- |
| `select` / `execute` | Buffered validated reads |
| `stream` | Stream accepted models (no accepted-row buffer) |
| `aselect` / `aexecute` / `astream` | Async counterparts |
| `validate_rows` | Validate mappings without SQL |
| `compile_plan` | Inspect an `ExecutionPlan` without executing |

Rejection policies: `raise` (default), `collect`, `skip`, `log`, `callback`,
`quarantine` — plus optional `max_rejections` / `max_rejection_rate`. See
[Rejection policies](https://rowguard.readthedocs.io/en/latest/guides/rejection-policies.html).

**`table=` vs `source=`:** use `table=` on `select`/`stream` (Core `Table` or
mapped class). On `execute` with a projected `Select`, pass the mapped class as
`source=`. Full parameter contracts:
[API guide](https://rowguard.readthedocs.io/en/latest/api.html) ·
[Python autodoc](https://rowguard.readthedocs.io/en/latest/reference/api.html) ·
[Errors](https://rowguard.readthedocs.io/en/latest/reference/errors.html).

ORM / SQLModel guide · Streaming · Async ·
[Performance](https://rowguard.readthedocs.io/en/latest/guides/performance.html) ·
[Upgrading](https://rowguard.readthedocs.io/en/latest/guides/upgrading.html).

## Documentation

Start here → [Installation](https://rowguard.readthedocs.io/en/latest/guides/installation.html)
→ [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html).

- [Docs home](https://rowguard.readthedocs.io/en/latest/)
- [Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html)
- [Examples](https://rowguard.readthedocs.io/en/latest/examples/index.html)
- [Changelog](https://rowguard.readthedocs.io/en/latest/project/changelog.html)

## Development

See [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md).

```bash
make install      # .[dev,async,sqlmodel] — matches CI
make all
python examples/sqlrules_default.py
python examples/basic.py
```

## License

[MIT](LICENSE)
