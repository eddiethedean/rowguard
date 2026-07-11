# SQLRules pushdown

RowGuard defaults to `use_sqlrules=True`. That is powerful—and the most common
source of “validation isn’t working” confusion.

**SQLRules** is a separate library that compiles Pydantic field constraints into
SQLAlchemy `WHERE` expressions. RowGuard depends on `sqlrules>=1.0,<2`.

## What pushdown does

When enabled, RowGuard asks SQLRules to compile **supported** Pydantic
constraints into SQL `WHERE` clauses.

Example: `age: Annotated[int, Field(ge=18)]` may become `WHERE age >= 18`.

Rows that fail those constraints **never leave the database**, so they never
appear in `result.rejected` or stream statistics as Python-side rejections.

Pushdown is an **optimization**, not authorization. Express tenant / ACL filters
as explicit SQL or `where=` clauses.

## Capability matrix (practical)

Exact coverage is defined by SQLRules. As a rule of thumb for {{ release }}:

| Constraint style | Typically pushed down? | Notes |
| --- | --- | --- |
| `Field(ge=)`, `le=`, `gt=`, `lt=` on ints/floats | Yes | Common numeric bounds |
| `Field(min_length=)`, `max_length=` on strings | Often | Depends on SQLRules + dialect |
| `Field(pattern=)` / regex | Sometimes | Dialect-sensitive |
| `Literal[...]` / enums | Often | When mapped to comparable columns |
| `@field_validator` / `@model_validator` | No | Python-only |
| Computed fields / properties | No | Python-only |
| Cross-field model logic | No | Use `where=` or Python validation |

When unsure: run once with `use_sqlrules=False` and compare `rows_read` /
`rejected`, or inspect `compile_plan(...).pushdown_plan`.

## When to use `True` (default)

- Production reads where invalid candidates should not waste bandwidth
- You only need accepted models

## When to use `False`

- Debugging validation failures
- Auditing / ETL with `on_reject="collect"`
- Tests that assert on `rejected`
- Constraints SQLRules cannot push

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,
)
print(result.rejected)
```

## Mental model

```text
use_sqlrules=True
  → DB filters what it can
  → Pydantic validates remaining rows
  → rejected only for rows that still failed in Python

use_sqlrules=False
  → DB returns candidates without those constraint filters
  → Pydantic validates every returned row
  → rejected reflects Python-side failures
```

## Related

- [FAQ](faq.md#why-do-invalid-rows-disappear-with-the-default-settings)
- [Troubleshooting](troubleshooting.md)
- [Performance](performance.md)
- [Best practices](best-practices.md)
