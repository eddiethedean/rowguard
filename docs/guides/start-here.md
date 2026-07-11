# Start here

RowGuard turns SQLAlchemy query results into validated Pydantic models.

**Day-1 path:** [Install](installation.md) → [Quickstart](quickstart.md)
→ skim [SQLRules pushdown](sqlrules-pushdown.md).

By default, SQLRules pushes supported constraints into SQL. Every row that
*reaches* validation is accepted or explicitly rejected—never ignored after
fetch. Use `use_sqlrules=False` when you need invalid rows classified in Python.

## Choose a path

| You want to… | Go to |
| --- | --- |
| Install and run a first query | [Installation](installation.md) → [Quickstart](quickstart.md) |
| Understand why `rejected` can be empty | [SQLRules pushdown](sqlrules-pushdown.md) |
| Upgrade from 0.4 | [Upgrading](upgrading.md) |
| Rejection policies | [Rejection policies](rejection-policies.md) |
| Stream large results | [Streaming](streaming.md) |
| AsyncSession | [Async](async.md) |
| Performance tips | [Performance](performance.md) |
| What is shipped vs planned | [Supported vs planned](../project/supported.md) |
| API contracts | [API guide](../api.md) · [Errors](../reference/errors.md) |

## What RowGuard is

- Orchestration over SQLAlchemy + SQLRules + Pydantic
- Sync and async buffered and streaming APIs
- Policies: `raise` (default), `collect`, `skip`

## What RowGuard is not

- Not an ORM / persistence layer (it **validates ORM and SQLModel reads** in 0.5)
- Not a migration tool
- Not a replacement for SQLAlchemy or Pydantic
- Not an authorization system (pushdown is not a security boundary)

## Requirements

- Python {{ python_min }} (3.10–3.12 tested in CI; 3.13 untested)
- Pydantic v2, SQLAlchemy 2.x, SQLRules ≥ 1.0

Optional: `pip install "rowguard[async]"` / `"rowguard[sqlmodel]"`.

## Next

1. [Install](installation.md)
2. [Quickstart](quickstart.md) — default path first, then inspect rejections
3. [FAQ](faq.md) / [Troubleshooting](troubleshooting.md)
