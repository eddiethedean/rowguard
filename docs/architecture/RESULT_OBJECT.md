# RESULT_OBJECT.md

:::{admonition} Design notes — read the user guide first
:class: caution

Shipped result types are documented in the [API guide](../api.md). Callback /
quarantine / log result shapes described below are **not shipped** in 0.5.0.
:::

# RowGuard Result Object

## Purpose

The `QueryResult` object is the primary buffered result returned by RowGuard.

It provides a structured, typed, and observable representation of a completed
query operation, including:

- Validated Pydantic models
- Rejected rows
- Execution statistics
- Diagnostics
- The executed SQLAlchemy statement
- Timing information

The result object should make successful and failed row handling equally visible.

---

# Core Contract

```python
QueryResult[T]
```

Where `T` is the target Pydantic model type.

Example:

```python
result: QueryResult[UserRead] = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

---

# Suggested Data Model

```python
from dataclasses import dataclass
from datetime import timedelta
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class QueryResult(Generic[T]):
    models: tuple[T, ...]
    rejected: tuple[RejectedRow, ...]
    statistics: QueryStatistics
    statement: object
    diagnostics: tuple[Diagnostic, ...]
```

The result should be immutable after construction.

---

# Models

```python
result.models
```

Contains every successfully validated Pydantic model.

Recommended type:

```python
tuple[T, ...]
```

A tuple communicates that query results are complete and immutable.

Convenience aliases may include:

```python
result.valid
result.accepted
```

The canonical public name should remain `models`.

---

# Rejected Rows

```python
result.rejected
```

Contains every rejected row when the rejection policy retains them.

Each item should be a `RejectedRow` containing:

- Raw database row
- Adapted mapping
- Pydantic validation error
- Target model
- Row index or sequence number
- Optional source metadata
- Diagnostics

Example:

```python
for rejected in result.rejected:
    print(rejected.validation_error)
    print(rejected.mapping)
```

---

# QueryStatistics

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class QueryStatistics:
    rows_read: int
    rows_validated: int
    rows_valid: int
    rows_rejected: int
    execution_time_ns: int
    adaptation_time_ns: int
    validation_time_ns: int
    rejection_time_ns: int
```

Derived properties:

```python
statistics.acceptance_rate
statistics.rejection_rate
statistics.total_time_ns
```

The statistics object should avoid floating-point values until requested.

---

# Statement

```python
result.statement
```

Contains the SQLAlchemy statement that RowGuard executed.

This is useful for:

- Debugging
- Logging
- Testing
- Observability
- Reproducing query behavior

RowGuard should preserve the SQLAlchemy expression object rather than rendering
a SQL string by default.

---

# Diagnostics

```python
result.diagnostics
```

Diagnostics may include:

- SQLRules pushdown decisions
- Skipped constraints
- Field mappings
- Alias resolution
- Rejection-policy actions
- Adapter warnings
- Query planning notes

Diagnostics should be structured objects, not plain strings.

---

# Convenience Properties

Recommended properties:

```python
result.valid_count
result.rejected_count
result.total_count
result.has_rejections
result.is_clean
```

Suggested semantics:

```python
result.valid_count == len(result.models)
result.rejected_count == len(result.rejected)
result.has_rejections is bool(result.rejected)
result.is_clean is not result.has_rejections
```

`total_count` should reflect rows processed, not merely retained objects.

---

# Iteration

A `QueryResult` may iterate over valid models:

```python
for user in result:
    ...
```

Equivalent to:

```python
for user in result.models:
    ...
```

This should be a convenience only. Explicit access through `result.models`
remains clearer in most code.

---

# Length

```python
len(result)
```

Recommended meaning:

```python
len(result.models)
```

This matches the iterable behavior.

Rejected rows are available separately.

---

# Indexing

Optional support:

```python
result[0]
```

Equivalent to:

```python
result.models[0]
```

This makes buffered results list-like without hiding rejected-row metadata.

---

# Truthiness

`QueryResult` should not overload truthiness ambiguously.

Possible options:

1. Always truthy.
2. Truthy only when valid models exist.
3. Disallow implicit boolean conversion.

Recommended behavior:

```python
bool(result) == bool(result.models)
```

This is intuitive, but it must be documented because a result may contain only
rejections.

Applications checking query success should use explicit properties such as:

```python
result.is_clean
result.has_rejections
```

---

# Rejection Policy Effects

The result shape depends on the configured rejection policy.

## collect

Rejected rows are included in `result.rejected`.

## skip

Rejected rows may not be retained, but statistics must still count them.

## raise

No `QueryResult` is returned if validation fails.

## log

Rejected rows may or may not be retained depending on configuration.

## callback

Retention is configurable.

## quarantine

Rejected rows may be represented by lightweight references if raw data is moved
to another destination.

The result object must clearly distinguish:

- Rejected rows encountered
- Rejected rows retained

Suggested statistics:

```python
rows_rejected
rows_rejected_retained
```

---

# QueryOutcome vs QueryResult

Internally, RowGuard may distinguish between:

```python
QueryOutcome[T]
```

and:

```python
QueryResult[T]
```

`QueryOutcome` could represent mutable in-progress execution state, while
`QueryResult` is the immutable public object assembled after completion.

This prevents partially constructed public results.

---

# Streaming Results

Streaming requires a separate abstraction because the complete result is not
known upfront.

Suggested type:

```python
StreamResult[T]
```

