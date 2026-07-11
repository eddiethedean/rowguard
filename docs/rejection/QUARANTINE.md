# QUARANTINE.md

:::{admonition} Status: not shipped in 0.5.0
:class: warning

This document is a **design draft for 0.6.0**. Quarantine rejection policies are
**not available** yet. Shipped policies are `raise`, `collect`, and `skip`.
See [Supported vs planned](../project/supported.md).
:::

# RowGuard Quarantine

## Purpose

Quarantine is a durable rejection-handling strategy for rows that fail
adaptation or Pydantic validation.

Unlike `collect`, which retains rejected rows in memory, quarantine sends
rejected data to an external sink for later inspection, repair, replay, or audit.

Typical quarantine destinations include:

- A dedicated SQL table.
- Object storage.
- JSONL, CSV, or Parquet files.
- Message queues.
- Data quality platforms.
- Audit systems.
- Dead-letter queues.

Quarantine must preserve enough context to understand and safely process the
rejected row later.

---

# Core Principle

```text
Database Row
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      └── RejectedRow
              │
              ▼
      Quarantine Provider
              │
              ▼
      Durable Quarantine Record
```

Quarantine occurs after RowGuard has classified the row as rejected.

It does not change the validation result.

---

# Goals

The quarantine system should:

- Persist rejected rows durably.
- Preserve structured validation errors.
- Preserve source identity and execution context.
- Support redaction and retention policies.
- Support synchronous and asynchronous sinks.
- Support batching.
- Define transaction behavior explicitly.
- Expose delivery failures.
- Support replay and repair workflows.
- Avoid coupling RowGuard core to any one storage backend.

---

# Non-Goals

Quarantine should not:

- Silently repair rows.
- Automatically update the source database.
- Hide validation failures.
- Parse or reinterpret validation errors.
- Assume every rejected row may be stored in full.
- Require the source database transaction.
- Guarantee exactly-once delivery in all providers.
- Become a general-purpose message broker abstraction.
- Run as unobservable background work owned by RowGuard.

---

# Why Quarantine Is Separate from Collect

## collect

- Stores rejections in the in-memory `QueryResult`.
- Best for small and medium workloads.
- Data is lost when the process exits unless the application persists it.

## quarantine

- Sends rejections to an external durable sink.
- Best for large workloads, governance, audit, and replay.
- May retain only a lightweight receipt in the result.

A query may use both:

```python
rejection_policy=CompositePolicy(
    QuarantinePolicy(provider),
    retain_receipts=True,
)
```

The MVP may expose one primary policy at a time, but the architecture should not
prevent composition later.

---

# Public API

Potential API:

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    rejection_policy=QuarantinePolicy(
        provider=provider,
    ),
)
```

Convenience form:

```python
result = rowguard.select(
    ...,
    on_reject="quarantine",
    quarantine=provider,
)
```

Internally, the policy-object form is preferred.

---

# Quarantine Provider Protocol

Recommended synchronous protocol:

```python
class QuarantineProvider(Protocol):
    def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        ...
```

Recommended asynchronous protocol:

```python
class AsyncQuarantineProvider(Protocol):
    async def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        ...
```

Optional batch protocol:

```python
class BatchQuarantineProvider(Protocol):
    def write_batch(
        self,
        records: Sequence[QuarantineRecord],
        context: QuarantineContext,
    ) -> Sequence[QuarantineReceipt]:
        ...
```

---

# QuarantineRecord

A quarantine record is a storage-safe representation of a rejected row.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    schema_version: str
    execution_id: str
    row_index: int
    model_name: str
    source_identity: SourceIdentity | None
    rejection_type: str
    mapping: Mapping[str, object] | None
    errors: tuple[Mapping[str, object], ...]
    diagnostics: tuple[Diagnostic, ...]
    metadata: Mapping[str, object]
    created_at: datetime
```

The record should not retain live SQLAlchemy or Pydantic objects.

---

# Schema Versioning

Quarantine payloads must be versioned.

Example:

```python
schema_version="1"
```

Versioning allows:

- Replay tools to evolve.
- Providers to validate payloads.
- Repair jobs to migrate records.
- Backward compatibility across RowGuard releases.

Schema changes should follow semantic compatibility rules.

---

# Error Representation

The original Pydantic `ValidationError` should be converted into a structured,
storage-safe form.

Example:

```python
errors=tuple(validation_error.errors())
```

Stored errors should include:

- `type`
- `loc`
- `msg`
- `ctx`, when safe
- input value only according to redaction policy

The live exception object remains available during execution but is not required
in the durable record.

---

# Rejection Types

Suggested categories:

