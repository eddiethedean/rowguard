# CALLBACKS.md

# RowGuard Rejection Callbacks

## Purpose

Callbacks allow applications to run custom logic whenever RowGuard rejects a
row.

A callback may:

- Record the rejection.
- Emit metrics.
- Notify another system.
- Route the row to a custom sink.
- Attempt repair.
- Trigger application-specific workflows.

Callbacks must not alter RowGuard's core validation decision. A row is rejected
before the callback runs.

---

# Core Principle

```text
Row Adapter
      │
      ▼
Pydantic Validation
      │
      └── RejectedRow
              │
              ▼
          Callback
              │
              ▼
      Continue / Stop / Retain
```

The callback responds to a rejection. It does not decide whether validation
succeeded.

---

# Goals

The callback system should:

- Pass structured rejection data.
- Preserve deterministic execution order.
- Support synchronous and asynchronous handlers.
- Define clear failure behavior.
- Respect privacy and redaction settings.
- Avoid hidden transaction side effects.
- Remain compatible with buffered and streaming execution.
- Provide enough context for observability and routing.

---

# Non-Goals

Callbacks should not:

- Replace Pydantic validation.
- Rewrite SQL statements.
- Mutate RowGuard's execution plan.
- Silently mark rejected rows as valid.
- Automatically write repairs to the source database.
- Receive raw database sessions unless explicitly enabled.
- Trigger implicit retries.
- Hide callback failures.

---

# Callback Interface

Recommended synchronous protocol:

```python
class RejectionCallback(Protocol):
    def __call__(
        self,
        rejected: RejectedRow,
        context: CallbackContext,
    ) -> CallbackDecision | None:
        ...
```

Recommended asynchronous protocol:

```python
class AsyncRejectionCallback(Protocol):
    async def __call__(
        self,
        rejected: RejectedRow,
        context: CallbackContext,
    ) -> CallbackDecision | None:
        ...
```

Returning `None` is equivalent to the default continue behavior.

---

# RejectedRow Input

The callback receives a structured `RejectedRow`.

Typical fields:

```python
rejected.index
rejected.model
rejected.mapping
rejected.validation_error
rejected.adaptation_error
rejected.source_identity
rejected.diagnostics
```

The exact retained payload depends on:

- Redaction policy.
- Raw-row retention.
- Adapted-row retention.
- Source type.
- Security configuration.

Callbacks must not assume every field is present.

---

# CallbackContext

Suggested immutable structure:

```python
@dataclass(frozen=True, slots=True)
class CallbackContext:
    execution_id: str
    model: type[BaseModel]
    statement: object | None
    source_name: str | None
    rejection_count: int
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    metadata: Mapping[str, object]
```

Optional context may include:

- Dialect name.
- Pushdown summary.
- Stream state.
- Partition identifier.
- Request identifier.
- Validation-context identifier.

Sensitive values should not be included automatically.

---

# Callback Decisions

A callback may return a structured decision.

Suggested enum:

```python
class CallbackDecision(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    RETAIN = "retain"
    DROP = "drop"
```

## CONTINUE

Continue processing with the normal rejection policy.

## STOP

Stop execution after the current rejection.

Buffered execution raises a callback-stop exception or returns a partial result
only when partial-result behavior is explicitly enabled.

Streaming execution closes the stream and releases resources.

## RETAIN

Ensure the rejected row is retained in the result or stream summary.

## DROP

Do not retain the rejected row after the callback completes.

`DROP` affects retention only. Statistics must still count the rejection.

---

# Default Behavior

Recommended default:

```python
CallbackDecision.CONTINUE
```

The callback should not need to return anything for the common case.

Example:

```python
def record_rejection(
    rejected: RejectedRow,
    context: CallbackContext,
) -> None:
    metrics.increment(
        "rowguard.rejected",
        tags={"model": rejected.model.__name__},
    )
```

---

# Public API

