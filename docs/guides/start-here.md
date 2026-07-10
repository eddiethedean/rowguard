# Start here

RowGuard is a validation-first query layer for SQLAlchemy and Pydantic.

Every row returned from a query is classified as either:

1. An accepted Pydantic model, or
2. A rejected row with structured diagnostics

Nothing is silently dropped.

## Choose a path

| You want to… | Go to |
| --- | --- |
| Install and run a first query | [Installation](installation.md) → [Quickstart](quickstart.md) |
| Understand rejection policies | [Rejection policies](rejection-policies.md) |
| Stream large result sets | [Streaming guide](streaming.md) |
| Use AsyncSession | [Async guide](async.md) |
| Look up function signatures | [API reference](../reference/api.md) · [API guide](../api.md) |
| Understand internals | [Architecture overview](../architecture_overview.md) |

## What RowGuard is

- A thin orchestration layer over SQLAlchemy + SQLRules + Pydantic
- Sync and async Core APIs (`select` / `stream` / `aselect` / `astream`)
- Explicit rejection handling (`raise`, `collect`, `skip`)

## What RowGuard is not

- Not an ORM
- Not a migration tool
- Not a replacement for SQLAlchemy or Pydantic
- Not a silent “best effort” validator

## Requirements

- Python {{ python_min }}
- Pydantic v2
- SQLAlchemy 2.x
- SQLRules

Optional: `pip install "rowguard[async]"` for `sqlite+aiosqlite` and async APIs.

## Next

1. [Install](installation.md)
2. [Quickstart](quickstart.md)
3. Skim the [FAQ](faq.md) if something surprises you
