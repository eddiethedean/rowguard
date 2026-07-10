# Design philosophy

Why RowGuard is built the way it is—and what it deliberately is not.

## Validation-first reads

Every returned row is classified as an accepted Pydantic model or a rejected row
with structured diagnostics. Silent drops are a bug, not a feature.

## Thin orchestration

- **SQLAlchemy** owns SQL, sessions, and dialects.
- **SQLRules** owns compiling safe constraints to SQL.
- **Pydantic** owns validation.
- **RowGuard** owns planning, adaptation, rejection policy, and results.

## Explicit rejection handling

Policies (`raise` / `collect` / `skip` today) decide what happens **after**
validation fails. They never change whether a row is valid.

## Sync and async share semantics

Async changes I/O, not validation rules. `aselect` / `astream` mirror sync
behavior; only DB awaits are asynchronous.

## Explicit non-goals (0.4)

| Non-goal | Alternative |
| --- | --- |
| Becoming an ORM | Use SQLAlchemy ORM; RowGuard validates ORM/SQLModel reads in 0.5 |
| Replacing Pydantic / SQLModel | Compose with them |
| Silent “best effort” filtering | Use rejection policies and statistics |
| Hiding pushdown surprises | Document `use_sqlrules` defaults |

## Related

- [Architecture overview](../architecture_overview.md)
- [Supported vs planned](../project/supported.md)
