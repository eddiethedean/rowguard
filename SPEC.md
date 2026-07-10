# SPEC.md

# RowGuard Specification

## Overview

RowGuard is a validation-first query engine built on top of SQLAlchemy,
Pydantic, and SQLRules.

Its purpose is to guarantee that every row returned from a database
query is classified as either:

1.  A valid Pydantic model.
2.  A rejected row with structured diagnostics.

Unlike an ORM, RowGuard does not own your schema. It works with existing
SQLAlchemy Core tables, ORM models, reflected schemas, and eventually
SQLModel.

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

Additional APIs:

``` python
rowguard.stream(...)
rowguard.execute(...)
rowguard.validate_rows(...)
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
-   execution_time

------------------------------------------------------------------------

# RejectedRow

A rejected row contains:

-   original row
-   adapted mapping
-   ValidationError
-   model type
-   diagnostics
-   query metadata

Rejected rows are first-class objects.

------------------------------------------------------------------------

# Rejection Policies

Supported policies:

-   raise
-   collect
-   skip
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

Initial targets:

-   SQLAlchemy Table
-   SQLAlchemy Select
-   SQLAlchemy ORM model
-   SQLAlchemy Session

Future:

-   AsyncSession
-   SQLModel
-   reflected metadata

------------------------------------------------------------------------

# Streaming

Large result sets should be processed incrementally.

``` python
for model in rowguard.stream(...):
    ...
```

Streaming should validate each row independently.

------------------------------------------------------------------------

# Async

Future API:

``` python
await rowguard.aselect(...)
```

Async behavior should mirror synchronous behavior.

------------------------------------------------------------------------

# Statistics

Every QueryResult should expose metrics:

-   rows_read
-   rows_valid
-   rows_rejected
-   validation_time
-   execution_time

------------------------------------------------------------------------

# Diagnostics

Diagnostics may include:

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
-   ValidationFailure
-   RejectHandlerError
-   ConfigurationError

------------------------------------------------------------------------

# SQLModel Position

SQLModel and RowGuard solve different problems.

SQLModel models tables.

RowGuard validates query results.

The libraries should integrate naturally without overlapping
responsibilities.

------------------------------------------------------------------------

# Performance Goals

-   Stream large datasets
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
