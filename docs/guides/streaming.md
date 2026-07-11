# Streaming

Use `stream()` / `astream()` when you do not want to buffer every accepted model.

## Sync

```python
with rowguard.stream(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
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

## Lifecycle rules

- Prefer `with` / `async with` so cursors close on break, cancel, or error.
- Re-entering a closed stream raises `QueryExecutionError`.
- Raise-policy rejections update statistics before the exception is raised.
- Observers (`StreamObserver` / `BaseStreamObserver`) are sync callables in 0.5.

## Options

- `yield_per=` — SQLAlchemy fetch size (must be a positive integer)
- `observers=` — progress hooks

## Deep dive

- [Streaming architecture](../architecture/STREAMING.md)
- Example: `examples/streaming.py`