Example:

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="callback",
    reject_callback=record_rejection,
)
```

Alternative policy object:

```python
result = rowguard.select(
    ...,
    rejection_policy=CallbackPolicy(record_rejection),
)
```

The policy-object form is preferred internally because it avoids expanding the
top-level API indefinitely.

---

# Callback Ordering

Callbacks must execute in row-processing order.

If rows 3, 8, and 10 are rejected, callbacks run in this order:

```text
3 → 8 → 10
```

This guarantee applies to:

- Buffered execution.
- Streaming execution.
- Synchronous execution.
- Asynchronous execution, unless explicit concurrent callback mode is enabled.

Concurrent callback execution should be opt-in because it can reorder side
effects.

---

# Callback Timing

The callback runs after RowGuard has:

1. Adapted the row.
2. Attempted Pydantic validation.
3. Created the `RejectedRow`.
4. Updated basic rejection counters.

The callback runs before:

- The next streaming row is yielded.
- The rejected row is finalized for retention.
- Threshold checks that depend on callback decisions, when documented.

The exact ordering should remain stable across releases.

---

# Buffered Execution

In buffered mode, callbacks run as rows are processed.

RowGuard should not wait until the entire result set is validated before invoking
callbacks.

Benefits:

- Lower rejection latency.
- Early side effects.
- Consistency with streaming.
- Immediate callback failure handling.

---

# Streaming Execution

In streaming mode, the callback runs before RowGuard advances to the next row.

```python
with rowguard.stream(
    ...,
    rejection_policy=CallbackPolicy(record_rejection),
) as stream:
    for model in stream:
        process(model)
```

If the callback blocks, stream progress blocks.

Users should keep synchronous callbacks fast.

---

# Async Callbacks

Async APIs should support async callbacks.

```python
async def record_rejection(
    rejected: RejectedRow,
    context: CallbackContext,
) -> None:
    await sink.write(rejected)
```

Example:

```python
result = await rowguard.aselect(
    ...,
    rejection_policy=AsyncCallbackPolicy(record_rejection),
)
```

An async RowGuard API may also accept a synchronous callback, but behavior must
be explicit.

Recommended:

- Sync callback in sync execution.
- Async callback in async execution.
- Sync callback allowed in async execution when it is known to be non-blocking.
- Async callback rejected in sync execution.

---

# Blocking Work

Callbacks that perform slow network or file I/O can reduce throughput.

Applications should consider:

- Async callbacks.
- Buffered queues.
- Batch sinks.
- External workers.
- Quarantine providers.
- Sampling.

RowGuard should not automatically create background tasks that outlive query
execution.

All callback work should complete or fail within the observable execution
lifecycle unless a user-supplied queue explicitly owns the handoff.

---

# Callback Failures

Callbacks may raise exceptions.

Suggested policies:

```python
on_callback_error="raise"
on_callback_error="log"
on_callback_error="continue"
on_callback_error="reject_handler"
```

## raise

Recommended default.

Stop processing and raise `CallbackError` with the original exception as the
cause.

## log

Record the callback failure and continue.

This should require explicit configuration because it can lose rejection-side
effects.

## continue

Continue without logging through RowGuard's logger.

This is the least observable mode and should be discouraged.

## reject_handler

Route callback failures to a dedicated secondary handler.

This is useful for dead-letter or alerting workflows.

---

# CallbackError

Suggested structure:

```python
@dataclass(slots=True)
class CallbackError(RejectHandlerError):
    rejected: RejectedRow
    callback: object
    original_error: Exception
    callback_index: int
