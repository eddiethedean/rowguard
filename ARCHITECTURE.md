# ARCHITECTURE.md

# RowGuard Architecture

## Overview

RowGuard is a layered validation-first query engine built on top of
SQLAlchemy, Pydantic, and SQLRules.

Its architecture intentionally separates SQL compilation, query
execution, row adaptation, validation, rejection handling, and result
construction.

``` text
                  Application
                        │
                        ▼
                 RowGuard Public API
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
   Query Builder   Validation Engine   Streaming API
        │               │                │
        └───────────────┼────────────────┘
                        ▼
                  Execution Engine
                        │
                        ▼
                  SQLAlchemy Engine
                        │
                        ▼
                     Database
```

------------------------------------------------------------------------

# Architectural Principles

-   Single responsibility per component
-   SQLAlchemy-native
-   Pydantic-native
-   SQLRules for SQL pushdown only
-   Immutable data flow where practical
-   Explicit rejection handling
-   Observable execution

------------------------------------------------------------------------

# Layered Design

## Layer 1 -- Public API

Responsibilities:

-   Accept user requests
-   Configure execution
-   Return QueryResult

Representative API:

``` python
rowguard.select(...)
rowguard.stream(...)
rowguard.execute(...)
rowguard.validate_rows(...)
```

------------------------------------------------------------------------

## Layer 2 -- Query Builder

Responsibilities:

-   Accept SQLAlchemy objects
-   Invoke SQLRules
-   Merge WHERE expressions
-   Produce executable SQLAlchemy statements

Output:

``` text
SQLAlchemy Select
```

------------------------------------------------------------------------

## Layer 3 -- Execution Engine

Responsibilities:

-   Execute statements
-   Iterate database rows
-   Support sync and async execution
-   Support streaming

The execution engine never performs validation itself.

------------------------------------------------------------------------

## Layer 4 -- Row Adapter

Responsibilities:

-   Convert SQLAlchemy rows into mappings
-   Preserve column names
-   Apply aliases when configured

Output:

``` python
dict[str, object]
```

------------------------------------------------------------------------

## Layer 5 -- Validation Engine

Responsibilities:

-   Call `model_validate()`
-   Produce typed Pydantic models
-   Capture ValidationError objects
-   Forward failures to rejection handling

Validation remains entirely delegated to Pydantic.

------------------------------------------------------------------------

## Layer 6 -- Rejection Handling (shipped)

Shipped policies:

-   `raise` — stop on first rejection (default)
-   `collect` — retain `RejectedRow` values
-   `skip` — count rejections but do not retain them

Callback, quarantine, and log policies are **not shipped** in 0.5. See
[Supported vs planned](docs/project/supported.md).

Every row that reaches validation follows the configured policy. Default
SQLRules pushdown may filter invalid candidates in SQL before fetch.

------------------------------------------------------------------------

## Layer 7 -- Result Assembly

Produces a QueryResult containing:

-   validated models
-   rejected rows
-   execution statistics
-   diagnostics
-   executed statement

------------------------------------------------------------------------

# SQLRules Integration

``` text
Pydantic Model
      │
      ▼
SQLRules
      │
      ▼
WHERE Expressions
      │
      ▼
Query Builder
```

SQLRules is responsible only for SQL-safe constraint compilation.

RowGuard owns execution and validation.

------------------------------------------------------------------------

# Internal Components

``` text
Public API
     │
Compiler Bridge
     │
Query Builder
     │
Execution Engine
     │
Row Adapter
     │
Validation Engine
     │
Reject Handler
     │
Result Assembler
```

Each component should be independently testable.

------------------------------------------------------------------------

# Query Lifecycle

``` text
Receive Request
      │
Build Statement
      │
Compile SQLRules Filters
      │
Execute SQL
      │
Adapt Row
      │
Validate
      │
Accept or Reject
      │
Return QueryResult
```

------------------------------------------------------------------------

# Thread Safety

Compiler configuration and registries should be immutable after
initialization.

Execution state is scoped to each query.

------------------------------------------------------------------------

# Extension Points

Future plugins may provide:

-   row adapters
-   reject handlers
-   diagnostics
-   dialect helpers
-   result exporters

------------------------------------------------------------------------

# Non-Goals

Architecture intentionally excludes:

-   Owning ORM persistence / relationship graphs (0.5 **does** validate ORM and
    SQLModel **reads**)
-   migrations
-   SQL parsing
-   schema reflection helpers (planned later)
-   database drivers

------------------------------------------------------------------------

# Design Goals

The architecture should make it easy to:

-   support legacy databases
-   integrate SQLRules
-   validate every row
-   stream millions of rows
-   first-class async execution (shipped in 0.4.0)
-   extend behavior without changing the core
