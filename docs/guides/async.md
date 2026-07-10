# Async

RowGuard 0.4 ships first-class async APIs over SQLAlchemy `AsyncSession` and
`AsyncConnection`.

| Sync | Async |
| --- | --- |
| `select` | `aselect` |
| `execute` | `aexecute` |
| `stream` | `astream` → `AsyncStreamResult` |

Install extras:

```bash
pip install "rowguard[async]"
```

## Buffered

```python
result = await rowguard.aselect(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

Returns the same `QueryResult` type as sync.

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
event loop and can block under heavy models. Prefer lean read models on hot
paths.

## Not in 0.4

- Async callback / quarantine reject handlers (0.6)
- Thread-pool wrappers around sync APIs
- Required asyncpg CI matrix (sqlite+aiosqlite is the 0.4 driver)

## Deep dive

- [Async architecture](../architecture/ASYNC.md)
- Example: `examples/async_basic.py`
