# Error catalog

Public exceptions raised by RowGuard {{ release }}. Import from `rowguard`
(for example `from rowguard import PlanningError`).

## Hierarchy

```text
RowGuardError
├── ConfigurationError
│   └── PlanningError          # also a ConfigurationError
├── QueryExecutionError
├── RowAdaptationError
├── RowValidationError
├── RejectHandlerError         # reserved for 0.6 callbacks/quarantine
└── ResultAssemblyError        # internal consistency (rare)
```

Catching `ConfigurationError` also catches `PlanningError`.

## Catalog

| Exception | When | Notable attributes |
| --- | --- | --- |
| `ConfigurationError` | Invalid call shape (both/neither session & connection; both `table` & `statement`; bad `yield_per`; bad ORM knobs) | — |
| `PlanningError` | Plan-time failures (missing source, invalid maps, pushdown errors) | `stage`, `execution_id` |
| `QueryExecutionError` | DB/driver failures; closed stream re-entry | `__cause__` often set |
| `RowValidationError` | Pydantic failure under `on_reject="raise"` | `model`, `validation_error`, `row_index` |
| `RowAdaptationError` | Adaptation failure under raise (or wrapped) | `model`, `row_index` |
| `RejectHandlerError` | Reserved for future callback/quarantine failures | — |
| `ResultAssemblyError` | Inconsistent result about to be published (should be rare) | — |

## Examples

```python
import rowguard
from rowguard import PlanningError, RowValidationError

try:
    rowguard.select(session=session, table=users, model=UserRead)
except RowValidationError as exc:
    print(exc.row_index, exc.validation_error)
except PlanningError as exc:
    print(exc.stage, exc)
```

Under default `on_reject="raise"`, the first invalid **fetched** row raises
`RowValidationError`. With default `use_sqlrules=True`, that row may never be
fetched—see [SQLRules pushdown](../guides/sqlrules-pushdown.md).

## Stream lifecycle

- Re-using a closed `StreamResult` / `AsyncStreamResult` raises `QueryExecutionError`.
- Prefer `with` / `async with` so cursors close on break, cancel, or error.

## Related

- [API guide](../api.md)
- [Troubleshooting](../guides/troubleshooting.md)
- Autodoc: [Python API reference](api.md)
