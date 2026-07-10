# Cursor Build Prompt

Build RowGuard incrementally from the architecture and specification documents in
this repository.

Start with milestone 0.1.0 only.

## Required 0.1.0 Scope

- Python 3.10+
- Pydantic v2
- SQLAlchemy 2.x
- SQLRules integration
- SQLAlchemy Core `Table` and `Select`
- Sync `Session` and `Connection`
- `select()`
- `execute()`
- `validate_rows()`
- `QueryResult[T]`
- `RejectedRow`
- `QueryStatistics`
- Rejection policies:
  - raise
  - collect
  - skip
- Mapping-based validation
- SQLite tests
- PostgreSQL-ready design
- Strict typing
- No hidden global mutable state
- No ORM relationship traversal
- No raw SQL rewriting
- No async implementation until sync core is stable

## Implementation Rules

1. Read all documents under `docs/`.
2. Preserve package boundaries:
   - SQLAlchemy owns SQL.
   - SQLRules owns constraint compilation.
   - Pydantic owns validation.
   - RowGuard owns orchestration and rejection handling.
3. Keep public APIs thin.
4. Use immutable plans and result objects.
5. Keep mutable state per execution.
6. Add tests before moving to the next subsystem.
7. Do not implement deferred features.
8. Keep docs aligned with code.
9. Run Ruff, mypy, pytest, and benchmark smoke tests before completion.

## First Deliverable

Implement the 0.1.0 public API and all unit/integration tests required by
`docs/developer/TESTING.md`.
