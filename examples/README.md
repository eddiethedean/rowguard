# Examples

Runnable scripts smoked in CI. From the repo root after
`pip install -e ".[dev,async,sqlmodel]"` (or `make install`):

```bash
python examples/basic.py
python examples/sqlrules_default.py
python examples/streaming.py
python examples/async_basic.py
python examples/orm_projected.py
python examples/orm_entity.py
python examples/sqlmodel_basic.py
python examples/callback_basic.py
python examples/quarantine_jsonl.py
```

| Script | Extras | Notes |
| --- | --- | --- |
| `basic.py` | none | `use_sqlrules=False` so invalid rows appear in `rejected` |
| `sqlrules_default.py` | none | Default `use_sqlrules=True`; invalid candidates filtered in SQL |
| `streaming.py` | none | Sync `stream` with `on_reject="collect"` and `use_sqlrules=False` |
| `async_basic.py` | `async` | `aselect` + `astream` |
| `orm_projected.py` | none | Projected ORM `Select` with `source=User` |
| `orm_entity.py` | none | Entity path with `table=User` on `select` |
| `sqlmodel_basic.py` | `sqlmodel` | SQLModel table model as `source=` |
| `callback_basic.py` | none | `on_reject="callback"` with `CallbackDecision.RETAIN` |
| `quarantine_jsonl.py` | none | `JSONLQuarantineProvider` with receipt retention |

## `table=` vs `source=`

- **`select` / `stream` / `aselect` / `astream`:** pass a Core `Table` or mapped
  class as `table=`.
- **`execute` / `aexecute` with a projected `Select`:** pass the mapped class as
  `source=` for pushdown and adaptation.
- Use only one of `table=` or `source=` per call.

Docs gallery: [Examples](https://rowguard.readthedocs.io/en/latest/examples/index.html).
