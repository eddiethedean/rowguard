# FAQ

## Why do invalid rows disappear with the default settings?

With `use_sqlrules=True` (default), supported Pydantic constraints may be
compiled into SQL `WHERE` clauses. Invalid candidates never leave the database,
so they never appear in `rejected`.

To inspect validation failures in Python, set `use_sqlrules=False` (as in the
quickstart) or use a statement that still returns those rows.

## What is the difference between `has_rejections` and `rejected`?

- `has_rejections` — any row was rejected (`statistics.rows_rejected > 0`)
- `rejected` — retained rejection objects (empty under `skip`)

## Do I need an ORM?

No. 0.4 targets SQLAlchemy Core `Table` / `Select` with `Session`, `Connection`,
`AsyncSession`, or `AsyncConnection`. ORM / SQLModel support is planned for
**0.5.0**.

## Is async just a thread pool around sync?

No. Async APIs await SQLAlchemy async I/O. Validation stays sync on the loop
(documented blocking risk).

## Can I validate rows without SQL?

Yes — `validate_rows(rows=..., model=...)` validates mappings only.

## Where is the public API contract?

- User guide: [API.md](../api.md)
- Autodoc: [Python API reference](../reference/api.md)
- Spec: [SPEC.md](../spec.md)

## How do I report a bug?

Open an issue at [github.com/eddiethedean/rowguard](https://github.com/eddiethedean/rowguard/issues).
Include driver, RowGuard version, and a minimal repro when possible.
