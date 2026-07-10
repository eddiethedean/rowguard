# QUERY_COMPILATION.md

# RowGuard Query Compilation

## Purpose

Query compilation is the planning phase that transforms a user's request into an
immutable execution plan. Unlike execution, compilation performs no database
I/O. Its responsibilities are to normalize inputs, integrate SQLRules,
construct a SQLAlchemy statement, and prepare all metadata required by the
runtime.

Compilation should be deterministic, cache-friendly, and independently testable.

---

# Compilation vs Execution

```text
Application Request
        │
        ▼
 Query Compilation
        │
        ▼
  ExecutionPlan
        │
        ▼
 Query Execution
        │
        ▼
 Database
```

Compilation decides **what** will be executed.

Execution decides **when** and **how** it is executed.

---

# Inputs

A compilation request may include:

- SQLAlchemy `Table`
- SQLAlchemy `Select`
- ORM model
- `Session` or `AsyncSession` (for dialect/context only; no execution)
- Target Pydantic model
- Additional WHERE expressions
- SQLRules configuration
- Field mappings
- Rejection policy
- Diagnostics configuration

---

# Compilation Stages

## 1. Normalize Inputs

Resolve the incoming request into a canonical internal representation.

Examples:

- Convert a table into a `select(table)`
- Validate supplied SQLAlchemy statements
- Resolve target model

---

## 2. Build Statement

If the caller supplied a table:

```python
stmt = select(users)
```

If the caller supplied a statement:

```python
stmt = existing_statement
```

The compiler should preserve existing clauses whenever possible.

---

## 3. Compile SQLRules

When enabled:

```python
compiled = sqlrules.compile(
    model=UserRead,
    table=users,
)
```

This stage never executes SQL.

---

## 4. Merge Filters

SQLRules expressions and user-provided expressions are merged into a single
statement.

Conceptually:

```python
stmt = stmt.where(
    *sqlrules.where(compiled),
    *user_filters,
)
```

The merge should preserve SQLAlchemy composability.

---

## 5. Resolve Adaptation

Precompute:

- field mappings
- alias mappings
- duplicate-key strategy
- adapter configuration

This avoids repeated work during execution.

---

## 6. Resolve Validation

Prepare:

- target model
- validation context
- strictness configuration

No validation occurs yet.

---

## 7. Resolve Rejection Policy

Prepare the configured reject handler and immutable rejection configuration.

---

## 8. Build Execution Plan

The final output is an immutable execution plan.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    statement: Select
    model: type[BaseModel]
    compiled_rules: object | None
    row_adapter: RowAdapter
    validator: Validator
    reject_handler: RejectHandler
    statistics: StatisticsPlan
```

Execution plans should be reusable.

---

# Caching

Compilation is a good candidate for caching.

Potential cache key:

- model type
- statement shape
- SQLRules options
- adapter configuration

Execution-specific state must not be cached.

---

# Diagnostics

Compilation diagnostics may include:

- SQLRules constraints applied
- constraints skipped
- alias resolution
- field mappings
- adapter selection
- statement transformations

Diagnostics become part of the execution result.

---

# Error Handling

Compilation errors occur before database access.

Examples:

- invalid field mappings
- unsupported SQLRules configuration
- incompatible adapter
- ambiguous result mappings

These errors should be reported immediately.

---

# Performance

Goals:

- O(fields + constraints)
- No database I/O
- Immutable outputs
- Minimal allocations
- Reusable execution plans

---

# Testing

Compilation tests should verify:

- statement generation
- SQLRules integration
- filter merging
- adapter selection
- execution plan contents
- cache correctness
- deterministic output

---

# MVP Scope

Initial implementation:

- table → select()
- existing statement support
- SQLRules integration
- field-map planning
- immutable execution plans
- diagnostics

Deferred:

- advanced plan caching
- optimizer passes
- cost estimation
- distributed planning

---

# Design Principles

- Planning and execution are separate concerns.
- Compilation performs no I/O.
- Execution plans are immutable.
- SQLRules is the only source of SQL constraint compilation.
- Compilation should be fast enough to cache, but simple enough that caching is optional.
