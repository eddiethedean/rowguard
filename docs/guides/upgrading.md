# Upgrading

## 0.5 → 0.6

### New capabilities

- Rejection policies: `callback`, `quarantine`, and `log`
- Optional thresholds: `max_rejections`, `max_rejection_rate`
- Redaction / retention knobs for callback and quarantine handoff
- Async reject handlers on `aselect` / `aexecute` / `astream`
- See [Rejection policies](rejection-policies.md)

### Contract notes

- `quarantine_transaction` must be `"separate"` (the only supported value in
  0.6); other values raise `ConfigurationError` / `PlanningError`
- `on_callback_error="reject_handler"` remains an alias of `"raise"`
- Defaults are unchanged: `use_sqlrules=True`, `on_reject="raise"`

### Docs / scope

Use [Supported vs planned](../project/supported.md) as the source of truth.
Plugin registration of quarantine providers remains deferred to 0.7.0.

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

## Pre-1.0 note

Before 1.0, minor releases may include breaking changes. Read the
[Changelog](../project/changelog.md) **Upgrade notes** for each release.

## Related

- [Changelog](../project/changelog.md)
- [Installation](installation.md)
- [SQLRules pushdown](sqlrules-pushdown.md)
