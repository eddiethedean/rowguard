# SQLRules pushdown

RowGuard defaults to `use_sqlrules=True`. That is powerful—and the most common
source of “validation isn’t working” confusion.

## What pushdown does

When enabled, RowGuard asks [SQLRules](https://github.com/eddiethedean/sqlrules)
to compile **supported** Pydantic constraints into SQL `WHERE` clauses.

Example: `age: Annotated[int, Field(ge=18)]` may become `WHERE age >= 18`.

Rows that fail those constraints **never leave the database**, so they never
appear in `result.rejected` or stream statistics as Python-side rejections.

## When to use `True` (default)

- Production reads where invalid candidates should not waste bandwidth
- You trust SQLRules coverage for the constraints you care about
- You only need accepted models (and are fine not seeing rejected rows in Python)

## When to use `False`

- Debugging validation failures
- Auditing / ETL where you need `on_reject="collect"` to retain bad rows
- Quickstarts and tests that assert on `rejected`
- Constraints SQLRules cannot push (complex validators, custom logic)

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
    use_sqlrules=False,  # invalid rows reach Pydantic
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
- [SQLRules integration (design)](../architecture/SQLRULES_INTEGRATION.md)
- [Best practices](best-practices.md)