```text
validation_error
adaptation_error
unexpected_validation_error
callback_error
unknown
```

Quarantine providers should not infer categories from message text.

A stable `rejection_type` field should be supplied explicitly.

---

# Source Identity

Quarantine records should preserve a durable source identity when possible.

Examples:

- Table and primary key.
- ORM mapper and identity tuple.
- Raw SQL row number.
- Partition and offset.
- File name and line number.
- Stream checkpoint.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source_name: str | None
    primary_key: tuple[object, ...] | None
    partition: str | None
    offset: object | None
```

Source identity should not require retaining the full source row.

---

# Quarantine Context

Suggested immutable context:

```python
@dataclass(frozen=True, slots=True)
class QuarantineContext:
    execution_id: str
    query_plan_id: str | None
    source_name: str | None
    model_name: str
    dialect: str | None
    metadata: Mapping[str, object]
```

The context may include safe identifiers but should not automatically include:

- Full SQL text.
- Bound parameter values.
- Live sessions.
- Authentication tokens.
- Raw database connections.

---

# QuarantineReceipt

A provider should return a receipt.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class QuarantineReceipt:
    provider: str
    record_id: str | None
    location: str | None
    written_at: datetime
    metadata: Mapping[str, object]
```

Receipts let RowGuard report:

- Delivery success.
- External record identifier.
- Storage location.
- Provider metadata.

The result may retain receipts instead of full rejected rows.

---

# Retention Modes

Potential configuration:

```python
quarantine_retention="receipt"
quarantine_retention="rejection"
quarantine_retention="both"
quarantine_retention="none"
```

## receipt

Retain only `QuarantineReceipt`.

Recommended for large workloads.

## rejection

Retain the in-memory `RejectedRow`.

## both

Retain both rejection and receipt.

## none

Retain neither; statistics still record quarantine success.

---

# Redaction

Quarantine may persist sensitive data, so redaction is mandatory to design
explicitly.

Potential policies:

```python
quarantine_values="full"
quarantine_values="redacted"
quarantine_values="metadata_only"
```

## full

Store the complete adapted mapping.

Use only for secured data-quality environments.

## redacted

Store the mapping with configured sensitive fields replaced.

## metadata_only

Store source identity, errors, and diagnostics without row values.

RowGuard should apply redaction before handing the record to the provider.

---

# Field-Level Redaction

Potential configuration:

```python
redact_fields={
    "password",
    "token",
    "ssn",
}
```

Future path support:

```python
redact_paths={
    "credentials.secret",
    "payment.card_number",
}
```

Redaction should be deterministic and testable.

---

# Hashing Sensitive Values

Some workflows need correlation without retention.

Optional transformation:

```python
hash_fields={
    "email",
    "account_number",
}
```

Requirements:

- Explicit cryptographic algorithm.
- Application-supplied salt or key where appropriate.
- Stable versioning.
- Never use Python's built-in `hash()` for durable records.
- Document collision and privacy implications.

This is a future feature, not required for the MVP.

---

# Provider Types

Potential official providers:

- `SQLTableQuarantineProvider`
- `JSONLQuarantineProvider`
- `CSVQuarantineProvider`
- `ParquetQuarantineProvider`
- `S3QuarantineProvider`
- `AzureBlobQuarantineProvider`
- `KafkaQuarantineProvider`
- `InMemoryQuarantineProvider` for tests

RowGuard core should define protocols and simple reference providers only.

Cloud and broker integrations should live in optional packages.

---

# SQL Table Provider

A SQL quarantine table might contain:

```text
id
schema_version
execution_id
source_name
source_identity_json
model_name
rejection_type
mapping_json
errors_json
diagnostics_json
created_at
```

The provider should:

- Use bound parameters.
- Define its own schema explicitly.
- Avoid mutating source tables.
- Support a separate transaction by default.
- Return a durable record ID.

---

# File Providers

JSONL is a natural initial file format because each rejection is independent.

Example record:

```json
{
  "schema_version": "1",
  "execution_id": "exec-123",
  "row_index": 42,
  "model_name": "UserRead",
  "rejection_type": "validation_error",
  "source_identity": {
    "source_name": "users",
    "primary_key": [123]
  },
  "errors": [
    {
      "type": "greater_than_equal",
      "loc": ["age"],
      "msg": "Input should be greater than or equal to 18"
    }
  ]
}
```

File providers must define:

- File rotation.
- Flush behavior.
- Encoding.
- Atomicity.
- Concurrent writer behavior.
- Compression.
- Partial-write handling.

---

# Message Queue Providers

Queue-based quarantine can decouple the validation job from repair or audit
processing.

Providers may target:

