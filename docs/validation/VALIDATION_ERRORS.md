# VALIDATION_ERRORS.md

:::{admonition} Design notes
:class: tip

See the [error catalog](../reference/errors.md) for shipped exceptions including
`CallbackError`, `QuarantineError`, and `RejectionThresholdError` (0.6.0).
:::

# RowGuard Validation Errors

## Purpose

Validation errors are first-class outcomes in RowGuard.

A database row that fails Pydantic validation should produce structured,
actionable information that can be:

- Raised
- Collected
- Logged
- Counted
- Quarantined
- Inspected
- Serialized safely
- Used in repair workflows

RowGuard must preserve Pydantic's original validation details while adding the
database and query context needed to understand where the invalid row came from.

---

# Core Principle

> A validation error should explain both **why the model rejected the input** and
> **which database row produced that input**.

Pydantic provides the validation semantics.

RowGuard adds execution context.

---

# Position in the Pipeline

```text
Database Row
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ├── Accepted Model
      └── ValidationError
              │
              ▼
     RowGuard Error Context
              │
              ▼
       Rejection Policy
```

Ordinary Pydantic validation failures are expected data-quality outcomes, not
necessarily system failures.

---

# Error Categories

RowGuard should distinguish several classes of failure.

## Validation Failure

Pydantic received a valid input shape but rejected one or more values.

Examples:

- Invalid integer
- Missing required field
- Invalid enum value
- Failed custom validator
- Cross-field invariant failure

## Adaptation Failure

RowGuard could not construct an unambiguous Pydantic input.

Examples:

- Duplicate result keys
- Unsupported row type
- Missing field mapping
- Ambiguous ORM entity shape

## Validation Engine Failure

An unexpected error occurred while invoking validation.

Examples:

- A custom validator raised an unexpected exception
- Misconfigured validation context
- Integration bug

## Reject Handler Failure

Validation failed normally, but the configured callback, logger, or quarantine
sink failed.

These categories should remain distinct in public diagnostics.

---

# Public Error Hierarchy

Suggested hierarchy:

```text
RowGuardError
├── ValidationEngineError
│   ├── InvalidValidationTargetError
│   ├── ValidationConfigurationError
│   ├── RowValidationError
│   └── UnexpectedValidationError
├── RowAdaptationError
└── RejectHandlerError
```

`RowValidationError` is used primarily by `on_reject="raise"`.

Collected rejections should normally use `RejectedRow` objects rather than
raising exceptions.

---

# RowValidationError

Suggested structure:

```python
@dataclass(slots=True)
class RowValidationError(RowGuardError):
    model: type[BaseModel]
    validation_error: ValidationError
    row_index: int | None
    mapping: Mapping[str, object] | None
    source_identity: SourceIdentity | None
    diagnostics: tuple[Diagnostic, ...]
```

The original Pydantic `ValidationError` must remain directly accessible.

Example:

```python
try:
    rowguard.select(..., on_reject="raise")
except RowValidationError as exc:
    print(exc.validation_error.errors())
    print(exc.row_index)
```

---

# RejectedRow Error Payload

Under collection-oriented policies, validation failures should be represented
inside `RejectedRow`.

Suggested fields:

```python
@dataclass(frozen=True, slots=True)
class RejectedRow:
    index: int
    model: type[BaseModel]
    mapping: Mapping[str, object] | None
    validation_error: ValidationError | None
    adaptation_error: Exception | None
    source_identity: SourceIdentity | None
    diagnostics: tuple[Diagnostic, ...]
```

Exactly one primary rejection cause should normally be present.

---

# Preserving Pydantic Errors

RowGuard should preserve:

- Error type
- Field location
- Message
- Context
- Input value, subject to redaction policy
- Error count
- Nested error paths
- Model-level errors
- Original exception object

RowGuard should not reduce all failures to a single string.

Structured data is necessary for:

- Programmatic routing
- Metrics
- UI rendering
- Data quality reports
- Repair systems
- Testing

---

# Error Locations

Pydantic error locations identify the failing field path.

Examples:

```python
("age",)
("address", "postal_code")
("items", 3, "price")
()
```

An empty location may represent a model-level error.

RowGuard should preserve locations exactly.

Potential helper:

```python
rejected.error_paths
```

Example output:

```python
[
    "address.postal_code",
    "items[3].price",
]
```

Formatted paths are conveniences only; tuple locations remain canonical.

---

# Error Codes

Pydantic provides stable error type identifiers.

Examples may include:

```text
int_parsing
missing
greater_than_equal
literal_error
value_error
```

RowGuard should preserve these identifiers.

They are useful for:

- Grouping failures
- Metrics
- Rejection routing
- Automated repair
- Alert thresholds

