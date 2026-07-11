# Cursor Build Prompt

Build and maintain RowGuard from the architecture and specification documents in
this repository.

**Current shipped release: 0.5.0.** Do not re-implement 0.1.0–0.5.0 unless fixing
regressions. Next planned milestone is **0.6.0 (rejection platform)** per
`ROADMAP.md` and `docs/developer/MILESTONES.md` (MILESTONES is authoritative).

## Shipped through 0.5.0

- Python 3.10+
- Pydantic v2
- SQLAlchemy 2.x
- SQLRules integration (`sqlrules>=1.0.0,<2`)
- SQLAlchemy Core `Table` and `Select`
- SQLAlchemy ORM mapped classes (projected + single-entity)
- SQLModel table sources (`rowguard[sqlmodel]`)
- Sync `Session` / `Connection` and async `AsyncSession` / `AsyncConnection`
- `select()`, `execute()`, `validate_rows()`, `compile_plan()`, `stream()`
- `aselect()`, `aexecute()`, `astream()`
- `StreamResult[T]` / `AsyncStreamResult[T]` with context-managed cleanup
- `StreamObserver` / `BaseStreamObserver` progress hooks (sync callables)
- Staged immutable `ExecutionPlan` and planning configs
- `QueryResult[T]`, `RejectedRow` (incl. `source_identity`), `QueryStatistics`
- Rejection policies: `raise`, `collect`, `skip`
- Mapping-based validation default; opt-in `orm_validation="from_attributes"`
- Unloaded/deferred attribute errors (`unloaded_attributes="error"`)
- SQLite unit + integration + streaming + async + ORM/SQLModel tests
- Strict typing
- No ORM relationship traversal
- No async callback/quarantine handlers until 0.6.0

## Implementation Rules

1. Read all documents under `docs/`; treat MILESTONES as authoritative for scope.
2. Preserve package boundaries:
   - SQLAlchemy owns SQL.
   - SQLRules owns constraint compilation.
   - Pydantic owns validation.
   - RowGuard owns orchestration and rejection handling.
3. Keep public APIs thin.
4. Use immutable plans and result objects.
5. Keep mutable state per execution.
6. Add tests before moving to the next subsystem.
7. Do not implement deferred features ahead of their milestone.
8. Keep docs aligned with code (especially README / API.md / SPEC.md).
9. Run Ruff, mypy, pytest, and benchmark smoke tests before completion.

## Next Deliverable

Implement the **0.6.0 rejection platform** (callback / quarantine) required by
`docs/developer/MILESTONES.md`, without breaking 0.5.x call sites.
