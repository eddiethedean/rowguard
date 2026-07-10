# Rejection policies

Every validated row is either accepted or rejected. The `on_reject=` argument
controls what happens next.

| Policy | Accepted rows | Rejected rows | Raises? |
| --- | --- | --- | --- |
| `raise` (default) | Returned / yielded until first failure | Counted; then abort | Yes (`RowValidationError`) |
| `collect` | Returned / yielded | Retained on `result.rejected` / `stream.rejected` | No |
| `skip` | Returned / yielded | Counted in statistics only | No |

## Choosing a policy

- **`raise`** — fail fast in tests and strict pipelines.
- **`collect`** — ETL / audit paths that need the bad rows.
- **`skip`** — best-effort reads where invalid rows should not stop the stream.

:::{admonition} `has_rejections` vs `rejected`
:class: tip

`has_rejections` is based on `statistics.rows_rejected`. Under `skip`, it may be
`True` while `rejected` is empty because rows were not retained.
:::

## Deferred policies

Callback, quarantine, and log policies are planned for **0.6.0**. They are not
available in {{ release }}.

## Deep dive

- [Rejection policies architecture](../rejection/REJECTION_POLICIES.md)
- [Rejection handling](../rejection/REJECTION_HANDLING.md)
- [Diagnostics](../rejection/DIAGNOSTICS.md)
