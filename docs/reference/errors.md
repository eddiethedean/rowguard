# Error catalog

Public exceptions raised by RowGuard 0.4. All inherit from `RowGuardError`
unless noted.

| Exception | When it is raised |
| --- | --- |
| `ConfigurationError` | Invalid call shape (both/neither session & connection; both `table` & `statement` for stream; bad `yield_per`; etc.) |
| `PlanningError` | Plan-time failures (missing source, invalid maps, pushdown config errors) |
| `QueryExecutionError` | DB/driver failures wrapped during execute/stream; closed stream re-entry |
| `RowValidationError` | A row failed Pydantic validation under `on_reject="raise"` |
| `RowAdaptationError` | Row could not be adapted to a mapping under raise policy |
| `RejectHandlerError` | Reserved for future callback/quarantine handler failures (0.6) |
| `ResultAssemblyError` | Internal consistency failure assembling `QueryResult` (should be rare) |

## Stream lifecycle

- Re-using a closed `StreamResult` / `AsyncStreamResult` raises `QueryExecutionError`.
- Prefer `with` / `async with` so cursors close on break, cancel, or error.

## Related

- [API guide](../api.md)
- [Troubleshooting](../guides/troubleshooting.md)
- Autodoc: [Python API reference](api.md)
