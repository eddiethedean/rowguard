# Streaming

Use `stream()` / `astream()` when you do not want to buffer every accepted model.

## Sync

```python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,  # inspect invalid rows; omit for default pushdown
    yield_per=500,
) as stream:
    for model in stream:
        process(model)

print(stream.statistics)
print(stream.rejected)
```

## Async

```python
async with rowguard.astream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="skip",
) as stream:
    async for model in stream:
        process(model)
```

## Observers

Hooks are **sync** callables. Subclass `BaseStreamObserver` or implement
`StreamObserver`:

```python
from rowguard import BaseStreamObserver, stream


class CountingObserver(BaseStreamObserver):
    def __init__(self) -> None:
        self.accepted = 0

    def on_row_accepted(self, *, index: int, model: object) -> None:
        self.accepted += 1


observer = CountingObserver()
with stream(
    session=session,
    table=users,
    model=UserRead,
    observers=(observer,),
) as result:
    list(result)
print(observer.accepted)
```

Common hooks: `on_stream_start`, `on_row_accepted`, `on_row_rejected`,
`on_stream_complete`, `on_stream_failed`, `on_stream_closed`. Observer errors are
recorded as diagnostics and do not abort the stream.

## Lifecycle rules

- Prefer `with` / `async with` so cursors close on break, cancel, or error.
- Re-entering a closed stream raises `QueryExecutionError`.
- Raise-policy rejections update statistics before the exception is raised.
- `collect` retains rejected rows (memory grows with reject count).

## Options

- `yield_per=` — SQLAlchemy fetch size (positive integer)
- `observers=` — progress hooks

## Related

- [Performance](performance.md)
- Example: `examples/streaming.py`
- Design notes: [Streaming architecture](../architecture/STREAMING.md)