- Kafka.
- RabbitMQ.
- SQS.
- Pub/Sub.
- Azure Service Bus.

They should define:

- Delivery acknowledgment.
- Retry semantics.
- Message size limits.
- Ordering guarantees.
- Partition key.
- Authentication.
- Serialization.

RowGuard core should not claim exactly-once delivery unless the provider can
prove it.

---

# Transaction Strategies

Quarantine writes may use different transaction strategies.

Potential configuration:

```python
quarantine_transaction="separate"
quarantine_transaction="same"
quarantine_transaction="external"
```

## separate

Recommended for SQL-backed quarantine.

Benefits:

- A source read transaction failure does not erase rejection records.
- Quarantine failures can be isolated.
- Source locks are less likely to be extended.

## same

Use the source session/transaction.

Risks:

- Rejection storage may roll back with the source transaction.
- Quarantine failures may invalidate the source transaction.
- Streaming locks may be held longer.
- Read-only transactions may not allow writes.

This should require explicit opt-in.

## external

Provider manages its own non-database durability mechanism.

Examples:

- Object storage.
- Queue.
- File.

---

# Provider Failure Policy

Quarantine can fail.

Suggested policies:

```python
on_quarantine_error="raise"
on_quarantine_error="retry"
on_quarantine_error="collect"
on_quarantine_error="log"
```

## raise

Recommended default.

Stop execution and raise `QuarantineError`.

## retry

Retry according to an explicit policy.

## collect

Retain the failed rejection in memory and continue.

## log

Record failure and continue.

This risks losing rejected rows and should require explicit opt-in.

---

# Retry Policy

Potential configuration:

```python
RetryPolicy(
    max_attempts=3,
    backoff="exponential",
    initial_delay=0.25,
    max_delay=5.0,
)
```

Retry rules should define:

- Retryable exception classes.
- Maximum attempts.
- Backoff.
- Jitter.
- Idempotency expectations.
- Cancellation behavior.
- Batch retry behavior.

The MVP may support provider-managed retries or no automatic retry.

---

# Idempotency

A provider should document whether repeated writes create duplicates.

Potential deterministic record ID inputs:

- Execution ID.
- Source identity.
- Row index.
- Rejection fingerprint.
- Quarantine schema version.

Example:

```text
record_id = hash(execution_id, row_index, rejection_fingerprint)
```

Durable hashing must use a stable cryptographic algorithm, not Python's built-in
hash function.

---

# Rejection Fingerprints

A future fingerprint may include:

- Model name.
- Source identity.
- Error types.
- Error locations.
- Validation policy version.

It should exclude raw sensitive values by default.

Fingerprints help:

- Deduplicate records.
- Correlate repeated failures.
- Group repair jobs.
- Suppress duplicate alerts.

---

# Batching

Batching improves throughput for external sinks.

Potential policy:

```python
QuarantinePolicy(
    provider=provider,
    batch_size=500,
)
```

Batching must define:

- Flush at batch size.
- Flush at query completion.
- Flush at stream close.
- Flush on cancellation.
- Flush on exception.
- Partial batch failure behavior.
- Receipt mapping.

---

# Batch Failure

A batch provider may fail all or part of a batch.

Potential outcomes:

```python
BatchWriteResult(
    succeeded=...,
    failed=...,
)
```

RowGuard must not assume batch writes are atomic.

The provider should return per-record status when partial failure is possible.

---

# Streaming

Quarantine is particularly useful during streaming because rejected rows need
not accumulate in memory.

```python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
    rejection_policy=QuarantinePolicy(provider),
) as stream:
    for model in stream:
        process(model)
```

The provider should write or buffer each rejection before the next row proceeds,
subject to configured batching.

Stream close must flush outstanding records.

---

# Async Quarantine

Async APIs should support async providers.

```python
async with rowguard.astream(
    ...,
    rejection_policy=AsyncQuarantinePolicy(provider),
) as stream:
    async for model in stream:
        ...
```

Async providers are appropriate for:

- Cloud storage.
- Queues.
- Remote audit services.
- Async database connections.

Synchronous providers in async execution may block the event loop and should be
discouraged unless they are fast.

---

# Cancellation

Cancellation must define what happens to pending quarantine records.

Requirements:

- Attempt configured flush when safe.
- Do not claim success for unwritten records.
- Preserve completed receipts.
- Release provider resources.
- Propagate cancellation.
- Avoid indefinite cleanup waits.

Provider-specific shutdown timeouts may be necessary.

---

# Resource Management

Providers may own:

- File handles.
- Network clients.
- Database connections.
- Buffers.
- Background producer resources.

Recommended lifecycle:

