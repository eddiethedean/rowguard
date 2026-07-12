# Installation

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python | **3.10+** (3.10–3.12 tested in CI; **3.13 untested**) |
| Pydantic | v2 (`pydantic>=2.7,<3`) |
| SQLAlchemy | 2.x (`SQLAlchemy>=2.0,<3`) |
| SQLRules | **≥ 1.0.0, &lt; 2** |

## From PyPI

```bash
pip install rowguard
```

### Extras matrix

| Extra | Install | Purpose |
| --- | --- | --- |
| *(none)* | `pip install rowguard` | Sync Core / ORM (SQLRules included) |
| `async` | `pip install "rowguard[async]"` | aiosqlite + greenlet for async APIs / tests |
| `sqlmodel` | `pip install "rowguard[sqlmodel]"` | SQLModel table-source support |
| `postgresql` | `pip install "rowguard[postgresql]"` | Optional `psycopg` driver |
| `dev` | `pip install "rowguard[dev]"` | pytest, ruff, mypy, coverage, … |
| `docs` | `pip install "rowguard[docs]"` | Sphinx documentation build |

Full contributor install (matches CI / `make install`):

```bash
pip install -e ".[dev,async,sqlmodel]"
```

With [uv](https://github.com/astral-sh/uv):

```bash
uv pip install rowguard
uv pip install "rowguard[async]"
uv pip install "rowguard[sqlmodel]"
```

## Supported drivers (0.6.0)

| Stack | Status |
| --- | --- |
| `sqlite+pysqlite` (sync) | Supported / primary unit tests |
| `sqlite+aiosqlite` (async) | Supported / required async CI matrix |
| PostgreSQL sync (`psycopg`) | Optional extra `rowguard[postgresql]`; not required for Core |
| `asyncpg` | Not required for 0.6; may work via SQLAlchemy async but is not a CI gate |

See [Supported vs planned](../project/supported.md).

## From source

```bash
git clone https://github.com/eddiethedean/rowguard.git
cd rowguard
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev,async,sqlmodel]"
```

## Verify

```python
import rowguard

print(rowguard.__version__)
```

## Documentation tooling

```bash
pip install -e ".[docs]"
make docs
```

Opens at `docs/_build/html/index.html`.

## Common install problems

- **Resolver conflicts on Pydantic v1** — RowGuard requires Pydantic v2.
- **`ModuleNotFoundError: aiosqlite`** — install `rowguard[async]`.
- **`ModuleNotFoundError: sqlmodel`** — install `rowguard[sqlmodel]` (SQLModel tests skip without it).
- **Old sqlrules** — upgrade to `sqlrules>=1.0.0,<2`.
- **Partial extras + full `pytest`** — use `make install` (or `.[dev,async,sqlmodel]`) for the complete suite.

## Next

Continue with the [quickstart](quickstart.md).
