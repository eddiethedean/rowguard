# Troubleshooting

## `ConfigurationError: Provide exactly one of session or connection`

Pass **either** `session=` **or** `connection=`, not both and not neither.

## `ConfigurationError: Pass exactly one of table= or statement=`

`stream` / `astream` require exactly one of `table=` or `statement=`.

## `QueryExecutionError: ... is closed and cannot be reused`

Streams are single-use. Create a new `stream()` / `astream()` call after close.

## Stream cursor still open after early `break`

Prefer:

```python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
```

Bare `for` / `async for` without a context manager relies on iterator finalizers,
which are less reliable under async cancellation. Always prefer `async with` for
`astream`.

## Coverage / CI fails but docs look fine

Docs CI runs `make docs` (Sphinx `-W`). Locally:

```bash
pip install -e ".[docs]"
make docs
```

## SQLRules / pushdown surprises

See [FAQ](faq.md#why-do-invalid-rows-disappear-with-the-default-settings) and
[SQLRules integration](../architecture/SQLRULES_INTEGRATION.md).

## Still stuck?

- [FAQ](faq.md)
- [Contributing](../developer/CONTRIBUTING.md)
- GitHub Issues
