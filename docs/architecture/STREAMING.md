# STREAMING.md

:::{admonition} Design notes — read the user guide first
:class: caution

For day-to-day use see [Streaming guide](../guides/streaming.md). Sections below
that describe callback / quarantine / log policies are **not shipped** in 0.5.0.
Shipped policies: `raise`, `collect`, `skip`.
:::

# RowGuard Streaming

## Purpose

Streaming allows RowGuard to process arbitrarily large result sets without
materializing every validated model in memory.

Instead of returning a complete `QueryResult`, the streaming API validates,
classifies, and yields rows incrementally.

Streaming is intended for:

- ETL pipelines
- Batch processing
- Data migration
- Analytics
- Large exports
- Long-running services

---

# Philosophy

Streaming should preserve the same correctness guarantees as buffered
execution.

Every processed row must still become either:

1. A validated Pydantic model, or
2. A rejected row handled by the configured rejection policy.

The only difference is **when** models are delivered.

---

# Pipeline

```text
Execution Plan
      │
      ▼
Execute SQL
      │
      ▼
Read Next Row
      │
      ▼
Row Adapter
      │
      ▼
Validation Engine
      │
      ├── Valid Model ─────► yield
      └── Rejected Row
               │
               ▼
        Reject Handler
```

Rows are processed independently.

---

# Public API

```python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
) as stream:
    for model in stream:
        process(model)
```

Bare ``for model in stream`` also closes the underlying result when the loop
ends or breaks. Prefer the context manager when combining early exit with
post-stream inspection of ``statistics`` / ``rejected``.

Shipped async API (0.4.0+; ORM async in 0.5):

```python
async with rowguard.astream(...) as stream:
    async for model in stream:
        ...
```

See [Async architecture](ASYNC.md) and the [async guide](../guides/async.md).

---

# StreamResult

Streaming should expose an object that is iterable and accumulates execution
metadata.

Suggested interface:

```python
stream = rowguard.stream(...)

for model in stream:
    ...

stats = stream.statistics
rejected = stream.rejected
```

The stream object should not pretend to be a completed `QueryResult`.

---

# Rejection Policies

Streaming supports the same policies as buffered execution.

## raise

Stop iteration immediately.

## collect

Retain rejected rows until the stream completes.

## skip

Continue without retaining the rejected row.

## callback

Invoke the callback before reading the next row.

## quarantine

Forward rejected rows to the configured quarantine provider.

---

# Statistics

Streaming statistics should update continuously.

Suggested metrics:

- rows_read
- rows_valid
- rows_rejected
- execution_time
- validation_time
- throughput

Statistics become final when iteration completes.

---

# Backpressure

Streaming should naturally respect consumer speed.

RowGuard should not prefetch large batches unless explicitly configured.

Future option:

```python
batch_size=500
```

---

# Resource Management

Streaming should cleanly release database resources.

Recommended usage:

```python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
```

Async:

```python
async with rowguard.astream(...) as stream:
    async for model in stream:
        ...
```

Context managers help guarantee cursor cleanup.

---

# Error Handling

Execution errors terminate the stream.

Validation failures follow the configured rejection policy.

Unexpected adapter or engine failures should close the stream and release
resources.

---

# Ordering

Streaming preserves database row order.

Rejected rows retain their original sequence number.

---

# Memory Goals

Streaming should avoid retaining:

- all validated models
- duplicate row mappings
- unnecessary diagnostics

Only configured rejection retention should consume additional memory.

---

# Extension Points

Future plugins may provide:

- progress reporting
- throughput monitoring
- adaptive batching
- checkpointing
- resumable streams

---

# Testing

Streaming tests should verify:

- ordering
- resource cleanup
- rejection handling
- statistics
- sync/async parity
- cancellation
- large result sets

---

# MVP Scope

Initial release:

- synchronous streaming
- SQLAlchemy 2.x
- validation per row
- rejection policies
- statistics

Deferred:

- adaptive batching
- resumable execution
- distributed streaming

---

# Design Principles

- Constant-memory processing.
- Preserve validation guarantees.
- Release resources promptly.
- Maintain deterministic ordering.
- Match buffered semantics wherever practical.