```python
with QuarantinePolicy(provider) as policy:
    ...
```

or managed through RowGuard's execution context.

Async providers may implement async context management.

RowGuard should not leave provider resources open after execution.

---

# Background Delivery

RowGuard should not promise hidden background delivery.

If a provider hands off records to an application-owned queue, durability begins
only according to that queue's contract.

RowGuard's result should distinguish:

- Written durably.
- Accepted by provider.
- Buffered locally.
- Enqueued for external delivery.

Receipts should report the actual guarantee.

---

# Replay

Quarantine records should support later replay.

Replay workflow:

```text
Quarantine Record
      │
      ▼
Load stored mapping
      │
      ▼
Optional repair
      │
      ▼
Current Pydantic validation
      │
      ├── Accepted
      └── Still rejected
```

Replay tools should record:

- Original schema version.
- Original model name.
- Current model version.
- Repair version.
- Replay attempt count.
- Final disposition.

Replay belongs in a future tool or package, not the query hot path.

---

# Repair

A quarantine record may be repaired manually or programmatically.

RowGuard should not mutate the original record.

Recommended audit model:

```text
Original QuarantineRecord
      │
      ▼
RepairAttempt
      │
      ├── Proposed mapping
      ├── Repair metadata
      ├── Validation result
      └── Timestamp
```

Successful repair does not automatically write back to the source database.

That remains an explicit application operation.

---

# Quarantine Record States

Potential lifecycle states:

```text
new
reviewed
repair_pending
repaired
replayed
resolved
discarded
failed
```

State management belongs to the quarantine system or downstream tooling, not
RowGuard core.

RowGuard's responsibility ends after the provider accepts the record.

---

# Observability

Suggested metrics:

- Quarantine records attempted.
- Quarantine records written.
- Quarantine failures.
- Retry attempts.
- Batch flushes.
- Batch sizes.
- Write latency.
- Pending buffer size.
- Bytes written.
- Receipts retained.
- Records redacted.

High-cardinality values such as primary keys should not be metric labels.

---

# Diagnostics

Suggested diagnostic codes:

```text
quarantine.record_created
quarantine.write_started
quarantine.write_succeeded
quarantine.write_failed
quarantine.retry_scheduled
quarantine.batch_flushed
quarantine.record_redacted
quarantine.receipt_retained
```

Diagnostics should identify the provider but avoid leaking credentials or row
values.

---

# Error Hierarchy

Suggested hierarchy:

```text
RowGuardError
└── RejectHandlerError
    └── QuarantineError
        ├── QuarantineConfigurationError
        ├── QuarantineSerializationError
        ├── QuarantineWriteError
        ├── QuarantineBatchError
        ├── QuarantineRetryExhaustedError
        ├── QuarantineTransactionError
        └── QuarantineCloseError
```

The original provider exception should remain available as the cause.

---

# Serialization

A provider may require JSON-safe values.

RowGuard should define a deterministic serializer boundary.

Potential strategies:

```python
serialization="pydantic"
serialization="json_safe"
serialization="provider"
```

## pydantic

Use Pydantic-compatible serialization rules for known values.

## json_safe

Convert supported values such as:

- `datetime`
- `date`
- `time`
- `Decimal`
- `UUID`
- Enum

into deterministic JSON-safe representations.

## provider

Pass the structured record to the provider, which owns serialization.

The core record should avoid arbitrary `repr()` conversion of unknown objects.

---

# Unsupported Values

If a rejected mapping contains non-serializable objects, policies may include:

```python
on_unserializable="raise"
on_unserializable="omit"
on_unserializable="redact"
on_unserializable="provider"
```

Recommended default:

```python
raise
```

Silently stringifying arbitrary objects can leak secrets or produce unstable
records.

---

# Metadata

Applications may attach safe metadata:

```python
quarantine_metadata={
    "pipeline": "nightly-users",
    "environment": "production",
    "policy_version": "2026-07",
}
```

Metadata should be immutable and serializable.

Row-specific metadata may be provided by a callback, but it must follow the same
privacy policy.

---

# Model Versioning

Model names alone may not be sufficient for replay.

Potential metadata:

```python
model_name="UserRead"
model_version="3"
model_module="myapp.models"
```

Applications should define how model versions are assigned.

RowGuard may accept an explicit validation policy or contract version.

---

# Source Schema Version

When known, quarantine records may include:

- Database migration revision.
- Schema version.
- Source application version.
- Data contract version.

This can significantly improve repair and replay accuracy.

RowGuard should accept these as explicit metadata rather than discovering them
implicitly.

---

# Access Control

Quarantine stores often contain invalid and sensitive data.

