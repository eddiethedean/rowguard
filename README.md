# RowGuard

[![CI](https://github.com/eddiethedean/rowguard/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/rowguard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rowguard.svg)](https://pypi.org/project/rowguard/)
[![Documentation](https://readthedocs.org/projects/rowguard/badge/?version=latest)](https://rowguard.readthedocs.io/en/latest/)
[![Python Versions](https://img.shields.io/pypi/pyversions/rowguard.svg)](https://pypi.org/project/rowguard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RowGuard makes every SQLAlchemy query return **validated Pydantic models**—or
**explicit rejected rows**. Rows that reach validation are never silently
discarded: they become accepted models or counted rejections.

**SQLRules** (a required dependency) can push supported Pydantic constraints into
SQL. With the default `use_sqlrules=True`, invalid candidates may never leave the
database—so `rejected` can be empty even though bad rows exist in the table. That
is pushdown filtering, not silent drop-after-fetch. Use `use_sqlrules=False` when
you need every fetched row classified by Pydantic.

Use it when you already have SQLAlchemy Core tables/selects or ORM / SQLModel
mapped classes and need typed reads with deterministic rejection handling. It is
**not** an ORM and does not replace SQLAlchemy, Pydantic, or SQLModel.

## Status

Current release: **[0.5.0](https://rowguard.readthedocs.io/en/latest/project/changelog.html)**
(Core + async + ORM/SQLModel). See
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

Requires Python 3.10+, Pydantic v2, SQLAlchemy 2.x, and SQLRules ≥1.0. See the
[installation guide](https://rowguard.readthedocs.io/en/latest/guides/installation.html).

## Quickstart

Full walkthrough: [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html).

**Default path** (SQLRules on): invalid rows are filtered in SQL; `rejected` is empty.

```python
result = rowguard.select(session=session, table=users, model=UserRead)
# result.models → only rows that satisfied pushdown + Pydantic
# result.rejected → () when pushdown removed invalid candidates
```

**Explicit rejection path** (`use_sqlrules=False`): every fetched row is validated;
invalid rows appear in `rejected` under `on_reject="collect"` (default policy is
`"raise"`).

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
    print(result.models)    # (UserRead(id=1, name='Ada', age=37),)
    print(result.rejected)  # Legacy failed age >= 18
```

See [SQLRules pushdown](https://rowguard.readthedocs.io/en/latest/guides/sqlrules-pushdown.html)
and the [FAQ](https://rowguard.readthedocs.io/en/latest/guides/faq.html).

## Public API (0.5.0)

Full reference: [API guide](https://rowguard.readthedocs.io/en/latest/api.html) ·
[Python autodoc](https://rowguard.readthedocs.io/en/latest/reference/api.html) ·
[Error catalog](https://rowguard.readthedocs.io/en/latest/reference/errors.html).

| Function | Purpose |
| --- | --- |
| `select(...)` | Build and execute a table / mapped-class query with validation |
| `execute(...)` | Validate rows from an existing `Select` |
| `validate_rows(...)` | Validate mappings without SQL |
| `compile_plan(...)` | Compile an `ExecutionPlan` without executing |
| `stream(...)` | Stream validated models without buffering accepted rows |
| `aselect(...)` | Async `select` for `AsyncSession` / `AsyncConnection` |
| `aexecute(...)` | Async `execute` for `AsyncSession` / `AsyncConnection` |
| `astream(...)` | Async stream (`AsyncStreamResult`) without buffering accepted rows |

**`table=` vs `source=`:** pass a Core `Table` or ORM/SQLModel mapped class as
`table=` on `select` / `stream` / `aselect` / `astream`. On `execute` /
`aexecute` with a projected `Select`, pass the same mapped class as `source=`
for pushdown and adaptation. Use only one of `table=` or `source=` per call.

Rejection policies: `raise` (default), `collect`, `skip` — see
[rejection policies](https://rowguard.readthedocs.io/en/latest/guides/rejection-policies.html).

Optional planning knobs: `compiled_rules=` (precompiled SQLRules), `strict=`
(Pydantic), `field_map=` / `column_map=` / `attribute_map=`,
`orm_validation=` / `unloaded_attributes=` (ORM entity path).

Streaming knobs: `yield_per=`, `observers=` (`StreamObserver` / `BaseStreamObserver`).
Observers remain sync callables. See the
[streaming guide](https://rowguard.readthedocs.io/en/latest/guides/streaming.html).

ORM / SQLModel: prefer projections; see
[ORM and SQLModel](https://rowguard.readthedocs.io/en/latest/guides/orm-sqlmodel.html).
Install SQLModel support with `pip install "rowguard[sqlmodel]"`.

Async note: only DB I/O is awaited. Pydantic validation runs on the event loop;
heavy models can block. Prefer `async with rowguard.astream(...)` for cleanup.
Install async extras with `pip install "rowguard[async]"`. Details:
[async guide](https://rowguard.readthedocs.io/en/latest/guides/async.html).

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

More detail:
[architecture overview](https://rowguard.readthedocs.io/en/latest/architecture_overview.html)
· [design philosophy](https://rowguard.readthedocs.io/en/latest/guides/design-philosophy.html)
· [specification](https://rowguard.readthedocs.io/en/latest/spec.html).

## Documentation

- [Docs home](https://rowguard.readthedocs.io/en/latest/)
- [Start here](https://rowguard.readthedocs.io/en/latest/guides/start-here.html)
- [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html)
- [Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html)
- [Examples](https://rowguard.readthedocs.io/en/latest/examples/index.html)
- [API guide](https://rowguard.readthedocs.io/en/latest/api.html)
- [Python autodoc](https://rowguard.readthedocs.io/en/latest/reference/api.html)
- [Changelog](https://rowguard.readthedocs.io/en/latest/project/changelog.html)
- [Roadmap](https://rowguard.readthedocs.io/en/latest/project/roadmap.html)

Build docs locally:

```bash
pip install -e ".[docs]"
make docs
# open docs/_build/html/index.html
```

## Development

See [Contributing](CONTRIBUTING.md) (also on
[Read the Docs](https://rowguard.readthedocs.io/en/latest/developer/CONTRIBUTING.html)),
[Security](SECURITY.md), and
[Releasing](https://rowguard.readthedocs.io/en/latest/project/releasing.html).

```bash
pip install -e ".[dev,async,sqlmodel]"
make all          # ruff + mypy + pytest --cov
python examples/basic.py
python examples/streaming.py
python examples/async_basic.py
python examples/orm_projected.py
python examples/orm_entity.py
python examples/sqlmodel_basic.py
python examples/sqlrules_default.py
```

## License

[MIT](LICENSE)
