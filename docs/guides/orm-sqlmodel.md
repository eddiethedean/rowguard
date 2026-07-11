# ORM and SQLModel

RowGuard 0.5 validates SQLAlchemy ORM and SQLModel reads into Pydantic (or
SQLModel) contracts without becoming an ORM itself.

## Prefer projections

```python
from sqlalchemy import select

result = rowguard.execute(
    session=session,
    statement=select(User.id, User.name, User.age),
    source=User,
    model=UserRead,
    on_reject="collect",
)
```

Projected columns return ordinary row mappings and avoid identity-map /
lazy-load surprises. Pass the mapped class as `source=` (or `table=` for
`select`) so SQLRules can push down constraints.

## Single-entity selects

```python
result = rowguard.select(
    session=session,
    table=User,  # Core Table or mapped class
    model=UserRead,
    on_reject="collect",
)
```

`select(User)` uses `ORMEntityAdapter`: only planned scalar attributes are
extracted. Relationships are never traversed. Rejected rows may include
`source_identity` (primary-key dict); live entities are not retained by default.

### Options

| Knob | Default | Notes |
| --- | --- | --- |
| `orm_validation` | `"mapping"` | `"from_attributes"` opts into `model_validate(..., from_attributes=True)` after unloaded checks. Cannot combine with `attribute_map`. |
| `unloaded_attributes` | `"error"` | Only supported value in 0.5 — deferred/expired attrs raise `RowAdaptationError` |
| `attribute_map` | `None` | Model field → entity attribute (entity results only; requires `orm_validation="mapping"`) |
| `field_map` | `None` | Model field → result key (projected rows only) |

Multi-entity or entity+scalar shapes raise at plan time — project explicitly.

## SQLModel

Install the optional extra:

```bash
pip install rowguard[sqlmodel]
```

SQLModel `table=True` classes work as `table=` / `source=` the same way as
SQLAlchemy mapped classes. Keep SQLModel for persistence and `Session.exec()`;
use RowGuard when every read must be proven against a read contract.

```python
result = rowguard.select(
    session=session,
    table=User,  # SQLModel table model
    model=UserRead,
    on_reject="collect",
)
```

## Async

`aselect` / `aexecute` / `astream` accept the same ORM knobs. Validation remains
synchronous on the event loop.

## Out of scope (0.5)

- Nested relationship adaptation / graph validation
- Write-back / repair / ORM events
- Lazy-load-enabled validation (`unloaded_attributes="load"`)
- Replacing SQLModel `session.exec()`

## Next

- [Supported vs planned](../project/supported.md)
- [ORM design notes](../integrations/ORM.md)
- [SQLModel design notes](../integrations/SQLMODEL.md)
- [Why not SQLModel (positioning)](../integrations/WHY_NOT_SQLMODEL.md)
