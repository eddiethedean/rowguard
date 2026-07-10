# Supported vs planned

Single source of truth for what RowGuard **ships today** versus what is still
**design / roadmap**. When a deep design doc conflicts with this page, **this
page wins** for adopter expectations.

## Shipped in 0.4.0

| Area | Status |
| --- | --- |
| Sync Core API (`select`, `execute`, `validate_rows`, `compile_plan`) | Shipped |
| Sync streaming (`stream` → `StreamResult`) | Shipped |
| Async Core API (`aselect`, `aexecute`) | Shipped |
| Async streaming (`astream` → `AsyncStreamResult`) | Shipped |
| Rejection policies `raise` / `collect` / `skip` | Shipped |
| SQLAlchemy Core `Table` / `Select` | Shipped |
| `Session` / `Connection` / `AsyncSession` / `AsyncConnection` | Shipped |
| SQLRules pushdown (`use_sqlrules`, `compiled_rules`) | Shipped |
| Stream observers (sync callables) | Shipped |
| Driver matrix for async CI | **sqlite+aiosqlite** required |

## Planned — not available yet

| Area | Target | Notes |
| --- | --- | --- |
| SQLAlchemy ORM mapped classes | **0.5.0** | Design docs under Future / design |
| SQLModel integration | **0.5.0** | Design docs under Future / design |
| Callback / quarantine / log rejection policies | **0.6.0** | Design docs under Future / design |
| Async reject handlers | **0.6.0** | Same as sync: not shipped in 0.4 |
| Plugin system | **0.7.0** | Design draft only |
| Reflection / raw `text()` | **0.8.0** | Design draft only |
| asyncpg as required CI driver | Later | Not required for 0.4 |

## How to read design docs

Pages under **Future / design (not shipped)** describe intended behavior. They
use present tense in places for readability, but **APIs and examples there must
not be copied into production code** until the matching release ships and this
page is updated.

## Related

- [Changelog](changelog.md)
- [Roadmap](roadmap.md)
- [Start here](../guides/start-here.md)