RowGuard-specific diagnostics should use a separate namespace.

Examples:

```text
validation.row_rejected
validation.missing_field
validation.model_error
```

---

# Error Messages

Human-readable messages should be concise and contextual.

Example:

```text
Row 42 failed validation for UserRead:
age: Input should be greater than or equal to 18
```

The message is not the canonical machine-readable representation.

Applications should use structured error fields for logic.

---

# Model-Level Errors

Model validators may produce errors without a specific field.

Example:

```python
@model_validator(mode="after")
def validate_dates(self):
    if self.ends_at <= self.starts_at:
        raise ValueError("ends_at must be after starts_at")
    return self
```

RowGuard should preserve:

- Empty or model-level location
- Original message
- Input mapping
- Source identity

It should not invent a field assignment.

---

# Multiple Errors per Row

One row may produce multiple validation errors.

Example:

```python
[
    {"loc": ("age",), "type": "int_parsing", ...},
    {"loc": ("email",), "type": "value_error", ...},
]
```

RowGuard should treat the row as one rejection with multiple errors.

Statistics may track both:

- Rejected row count
- Validation error count

These are different metrics.

---

# Source Identity

A rejection is more useful when it can be traced back to the database.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source_name: str | None
    primary_key: tuple[object, ...] | None
    row_number: int | None
    partition: str | None
```

Examples:

- Table name and primary key
- ORM mapper and identity tuple
- Stream sequence number
- Raw SQL row number
- External partition identifier

Source identity should avoid retaining full ORM entities by default.

---

# Row Index

Every processed row should receive a stable sequence index.

Recommended behavior:

- Zero-based internally
- Clearly documented
- Preserved through streaming
- Included in diagnostics
- Independent of database primary key

A row index is not a database identity, but it helps reproduce execution order.

---

# Statement Context

Validation error context may include:

- Statement identity
- Source table or entity
- Query plan identifier
- Pushdown mode
- Rejection policy
- Dialect
- Selected result keys

The full rendered SQL string should not be included by default.

Bound parameter values should not be included by default.

---

# Redaction

Validation errors may include sensitive data.

RowGuard should support explicit policies:

```python
error_values="preserve"
error_values="redact"
error_values="omit"
```

## preserve

Keep original invalid values in diagnostics and retained error structures.

Best for controlled debugging and local data quality work.

## redact

Replace sensitive values with a marker.

Example:

```python
"<redacted>"
```

## omit

Exclude values entirely.

Recommended for high-security environments.

---

# Field-Level Redaction

Applications may need different policies per field.

Potential API:

```python
redact_fields={
    "password_hash",
    "access_token",
    "ssn",
}
```

Future pattern support:

```python
redact_paths=[
    "credentials.*",
    "payment.card_number",
]
```

Redaction affects retained and serialized diagnostics, not Pydantic validation
input.

---

# Raw Row Retention

Rejected rows may optionally retain:

- Raw SQLAlchemy row
- Adapted mapping
- Both
- Neither

Potential options:

```python
retain_raw_rows=False
retain_adapted_rows=True
```

Recommended default:

- Retain adapted mapping for `collect`
- Avoid retaining raw ORM entities
- Allow privacy-sensitive applications to disable both

Statistics and source identity should still remain available.

---

# Raise Policy

With:

```python
on_reject="raise"
```

RowGuard stops at the first rejected row and raises `RowValidationError`.

The exception should include:

- Original Pydantic error
- Row index
- Source identity
- Adapted mapping according to retention/redaction policy
- Target model
- Execution diagnostics

No completed `QueryResult` is returned unless partial-result behavior is
explicitly enabled in a future release.

---

# Collect Policy

With:

```python
on_reject="collect"
```

RowGuard stores a `RejectedRow`.

Example:

```python
result = rowguard.select(
    ...,
    on_reject="collect",
)

for rejected in result.rejected:
    print(rejected.validation_error.errors())
```

The query continues unless a configured rejection threshold is exceeded.

---

# Skip Policy

With:

```python
on_reject="skip"
```

RowGuard does not retain the full rejection by default.

It must still record:

- Rejected row count
- Error count
- Optional aggregated error codes
- Optional diagnostics

Skip must never mean "pretend the row was valid."

---

# Callback Policy

With:

```python
on_reject="callback"
```

The callback receives structured rejection data.

```python
def handle_rejection(rejected: RejectedRow) -> None:
    ...
