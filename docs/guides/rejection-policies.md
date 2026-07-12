# Rejection policies

Every validated row is either accepted or rejected. The `on_reject=` argument
controls what happens next.

| Policy | Accepted rows | Rejected rows | Raises? |
| --- | --- | --- | --- |
| `raise` (default) | Returned / yielded until first failure | Counted; then abort | Yes (`RowValidationError`) |
| `collect` | Returned / yielded | Retained on `result.rejected` / `stream.rejected` | No |
| `skip` | Returned / yielded | Counted in statistics only | No |
| `log` | Returned / yielded | Logged at WARNING; not retained | No |
| `callback` | Per `CallbackDecision` | User `reject_callback=` runs first | Optional (`CallbackError`) |
| `quarantine` | Returned / yielded | Written via `quarantine=` provider | Optional (`QuarantineError`) |

## Choosing a policy

- **`raise`** — fail fast in tests and strict pipelines.
- **`collect`** — ETL / audit paths that need the bad rows.
- **`skip`** — best-effort reads where invalid rows should not stop the stream.
- **`log`** — same as skip, with a stdlib warning per rejection.
- **`callback`** — metrics, conditional retention, or stop-on-critical-field.
- **`quarantine`** — durable handoff (in-memory or JSONL in 0.6).

:::{admonition} `has_rejections` vs `rejected`
:class: tip

`has_rejections` is based on `statistics.rows_rejected`. Under `skip` / `log` /
receipt-only quarantine, it may be `True` while `rejected` is empty because rows
were not retained.
:::

## Callback

```python
from rowguard import CallbackDecision

def on_bad(rejected, context):
    metrics.increment("rejects")
    return CallbackDecision.RETAIN  # or STOP / DROP / CONTINUE / None

result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="callback",
    reject_callback=on_bad,
)
```

Async APIs accept `async def` callbacks. Sync APIs reject async callables at
plan time.

### Callback decisions (0.6)

For standalone `on_reject="callback"` (the callback *is* the rejection policy):

| Decision | Continue? | Retain rejected row? |
| --- | --- | --- |
| `None` or `CONTINUE` | Yes | No |
| `DROP` | Yes | No |
| `RETAIN` | Yes | Yes |
| `STOP` | No | No |

`CONTINUE`, `None`, and `DROP` are equivalent for retention in 0.6: processing
continues and the row is not kept on `result.rejected`. Prefer `CONTINUE` /
`None` for “acknowledge and move on”; use `DROP` when you want to emphasize
non-retention.

## Quarantine

```python
from rowguard import InMemoryQuarantineProvider, JSONLQuarantineProvider

provider = JSONLQuarantineProvider("rejects.jsonl")
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="quarantine",
    quarantine=provider,
    quarantine_retention="receipt",  # default
    redact_fields={"ssn"},
)
for receipt in result.quarantine_receipts:
    print(receipt.location)
```

RowGuard closes the quarantine provider when the execution finishes (including
on error). Construct a new provider for each call; do not rely on reusing a
closed instance.

Reference providers never use the source Session. In 0.6,
`quarantine_transaction` must be `"separate"` (the default); other values raise
`ConfigurationError`.

`redact_fields` / `callback_values` / `quarantine_values` apply to **handoff**
payloads (callback arguments and quarantine records). They strip raw
`validation_error` inputs and redact overlapping `source_identity` keys.

## Thresholds

Optional on any policy:

```python
rowguard.select(
    ...,
    max_rejections=100,
    max_rejection_rate=0.05,
)
```

Exceeding a threshold raises `RejectionThresholdError` with summary stats and
the last rejection.

## Deep dive

- [Rejection policies architecture](../rejection/REJECTION_POLICIES.md)
- [Callbacks](../rejection/CALLBACKS.md) (shipped in 0.6)
- [Quarantine](../rejection/QUARANTINE.md) (shipped in 0.6)
- [Supported vs planned](../project/supported.md)
