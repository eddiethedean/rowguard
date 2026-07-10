# REFLECTION.md

# RowGuard Reflection

## Purpose

Reflection allows RowGuard to operate against existing databases without
requiring users to manually define every SQLAlchemy table.

RowGuard itself does **not** implement schema reflection. Instead, it integrates
with SQLAlchemy's reflection facilities and consumes the resulting metadata.

Reflection is a convenience for discovering database structure. Validation
continues to be driven by Pydantic models and SQLRules.

---

# Goals

Reflection support should:

- Work with reflected SQLAlchemy `Table` objects.
- Integrate cleanly with SQLAlchemy's `MetaData`.
- Support existing databases.
- Require no ORM mappings.
- Preserve SQLRules pushdown.
- Remain dialect-neutral.

Reflection should **not**:

- Generate Pydantic models automatically (MVP).
- Modify database schemas.
- Infer business rules.
- Replace migrations.

---

# Architecture

```text
Database
    │
    ▼
SQLAlchemy Reflection
    │
    ▼
Reflected Table
    │
    ▼
RowGuard Planning
    │
    ▼
SQLRules Pushdown
    │
    ▼
Execution
    │
    ▼
Pydantic Validation
```

---

# Basic Usage

```python
metadata = MetaData()

users = Table(
    "users",
    metadata,
    autoload_with=engine,
)

result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)
```

Once reflected, RowGuard treats the table exactly like a declaratively defined
SQLAlchemy Core table.

---

# Supported Objects

The initial implementation should support reflected:

- Tables
- Columns
- Primary keys
- Foreign keys
- Index metadata (diagnostics only)

Future support may leverage:

- Views
- Materialized views
- Computed columns
- Generated columns

---

# Column Mapping

Reflection provides database column names, not Pydantic field names.

Applications may provide explicit mappings:

```python
field_map = {
    "id": "user_id",
    "name": "display_name",
}
```

or use SQL labels:

```python
stmt = select(
    users.c.user_id.label("id"),
    users.c.display_name.label("name"),
)
```

Labels are preferred for complex queries.

---

# SQLRules Integration

Reflected columns work normally with SQLRules.

```python
compiled = sqlrules.compile(
    model=UserRead,
    table=users,
)
```

SQLRules remains responsible for translating supported constraints into SQL.

---

# Reflection Caching

Reflection is relatively expensive.

Applications should normally reflect metadata once during startup and reuse the
resulting `MetaData` and `Table` objects.

RowGuard should not repeatedly reflect schemas internally.

---

# Dynamic Schemas

Reflection makes RowGuard suitable for:

- Legacy databases
- Customer-managed databases
- Plug-in databases
- Multi-tenant systems with varying schemas

Applications remain responsible for selecting the correct reflected metadata.

---

# Error Handling

Suggested errors:

```text
RowGuardError
└── ReflectionError
    ├── ReflectedTableNotFoundError
    ├── ReflectionConfigurationError
    ├── MissingColumnMappingError
    └── UnsupportedReflectedObjectError
```

Database reflection failures originating from SQLAlchemy should remain visible as
the underlying cause.

---

# Diagnostics

Useful diagnostics include:

- reflected table name
- schema name
- reflected column count
- missing field mappings
- SQLRules pushdown summary

---

# Performance

Recommendations:

- Reflect once.
- Reuse immutable `Table` objects.
- Cache execution plans separately from metadata.
- Avoid reflection during request handling.

---

# Security

Reflection exposes database metadata.

Applications should:

- Reflect only authorized schemas.
- Avoid exposing reflected metadata to untrusted users.
- Treat schema names as configuration, not user input.

---

# Testing

Tests should cover:

- reflected tables
- multiple schemas
- legacy column names
- SQLRules integration
- field mappings
- reflected joins
- SQLite and PostgreSQL

---

# MVP Scope

Initial support:

- Reflected SQLAlchemy Core tables
- Existing reflected metadata
- SQLRules integration
- Explicit field mappings
- Normal RowGuard execution

Deferred:

- Automatic Pydantic model generation
- Reflection helpers
- Schema diffing
- Reverse engineering

---

# Design Principles

- SQLAlchemy owns reflection.
- RowGuard consumes reflected metadata.
- Reflection is optional.
- Validation always comes from Pydantic.
- Reflection should never change execution semantics.
