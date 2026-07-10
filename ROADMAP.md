# ROADMAP.md

# RowGuard Roadmap

## Vision

RowGuard will become the validation-first query layer for SQLAlchemy,
providing typed Pydantic models, deterministic validation, and
first-class rejected-row handling.

------------------------------------------------------------------------

# Design Principles

Every release should:

-   Keep SQLAlchemy as the execution engine.
-   Keep Pydantic as the validation engine.
-   Keep SQLRules responsible only for SQL constraint compilation.
-   Avoid feature creep into ORM responsibilities.
-   Preserve backward compatibility after 1.0.

------------------------------------------------------------------------

# 0.1.0 --- Foundation (MVP)

## Goals

-   Public synchronous API
-   SQLRules integration
-   QueryResult and RejectedRow
-   Rejection policies: raise, collect, skip
-   SQLAlchemy Core support
-   Pydantic v2 validation
-   Comprehensive unit tests

Deliverable:

``` python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)
```

------------------------------------------------------------------------

# 0.2.0 --- Execution Engine

## Goals

-   Explicit execution plans
-   Diagnostics
-   Statistics
-   Improved error model
-   ORM support
-   Column mapping improvements

------------------------------------------------------------------------

# 0.3.0 --- Streaming

## Goals

-   Sync streaming
-   Incremental validation
-   Configurable batch sizes
-   Memory-efficient processing
-   Progress callbacks

------------------------------------------------------------------------

# 0.4.0 --- Async

## Goals

-   AsyncSession support
-   aselect()
-   aexecute()
-   astream()
-   Async rejection handlers

------------------------------------------------------------------------

# 0.5.0 --- Plugin Platform

## Goals

-   Reject-handler plugins
-   Row-adapter plugins
-   Diagnostics plugins
-   Result exporters
-   Stable plugin API

------------------------------------------------------------------------

# 0.6.0 --- SQL Ecosystem

## Goals

-   SQLModel integration
-   Reflected database support
-   Advanced SQLAlchemy selectable support
-   Better alias handling

------------------------------------------------------------------------

# 0.7.0 --- Performance

## Goals

-   Optimized row adaptation
-   Cached execution plans
-   Parallel validation (where appropriate)
-   Benchmark suite
-   Performance regression testing

------------------------------------------------------------------------

# 0.8.0 --- Enterprise Features

## Goals

-   Quarantine providers
-   Audit trails
-   Metrics integration
-   Structured logging
-   OpenTelemetry hooks

------------------------------------------------------------------------

# 0.9.0 --- Release Candidate

## Goals

-   API freeze
-   Documentation complete
-   Compatibility validation
-   Performance tuning
-   Bug fixes only

------------------------------------------------------------------------

# 1.0.0 --- Stable

## Success Criteria

-   Stable public API
-   Stable plugin API
-   Excellent documentation
-   Comprehensive tests
-   SQLAlchemy 2.x support
-   Pydantic v2 support
-   SQLRules integration
-   Deterministic validation behavior

------------------------------------------------------------------------

# Post-1.0

Potential directions:

-   Pandas/Polars adapters
-   ETL integrations
-   FastAPI dependency helpers
-   Airflow and Dagster integrations
-   Cloud storage quarantine providers
-   Rust acceleration for row adaptation

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
