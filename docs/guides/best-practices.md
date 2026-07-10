# Best practices

Practical guidance for 0.4.0 Core usage.

## Prefer projection models

Validate **read models** (the columns you select), not full persistence entities.
Smaller models are faster to validate and clearer contracts.

## Choose rejection policy deliberately

| Situation | Policy |
| --- | --- |
| Tests / strict APIs | `raise` (default) |
| ETL / audit of bad rows | `collect` |
| Best-effort streaming | `skip` |

Remember: under `skip`, `has_rejections` may be true while `rejected` is empty.
See [Rejection policies](rejection-policies.md).

## Know your pushdown setting

Default `use_sqlrules=True` filters in SQL. Use `False` when you need Python-side
rejected rows. See [SQLRules pushdown](sqlrules-pushdown.md).

## Always context-manage streams

```python
with rowguard.stream(...) as stream:
    for model in stream:
        ...

async with rowguard.astream(...) as stream:
    async for model in stream:
        ...
```

Bare iteration is weaker under async cancellation.

## Keep async models lean

Pydantic runs on the event loop. Heavy validators can stall other coroutines.
See [Async](async.md).

## Pass exactly one execution handle

Provide `session=` **or** `connection=`, never both.

## Inspect plans in tests

Use `compile_plan(...)` to assert pushdown / statement shape without hitting the
database.

## Related

- [Error catalog](../reference/errors.md)
- [Supported vs planned](../project/supported.md)
