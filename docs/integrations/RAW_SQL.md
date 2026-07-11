# RAW_SQL.md

:::{admonition} Status: not shipped in 0.5.0
:class: warning

This document is a **design draft for 0.8.0**. First-class raw `text()` support
is **not available** yet. 0.5 works with SQLAlchemy `Select` / `Table` sources.
See [Supported vs planned](../project/supported.md).
:::

# RowGuard Raw SQL Integration

## Purpose

RowGuard primarily targets SQLAlchemy Core expressions. However, many applications use handwritten SQL for reporting, analytics, legacy systems, or performance tuning.

**When shipped**, RowGuard will support raw SQL while preserving its central guarantee:

> Every returned row is explicitly validated against the requested Pydantic model.

Raw SQL is simply another execution source.

---

# Design Philosophy

Raw SQL support should be:

- Explicit
- Safe
- Parameterized
- Observable

RowGuard should never parse, rewrite, or concatenate SQL strings.

SQLAlchemy remains responsible for SQL execution and parameter binding.

---

# Architecture

```text
SQL Text
    │
    ▼
SQLAlchemy text()
    │
    ▼
Bound Parameters
    │
    ▼
Database
    │
    ▼
Result Rows
    │
    ▼
Row Adapter
    │
    ▼
Pydantic Validation
```

---

# Supported APIs

Preferred entry point:

```python
from sqlalchemy import text

stmt = text(
    "SELECT user_id AS id, display_name AS name, age "
    "FROM users WHERE tenant_id=:tenant_id"
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    parameters={"tenant_id": tenant_id},
    model=UserRead,
)
```

---

# Result Shape

Raw SQL should expose predictable column names.

Preferred techniques:

- SQL aliases
- Explicit field maps

Example:

```sql
SELECT
    user_id AS id,
    display_name AS name
```

---

# Parameter Binding

Always use bound parameters.

Good:

```python
text("SELECT * FROM users WHERE id=:id")
```

Never:

```python
f"SELECT * FROM users WHERE id={user_id}"
```

---

# SQLRules Integration

Automatic SQLRules pushdown is disabled by default for arbitrary SQL because RowGuard cannot safely rewrite SQL text.

Pydantic validation still executes for every returned row.

---

# Streaming

Raw SQL supports the same streaming interface as Core execution.

---

# Rejection Handling

All standard rejection policies are supported:

- raise
- collect
- skip
- callback
- quarantine

---

# Diagnostics

Suggested diagnostics:

- statement type
- parameter names
- result keys
- pushdown disabled
- field mappings

Parameter values should never be logged automatically.

---

# Security

Recommendations:

- Always use bound parameters.
- Never concatenate SQL.
- Restrict SQL to trusted application code.
- Do not expose raw SQL from untrusted users.

---

# Error Handling

Suggested hierarchy:

```text
RowGuardError
└── RawSQLError
    ├── InvalidRawSQLShapeError
    ├── MissingResultColumnError
    ├── InvalidFieldMapError
    └── RawSQLExecutionError
```

---

# Testing

Tests should verify:

- parameter binding
- aliases
- field maps
- streaming
- rejection handling
- diagnostics
- SQLite
- PostgreSQL

---

# MVP Scope

Initial support:

- SQLAlchemy text()
- Bound parameters
- Row adaptation
- Pydantic validation
- Streaming
- Rejection handling

Deferred:

- SQL parsing
- Query rewriting
- Automatic SQLRules pushdown

---

# Design Principles

- SQLAlchemy owns SQL execution.
- Validation always occurs after execution.
- Parameterization is mandatory.
- Raw SQL is explicit and opt-in.
- Never rewrite arbitrary SQL.