```

The exception message should not include raw sensitive row values.

---

# Original Rejection Preservation

A callback failure must never erase the original validation rejection.

The resulting error should preserve both:

- The original `RejectedRow`.
- The callback exception.

This allows operators to distinguish bad data from broken callback infrastructure.

---

# Transactions

Callbacks may perform database writes.

This introduces transaction concerns.

Possible strategies:

```python
callback_transaction="none"
callback_transaction="same"
callback_transaction="separate"
callback_transaction="external"
```

## none

Callback receives no session or connection.

Recommended default.

## same

Callback uses the same session/transaction as the read query.

Risks:

- Rejection writes may affect the read transaction.
- Callback failure may poison the transaction.
- Lock duration may increase.
- Streaming semantics become more complex.

## separate

Callback receives or opens a separate transaction.

Safer for quarantine tables but requires explicit configuration.

## external

Callback writes to a non-database sink such as a queue or object store.

RowGuard should never silently inject the query session into callbacks.

---

# Session Access

Potential explicit context:

```python
callback_access="metadata_only"
callback_access="execution_context"
callback_access="session"
```

Recommended default:

```python
metadata_only
```

Passing a live session should require deliberate opt-in and clear documentation.

---

# Mutation

Callbacks should treat `RejectedRow` and `CallbackContext` as immutable.

They must not mutate:

- Adapted mappings.
- Diagnostics.
- Statistics.
- Execution plans.
- Source entities.
- Validation errors.

If a callback wants to propose a repair, it should return or submit a separate
repair object.

---

# Repair Callbacks

A future specialized callback may propose a repaired mapping.

Suggested protocol:

```python
class RepairCallback(Protocol):
    def __call__(
        self,
        rejected: RejectedRow,
        context: CallbackContext,
    ) -> Mapping[str, object] | None:
        ...
```

Safe flow:

```text
RejectedRow
    │
    ▼
Repair callback
    │
    ▼
Candidate repaired mapping
    │
    ▼
Pydantic revalidation
    │
    ├── Accepted repaired model
    └── Final rejection
```

Repair must be explicit and independently auditable.

---

# Retention Decisions

Callbacks may influence whether a rejected row is retained.

Example:

```python
def sample_large_rejections(
    rejected: RejectedRow,
    context: CallbackContext,
) -> CallbackDecision:
    if context.rejection_count <= 100:
        return CallbackDecision.RETAIN
    return CallbackDecision.DROP
```

Statistics must always record total rejections regardless of retention.

---

# Sampling

High-volume workloads may sample callback invocations.

Potential configuration:

```python
callback_sample_rate=0.01
```

Sampling must be deterministic when reproducibility is required.

Alternative:

```python
callback_every_n=100
```

RowGuard should distinguish:

- Rejections encountered.
- Callbacks invoked.
- Rejections retained.
- Rejections sampled out.

Sampling belongs to the callback policy, not validation.

---

# Batching

Future callback policies may batch rejected rows.

Example:

```python
BatchCallbackPolicy(
    callback=write_batch,
    batch_size=500,
)
```

Batching must define:

- Flush on completion.
- Flush on stream close.
- Flush on exception.
- Flush on cancellation.
- Maximum wait time.
- Partial-batch behavior.

The MVP should focus on per-row callbacks.

---

# Idempotency

Callbacks may be retried by application code or repair workflows.

Applications should design side effects to be idempotent when possible.

Useful identifiers:

- Execution ID.
- Source identity.
- Row index.
- Rejection fingerprint.
- Query plan ID.

RowGuard may expose a deterministic rejection identifier in a future release.

---

# Rejection Fingerprints

A future helper may compute a fingerprint from:

- Model name.
- Source identity.
- Error codes.
- Error locations.
- Validation-policy version.

Fingerprints help deduplicate:

- Alerts.
- Quarantine records.
- Metrics.
- Retry workflows.

Sensitive raw values should not be required to compute the fingerprint.

---

# Privacy and Redaction

Callbacks receive data after RowGuard applies configured retention and redaction
policies.

Potential modes:

```python
callback_values="full"
callback_values="redacted"
callback_values="metadata_only"
```

Recommended production default depends on the callback purpose.

Examples:

- Metrics callback: metadata only.
- Secure quarantine callback: full mapping.
- Logging callback: redacted.
- Alert callback: metadata and summary.

---

# Logging Callbacks

A logging callback should emit structured records.

Example:

```python
def log_rejection(
    rejected: RejectedRow,
    context: CallbackContext,
) -> None:
    logger.warning(
        "row rejected",
        extra={
            "event": "rowguard.validation.rejected",
            "model": rejected.model.__name__,
            "row_index": rejected.index,
            "error_codes": rejected.error_codes,
        },
    )
