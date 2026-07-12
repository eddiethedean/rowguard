# PARTIAL_VALIDATION.md

:::{admonition} Status: not shipped in 0.6.0
:class: caution

This document is a **design draft**. Partial / subset-field validation is **not**
available in the current release. See [Supported vs planned](../project/supported.md).
:::

# RowGuard Partial Validation

## Purpose

Partial validation allows RowGuard to validate only a subset of a model's fields
when the query intentionally returns a partial projection.

This is an explicit feature intended for read optimization. It must never weaken
the guarantees of full-model validation without the caller opting in.

---

# Philosophy

There are two fundamentally different operations:

1. **Full validation** — prove a row satisfies the complete model contract.
2. **Partial validation** — prove a row satisfies only a declared subset of that contract.

These operations must never be confused.

---

# Motivation

Many applications issue projections:

```sql
SELECT id, name
FROM users
```

instead of:

```sql
SELECT *
FROM users
```

Loading only required columns:

- reduces network traffic
- improves query performance
- reduces memory usage
- enables index-only scans
- avoids unnecessary joins

The challenge is that a normal Pydantic model may require fields that were never
selected.

---

# Explicit API

Partial validation should always be opt-in.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    validation="partial",
    fields={
        "id",
        "name",
    },
)
```

or

```python
projection = UserSummary

result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    projection=projection,
)
```

---

# What Partial Validation Means

Given:

```python
class UserRead(BaseModel):
    id: int
    name: str
    age: int
    email: EmailStr
```

and:

```sql
SELECT id, name
```

Partial validation proves only:

- id is valid
- name is valid

It makes **no statement** about:

- age
- email

---

# Recommended Pattern

The preferred approach is a dedicated projection model.

```python
class UserSummary(BaseModel):
    id: int
    name: str
```

instead of attempting to partially validate `UserRead`.

Projection models are:

- explicit
- reusable
- statically typed
- easier to document
- easier to test

Partial validation should remain available for dynamic scenarios.

---

# Relationship to SQLRules

SQLRules only compiles constraints for fields participating in the validation
contract.

If only:

```python
{id, name}
```

are validated, only those fields contribute SQL pushdown.

---

# Missing Fields

Fields intentionally excluded from validation are not treated as missing.

Fields expected by the declared partial contract but absent from the result
remain validation errors.

---

# Statistics

Suggested metrics:

- rows partially validated
- rows fully validated
- fields validated
- fields skipped
- rejection count
- partial validation duration

---

# Error Reporting

Validation errors should identify:

- requested validation mode
- validated field set
- skipped field set
- projection model (if used)

This prevents confusion when debugging.

---

# Performance

Partial validation may improve performance by:

- selecting fewer columns
- validating fewer fields
- reducing nested object creation
- reducing JSON decoding

The greatest gains usually come from smaller SQL projections rather than the
validation step itself.

---

# Security

Partial validation must never imply that omitted fields satisfy the full model.

Documentation should clearly distinguish:

> "Validated subset"

from

> "Validated complete model"

---

# Testing

Tests should verify:

- subset validation
- projection models
- missing projected fields
- SQLRules pushdown
- nested projections
- aliases
- strict mode
- streaming
- async execution

---

# MVP Scope

Initial support:

- Explicit partial mode
- Explicit validated field list
- Projection models
- SQLRules subset compilation
- Statistics
- Diagnostics

Deferred:

- Automatic projection inference
- Partial nested validation planning
- Field dependency analysis

---

# Design Principles

- Full validation is the default.
- Partial validation is always explicit.
- Prefer projection models.
- Never overstate validation guarantees.
- Keep SQL projection and validation scope aligned.