Possible API:

```python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
    statistics = stream.statistics
```

`StreamResult` should not pretend to be a complete `QueryResult`.

After a stream is exhausted, it may expose:

- Final statistics
- Retained rejected rows
- Diagnostics

---

# Async Results

Buffered async execution should return the same `QueryResult[T]` type as
synchronous execution.

Example:

```python
result = await rowguard.aselect(...)
```

This keeps result handling consistent across sync and async APIs.

Async streaming should use a separate `AsyncStreamResult[T]`.

---

# Serialization

The result object itself should not automatically serialize SQLAlchemy
statements, raw rows, or Pydantic errors.

Optional export helpers may provide:

```python
result.model_dump()
result.to_dict()
result.to_json()
```

However, serialization must be explicit because rejected rows may contain:

- Sensitive values
- Non-JSON-native database types
- Large payloads
- SQLAlchemy objects

Recommended default export shape:

```python
{
    "models": [...],
    "rejections": [...],
    "statistics": {...},
    "diagnostics": [...],
}
```

The executed statement should be omitted unless explicitly requested.

---

# Memory Behavior

Buffered results retain valid models and, depending on policy, rejected rows.

For large datasets, users should prefer streaming.

The result object should avoid retaining duplicate representations of data unless
needed for diagnostics.

Potential options:

```python
retain_raw_rows=False
retain_adapted_rows=True
retain_validation_input=False
```

These should be configured during execution, not mutated afterward.

---

# Type Safety

`QueryResult[T]` should preserve the target model type for static type checkers.

Example:

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)

reveal_type(result)         # QueryResult[UserRead]
reveal_type(result.models)  # tuple[UserRead, ...]
```

Public APIs should use generics consistently.

---

# Equality and Hashing

`QueryResult` should not be hashable by default because it may contain:

- SQLAlchemy statement objects
- Unhashable diagnostics
- Complex rejected-row payloads

Structural equality may be useful in tests, but statement identity can make
equality surprising.

Recommended approach:

- Dataclass equality may be disabled.
- Tests compare explicit fields.
- Dedicated snapshot helpers may be added later.

---

# RejectedRow Structure

Suggested model:

```python
@dataclass(frozen=True, slots=True)
class RejectedRow:
    index: int
    raw_row: object | None
    mapping: Mapping[str, object] | None
    validation_error: ValidationError | None
    adaptation_error: Exception | None
    model: type[BaseModel]
    diagnostics: tuple[Diagnostic, ...]
```

A rejected item may originate from either:

- Row adaptation failure
- Pydantic validation failure
- Reject-handler failure, if safely recoverable

The rejection reason should therefore be explicit.

---

# Diagnostic Structure

Suggested base model:

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity
    metadata: Mapping[str, object]
```

Diagnostic codes should be stable enough for programmatic use.

Examples:

```text
sqlrules.constraint_skipped
adapter.alias_applied
validation.row_rejected
rejection.row_quarantined
```

---

# Partial Results

Buffered APIs should not return partial results after unrecoverable execution
errors unless the user explicitly opts into partial-result behavior.

Possible future option:

```python
on_execution_error="raise"
on_execution_error="return_partial"
```

If partial results are supported, the result must expose:

```python
result.complete
result.execution_error
```

This is deferred beyond the MVP because partial query semantics can be subtle.

---

# Result Invariants

Every completed `QueryResult` must satisfy:

```python
statistics.rows_valid == len(models)
```

When all rejected rows are retained:

```python
statistics.rows_rejected == len(rejected)
```

Always:

```python
statistics.rows_read >= statistics.rows_valid
statistics.rows_read >= statistics.rows_rejected
statistics.rows_valid + statistics.rows_rejected == statistics.rows_classified
```

Additional states such as adaptation failures should be counted explicitly
rather than hidden.

---

# Error Handling

Constructing an inconsistent result should raise an internal error.

Suggested exception:

```python
ResultAssemblyError
```

Examples:

- Negative statistics
- Valid count differs from model count
- Retained rejection count exceeds total rejection count
- Missing required statement metadata

These failures indicate a RowGuard bug or invalid plugin behavior.

---

# Extension Points

Future result plugins may provide:

- Pandas export
- Polars export
- Metrics export
- Audit-record generation
- JSON-safe serialization
- Quarantine summaries
- Web framework response adapters

Plugins should consume the immutable result rather than mutate it.

---

# Testing Requirements

Tests should cover:

- Generic typing
- Immutability
- Convenience properties
- Iteration
- Length and indexing
- Clean results
- Mixed valid and rejected rows
- All-rejected results
- Statistics invariants
- Rejection retention policies
- Serialization helpers
- Statement preservation
- Sync/async parity
- Streaming finalization behavior

---

# MVP Scope

The initial release should implement:

- `QueryResult[T]`
- `RejectedRow`
- `QueryStatistics`
- Structured diagnostics
- Validated models
- Retained rejections for `collect`
- Statement preservation
- Basic convenience properties
- Immutable public objects

Deferred:

- Partial results
- Automatic JSON serialization
- DataFrame exporters
- Rich report rendering
- Result pagination
- Result persistence

---

# Design Principles

- Make accepted and rejected rows equally visible.
- Preserve strong generic typing.
- Keep public results immutable.
- Separate buffered and streaming abstractions.
- Record what happened, not just what succeeded.
- Avoid hidden serialization or data retention.
- Enforce result invariants during assembly.
