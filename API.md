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
    attribute_map=None,
    column_map=None,
    parameters=None,
    on_reject="raise",
    use_sqlrules=True,
    compiled_rules=None,
    strict=None,
    orm_validation="mapping",
    unloaded_attributes="error",
)
```

Parameters:

-   `session` or `connection`: exactly one SQLAlchemy execution context
-   `table`: SQLAlchemy Core `Table`, ORM mapped class, or SQLModel table model
-   `model`: Pydantic `BaseModel` subclass
-   `where`: optional additional SQLAlchemy expressions (default `()`)
-   `field_map`: optional model-field → result-key mapping (validated at plan time)
-   `attribute_map`: optional model-field → entity-attribute mapping (entity results)
-   `column_map`: optional model-field → SQLAlchemy column mapping for SQLRules
    (validated at plan time when source columns are known)
-   `parameters`: optional bound parameters forwarded to SQLAlchemy
-   `on_reject`: `raise`, `collect`, or `skip`
    (`callback` / `quarantine` / `log` planned for later releases)
-   `use_sqlrules`: enable SQLRules constraint pushdown (default `True`)
-   `compiled_rules`: optional precompiled SQLRules dict; when set, skips live
    `sqlrules.compile` and only flattens via `sqlrules.where`
-   `strict`: optional Pydantic strict-mode flag for validation planning
-   `orm_validation`: `"mapping"` (default) or `"from_attributes"` (entity selects)
-   `unloaded_attributes`: `"error"` only in 0.5 (deferred/expired attrs fail adaptation)

Returns:

``` python
QueryResult[UserRead]
```

------------------------------------------------------------------------

### compile_plan()

Compile an immutable `ExecutionPlan` without executing against the database.

``` python
plan = rowguard.compile_plan(
    table=users,
    model=UserRead,
    use_sqlrules=True,
    compiled_rules=None,
)
```

Useful for inspection and tests. The plan holds staged sub-plans
(`resolved_source`, `pushdown_plan`, `adapter_plan`, `validation_plan`,
`rejection_plan`), the final `statement`, `parameters`, `execution_id`, and
planning `diagnostics`. It does **not** hold a session or connection.

Internal plan field layout may change before 1.0.

------------------------------------------------------------------------

### stream()

Validate rows incrementally while streaming large result sets. Accepted models
are yielded and never retained. Use a context manager so database resources are
released on early exit.

``` python
with rowguard.stream(
    session=session,
    table=users,          # or statement=stmt
    model=UserRead,
    on_reject="collect",
    use_sqlrules=True,
    yield_per=500,
    observers=None,
) as stream:
    for model in stream:
        process(model)
    stats = stream.statistics
    rejected = stream.rejected
```

Parameters match `select` / `execute` planning knobs, plus:

-   Pass exactly one of `table` or `statement`
-   `yield_per`: optional SQLAlchemy fetch size
-   `observers`: optional sequence of `StreamObserver` hooks

Returns:

``` python
StreamResult[UserRead]
```

`StreamResult` is an iterator and context manager. It exposes live
`statistics`, retained `rejected` rows (under `collect`), `diagnostics`,
`statement`, and `closed`. See `astream` / `AsyncStreamResult` for the async
equivalent.

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

## StreamResult

``` python
stream.statistics
stream.rejected
stream.diagnostics
stream.statement
stream.closed
stream.execution_time
stream.rejected_count
stream.has_rejections
stream.is_clean
```

Accepted models are yielded by iteration and are **not** retained. Prefer:

``` python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
```

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

## Async API (0.5.0)

Requires an async SQLAlchemy engine/driver (e.g. `sqlite+aiosqlite`). Install
with `pip install rowguard[async]`.

``` python
result = await rowguard.aselect(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)

result = await rowguard.aexecute(
    session=session,
    statement=stmt,
    model=UserRead,
)

async with rowguard.astream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="skip",
    yield_per=100,
) as stream:
    async for model in stream:
        ...
```

`aselect` / `aexecute` return the same `QueryResult[T]` as sync. `astream`
returns `AsyncStreamResult[T]` immediately; work starts on `async with` /
`async for`. Prefer `async with` for reliable cursor cleanup (including
cancellation).

Only database I/O is awaited. Pydantic validation runs synchronously on the
event loop and can block under heavy models. Stream observers remain sync
callables. Async reject handlers (callback / quarantine) are not shipped in
0.5.0.

## ORM / SQLModel (0.5.0)

- Prefer projected selects: `execute(statement=select(User.id, ...), source=User)`
- Entity selects: `select(table=User, ...)` uses `ORMEntityAdapter`
- `RejectedRow.source_identity` may hold a primary-key dict
- Install SQLModel support with `pip install rowguard[sqlmodel]`

## Errors

Common public exceptions (see also the docs [error catalog](https://rowguard.readthedocs.io/en/latest/reference/errors.html)):

-   `ConfigurationError` — invalid call configuration
-   `PlanningError` — plan-time failure
-   `QueryExecutionError` — execution / closed-stream failures
-   `RowValidationError` — raise-policy validation failure
-   `RowAdaptationError` — raise-policy adaptation failure

Default `use_sqlrules=True` may filter invalid candidates in SQL so they never
appear in `rejected`. See the SQLRules pushdown guide on the docs site.

## Design Guidelines

-   Return immutable result objects where practical.
-   Never silently discard invalid rows without counting them.
-   Keep function names short and predictable.
-   Prefer explicit configuration over implicit behavior.
-   Build on SQLAlchemy and SQLRules rather than replacing them.
