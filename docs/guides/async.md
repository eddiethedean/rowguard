# Async

RowGuard ships first-class async APIs over SQLAlchemy `AsyncSession` and
`AsyncConnection`.

| Sync | Async |
| --- | --- |
| `select` | `aselect` |
| `execute` | `aexecute` |
| `stream` | `astream` → `AsyncStreamResult` |

```bash
pip install "rowguard[async]"
```

Pass exactly one of `session=` or `connection=` (`AsyncSession` /
`AsyncConnection`).

## Default path

```python
result = await rowguard.aselect(
    session=session,
    table=users,
    model=UserRead,
)
# use_sqlrules=True, on_reject="raise" by default
```

## Inspect rejections

```python
result = await rowguard.aselect(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,
)
print(result.rejected)
```

## Streaming

```python
async with rowguard.astream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="skip",
) as stream:
    async for model in stream:
        ...
```

`astream()` returns immediately; work starts on `async with` / `async for`.

## Event-loop note

Only database I/O is awaited. Pydantic validation runs synchronously on the
event loop and can block under heavy models. See [Performance](performance.md).

## Not in 0.5

- Async callback / quarantine reject handlers (0.6)
- Thread-pool wrappers around sync APIs
- Required asyncpg CI matrix (sqlite+aiosqlite is the async CI driver)

## Related

- Example: `examples/async_basic.py`
- [ORM and SQLModel](orm-sqlmodel.md) (async entity/`astream` supported)
- Design notes: [Async architecture](../architecture/ASYNC.md)
