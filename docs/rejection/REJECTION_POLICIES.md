# REJECTION_POLICIES.md

:::{admonition} Status note (0.4.0)
:class: tip

**Shipped today:** `raise`, `collect`, `skip`.  
**Not shipped (design for 0.6.0):** `callback`, `quarantine`, `log`.  
See [Supported vs planned](../project/supported.md) and the
[rejection policies guide](../guides/rejection-policies.md).
:::

# RowGuard Rejection Policies

## Purpose

Rejection policies determine what RowGuard does after a row fails validation.

Validation always happens first. A rejection policy never changes whether a row
is valid; it only determines how execution proceeds after a rejection.

---

# Core Principle

```
Database Row
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ├── Accepted
      └── Rejected
              │
              ▼
      Rejection Policy
```

Validation and rejection handling are intentionally separate concerns.

---

# Built-in Policies

## raise (default)

Stop immediately and raise `RowValidationError`.

Use when:

- API requests
- transactional reads
- strict correctness

```python
rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="raise",
)
```

---

## collect

Continue processing and accumulate rejected rows.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)

print(result.models)
print(result.rejected)
```

Best for:

- audits
- migrations
- reporting
- data quality jobs

---

## skip

Discard rejected rows while recording aggregate statistics.

Useful when invalid rows are expected but should not stop processing.

Statistics should still include:

- rows rejected
- validation errors
- rejection rate

---

## callback

Invoke a user callback for every rejected row.

```python
def on_reject(row):
    ...

rowguard.select(
    ...,
    on_reject=on_reject,
)
```

Callbacks receive a `RejectedRow`, not a formatted string.

---

## quarantine

Write rejected rows to a dedicated sink.

Possible sinks:

- SQL table
- CSV
- Parquet
- JSONL
- Kafka
- S3
- Blob storage

Quarantine writers should respect redaction settings.

---

# Policy Comparison

| Policy | Stops Execution | Retains Rows | Typical Use |
| --- | :---: | :---: | --- |
| raise | Yes | Optional | APIs |
| collect | No | Yes | Audits |
| skip | No | No | Streaming |
| callback | No | User-defined | Custom workflows |
| quarantine | No | External | Data governance |

---

# Thresholds

Execution may terminate after configured limits.

Examples:

```python
max_rejections=100
```

```python
max_rejection_rate=0.02
```

Threshold failures should raise a dedicated execution exception that includes
summary statistics.

---

# Retry and Repair

Future repair workflows may be layered on top of rejection policies.

```
Rejected Row
      │
      ▼
Repair Callback
      │
      ▼
Revalidate
```

Repair is never implicit.

---

# Streaming

Policies behave consistently during streaming.

- raise: stop immediately
- collect: retain until stream completes
- skip: continue
- callback: invoke before next row
- quarantine: write before continuing

Accepted rows are yielded only after validation.

---

# Async

Async APIs preserve the same semantics.

Only callback and quarantine handlers may become asynchronous.

Validation behavior is identical.

---

# Diagnostics

Recommended metrics:

- rows accepted
- rows rejected
- rejection rate
- policy name
- callback failures
- quarantine failures

---

# Security

Rejected rows may contain sensitive values.

Policies should support:

- value redaction
- disabled raw row retention
- encrypted quarantine storage
- structured logging

---

# Testing

Tests should verify:

- every built-in policy
- thresholds
- callback failures
- quarantine failures
- streaming
- async parity
- statistics
- redaction

---

# MVP Scope

**Shipped in 0.4.0:**

- raise
- collect
- skip
- statistics
- diagnostics

**Target for 0.6.0 (not shipped):**

- callback
- quarantine
- log
- threshold support

Deferred further:

- retry queues
- distributed quarantine
- policy composition
- conditional routing

---

# Design Principles

- Validation determines acceptance.
- Policies determine behavior after rejection.
- Policies must be deterministic.
- Sync and async behavior should match.
- Privacy must be configurable.
- Rejection handling should remain observable.
