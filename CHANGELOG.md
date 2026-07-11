# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — 2026-07-10

### Added

- SQLAlchemy ORM mapped classes as `table=` / `source=` with SQLRules pushdown
- Projected ORM selects via `execute(statement=select(...), source=MappedClass)`
- Single-entity adaptation (`ORMEntityAdapter`) for `select(MappedClass)`
- Opt-in `orm_validation="from_attributes"` with unloaded-attribute guards
- `unloaded_attributes="error"` (only supported policy in 0.5)
- Optional `attribute_map` for entity attribute → model field remapping
- `RejectedRow.source_identity` primary-key dict (no live entity retention)
- SQLModel table-source support via optional `rowguard[sqlmodel]`
- Examples: `orm_projected.py`, `orm_entity.py`, `sqlmodel_basic.py`
- User guide: [ORM and SQLModel](docs/guides/orm-sqlmodel.md)

### Changed

- Require `sqlrules>=1.0.0,<2` (SQLRules 1.0 stable Application API)

### Fixed

- `attribute_map` cannot be combined with `from_attributes` (plan-time error)
- Entity-shaped selects require `Session` / `AsyncSession` (not bare `Connection`)
- Model-only default/optional fields no longer force entity `getattr` failures
- Synonyms are not treated as permanently unloaded when the target column is loaded
- Joined-inheritance `column_map` membership uses full mapper columns
- Select passed as `source=` is treated as the statement (no raw SA crash)
- `_table_column_names` uses `selected_columns` for Selects (no SelectBase.c warning)
- `field_map` rejected on entity shapes; relationships rejected at plan time
- Adaptation failures preserve best-effort `source_identity`
- Plan cache distinguishes `diagnostics.enabled`

### Notes

- Prefer column projections for strict read-contract validation
- Multi-entity and entity+scalar shapes are rejected at plan time
- Relationship traversal, write-back, and lazy-load-enabled validation remain out of scope

## [0.4.0] — 2026-07-10

### Added

- First-class async APIs: `aselect()`, `aexecute()`, and `astream()`
- `AsyncSession` / `AsyncConnection` execution via `AsyncExecutionContext`
- `AsyncStreamResult[T]` with lifecycle parity to sync `StreamResult`
  (`async with`, `async for`, idempotent `close()`, raise-policy stats)
- `AsyncExecutionEngine` / `AsyncStreamEngine` reusing planner + `process_row`
- Async tests under `tests/async/` (aiosqlite parity, lifecycle, cancellation)
- `examples/async_basic.py` and pytest-asyncio `asyncio_mode = auto`
- Optional install: `pip install rowguard[async]` (`aiosqlite`, `greenlet`)

### Notes

- Await only DB I/O; Pydantic validation remains synchronous on the event loop
  (document blocking risk for heavy models)
- Async callback / quarantine reject handlers remain deferred to 0.6.0
- Driver matrix for this release: **sqlite+aiosqlite** (asyncpg not required)

## [0.3.1] — 2026-07-10

### Fixed

- Stream iteration without `with` now closes the SQLAlchemy result on early
  `break` / consumer exit (`for model in stream`)
- Raise-policy rejections are recorded in stream statistics before raising, so
  post-mortem `is_clean` / `rows_rejected` are accurate
- `on_stream_complete` observers receive a non-zero `execution_time_ns` after
  rows were processed
- Close failures after a successful complete no longer emit a spurious
  `on_stream_failed` when using a context manager
- Re-entering a closed `StreamResult` raises `QueryExecutionError` instead of
  silently empty-iterating
- Invalid `yield_per` is rejected at `stream()` / `StreamingConfig` construction
- Plan-time `field_map` no longer treats values as source table columns (they
  are result keys); labeled `execute` + `source=` + `field_map` works
- Plan-cache hits rewrite diagnostic `execution_id`s to match the rebound plan
- `compile_plan` rejects `table=` + `statement=` together
- `compiled_rules` / `column_map` without a pushdown source raise `PlanningError`
  instead of being silently dropped

## [0.3.0] — 2026-07-10

### Added

- Public `stream()` returning context-managed `StreamResult[T]`
- Incremental validation that yields accepted models without retaining them
- SQLAlchemy streaming options: `stream_results=True` and optional `yield_per=`
- Rejection policy parity during streaming (`raise`, `collect`, `skip`)
- Live `statistics`, retained `rejected`, `diagnostics`, and `statement` on
  `StreamResult`
- First-party `StreamObserver` / `BaseStreamObserver` progress hooks
- `StreamingConfig` for execution-time streaming options
- Shared `MutableStatistics` / `ExecutionState` used by buffered and streaming
  engines
- Streaming tests (parity, cleanup, observers, memory regression) and
  `examples/streaming.py`

### Changed

- `stream()` accepts either `table=` or `statement=` with the same planning knobs
  as `select` / `execute` (`session`/`connection`, pushdown, maps, `strict`, …)
- Package version and docs updated for the 0.3.0 surface

### Deferred

- Async APIs including `astream()` (0.4.0)
- ORM / SQLModel (0.5.0)
- Callback and quarantine rejection policies (0.6.0)

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
- `pushdown_source` no longer overrides the SELECT `FROM` when `table=` is set
- Skipped pushdown (no source) sets `use_sqlrules=False` / `PushdownPlan.enabled=False`

### Fixed

- Plan cache key collisions on `parameters`, `column_map` values, `compiled_rules`,
  and `pushdown.source`; cache hits rebind parameters and mint a fresh `execution_id`
- `column_map` membership is hard-failed when pushdown source columns are known
- `result.close()` failures no longer mask validation/execution errors
- `validate_rows` rejects unknown `field_map` keys like the planner
- Unexpected adapter exceptions are wrapped as `RowAdaptationError` for rejection policies
- `StreamResult` raises `NotImplementedError` instead of silently empty-iterating
- `compile_plan` rejects passing both `table=` and `source=`
- `LRUCache` rejects non-positive `max_entries`

### Deferred

- ORM / SQLModel (planned for 0.5.0)
- Async APIs (0.4.0)
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

[0.5.0]: https://github.com/eddiethedean/rowguard/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/eddiethedean/rowguard/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/eddiethedean/rowguard/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/eddiethedean/rowguard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/eddiethedean/rowguard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/eddiethedean/rowguard/releases/tag/v0.1.0
