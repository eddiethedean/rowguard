# Performance

Practical guidance for {{ release }}. For deep design notes see
[Performance architecture](../architecture/PERFORMANCE.md) (maintainer draft).

## Prefer projections

For ORM / SQLModel, select only the columns you validate:

```python
await rowguard.aexecute(
    session=session,
    statement=select(User.id, User.name, User.age),
    source=User,
    model=UserRead,
)
```

Entity selects load full instances and are heavier.

## Use SQLRules pushdown when you do not need rejected payloads

Default `use_sqlrules=True` reduces rows fetched. Turn it off only when you must
inspect invalid rows in Python.

## Stream large result sets

- Buffered `select` / `aselect` retain **all** accepted models (and collected
  rejections).
- `stream` / `astream` do **not** retain accepted models.
- `on_reject="collect"` still retains every rejected row—use `skip` or raise for
  high-reject streams.

## Async: validation blocks the event loop

Only DB I/O is awaited. Keep read models lean on hot `astream` paths.

## Precompile rules for hot plans

Pass `compiled_rules=` from a prior `compile_plan` / SQLRules compile when the
same model+source is planned repeatedly.

## Checklist

| Situation | Prefer |
| --- | --- |
| Large N, few rejects | `stream` + pushdown on |
| Need rejected payloads | `use_sqlrules=False` + `collect` (watch memory) |
| Hot async path | lean models; avoid heavy validators |
| Repeated plans | `compiled_rules=` / inspect `compile_plan` |

## Related

- [Streaming](streaming.md)
- [SQLRules pushdown](sqlrules-pushdown.md)
- [Best practices](best-practices.md)
