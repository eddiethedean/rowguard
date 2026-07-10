# EXECUTION_PIPELINE.md

# RowGuard Execution Pipeline

## Purpose

This document specifies the end-to-end execution pipeline used by
RowGuard. The pipeline is deterministic: the same execution plan,
database state, and configuration should always produce the same
outcome.

The pipeline separates planning from execution so each stage is
independently testable and replaceable.

------------------------------------------------------------------------

# High-Level Flow

``` text
Application
      │
      ▼
Execution Plan
      │
      ▼
Query Builder
      │
      ▼
SQLRules Filter Pushdown
      │
      ▼
SQLAlchemy Statement
      │
      ▼
Database Execution
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ├── Valid Model
      └── Validation Failure
      │
      ▼
Reject Handler
      │
      ▼
Result Assembler
      │
      ▼
QueryResult
```

------------------------------------------------------------------------

# Stage 1 -- Build Execution Plan

Inputs:

-   Session or AsyncSession
-   SQLAlchemy table, selectable, or statement
-   Pydantic model
-   Rejection policy
-   Diagnostics options
-   Streaming configuration

Output:

An immutable `ExecutionPlan`.

No database access occurs during this stage.

------------------------------------------------------------------------

# Stage 2 -- Query Construction

If the caller supplied a table or ORM model, RowGuard constructs a
SQLAlchemy `Select` statement.

If a statement was supplied, this stage simply validates it.

------------------------------------------------------------------------

# Stage 3 -- SQLRules Integration

When enabled, RowGuard invokes SQLRules to compile SQL-safe constraints
from the Pydantic model into SQLAlchemy expressions.

These expressions are merged into the statement's `WHERE` clause.

This stage performs no database I/O.

------------------------------------------------------------------------

# Stage 4 -- Execute Statement

The Query Engine executes the SQLAlchemy statement using the supplied
session.

Execution modes:

-   Buffered
-   Streaming

Execution errors are surfaced immediately.

------------------------------------------------------------------------

# Stage 5 -- Adapt Rows

Each SQLAlchemy row is converted into a mapping suitable for Pydantic.

Responsibilities include:

-   Preserve column names
-   Respect aliases
-   Handle duplicate columns
-   Produce deterministic mappings

Output:

``` python
dict[str, object]
```

------------------------------------------------------------------------

# Stage 6 -- Validate

Each mapping is validated using:

``` python
Model.model_validate(mapping)
```

Possible outcomes:

-   Valid model
-   ValidationError

Validation is performed one row at a time.

------------------------------------------------------------------------

# Stage 7 -- Handle Rejections

Validation failures are forwarded to the configured rejection policy.

Supported policies:

-   raise
-   collect
-   skip
-   log
-   callback
-   quarantine

No validation failure should disappear silently.

------------------------------------------------------------------------

# Stage 8 -- Collect Statistics

The pipeline records:

-   rows read
-   rows validated
-   rows accepted
-   rows rejected
-   execution time
-   validation time

Future metrics may include throughput and adaptation time.

------------------------------------------------------------------------

# Stage 9 -- Assemble Result

Buffered execution returns:

``` python
QueryResult[T]
```

containing:

-   models
-   rejected rows
-   statistics
-   diagnostics
-   executed statement

Streaming execution yields validated models incrementally while
maintaining optional statistics.

------------------------------------------------------------------------

# Error Propagation

Pipeline stages should fail with contextual exceptions.

Expected public errors include:

-   QueryExecutionError
-   ValidationFailure
-   RejectHandlerError
-   ConfigurationError

Unexpected failures are wrapped with execution context.

------------------------------------------------------------------------

# Pipeline Invariants

The execution pipeline must guarantee:

-   Every processed row is classified.
-   Accepted rows satisfy the target Pydantic model.
-   Rejected rows are observable.
-   Stage ordering never changes.
-   Statistics reflect actual processing.

------------------------------------------------------------------------

# Extensibility

Future plugins may participate in:

-   execution observers
-   row adaptation
-   rejection handling
-   diagnostics
-   metrics
-   tracing

Extension points should not alter the core stage ordering.

------------------------------------------------------------------------

# Design Principles

-   Immutable execution plans
-   One responsibility per stage
-   Explicit state transitions
-   Deterministic execution
-   SQLAlchemy-native behavior
-   Pydantic-driven validation
