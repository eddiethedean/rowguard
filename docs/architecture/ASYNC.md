# ASYNC.md

# RowGuard Async Architecture

## Purpose

RowGuard's asynchronous API provides the same validation guarantees as the
synchronous API while integrating naturally with SQLAlchemy's `AsyncSession`
and Python's `asyncio` ecosystem.

The async API is a first-class interface, not a wrapper around synchronous
execution.

---

# Goals

- Feature parity with synchronous APIs
- SQLAlchemy `AsyncSession` support
- Async streaming
- Deterministic validation behavior
- Minimal API differences
- No duplicate validation logic

---

# Design Principles

- Share the same execution pipeline where possible.
- Keep validation synchronous; Pydantic validation is CPU-bound.
- Await only operations that perform I/O.
- Preserve identical rejection semantics.

---

# Public API

```python
result = await rowguard.aselect(
    session=session,
    table=users,
    model=UserRead,
)

result = await rowguard.aexecute(
    session=session,
    statement=stmt,
    model=UserRead,
)

async for model in rowguard.astream(
    session=session,
    table=users,
    model=UserRead,
):
    ...
```

---

# Execution Pipeline

```text
Execution Plan
      │
      ▼
Async Query Builder
      │
      ▼
Async SQLAlchemy Execute
      │
      ▼
Async Row Fetch
      │
      ▼
Row Adapter
      │
      ▼
Validation Engine
      │
      ├── Valid Model
      └── Rejected Row
```

Only database operations are asynchronous.

---

# AsyncSession Support

The MVP should target SQLAlchemy 2.x.

Example:

```python
async with AsyncSession(engine) as session:
    result = await rowguard.aselect(
        session=session,
        table=users,
        model=UserRead,
    )
```

---

# Async Streaming

Streaming should avoid buffering.

```python
async with rowguard.astream(...) as stream:
    async for model in stream:
        process(model)
```

Resources should be released automatically when the context exits.

---

# Rejection Handling

Policies remain identical for sync and async:

- raise
- collect
- skip
- log
- callback
- quarantine

Async APIs accept async callbacks / providers:

```python
async def handler(rejected, context):
    ...
```

In 0.4.0, rejection decisions stay synchronous via `process_row`. Do not fake
async reject handlers with thread pools.

---

# Event-loop blocking

Pydantic validation runs on the event loop (CPU-bound, not awaited). Heavy
models or large per-row validators can stall other coroutines. Prefer lean
read models for hot async paths; offload only if application code chooses to.

---

# Statistics

Statistics should mirror synchronous execution (`QueryStatistics`):

- rows_read
- rows_validated
- rows_accepted
- rows_rejected
- execution_time_ns
- adaptation_time_ns
- validation_time_ns
- rejection_time_ns

---

# Cancellation

Cancellation should:

- stop query execution
- release cursors
- close streaming resources
- preserve completed statistics when practical

No partially processed row should be reported as validated.

---

# Error Handling

Public async errors should match synchronous APIs.

Unexpected transport or driver errors should retain SQLAlchemy exception context.

---

# Testing

Async tests should verify:

- sync/async parity
- cancellation
- streaming
- rejection policies
- statistics
- cleanup
- resource leaks

---

# MVP Scope

**Shipped in 0.4.0+ (async since 0.4; ORM in 0.5):**

- AsyncSession / AsyncConnection
- aselect()
- aexecute()
- astream() / AsyncStreamResult
- identical validation semantics (raise / collect / skip / log / callback / quarantine)
- async reject handlers (callback / quarantine)
- sqlite+aiosqlite driver matrix
- cancellation closes stream resources

Deferred:

- adaptive batching
- resumable async streams
- asyncpg as a required CI driver

---

# Design Principles

- Async changes execution, not validation.
- Preserve API symmetry.
- Release resources promptly.
- Maintain deterministic behavior.
