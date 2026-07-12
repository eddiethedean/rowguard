# REJECTION_HANDLING.md

:::{admonition} Design notes — prefer the user guide
:class: tip

Shipped policies: `raise`, `collect`, `skip`, `log`, `callback`, `quarantine`.
See [Rejection policies](../guides/rejection-policies.md). This page retains
longer design history; defer to the guide for the supported 0.6 surface.
:::

# RowGuard Rejection Handling

## Purpose

Rejection handling is one of RowGuard's defining features.

Unlike traditional query libraries that either raise immediately or silently
discard invalid data, RowGuard treats rejected rows as first-class outcomes.

Every processed row must end in exactly one state:

1. Accepted as a validated Pydantic model.
2. Rejected according to an explicit rejection policy.

No row should disappear without an intentional policy deciding its fate.

---

# Philosophy

Validation failures are expected in many real-world systems:

- Legacy databases
- ETL pipelines
- Shared databases
- Manual data corrections
- Partial migrations
- Corrupted records

A validation failure is information, not merely an exception.

Applications should decide what to do with that information.

---

# Pipeline Position

```text
Database
    │
    ▼
Row Adapter
    │
    ▼
Validation Engine
    │
    ├── Accepted
    └── Rejected
           │
           ▼
    Reject Handler
           │
           ▼
      QueryResult
```

The Reject Handler never performs validation. It only responds to failures.

---

# Rejection Policies

## raise

Stop processing immediately.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="raise",
)
```

Characteristics:

- Fail fast
- No partial buffered results
- Best for transactional applications

---

## collect

Store rejected rows inside the result.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

Use cases:

- Reporting
- Data quality audits
- ETL review
- Interactive inspection

---

## skip

Discard rejected rows while continuing execution.

Statistics must still record:

- rows rejected
- rejection rate

Useful when occasional invalid rows are acceptable.

---

## log

Log each rejection through a configured logger.

The logger should receive structured information rather than formatted strings.

Suggested payload:

- row index
- model
- error type
- validation errors
- diagnostics

---

## callback

Invoke a user-supplied callback.

```python
def handler(rejected):
    ...

result = rowguard.select(
    ...,
    on_reject="callback",
    reject_handler=handler,
)
```

The callback should receive a `RejectedRow`.

---

## quarantine

Persist rejected rows outside the query result.

Possible targets:

- database table
- object storage
- message queue
- audit service

The query result may retain lightweight references instead of full payloads.

---

# RejectedRow

Every rejection should preserve as much context as possible.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class RejectedRow:
    index: int
    raw_row: object | None
    mapping: Mapping[str, object] | None
    model: type[BaseModel]
    validation_error: ValidationError | None
    adaptation_error: Exception | None
    diagnostics: tuple[Diagnostic, ...]
```

Exactly one primary rejection reason should be present.

---

# Classification

Rejected rows should be classified.

Suggested categories:

- adaptation_error
- validation_error
- callback_error
- quarantine_error
- unknown

Classification improves reporting and observability.

---

# Reject Handler Interface

```python
class RejectHandler(Protocol):
    def handle(
        self,
        rejected: RejectedRow,
        context: RejectContext,
    ) -> RejectDecision:
        ...
```

The handler should not mutate the rejected row.

---

# Reject Decision

Internal handlers may return:

```python
class RejectDecision(Enum):
    CONTINUE = auto()
    STOP = auto()
    RETAIN = auto()
    DROP = auto()
```

This separates policy decisions from execution logic.

---

# Reject Context

Suggested fields:

- execution plan
- query statistics
- rejection count
- logger
- diagnostics configuration

The context should be immutable.

---

# Handler Failures

Reject handlers may themselves fail.

Strategies:

```python
on_handler_error="raise"
on_handler_error="log"
on_handler_error="ignore"
```

Recommended default:

```python
raise
```

A failed reject handler should never silently hide the original rejection.

---

# Ordering

Rejected rows should preserve query order.

If row 17 fails validation, it should remain row 17 in diagnostics.

Streaming execution must preserve ordering as well.

---

# Statistics

Track:

- rows_rejected
- rows_retained
- rows_skipped
- callback_failures
- quarantine_failures
- rejection_time

---

# Diagnostics

Each rejection may include:

- SQL statement
- SQLRules pushdown summary
- field mapping
- validation locations
- execution timing

Diagnostics should be configurable to reduce memory usage.

---

# Security

Rejected rows may contain sensitive information.

Applications should control:

- raw row retention
- value redaction
- serialization
- logging

Sensitive values should never be logged automatically.

---

# Streaming

Streaming policies behave differently.

Examples:

## raise

Stop iteration immediately.

## collect

Retain rejected rows until the stream closes.

## callback

Invoke callback while continuing iteration.

Streaming should never require retaining all valid models in memory.

---

# Async

Async reject handlers are planned.

Possible API:

```python
async def handler(rejected):
    ...
```

The async API should mirror synchronous semantics.

---

# Plugin Support

Future plugins may provide:

- quarantine providers
- audit sinks
- metrics exporters
- notification systems

Plugins should implement the public RejectHandler protocol.

---

# Error Hierarchy

```text
RowGuardError
└── RejectHandlerError
    ├── CallbackError
    ├── QuarantineError
    └── RejectConfigurationError
```

Validation failures themselves are not RejectHandlerError instances.

---

# Testing Requirements

Test:

- every rejection policy
- handler failures
- ordering
- statistics
- diagnostics
- streaming behavior
- async parity
- quarantine integrations
- callback exceptions

---

# MVP Scope

Initial release:

- raise
- collect
- skip
- callback
- structured RejectedRow
- rejection statistics

Deferred:

- quarantine providers
- async handlers
- distributed rejection sinks
- retry workflows

---

# Design Principles

- Every row is classified.
- Rejections are observable.
- Policies are explicit.
- Preserve original validation information.
- Never silently discard failures.
- Keep rejection handling independent from validation.
