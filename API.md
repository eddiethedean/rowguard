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
    where=(),
    field_map=None,
    column_map=None,
    parameters=None,
    on_reject="raise",
    use_sqlrules=True,
)
```

Parameters:

-   `session` or `connection`: exactly one SQLAlchemy execution context
-   `table`: SQLAlchemy Core `Table` or selectable
-   `model`: Pydantic `BaseModel` subclass
-   `where`: optional additional SQLAlchemy expressions (default `()`)
-   `field_map`: optional model-field → result-key mapping
-   `column_map`: optional model-field → SQLAlchemy column mapping for SQLRules
-   `parameters`: optional bound parameters forwarded to SQLAlchemy
-   `on_reject`: `raise`, `collect`, or `skip`
    (`callback` / `quarantine` / `log` planned for later releases)
-   `use_sqlrules`: enable SQLRules constraint pushdown (default `True`)

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
    statement=stmt,
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
    source=None,
    on_reject="raise",
    use_sqlrules=True,
)
```

Optional `source=` supplies the selectable used for SQLRules pushdown when
`use_sqlrules=True`. When both `statement` and `source` are provided, RowGuard
emits a `sqlrules.pushdown_source_explicit` diagnostic.

------------------------------------------------------------------------

### validate_rows()

Validate an iterable of row mappings without executing SQL.

``` python
result = rowguard.validate_rows(
    rows=rows,
    model=UserRead,
    field_map=None,
    on_reject="raise",
)
```

Useful for CSV readers, ETL pipelines, or custom data sources.

## QueryResult

``` python
result.models
result.rejected
result.statistics
result.statement
result.diagnostics
result.execution_time
```

Convenience properties:

``` python
result.valid_count
result.rejected_count   # retained rejections only (0 under skip)
result.has_rejections   # True if any row was rejected (including skip)
result.is_clean
```

`has_rejections` is based on `statistics.rows_rejected`, not on whether
rejected rows were retained. Under `skip`, `has_rejections` may be `True`
while `rejected` is empty.

`execution_time` is end-to-end wall time in seconds (statement fetch plus
validation for SQL paths; full processing for `validate_rows`).

## RejectedRow

Each rejected row exposes:

``` python
rejected.index
rejected.model
rejected.mapping
rejected.validation_error
rejected.adaptation_error
rejected.raw_row
```

## Statistics

`QueryStatistics` fields:

-   `rows_read`
-   `rows_validated` (rows that reached Pydantic validation)
-   `rows_accepted`
-   `rows_rejected`
-   `execution_time_ns`
-   `adaptation_time_ns`
-   `validation_time_ns`
-   `rejection_time_ns`

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
-   Never silently discard invalid rows without counting them.
-   Keep function names short and predictable.
-   Prefer explicit configuration over implicit behavior.
-   Build on SQLAlchemy and SQLRules rather than replacing them.
