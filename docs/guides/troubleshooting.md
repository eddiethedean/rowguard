# Troubleshooting

## `rejected` is empty but the table has invalid rows

Default `use_sqlrules=True` likely filtered them in SQL. Set
`use_sqlrules=False` and `on_reject="collect"`. See
[SQLRules pushdown](sqlrules-pushdown.md) and the
[FAQ](faq.md#why-do-invalid-rows-disappear-with-the-default-settings).

## `RowValidationError` on the first bad row

Default `on_reject="raise"`. Use `collect` or `skip` if you need to continue.

## `ConfigurationError: Provide exactly one of session or connection`

Pass **either** `session=` **or** `connection=`, not both and not neither.

## `ConfigurationError: Pass exactly one of table= or statement=`

`stream` / `astream` require exactly one of `table=` or `statement=`.

## `ModuleNotFoundError: aiosqlite` / `sqlmodel`

Install extras: `pip install "rowguard[async]"` or `"rowguard[sqlmodel]"`.
See [Installation](installation.md).

## `QueryExecutionError: ... is closed and cannot be reused`

Streams are single-use. Create a new `stream()` / `astream()` after close.

## Stream cursor still open after early `break`

Prefer:

```python
with rowguard.stream(...) as stream:
    for model in stream:
        ...
```

Always prefer `async with` for `astream` (cancellation cleanup).

## Coverage / CI fails but docs look fine

```bash
pip install -e ".[docs]"
make docs
```

## Still stuck?

- [FAQ](faq.md)
- [Upgrading](upgrading.md)
- [Contributing](../developer/CONTRIBUTING.md)
- GitHub Issues
