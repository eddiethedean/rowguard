# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-07-10

### Added

- Staged immutable `ExecutionPlan` with source, pushdown, adapter, validation,
  and rejection sub-plans
- Public `compile_plan()` for plan inspection without database I/O
- Config dataclasses: `PushdownConfig`, `ValidationConfig`, `RejectionConfig`,
  `DiagnosticsConfig`, `AdapterConfig`
- Precompiled SQLRules via `compiled_rules=` (skips live `sqlrules.compile`)
- Plan-time validation of `field_map` / `column_map` keys
- `PlanningError` for stage failures with optional `stage` / `execution_id`
- Stable planning diagnostic codes (`planning.source_resolved`,
  `planning.pushdown_disabled`, `planning.precompiled_rules`, …)
- Optional structural plan cache on `QueryPlanner` (off by default)
- `SyncExecutionContext` holds session/connection (no longer on the plan)
- Optional `strict=` for Pydantic validation planning

### Changed

- Session/connection moved off `ExecutionPlan` onto execution context
- Internal plan shape is not frozen until 1.0; 0.1.0 call sites remain supported

### Deferred

- ORM / SQLModel (planned for 0.5.0)
- `stream()` (0.3.0), async APIs (0.4.0)
- Callback and quarantine rejection policies

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

### Fixed

- `field_map` no longer silently binds wrong keys or accepts defaults when mapped
  source columns are missing (raises `RowAdaptationError`)
- SQLAlchemy results are closed after buffered execution
- Rows are processed incrementally so `raise` can abort without full prefetch
- Adaptation failures record timing and enrich `RowAdaptationError` with
  `row_index` / `model` under the raise policy
- `execution_time` is end-to-end for SQL and `validate_rows` paths
- `rows_validated` counts only rows that reached Pydantic validation
- Explicit `statement` + `source` pushdown emits
  `sqlrules.pushdown_source_explicit` diagnostic
- Require `sqlrules>=0.4.0`

### Deferred

- `stream()` (planned for 0.3.0)
- Async APIs (planned for 0.4.0)
- ORM / SQLModel integrations
- Callback and quarantine rejection policies
