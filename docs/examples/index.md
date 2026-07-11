# Examples

Runnable scripts (see also
[`examples/README.md`](https://github.com/eddiethedean/rowguard/blob/main/examples/README.md)):

| Script | Lesson |
| --- | --- |
| [sqlrules_default.py](https://github.com/eddiethedean/rowguard/blob/main/examples/sqlrules_default.py) | Library defaults (`use_sqlrules=True`) |
| [basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/basic.py) | Inspect rejections (`use_sqlrules=False`, `collect`) |
| [streaming.py](https://github.com/eddiethedean/rowguard/blob/main/examples/streaming.py) | Sync `stream` + retained rejections |
| [async_basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/async_basic.py) | `aselect` / `astream` (`rowguard[async]`) |
| [orm_projected.py](https://github.com/eddiethedean/rowguard/blob/main/examples/orm_projected.py) | ORM projection (`source=User`) |
| [orm_entity.py](https://github.com/eddiethedean/rowguard/blob/main/examples/orm_entity.py) | Entity `table=User` |
| [sqlmodel_basic.py](https://github.com/eddiethedean/rowguard/blob/main/examples/sqlmodel_basic.py) | SQLModel (`rowguard[sqlmodel]`) |

```bash
make install
python examples/sqlrules_default.py
python examples/basic.py
```

Full copy-paste walkthrough: [Quickstart](../guides/quickstart.md).

## `validate_rows` (no SQL)

```python
result = rowguard.validate_rows(
    rows=[{"id": 1, "name": "Ada", "age": 37}, {"id": 2, "name": "Legacy", "age": 12}],
    model=UserRead,
    on_reject="collect",
)
```

## `compile_plan` (inspect without executing)

```python
plan = rowguard.compile_plan(table=users, model=UserRead)
print(plan.pushdown_plan.enabled, plan.execution_id)
```

## Raise policy

```python
try:
    rowguard.select(
        session=session,
        table=users,
        model=UserRead,
        on_reject="raise",
        use_sqlrules=False,
    )
except rowguard.RowValidationError as exc:
    print(exc.row_index, exc.validation_error)
```

## Next

- [Streaming observers](../guides/streaming.md#observers)
- [Async](../guides/async.md)
- [ORM and SQLModel](../guides/orm-sqlmodel.md)
