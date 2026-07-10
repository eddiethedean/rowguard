# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-10

### Added

- Public sync API: `select()`, `execute()`, `validate_rows()`
- SQLAlchemy Core support for `Table` and existing `Select`
- Sync `Session` and `Connection` execution
- SQLRules pushdown integration (`use_sqlrules`, optional `column_map`)
- Pydantic v2 row validation via mapping adaptation
- Rejection policies: `raise`, `collect`, `skip`
- `QueryResult[T]`, `RejectedRow`, `QueryStatistics`, and diagnostics
- Optional `field_map` for result key remapping
- SQLite integration tests, unit tests, CI, and example

### Deferred

- `stream()` (planned for 0.3.0)
- Async APIs (planned for 0.4.0)
- ORM / SQLModel integrations
- Callback and quarantine rejection policies
