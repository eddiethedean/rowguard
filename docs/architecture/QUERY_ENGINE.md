# QUERY_ENGINE.md

# RowGuard Query Engine

## Purpose

The Query Engine is the runtime core of RowGuard. It is responsible for
executing SQLAlchemy statements and coordinating row adaptation,
validation, rejection handling, and result assembly.

It does **not** generate SQL or perform validation logic itself.
Instead, it orchestrates the other components.

------------------------------------------------------------------------

# Responsibilities

The Query Engine:

-   Executes SQLAlchemy statements
-   Supports synchronous and asynchronous execution
-   Supports buffered and streaming modes
-   Coordinates row adaptation
-   Invokes the validation engine
-   Applies rejection policies
-   Collects statistics
-   Produces `QueryResult` objects

The Query Engine does **not**:

-   Build SQL statements
-   Compile SQLRules constraints
-   Parse SQL
-   Open or configure database engines
-   Replace SQLAlchemy's execution model

------------------------------------------------------------------------

# Execution Pipeline

``` text
Execution Plan
      │
      ▼
Execute Statement
      │
      ▼
Receive Rows
      │
      ▼
Row Adapter
      │
      ▼
Validation Engine
      │
      ├── Valid Model
      └── Rejected Row
      │
      ▼
Reject Handler
      │
      ▼
Result Assembler
```

------------------------------------------------------------------------

# Inputs

The Query Engine receives an immutable `ExecutionPlan`.

Suggested contents:

-   SQLAlchemy statement
-   Session or AsyncSession
-   Target Pydantic model
-   Rejection policy
-   Row adapter
-   Validation configuration
-   Diagnostics options

------------------------------------------------------------------------

# Execution Modes

## Buffered

Reads the complete result set before returning a `QueryResult`.

Best for:

-   Small and medium result sets
-   Interactive applications

## Streaming

Processes rows incrementally.

``` python
for model in rowguard.stream(...):
    ...
```

Best for:

-   Large datasets
-   ETL
-   Long-running jobs

------------------------------------------------------------------------

# SQLAlchemy Integration

The engine should work with:

-   SQLAlchemy Core
-   SQLAlchemy ORM
-   Select statements
-   Reflected tables
-   Aliases
-   Subqueries

Future support:

-   SQLModel
-   AsyncSession

------------------------------------------------------------------------

# Row Adaptation

The Query Engine delegates row conversion to a Row Adapter.

Output:

``` python
dict[str, object]
```

The adapter is responsible for:

-   column names
-   aliases
-   duplicate columns
-   SQLAlchemy Row objects

------------------------------------------------------------------------

# Validation

Validation is delegated to Pydantic.

``` python
model.model_validate(mapping)
```

The Query Engine only coordinates validation.

------------------------------------------------------------------------

# Rejection Handling

Every validation failure is forwarded to the configured rejection
policy.

Supported policies:

-   raise
-   collect
-   skip
-   log
-   callback
-   quarantine

------------------------------------------------------------------------

# Statistics

The Query Engine records:

-   rows_read
-   rows_valid
-   rows_rejected
-   execution_time
-   validation_time

Future metrics:

-   adaptation_time
-   callback_time
-   throughput

------------------------------------------------------------------------

# Error Handling

Public exceptions:

-   QueryExecutionError
-   ValidationFailure
-   RejectHandlerError
-   ConfigurationError

Unexpected failures are wrapped with contextual information.

------------------------------------------------------------------------

# Concurrency

Execution state is isolated per query.

The engine should avoid shared mutable state.

Thread safety is achieved through immutable execution plans and
per-query statistics collectors.

------------------------------------------------------------------------

# Extension Points

Future plugins may customize:

-   execution observers
-   metrics
-   tracing
-   retry strategies
-   result exporters

------------------------------------------------------------------------

# Performance Goals

-   O(n) with respect to rows processed
-   Minimal allocations
-   Streaming-first architecture
-   No unnecessary row copies
-   Efficient interaction with SQLAlchemy

------------------------------------------------------------------------

# Design Principles

-   Delegate specialized work
-   Keep orchestration simple
-   Preserve SQLAlchemy semantics
-   Make validation explicit
-   Provide deterministic behavior
