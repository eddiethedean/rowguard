# SPEC.md

# RowGuard Specification

## Current as of 0.4.0

Shipped surface:

- Synchronous Core API: `select`, `execute`, `validate_rows`, `compile_plan`, `stream`
- Async Core API: `aselect`, `aexecute`, `astream`
- `StreamResult[T]` / `AsyncStreamResult[T]` with context-managed cleanup
- SQLAlchemy Core `Table` / `Select` with sync or async session/connection
- SQLRules pushdown (`use_sqlrules`, optional `compiled_rules`)
- Rejection policies: `raise`, `collect`, `skip`
- Staged immutable `ExecutionPlan` and planning diagnostics
- Streaming options: `yield_per`, `StreamObserver` / `BaseStreamObserver`
  (observers remain sync callables)

Deferred (not available yet):

- ORM / SQLModel — 0.5.0
- Async callback / quarantine reject handlers — 0.6.0
- Callback / quarantine / log rejection policies — 0.6.0

## Overview

RowGuard is a validation-first query engine built on top of SQLAlchemy,
Pydantic, and SQLRules.

Its purpose is to guarantee that every row returned from a database
query is classified as either:

1.  A valid Pydantic model.
2.  A rejected row with structured diagnostics.

Unlike an ORM, RowGuard does not own your schema. It works with existing
SQLAlchemy Core tables today, and is designed to extend to ORM models,
reflected schemas, and SQLModel in later releases.

------------------------------------------------------------------------

# Scope

RowGuard is responsible for:

-   Building SQLAlchemy queries
-   Integrating SQLRules WHERE expressions
-   Executing queries
-   Adapting rows to dictionaries
-   Validating rows with Pydantic
-   Handling rejected rows
-   Returning typed results
-   Producing diagnostics and statistics

RowGuard is **not** responsible for:

-   ORM mapping
-   Schema migrations
-   SQL generation
-   Database drivers
-   Database connections

------------------------------------------------------------------------

# Core Pipeline

``` text
Pydantic Model
      │
      ▼
SQLRules
Compile SQL-safe constraints
      │
      ▼
SQLAlchemy Statement
      │
      ▼
Database
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ├── Valid Models
      └── Rejected Rows
```

------------------------------------------------------------------------

# Primary API

``` python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)
```

Additional APIs (0.2.0+):

``` python
rowguard.execute(...)
rowguard.validate_rows(...)
rowguard.compile_plan(...)
```

Streaming (0.3.0):

``` python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
```

------------------------------------------------------------------------

# QueryResult

Every query returns a QueryResult.

``` python
QueryResult[T]
```

Properties:

-   models
-   rejected
-   statistics
-   statement
-   diagnostics
-   execution_time (derived from `statistics.execution_time_ns`)

------------------------------------------------------------------------

# RejectedRow

A rejected row contains:

-   row index
-   adapted mapping (when adaptation succeeded)
-   ValidationError and/or adaptation error
-   model type
-   optional raw row

Rejected rows are first-class objects.

------------------------------------------------------------------------

# Rejection Policies

Supported in **0.1.0+**:

-   raise
-   collect
-   skip

Planned for later releases:

-   log
-   callback
-   quarantine

Policy selection is explicit.

------------------------------------------------------------------------

# SQLRules Integration

Before execution, RowGuard asks SQLRules to compile SQL-safe
constraints.

``` text
Pydantic
   ↓
SQLRules
   ↓
WHERE expressions
```

These expressions are added to the SQLAlchemy statement before
execution.

Validation still occurs after retrieval.

------------------------------------------------------------------------

# Validation

Validation uses:

``` python
Model.model_validate(mapping)
```

No custom validation engine is introduced.

Nested models, field validators, and model validators continue to work
because Pydantic remains the source of truth.

------------------------------------------------------------------------

# Supported Inputs

Current (0.4.0):

-   SQLAlchemy Table
-   SQLAlchemy Select
-   SQLAlchemy Session / Connection
-   SQLAlchemy AsyncSession / AsyncConnection
-   Buffered (`select` / `execute` / `aselect` / `aexecute`) and streaming
    (`stream` / `astream`) result modes

Future:

-   SQLAlchemy ORM model (0.5.0)
-   SQLModel (0.5.0)
-   reflected metadata

------------------------------------------------------------------------

# Streaming

Shipped in **0.3.0**. Large result sets are processed incrementally without
retaining accepted models:

``` python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="skip",
) as stream:
    for model in stream:
        ...
    statistics = stream.statistics
```

`StreamResult` is separate from `QueryResult`. Async streaming shipped in
**0.4.0** as `astream` / `AsyncStreamResult` with the same rejection and
lifecycle semantics.

------------------------------------------------------------------------

# Async

Shipped in **0.4.0**:

``` python
await rowguard.aselect(...)
await rowguard.aexecute(...)

async with rowguard.astream(...) as stream:
    async for model in stream:
        ...
```

Async behavior mirrors synchronous behavior for validation and rejection
policies. Await only DB I/O; Pydantic validation remains synchronous on the
event loop. See the docs site page **Supported vs planned** and
`docs/architecture/ASYNC.md`.

------------------------------------------------------------------------

# Statistics

Every QueryResult exposes `QueryStatistics` with:

-   rows_read
-   rows_validated
-   rows_accepted
-   rows_rejected
-   adaptation_time_ns
-   validation_time_ns
-   rejection_time_ns
-   execution_time_ns

`QueryResult.execution_time` is a convenience property over
`execution_time_ns`.

------------------------------------------------------------------------

# Diagnostics

Diagnostics may include:

-   planning codes (source resolved, pushdown applied/skipped, …)
-   rejected fields
-   validation summaries
-   SQL statement
-   rejection policy used

------------------------------------------------------------------------

# Error Model

Public exceptions derive from:

``` python
RowGuardError
```

Examples:

-   QueryExecutionError
-   RowValidationError
-   RowAdaptationError
-   PlanningError
-   ConfigurationError
-   RejectHandlerError

------------------------------------------------------------------------

# SQLModel Position

SQLModel and RowGuard solve different problems.

SQLModel models tables.

RowGuard validates query results.

The libraries should integrate naturally without overlapping
responsibilities.

------------------------------------------------------------------------

# Performance Goals

-   Stream large datasets (0.3.0+)
-   Avoid duplicate validation
-   Reuse SQLRules compilation
-   Linear scaling with row count

------------------------------------------------------------------------

# Plugin Opportunities

Future extension points:

-   reject handlers
-   row adapters
-   result serializers
-   diagnostics
-   dialect helpers

------------------------------------------------------------------------

# Compatibility

Initial release:

-   Python 3.10+
-   Pydantic v2
-   SQLAlchemy 2.x
-   SQLRules 0.x

------------------------------------------------------------------------

# Design Principles

-   Validation-first
-   SQLAlchemy-native
-   Pydantic-native
-   Deterministic
-   Observable
-   Composable
-   Explicit rejection handling

------------------------------------------------------------------------

# Success Criteria

A successful RowGuard application can state:

-   Every returned model satisfies the Pydantic contract.
-   Every rejected row is accounted for.
-   SQL filtering and Pydantic validation work together.
-   Invalid data never silently reaches application code.
