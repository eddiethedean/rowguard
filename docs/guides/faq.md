# FAQ

## Why do invalid rows disappear with the default settings?

With `use_sqlrules=True` (default), supported Pydantic constraints may be
compiled into SQL `WHERE` clauses. Invalid candidates never leave the database,
so they never appear in `rejected`.

To inspect validation failures in Python, set `use_sqlrules=False` (see
[Quickstart](quickstart.md#2-inspect-rejections-in-python)) and usually
`on_reject="collect"`.

## Why is `rejected` empty even with `on_reject="collect"`?

Most often pushdown removed the bad rows before fetch. Set `use_sqlrules=False`.
Also remember: default `on_reject` is `"raise"`, which never retains rejections.

## What is the difference between `has_rejections` and `rejected`?

- `has_rejections` — any row was rejected (`statistics.rows_rejected > 0`)
- `rejected` — retained rejection objects (empty under `skip`)

## Do I need an ORM?

No. 0.5 targets SQLAlchemy Core `Table` / `Select` and can validate ORM /
SQLModel **reads**. It does not own mapping or persistence. See
[ORM and SQLModel](orm-sqlmodel.md).

## Is async just a thread pool around sync?

No. Async APIs await SQLAlchemy async I/O. Validation stays sync on the loop
(documented blocking risk). See [Performance](performance.md).

## Can I validate rows without SQL?

Yes — `validate_rows(rows=..., model=...)`.

## Where is the public API contract?

- [API guide](../api.md)
- [Python autodoc](../reference/api.md)
- [Error catalog](../reference/errors.md)
- [Supported vs planned](../project/supported.md)

## How do I upgrade from 0.4?

See [Upgrading](upgrading.md) (sqlrules 1.x required; ORM reads added in 0.5).

## How do I report a bug?

Use the GitHub issue templates. Include driver, RowGuard version, and a minimal
repro. Security: [Security policy](../project/security.md)—do not file public
issues for vulnerabilities.
