# Installation

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python | **3.10+** (3.10–3.12 tested in CI) |
| Pydantic | v2 (`pydantic>=2.7,<3`) |
| SQLAlchemy | 2.x (`SQLAlchemy>=2.0,<3`) |
| SQLRules | **≥ 0.4.0** |

## From PyPI

```bash
pip install rowguard
```

Async extras (aiosqlite + greenlet):

```bash
pip install "rowguard[async]"
```

SQLModel table-source support:

```bash
pip install "rowguard[sqlmodel]"
```

With [uv](https://github.com/astral-sh/uv):

```bash
uv pip install rowguard
uv pip install "rowguard[async]"
uv pip install "rowguard[sqlmodel]"
```

## Supported drivers (0.5.0)

| Stack | Status |
| --- | --- |
| `sqlite+pysqlite` (sync) | Supported / primary unit tests |
| `sqlite+aiosqlite` (async) | Supported / required async CI matrix |
| PostgreSQL sync (`psycopg`) | Optional extra `rowguard[postgresql]`; not required for Core |
| `asyncpg` | Not required for 0.5; may work via SQLAlchemy async but is not a CI gate |

See [Supported vs planned](../project/supported.md).

## From source

```bash
git clone https://github.com/eddiethedean/rowguard.git
cd rowguard
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev,async]"
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
- **Old sqlrules** — upgrade to `sqlrules>=0.4.0`.

## Next

Continue with the [quickstart](quickstart.md).
