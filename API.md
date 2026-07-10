# API.md

# RowGuard Public API

## Philosophy

The public API is intentionally small. RowGuard should expose a few
powerful, composable entry points while keeping execution details
internal.

## Core Functions

### select()

Execute a SQL query, validate every returned row against a Pydantic
model, and return a `QueryResult`.

``` python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    where=None,
    column_map=None,
    on_reject="raise",
)
```

Parameters:

-   `session`: SQLAlchemy `Session`
-   `table`: SQLAlchemy `Table`, ORM model, or selectable
-   `model`: Pydantic `BaseModel` subclass
-   `where`: optional additional SQLAlchemy expressions
-   `column_map`: optional field-to-column mapping
-   `on_reject`: `raise`, `collect`, or `skip`
    (`callback` / `quarantine` / `log` planned for later releases)

Returns:

``` python
QueryResult[UserRead]
```

------------------------------------------------------------------------

### stream()

Validate rows incrementally while streaming large result sets.

> **Status (0.1.0):** Not implemented. Raises `NotImplementedError`.
> Planned for 0.3.0.

``` python
for model in rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
):
    ...
```

------------------------------------------------------------------------

### execute()

Execute an existing SQLAlchemy statement instead of constructing one.

``` python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

------------------------------------------------------------------------

### validate_rows()

Validate an iterable of row mappings without executing SQL.

``` python
result = rowguard.validate_rows(
    rows=rows,
    model=UserRead,
)
```

Useful for CSV readers, ETL pipelines, or custom data sources.

## QueryResult

``` python
result.models
result.rejected
result.statistics
result.statement
result.execution_time
```

Convenience methods:

``` python
result.valid_count
result.rejected_count
result.has_rejections()
```

## RejectedRow

Each rejected row exposes:

``` python
rejected.raw_row
rejected.mapping
rejected.validation_error
rejected.model
rejected.metadata
```

## Statistics

Statistics should include:

-   rows_read
-   rows_valid
-   rows_rejected
-   execution_time
-   validation_time

## Async API (Planned — 0.4.0)

> Not available in 0.1.0.

``` python
await rowguard.aselect(...)
await rowguard.aexecute(...)
async for model in rowguard.astream(...):
    ...
```

## Design Guidelines

-   Return immutable result objects where practical.
-   Never silently discard invalid rows.
-   Keep function names short and predictable.
-   Prefer explicit configuration over implicit behavior.
-   Build on SQLAlchemy and SQLRules rather than replacing them.
