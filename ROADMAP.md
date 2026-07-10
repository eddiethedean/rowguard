# ROADMAP.md

# RowGuard Roadmap

## Vision

RowGuard will become the validation-first query layer for SQLAlchemy,
providing typed Pydantic models, deterministic validation, and
first-class rejected-row handling.

This roadmap is a concise summary of
[docs/developer/MILESTONES.md](docs/developer/MILESTONES.md). When the two
disagree, **MILESTONES.md is authoritative**.

------------------------------------------------------------------------

# Design Principles

Every release should:

-   Keep SQLAlchemy as the execution engine.
-   Keep Pydantic as the validation engine.
-   Keep SQLRules responsible only for SQL constraint compilation.
-   Avoid feature creep into ORM responsibilities.
-   Preserve backward compatibility after 1.0.

------------------------------------------------------------------------

# 0.1.0 --- Validation-First Core (shipped)

## Goals

-   Public synchronous API (`select`, `execute`, `validate_rows`)
-   SQLRules integration
-   `QueryResult` and `RejectedRow`
-   Rejection policies: raise, collect, skip
-   SQLAlchemy Core support
-   Pydantic v2 validation
-   Comprehensive unit and SQLite integration tests

Deliverable:

``` python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)
```

------------------------------------------------------------------------

# 0.2.0 --- Execution Planning (shipped)

## Goals

-   Immutable staged `ExecutionPlan`
-   Normalized `QueryRequest` and planning configs
-   Source / statement / pushdown / adapter / validation / rejection planning
-   Public `compile_plan()` for plan inspection
-   Precompiled SQLRules (`compiled_rules=`)
-   Plan-time field/column map validation
-   Structured planning diagnostics and `PlanningError`
-   Optional structural plan cache (opt-in)
-   Session/connection held only on execution context

ORM and SQLModel remain deferred to **0.5.0**.

------------------------------------------------------------------------

# 0.3.0 --- Streaming Engine (shipped)

## Goals

-   `stream()` and `StreamResult[T]`
-   Incremental validation
-   Context-managed resource lifecycle
-   Memory-bounded processing
-   Rejection policies during streaming
-   Progress / observer hooks

Deliverable:

``` python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
) as stream:
    for model in stream:
        process(model)
```

------------------------------------------------------------------------

# 0.4.0 --- Async Engine

## Goals

-   `aselect()` / `aexecute()` / `astream()`
-   `AsyncSession` / `AsyncConnection`
-   Async stream lifecycle
-   Async rejection handlers
-   Sync/async parity

------------------------------------------------------------------------

# 0.5.0 --- ORM and SQLModel Integration

## Goals

-   SQLAlchemy ORM mapped classes and ORM `Select`
-   Projected-column validation
-   Explicit entity / `from_attributes` behavior
-   Lazy-load safeguards
-   SQLModel table sources and read targets
-   Documentation and examples

------------------------------------------------------------------------

# 0.6.0 --- Rejection Platform

## Goals

-   Callback policy and structured callback context
-   Quarantine policy, records, and receipts
-   In-memory and JSONL providers
-   Redaction and retention policies
-   Rejection thresholds

------------------------------------------------------------------------

# 0.7.0 --- Plugin System

## Goals

-   Plugin API version 1
-   Adapter, source-resolver, and rejection-policy plugins
-   Quarantine providers and diagnostic exporters
-   Explicit registration and conformance tests

------------------------------------------------------------------------

# 0.8.0 --- Dialects, Reflection, and Raw SQL

## Goals

-   Dialect profiles and capability detection
-   Broader database support matrix
-   Reflected tables
-   Parameterized raw SQLAlchemy `text()`
-   Portable / native / strict dialect policies

------------------------------------------------------------------------

# 0.9.0 --- Stabilization and Release Candidate

## Goals

-   Public API and plugin API freeze
-   Documentation completion
-   Compatibility and security review
-   Performance tuning and cache hardening
-   Bug fixes only toward 1.0

------------------------------------------------------------------------

# 1.0.0 --- Stable

## Success Criteria

-   Stable public API and plugin API
-   Excellent documentation
-   Comprehensive tests
-   SQLAlchemy 2.x, Pydantic v2, and SQLRules integration
-   Core, ORM, SQLModel, sync, async, buffered, and streaming
-   Deterministic validation behavior

------------------------------------------------------------------------

# Post-1.0

Potential directions (see MILESTONES.md for detail):

-   Developer experience (plan explanations, FastAPI helpers)
-   Pandas / Polars / Arrow exporters
-   Airflow, Dagster, and Prefect integrations
-   Advanced quarantine / replay providers
-   Broader validation targets (`TypeAdapter`, dataclasses, TypedDict)

------------------------------------------------------------------------

# Long-Term Ecosystem

``` text
SQLRules
    │
    ▼
Compile SQL constraints

RowGuard
    │
    ▼
Execute queries
Validate rows
Manage rejected rows

Future Packages
    ├── ETL
    ├── Analytics
    ├── Monitoring
    └── Domain integrations
```