```

Raw input values should not be logged by default.

---

# Metrics Callbacks

Metrics callbacks should avoid high-cardinality labels.

Good labels:

- Model name.
- Error type.
- Source name.
- Policy name.

Bad labels:

- Primary key.
- Raw invalid value.
- Full error message.
- SQL string.
- Request ID as a metric label.

---

# Notification Callbacks

Notifications should usually aggregate rather than emit one message per row.

A per-row notification callback can overwhelm downstream systems.

Recommended pattern:

- Count rejections.
- Sample examples.
- Notify on thresholds.
- Produce a final summary.

---

# Quarantine Callbacks

A callback may hand rejected rows to a quarantine provider.

For large workloads, a dedicated `QuarantinePolicy` is preferable to a generic
callback because it can provide:

- Batching.
- Retry behavior.
- Schema versioning.
- Durable acknowledgments.
- Sink-specific diagnostics.
- Transaction policy.

Callbacks remain useful for custom or lightweight quarantine workflows.

---

# Callback Composition

Future versions may allow multiple callbacks.

Example:

```python
CompositeCallback(
    callbacks=[
        metrics_callback,
        logging_callback,
        quarantine_callback,
    ],
)
```

Composition must define:

- Execution order.
- Failure policy.
- Whether later callbacks run after an earlier failure.
- Decision precedence.
- Retention conflicts.

Recommended default order is declaration order.

---

# Decision Precedence

For composed callbacks, suggested precedence:

```text
STOP > RETAIN > DROP > CONTINUE
```

However, this should be explicit and configurable.

The MVP should support one callback per policy to avoid premature complexity.

---

# Diagnostics

Suggested callback diagnostics:

```text
callback.invoked
callback.completed
callback.failed
callback.stop_requested
callback.retention_changed
callback.sampled_out
callback.batch_flushed
```

Useful metadata:

- Callback name.
- Duration.
- Execution ID.
- Row index.
- Decision.
- Failure type.

Diagnostics should not include callback argument values by default.

---

# Statistics

Suggested metrics:

- Callbacks invoked.
- Callbacks completed.
- Callback failures.
- Callback time.
- Maximum callback time.
- Callback decisions by type.
- Rejections sampled out.
- Rejections retained by callback.
- Rejections dropped by callback.

Callback time should remain separate from validation time.

---

# Performance

Callbacks are on the rejection hot path.

Guidelines:

- Keep synchronous callbacks fast.
- Avoid expensive serialization unless needed.
- Prefer structured data over formatted text.
- Batch external writes when possible.
- Use async callbacks for async I/O.
- Avoid holding database locks during slow callbacks.
- Disable raw-row retention when not required.
- Measure callback throughput independently.

---

# Concurrency

Per-row callback execution should be sequential by default to preserve ordering
and simplify side effects.

Future opt-in concurrency:

```python
callback_concurrency=8
```

Concurrent mode must define:

- Ordering guarantees.
- Maximum in-flight callbacks.
- Backpressure.
- Cancellation.
- Error aggregation.
- Stream close behavior.
- Retention synchronization.

It should not be part of the initial release.

---

# Cancellation

When execution is cancelled:

- In-progress async callbacks should be cancelled according to normal asyncio
  semantics.
- Synchronous callbacks cannot be forcibly interrupted safely.
- Database resources must be released.
- Completed callback side effects remain completed.
- Partial callback batches must follow documented flush behavior.
- The current row must not be reported as accepted.

---

# Callback Registration

Callbacks should be supplied per execution or through an immutable configured
RowGuard client.

Per-query:

```python
rowguard.select(
    ...,
    rejection_policy=CallbackPolicy(callback),
)
```

Configured client:

```python
guard = RowGuard(
    default_rejection_policy=CallbackPolicy(callback),
)
```

Global mutable callback registries should be avoided.

---

# Plugin Integration

Third-party callback plugins may provide:

- Logging integrations.
- Metrics exporters.
- Message queues.
- Alerting systems.
- Audit services.
- Data catalogs.
- Quarantine storage.

Plugins should implement documented callback or rejection-policy protocols.

They should declare:

- Sync or async support.
- Data retention requirements.
- Transaction behavior.
- Idempotency guarantees.
- Batching behavior.
- Failure policy.

---

# Error Hierarchy

Suggested hierarchy:

```text
RowGuardError
└── RejectHandlerError
    ├── CallbackConfigurationError
    ├── CallbackError
    ├── AsyncCallbackRequiredError
    ├── CallbackDecisionError
    └── CallbackTransactionError