Applications should enforce:

- Least-privilege write access.
- Restricted read access.
- Encryption at rest.
- Encryption in transit.
- Audit logging.
- Retention limits.
- Deletion procedures.
- Separation from ordinary application logs.

RowGuard provides mechanisms, not compliance guarantees.

---

# Data Retention

Providers should document retention behavior.

Potential application policies:

```text
retain 30 days
retain until repaired
retain only error metadata
delete after successful replay
```

RowGuard should not automatically delete quarantine records.

---

# Provider Capabilities

A provider may declare capabilities.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class QuarantineCapabilities:
    async_supported: bool
    batch_supported: bool
    transactions_supported: bool
    receipts_supported: bool
    partial_batch_results_supported: bool
    max_record_size: int | None
```

Planning can validate configuration against capabilities before query execution.

---

# Provider Registration

Providers may be supplied directly:

```python
QuarantinePolicy(provider=JSONLProvider(path))
```

A future plugin registry may support named providers:

```python
registry.register_quarantine_provider(
    "s3",
    S3QuarantineProvider,
)
```

Global mutable provider instances should be avoided.

---

# Testing Providers

An in-memory provider is useful for tests.

```python
provider = InMemoryQuarantineProvider()
```

Tests can inspect:

```python
provider.records
provider.receipts
```

The in-memory provider is not a durability guarantee and should be labeled
clearly.

---

# Testing Requirements

Tests should cover:

- Single record write.
- Multiple record writes.
- Validation and adaptation errors.
- Record schema version.
- Source identity.
- Redaction.
- Metadata-only mode.
- Receipt retention.
- Provider failure.
- Retry exhaustion.
- Batch success.
- Partial batch failure.
- Stream flush.
- Completion flush.
- Exception flush.
- Cancellation.
- Sync and async parity.
- Separate and same transaction strategies.
- Non-serializable values.
- JSON-safe serialization.
- Large records.
- Provider resource cleanup.
- Idempotent record identifiers.
- Metrics and diagnostics.
- Quarantine error propagation.
- Original rejection preservation.

---

# MVP Scope

The first RowGuard quarantine implementation should support:

- `QuarantineProvider` protocol.
- Synchronous per-record writes.
- Structured `QuarantineRecord`.
- Schema version `1`.
- Structured Pydantic error serialization.
- Source identity.
- Full, redacted, and metadata-only value modes.
- `QuarantineReceipt`.
- Raise-on-provider-error default.
- Receipt-only result retention.
- Buffered and streaming compatibility.
- Provider lifecycle cleanup.
- In-memory reference provider.
- JSONL reference provider.
- Deterministic JSON-safe serialization for common Python types.
- No implicit access to the source session.

Near-term additions:

- Async providers.
- Batch writes.
- SQL table provider.
- Cloud object storage providers.
- Queue providers.
- Explicit retry policies.
- Provider capability declarations.

Deferred:

- Exactly-once guarantees.
- Automatic replay.
- Automatic source repair.
- Cross-provider replication.
- Distributed transactions.
- Background delivery owned by RowGuard.
- Quarantine UI.
- Automated model-version discovery.
- Global provider registry.
- Automatic retention management.

---

# Recommended Public Examples

## JSONL Quarantine

```python
provider = JSONLQuarantineProvider(
    path="quarantine/users.jsonl",
)

result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    rejection_policy=QuarantinePolicy(
        provider=provider,
        values="redacted",
    ),
)
```

## Receipt Retention

```python
policy = QuarantinePolicy(
    provider=provider,
    retention="receipt",
)
```

```python
for receipt in result.quarantine_receipts:
    print(receipt.record_id)
```

## Metadata-Only Quarantine

```python
policy = QuarantinePolicy(
    provider=provider,
    values="metadata_only",
)
```

## Separate SQL Quarantine Transaction

```python
policy = QuarantinePolicy(
    provider=SQLTableQuarantineProvider(
        engine=quarantine_engine,
        table=quarantine_table,
    ),
    transaction="separate",
)
```

## Async Queue Quarantine

```python
policy = AsyncQuarantinePolicy(
    provider=KafkaQuarantineProvider(...),
)
```

---

# Design Principles

- Quarantine is durable rejection handling, not in-memory collection.
- Validation decisions occur before quarantine.
- Providers receive storage-safe structured records.
- Redaction happens before external handoff.
- Source and quarantine transactions are separate by default.
- Delivery guarantees must be stated accurately.
- Provider failures never erase the original rejection.
- Streaming must flush and close providers predictably.
- RowGuard does not promise hidden background delivery.
- Replay and repair remain explicit downstream workflows.