```

The callback should not receive a preformatted message as its only input.

Callback errors are separate from validation errors.

---

# Quarantine Policy

Quarantine handlers may serialize validation errors for storage.

Recommended payload:

```python
{
    "source": {...},
    "model": "UserRead",
    "row_index": 42,
    "mapping": {...},
    "errors": [...],
    "diagnostics": [...],
}
```

Serialization must respect redaction and retention policies.

The original Pydantic error may not be directly serializable, so structured
`errors()` output is appropriate for persistence.

---

# Logging

Logging should use structured records.

Suggested fields:

```text
event=validation.row_rejected
model=UserRead
row_index=42
source_table=users
primary_key=123
error_count=2
error_codes=["int_parsing", "value_error"]
```

Raw values and full row mappings should not be logged by default.

---

# Error Aggregation

RowGuard may aggregate failures across a result.

Useful summaries:

- Rejections by model
- Rejections by field path
- Rejections by Pydantic error type
- Rejections by source table
- Rejections by partition
- Rejections over time

Example:

```python
result.statistics.validation_errors_by_type
```

High-cardinality values must not be used as metric labels.

---

# Validation Error Statistics

Suggested counters:

```text
rows_rejected
validation_errors_total
validation_errors_by_type
validation_errors_by_field
model_level_errors
adaptation_errors
unexpected_validation_errors
```

One row may increment multiple error-type counters.

---

# Rejection Thresholds

Future execution policies may stop processing after:

```python
max_rejections=100
max_rejection_rate=0.05
max_errors=250
```

Threshold exceptions should include summary statistics and the last rejection.

Threshold handling belongs to execution policy, not Pydantic.

---

# Unexpected Validator Exceptions

Custom validators may raise unexpected exceptions.

Examples:

- Network error
- Database error
- `KeyError`
- `RuntimeError`
- External service timeout

These should not automatically be treated as ordinary invalid data.

Recommended default:

```python
on_unexpected_validation_error="raise"
```

Optional future policies:

```python
"reject"
"log_and_raise"
```

The original exception must remain available as the cause.

---

# Adaptation Errors vs Validation Errors

Example adaptation failure:

```text
Two selected columns are both named "id".
```

Pydantic never received an input.

Example validation failure:

```text
The "age" key exists, but its value is invalid.
```

These should produce different error categories and metrics.

This distinction is critical for diagnosing:

- Bad data
- Bad query shapes
- Bad RowGuard configuration

---

# Missing Fields

A missing required field should generally be reported by Pydantic.

Example:

```python
{"name": "Ada"}
```

Target:

```python
class UserRead(BaseModel):
    id: int
    name: str
```

Pydantic produces a `missing` error for `id`.

If the field mapping itself references a nonexistent result key and planning
could have detected it, RowGuard may raise a planning or adaptation error
earlier.

---

# Extra Fields

Models configured with `extra="forbid"` may reject extra result columns.

This is a normal validation error.

RowGuard should not remove extra columns unless an explicit projection or
adapter policy requests it.

This preserves the model's intended contract.

---

# Nested Errors

Nested model errors may contain deep paths.

Example:

```text
address.postal_code
orders[2].total
```

RowGuard must preserve full location tuples.

Summary helpers may group errors by:

- Top-level field
- Full path
- Error type

---

# Union Errors

Union validation may produce multiple branch errors.

RowGuard should preserve the complete Pydantic error structure.

It should not select one branch error as "the real error" unless Pydantic does
so.

---

# Contextual Validation Errors

Validation context may affect error outcomes.

Rejected rows should record:

- Whether context was supplied
- A context identifier when appropriate
- Not necessarily the full context mapping

Sensitive context values should not be copied into every rejection.

Potential approach:

```python
validation_context_id="policy-2026-07"
```

---

# Error Serialization

Suggested public helper:

```python
rejected.to_dict(
    include_values=False,
    include_diagnostics=True,
)
```

Potential output:

```python
{
    "model": "UserRead",
    "row_index": 42,
    "source_identity": {
        "table": "users",
        "primary_key": [123],
    },
    "errors": [
        {
            "type": "greater_than_equal",
            "loc": ["age"],
            "msg": "Input should be greater than or equal to 18",
        }
    ],
}
```

Serialization should be deterministic.

---

# JSON Serialization

Potential helper:

```python
rejected.to_json()
```

Requirements:

- Respect redaction policy
- Convert tuples to lists
- Serialize model and source names safely
- Avoid arbitrary object repr leakage
- Handle non-JSON input values conservatively
- Omit raw SQLAlchemy objects by default

---

# Exception String Representation

`str(RowValidationError)` should be useful without being overly verbose.

Example:

```text
Row 42 from users (primary key: 123) failed validation for UserRead with 2 errors.
```

Detailed errors remain accessible through structured properties.

---

# Equality and Testing

Error objects containing exceptions and raw database values may not have useful
general equality semantics.

Tests should compare:

- Error types
- Locations
- Messages
- Source identity
- Row index
- Redacted mapping
- Diagnostic codes

Snapshot helpers may normalize error structures for stable testing.

---

# Diagnostics

Suggested diagnostics:

```text
validation.started
validation.accepted
validation.rejected
validation.error_redacted
validation.unexpected_exception
rejection.threshold_exceeded
```

Diagnostics should use stable codes.

Messages may evolve, but codes should remain suitable for programmatic use.

---

# Observability

Validation errors should integrate with:

- Structured logging
- Metrics
- Tracing
- Data quality dashboards
- Quarantine reports

Potential trace attributes:

```text
rowguard.model
rowguard.row_index
rowguard.rejected
rowguard.error_count
rowguard.source
```

Do not attach raw row values to traces by default.

---

# Privacy and Compliance

Rejected rows can be more sensitive than accepted models because they may
contain malformed or unexpected data.

Applications should define:

- Retention period
- Access controls
- Encryption
- Redaction
- Quarantine destination
- Deletion policy
- Audit requirements

RowGuard should make safe configuration possible but cannot determine an
application's compliance obligations.

---

# Streaming Errors

In streaming mode:

- Row indices remain monotonic.
- `raise` stops iteration immediately.
- `collect` retains errors until stream close.
- `skip` records aggregate statistics.
- Callback/quarantine handlers run before the next row is yielded.
- Resource cleanup must occur if an error stops the stream.

Final stream statistics should remain available when practical.

---

# Async Errors

Async APIs should expose the same validation error structures.

Async-specific differences apply only to:

- Query I/O
- Async callbacks
- Async quarantine sinks
- Cancellation

Pydantic validation errors themselves are identical.

Cancellation must not misclassify an in-progress row as a validation rejection.

---

# Repair Integration

A future repair workflow may use validation errors to decide how to transform a
row.

Example:

```python
def repair(rejected: RejectedRow) -> Mapping[str, object] | None:
    ...
