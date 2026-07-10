# DIAGNOSTICS.md

# RowGuard Rejection Diagnostics

## Purpose

Diagnostics provide structured, machine-readable information about rejection
handling without changing validation behavior. They are intended for debugging,
observability, auditing, metrics, tracing, and performance analysis.

Unlike exceptions, diagnostics describe **what happened**, not merely **what
failed**.

---

# Design Principles

- Diagnostics are structured, not formatted strings.
- Diagnostic generation must never change execution results.
- Stable diagnostic codes are preferred over human-readable messages.
- Sensitive values must respect redaction policies.
- Sync, async, buffered, and streaming execution expose equivalent diagnostics.

---

# Lifecycle

```text
Rejected Row
      │
      ▼
Rejection Policy
      │
      ▼
Diagnostics
      │
      ├── Metrics
      ├── Logs
      ├── Traces
      ├── QueryResult
      └── Quarantine
```

---

# Diagnostic Event

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: Literal["debug", "info", "warning", "error"]
    timestamp: datetime
    execution_id: str
    row_index: int | None
    metadata: Mapping[str, object]
```

Diagnostics should be immutable.

---

# Standard Diagnostic Codes

Validation:

- validation.started
- validation.accepted
- validation.rejected
- validation.unexpected_exception

Rejection:

- rejection.raise
- rejection.collect
- rejection.skip
- rejection.callback
- rejection.quarantine
- rejection.threshold_exceeded

Callbacks:

- callback.started
- callback.completed
- callback.failed

Quarantine:

- quarantine.write_started
- quarantine.write_succeeded
- quarantine.write_failed

Streaming:

- stream.started
- stream.completed
- stream.cancelled

---

# Severity

Suggested mapping:

| Severity | Meaning |
| --- | --- |
| debug | Internal execution detail |
| info | Normal lifecycle event |
| warning | Recoverable rejection |
| error | Execution failure |

---

# Metrics

Recommended counters:

- rows_processed
- rows_accepted
- rows_rejected
- callback_failures
- quarantine_failures
- rejection_rate

Recommended timers:

- validation_duration
- callback_duration
- quarantine_duration
- total_execution_duration

Avoid high-cardinality metric labels.

---

# Logging

Diagnostics should support structured logging.

Example:

```json
{
  "event": "validation.rejected",
  "model": "UserRead",
  "row_index": 42,
  "error_count": 2
}
```

Raw row values should not be logged by default.

---

# Tracing

Suggested trace attributes:

- rowguard.execution_id
- rowguard.model
- rowguard.rejection_policy
- rowguard.rows_processed
- rowguard.rows_rejected

Tracing should avoid embedding rejected payloads.

---

# QueryResult Integration

QueryResult may expose:

```python
result.diagnostics
```

Applications can inspect:

- warnings
- policy changes
- callback timings
- rejection summaries

Diagnostics are supplemental and should not replace statistics.

---

# Streaming

Streaming diagnostics should be emitted incrementally.

Events should preserve processing order.

Closing a stream should emit a final completion or cancellation event.

---

# Async

Async execution should produce the same diagnostic events and codes as
synchronous execution.

---

# Privacy

Diagnostics must obey:

- row retention settings
- redaction policies
- metadata-only modes

Sensitive values should never appear unless explicitly configured.

---

# Testing

Tests should verify:

- stable diagnostic codes
- ordering
- timestamps
- severity
- callback diagnostics
- quarantine diagnostics
- streaming diagnostics
- async parity
- redaction

---

# MVP Scope

Initial implementation:

- immutable Diagnostic objects
- stable event codes
- execution IDs
- row indices
- structured metadata
- QueryResult diagnostics
- logging integration
- metrics integration

Deferred:

- OpenTelemetry exporters
- live dashboards
- external diagnostic plugins
- distributed tracing helpers

---

# Design Principles

- Diagnostics are observable facts.
- Stable codes are part of the public API.
- Diagnostics never change execution behavior.
- Privacy is enforced before emission.
- Every rejection should be explainable through structured events.
