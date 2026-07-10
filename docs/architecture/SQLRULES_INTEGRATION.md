# SQLRULES_INTEGRATION.md

# SQLRules Integration

## Purpose

This document defines how RowGuard integrates with SQLRules.

The relationship between the two libraries is intentionally layered:

- **SQLRules** compiles supported Pydantic constraints into SQLAlchemy WHERE expressions.
- **RowGuard** executes queries, validates returned rows with Pydantic, and manages rejected rows.

Neither project should absorb the responsibilities of the other.

---

# Architecture

```text
Pydantic Model
      │
      ▼
SQLRules
Compile SQL-safe constraints
      │
      ▼
WHERE Expressions
      │
      ▼
RowGuard Query Builder
      │
      ▼
SQLAlchemy Statement
      │
      ▼
Database
      │
      ▼
RowGuard
Row Adaptation
      │
      ▼
Pydantic Validation
      │
      ├── Valid Models
      └── Rejected Rows
```

SQLRules performs **compile-time** work.

RowGuard performs **runtime** work.

---

# Responsibilities

## SQLRules

Responsible for:

- Inspecting Pydantic metadata
- Extracting supported constraints
- Producing SQLAlchemy boolean expressions
- Translator plugins
- Dialect-aware SQL compilation

Not responsible for:

- Query execution
- Database sessions
- Row validation
- Rejection handling

---

## RowGuard

Responsible for:

- Building SQLAlchemy statements
- Executing queries
- Streaming
- Row adaptation
- Pydantic validation
- Rejection policies
- Diagnostics
- Statistics

Not responsible for:

- Compiling constraints
- Translating Pydantic metadata into SQL

---

# Integration Contract

RowGuard should treat SQLRules as a dependency with a narrow public interface.

Preferred interaction:

```python
rules = sqlrules.compile(
    model=UserRead,
    table=users,
)

expressions = sqlrules.where(rules)
```

RowGuard should never depend on SQLRules internals such as compiler phases,
intermediate representations, or translator implementations.

---

# Query Construction

Typical flow:

```python
stmt = select(users)

rules = sqlrules.compile(UserRead, users)

stmt = stmt.where(*sqlrules.where(rules))
```

Additional user-supplied filters are combined naturally:

```python
stmt = stmt.where(users.c.active == True)
```

The ordering of WHERE expressions should not affect semantics.

---

# SQL Pushdown

SQLRules should push only constraints that have deterministic SQL equivalents.

Examples:

- gt
- ge
- lt
- le
- multiple_of
- min_length
- max_length
- Literal
- Enum

Constraints without safe SQL equivalents remain the responsibility of
Pydantic validation.

---

# Validation Remains Required

Even after SQL pushdown, RowGuard always validates returned rows.

Reasons include:

- Database drift
- Trigger behavior
- Views
- Joins
- Database-specific semantics
- Constraints not representable in SQL

SQLRules reduces candidate rows.

RowGuard establishes trust.

---

# Unsupported Constraints

SQLRules may report unsupported constraints.

Depending on compiler configuration:

- raise
- warn
- ignore

RowGuard should surface these diagnostics but continue to validate rows using
Pydantic.

An unsupported SQL constraint does **not** imply that validation should be
skipped.

---

# Diagnostics

RowGuard should preserve SQLRules diagnostics.

Examples:

- constraints translated
- constraints skipped
- translator warnings
- dialect decisions

Diagnostics become part of the final QueryResult.

---

# Caching

SQLRules may cache compilation work.

RowGuard should treat compiled rule dictionaries as immutable.

Possible optimization:

```python
compiled = sqlrules.compile(UserRead, users)

rowguard.select(
    session=session,
    statement=stmt,
    compiled_rules=compiled,
)
```

This avoids recompilation when repeatedly querying the same model.

---

# Execution Plans

Execution plans should reference compiled SQLRules output rather than the
original Pydantic model whenever practical.

Example:

```text
ExecutionPlan
    statement
    compiled_rules
    model
    reject_policy
```

This separates planning from execution.

---

# Version Compatibility

Initial compatibility target:

- SQLRules 0.x
- RowGuard 0.x

Before RowGuard 1.0, SQLRules should reach a stable public API.

RowGuard should depend only on documented SQLRules entry points.

---

# Error Handling

Compilation failures remain SQLRules errors.

Execution failures remain RowGuard errors.

Example:

```text
SQLRulesError
    UnsupportedConstraintError

RowGuardError
    QueryExecutionError
    ValidationFailure
```

Errors should not be wrapped unnecessarily.

---

# Optional Usage

RowGuard should allow SQLRules integration to be disabled.

Example:

```python
rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    use_sqlrules=False,
)
```

Behavior:

- No SQL pushdown
- Full Pydantic validation
- Identical rejection handling

This supports debugging and performance comparisons.

---

# Future Integration

Future SQLRules features may automatically benefit RowGuard:

- new translators
- new dialect plugins
- performance improvements
- compiler caching

RowGuard should gain these benefits without architectural changes.

---

# Testing Requirements

Integration tests should verify:

- SQLRules expressions are applied
- Additional WHERE clauses compose correctly
- Unsupported constraints still validate in Pydantic
- Diagnostics propagate
- Cached compilations behave identically
- SQLRules disabled mode
- Multiple dialects

---

# Design Principles

- Clear separation of responsibilities.
- Depend only on SQLRules' public API.
- SQL pushdown is an optimization, not a replacement for validation.
- Preserve diagnostics across library boundaries.
- Keep the integration thin, explicit, and testable.
