# Supported vs planned

Single source of truth for what RowGuard **ships today** versus what is still
**design / roadmap**. When a deep design doc conflicts with this page, **this
page wins** for adopter expectations.

## Shipped in 0.6.0

| Area | Status |
| --- | --- |
| Sync Core API (`select`, `execute`, `validate_rows`, `compile_plan`) | Shipped |
| Sync streaming (`stream` → `StreamResult`) | Shipped |
| Async Core API (`aselect`, `aexecute`) | Shipped |
| Async streaming (`astream` → `AsyncStreamResult`) | Shipped |
| Rejection policies `raise` / `collect` / `skip` / `log` / `callback` / `quarantine` | Shipped |
| `CallbackContext` / `CallbackDecision` / async reject callbacks | Shipped |
| `QuarantineRecord` / `QuarantineReceipt` | Shipped |
| `InMemoryQuarantineProvider` / `JSONLQuarantineProvider` | Shipped |
| Redaction / retention / rejection thresholds | Shipped |
| SQLAlchemy Core `Table` / `Select` | Shipped |
| SQLAlchemy ORM mapped classes (projected + single-entity) | Shipped |
| SQLModel table sources (`rowguard[sqlmodel]`) | Shipped |
| `orm_validation` / `unloaded_attributes` / `attribute_map` | Shipped |
| `RejectedRow.source_identity` (PK dict) | Shipped |
| `Session` / `Connection` / `AsyncSession` / `AsyncConnection` | Shipped |
| SQLRules pushdown (`use_sqlrules`, `compiled_rules`) | Shipped |
| Stream observers (sync callables) | Shipped |
| Driver matrix for async CI | **sqlite+aiosqlite** required |

## Planned — not available yet

| Area | Target | Notes |
| --- | --- | --- |
| Nested relationship / graph validation | Later | Explicitly out of 0.6 |
| Plugin system / provider registries | **0.7.0** | Design draft only |
| SQL / cloud / queue quarantine providers | Post-1.0 | In-memory + JSONL only in 0.6 |
| Reflection / raw `text()` | **0.8.0** | Design draft only |
| asyncpg as required CI driver | Later | Not required for 0.6 |

## How to read design docs

Pages under **Future / design (not shipped)** describe intended behavior. They
use present tense in places for readability, but **APIs and examples there must
not be copied into production code** until the matching release ships and this
page is updated.

Callback / quarantine design notes are **shipped** as of 0.6; prefer
[Rejection policies](../guides/rejection-policies.md) for the supported surface.

## Related

- [Changelog](changelog.md)
- [Roadmap](roadmap.md)
- [Start here](../guides/start-here.md)
