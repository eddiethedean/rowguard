# Upgrading

## 0.4 → 0.5

### Dependency

RowGuard 0.5 requires **SQLRules 1.x**:

```bash
pip install "sqlrules>=1.0.0,<2"
```

Older sqlrules majors are unsupported.

### New capabilities

- ORM mapped-class and SQLModel table-model reads (`table=` / `source=`)
- `orm_validation=` / `unloaded_attributes=` / `attribute_map=`
- `RejectedRow.source_identity` on entity adaptation failures
- See [ORM and SQLModel](orm-sqlmodel.md)

### Unchanged defaults

- `use_sqlrules=True` — pushdown still on by default
- `on_reject="raise"` — still the default policy

### Docs / scope

Use [Supported vs planned](../project/supported.md) as the source of truth.
Callback / quarantine / plugins remain deferred.

## Pre-1.0 note

Before 1.0, minor releases may include breaking changes. Read the
[Changelog](../project/changelog.md) **Upgrade notes** for each release.

## Related

- [Changelog](../project/changelog.md)
- [Installation](installation.md)
- [SQLRules pushdown](sqlrules-pushdown.md)