```

Validation errors remain separate.

---

# Security

Callback implementations may send rejected data outside the process.

RowGuard should make this risk explicit.

Applications must control:

- Destination.
- Authentication.
- Encryption.
- Redaction.
- Retention.
- Access control.
- Network policy.
- Compliance obligations.

A callback should never receive secrets merely because they existed in the raw
database row.

---

# Testing Requirements

Tests should cover:

- Basic synchronous callback.
- Basic asynchronous callback.
- Callback ordering.
- Callback context.
- Continue decision.
- Stop decision.
- Retain decision.
- Drop decision.
- Callback returning `None`.
- Callback exceptions.
- Each callback-error policy.
- Streaming behavior.
- Async cancellation.
- Redaction.
- Metadata-only mode.
- Session access restrictions.
- Transaction strategies.
- Callback statistics.
- Slow callback diagnostics.
- Callback sampling.
- Raw-row retention disabled.
- Source identity preservation.
- Rejection threshold interaction.

---

# MVP Scope

The first RowGuard callback implementation should support:

- One synchronous callback per execution.
- One asynchronous callback for async execution.
- Structured `RejectedRow`.
- Immutable `CallbackContext`.
- `CONTINUE`, `STOP`, `RETAIN`, and `DROP` decisions.
- Raise-on-callback-error default.
- Callback timing statistics.
- Buffered and streaming compatibility.
- Redaction-aware payloads.
- No implicit session access.
- Stable callback ordering.

Deferred:

- Concurrent callbacks.
- Callback batching.
- Multiple callback composition.
- Automatic retry.
- Background execution.
- Durable acknowledgments.
- Rejection fingerprints.
- Built-in notification integrations.
- Automatic repair callbacks.
- Global callback registries.

---

# Recommended Public Examples

## Metrics Callback

```python
def record_metrics(
    rejected: RejectedRow,
    context: CallbackContext,
) -> None:
    metrics.increment(
        "rowguard.rejections",
        tags={
            "model": rejected.model.__name__,
            "source": context.source_name or "unknown",
        },
    )
```

## Conditional Retention

```python
def retain_first_hundred(
    rejected: RejectedRow,
    context: CallbackContext,
) -> CallbackDecision:
    if context.rejection_count <= 100:
        return CallbackDecision.RETAIN
    return CallbackDecision.DROP
```

## Stop on Critical Field

```python
def stop_on_identity_failure(
    rejected: RejectedRow,
    context: CallbackContext,
) -> CallbackDecision:
    if "id" in rejected.error_paths:
        return CallbackDecision.STOP
    return CallbackDecision.CONTINUE
```

## Async Quarantine Handoff

```python
async def send_to_queue(
    rejected: RejectedRow,
    context: CallbackContext,
) -> None:
    await queue.publish(
        rejected.to_dict(include_values=False),
    )
```

---

# Design Principles

- Validation decisions happen before callbacks.
- Callbacks receive structured immutable data.
- Callback failures never erase original rejections.
- Side effects must remain explicit.
- Session and transaction access are opt-in.
- Sequential execution is the default.
- Sync and async semantics should align.
- Privacy policies apply before external handoff.
- Callback work is part of the observable execution lifecycle.
- RowGuard never promises background delivery.