```

Repair systems may inspect:

- Error codes
- Field locations
- Source identity
- Original mapping

After repair, Pydantic validation must run again.

The original error should remain part of the audit trail.

---

# API Examples

## Raise on First Error

```python
try:
    rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="raise",
    )
except RowValidationError as exc:
    for error in exc.validation_error.errors():
        print(error["loc"], error["type"])
```

## Collect Errors

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)

for rejected in result.rejected:
    print(rejected.source_identity)
    print(rejected.validation_error.errors())
```

## Redacted Errors

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    error_values="redact",
)
```

## Aggregate by Error Type

```python
counts = result.statistics.validation_errors_by_type
```

---

# Error Invariants

Every validation rejection must satisfy:

- A target model is recorded.
- A stable row index is recorded when rows are ordered.
- The original Pydantic error is retained internally unless policy forbids
  retaining it.
- Accepted models are never included in rejected results.
- Rejected rows are counted exactly once.
- Multiple field errors do not multiply the rejected-row count.
- Redaction never changes the validation decision.
- Serialization never mutates the stored error.

---

# Testing Requirements

Tests should cover:

- Single field error
- Multiple field errors
- Missing field
- Extra field
- Model-level error
- Nested error paths
- Union errors
- Alias-based errors
- Strict-mode errors
- Custom validator errors
- Unexpected validator exceptions
- Mapping vs adaptation failures
- Raise policy
- Collect policy
- Skip policy
- Callback policy
- Quarantine serialization
- Row index preservation
- Source identity
- Redaction
- Omission
- Structured logging payloads
- Aggregated statistics
- Threshold behavior
- Streaming cleanup
- Async parity
- JSON serialization
- Sensitive and non-JSON values

---

# MVP Scope

The first RowGuard release should implement:

- `RowValidationError`
- `RejectedRow`
- Complete Pydantic `ValidationError` preservation
- Stable row indices
- Basic source identity
- `raise`, `collect`, and `skip` behavior
- Structured error lists
- Redaction and omission policies
- Validation error statistics
- Nested error locations
- Clear distinction between adaptation and validation failures
- Streaming-compatible rejection records
- Sync/async error parity

Deferred:

- Rich repair routing
- Distributed quarantine schemas
- Persistent rejection stores
- Advanced field-pattern redaction
- Error dashboards
- Trace exporters
- Partial buffered results after failure
- Automated remediation recommendations
- Cross-run rejection deduplication

---

# Design Principles

- Validation errors are data, not just messages.
- Preserve Pydantic's original structure.
- Add source and execution context without hiding the cause.
- Keep bad data separate from bad query configuration.
- Count rejected rows and validation errors separately.
- Redact explicitly and safely.
- Never log raw sensitive values by default.
- Keep sync, async, buffered, and streaming semantics aligned.
- Make every rejected row traceable.
- Ensure errors are useful to both humans and programs.
