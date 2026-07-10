# FILTER_PUSHDOWN.md

# RowGuard Filter Pushdown

## Purpose

Filter pushdown is the process of moving supported Pydantic constraints into the
database query so invalid candidate rows can be excluded before they are
retrieved.

RowGuard delegates constraint compilation to SQLRules and applies the resulting
SQLAlchemy expressions to the query plan.

Filter pushdown is an optimization and data-reduction mechanism. It is **not** a
replacement for Pydantic validation.

---

# Core Principle

```text
Pydantic Model
      │
      ▼
SQLRules
Compile supported constraints
      │
      ▼
SQLAlchemy WHERE expressions
      │
      ▼
Database filters candidate rows
      │
      ▼
RowGuard validates every returned row
```

SQLRules determines what can be represented safely in SQL.

RowGuard remains responsible for validating all returned rows.

---

# Goals

Filter pushdown should:

- Reduce network transfer.
- Reduce application memory usage.
- Reduce the number of rows requiring Pydantic validation.
- Preserve the semantics of supported Pydantic constraints.
- Remain explicit and observable.
- Compose with existing SQLAlchemy filters.

Filter pushdown must not:

- Approximate unsupported validation rules.
- Weaken the Pydantic contract.
- Mutate the source Pydantic model.
- Execute queries.
- Hide skipped constraints.

---

# Responsibility Boundary

## SQLRules

SQLRules is responsible for:

- Inspecting supported Pydantic field metadata.
- Compiling deterministic constraints into SQLAlchemy expressions.
- Reporting unsupported constraints.
- Handling dialect-specific translation through its own extension system.

## RowGuard

RowGuard is responsible for:

- Selecting whether pushdown is enabled.
- Supplying the model and SQLAlchemy column source.
- Applying compiled expressions to the statement.
- Preserving SQLRules diagnostics.
- Validating all returned rows with Pydantic.

RowGuard should never duplicate SQLRules' constraint translation logic.

---

# Pushdown Modes

RowGuard should expose an explicit pushdown mode.

```python
pushdown="safe"
```

Suggested modes:

## safe

The default.

Apply only constraints SQLRules can translate with deterministic semantics.

Unsupported constraints remain application-side validation rules.

## disabled

Do not invoke SQLRules.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    pushdown="disabled",
)
```

Every selected row is still validated by Pydantic.

This mode is useful for:

- Debugging.
- Comparing performance.
- Queries whose selected columns do not align with the source table.
- Applications that deliberately want validation-only behavior.

## strict

Require every eligible declared constraint to be successfully pushed down.

If SQLRules reports an unsupported or unresolved constraint, query compilation
fails.

This mode is useful when an application requires database-side enforcement as
part of its execution policy.

## best_effort

Apply supported filters and record unsupported constraints as diagnostics.

This behaves similarly to `safe`, but may allow more permissive plugin-driven or
dialect-specific translations in future versions.

The MVP may implement only `safe` and `disabled`.

---

# Example

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field

class UserRead(BaseModel):
    age: Annotated[int, Field(ge=18, le=65)]
    status: Literal["active", "pending"]
```

SQLRules may produce expressions equivalent to:

```python
users.c.age >= 18
users.c.age <= 65
users.c.status.in_(["active", "pending"])
```

RowGuard applies them:

```python
stmt = select(users).where(
    users.c.age >= 18,
    users.c.age <= 65,
    users.c.status.in_(["active", "pending"]),
)
```

Every returned row is still validated with:

```python
UserRead.model_validate(mapping)
```

---

# Why Validation Still Runs

Even an apparently complete SQL pushdown cannot prove that the resulting row
satisfies the full Pydantic model.

Reasons include:

- Custom field validators.
- Model validators.
- Nested models.
- Cross-field invariants.
- Computed validation logic.
- Database collation differences.
- Database type coercion.
- View or expression semantics.
- Joined or labeled query shapes.
- Constraints added by application code after SQLRules compilation.
- Database values returned through drivers with backend-specific conversions.

Therefore, pushdown reduces candidates but does not establish trust.

---

# Supported Constraint Categories

The exact support matrix belongs to SQLRules, but common portable candidates
include:

- `gt`
- `ge`
- `lt`
- `le`
- `multiple_of`
- `min_length`
- `max_length`
- `Literal`
- `Enum`

Dialect-specific plugins may additionally support:

- Regular expressions.
- JSON predicates.
- ARRAY predicates.
- Range operations.
- Geospatial predicates.

RowGuard should consume these capabilities through SQLRules' public API without
special-casing them.

---

# Unsupported Constraints

When SQLRules cannot translate a constraint, RowGuard should preserve that fact
in structured diagnostics.

Example diagnostic:

```text
code: pushdown.constraint_not_applied
field: username
constraint: pattern
reason: no portable translator registered
```

The row is still validated by Pydantic after retrieval.

Unsupported pushdown is therefore not equivalent to unsupported validation.

---

# User-Supplied Filters

User-supplied SQLAlchemy expressions should compose with pushed-down filters.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    where=[
        users.c.enabled.is_(True),
        users.c.tenant_id == tenant_id,
    ],
)
```

Conceptually:

```python
stmt = select(users).where(
    *sqlrules_expressions,
    *user_expressions,
)
```

RowGuard should preserve SQLAlchemy's normal `AND` semantics unless the caller
constructs explicit `or_()`, `and_()`, or other expression trees.

---

# Existing Statements

When the caller provides an existing `Select`, RowGuard may apply pushdown only
when it can safely resolve model fields to the selected statement's underlying
columns.

Example:

```python
stmt = select(users).where(users.c.enabled.is_(True))
```

RowGuard may append SQLRules expressions if the source table is known.

For more complex statements, such as:

- Joins.
- CTEs.
- Subqueries.
- Labeled expressions.
- Aggregates.
- Unions.

RowGuard should require an explicit pushdown target or column map.

Example:

```python
rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    pushdown_source=users,
    column_map={
        "id": users.c.id,
        "name": users.c.name,
    },
)
```

The compiler must fail rather than guess when field-to-column resolution is
ambiguous.

---

# Column Mapping

Pushdown mapping and row-adaptation mapping solve related but distinct problems.

## Pushdown column map

Maps Pydantic fields to SQLAlchemy columns used in WHERE expressions.

```python
pushdown_column_map={
    "id": users.c.user_id,
    "name": users.c.display_name,
}
```

## Row field map

Maps Pydantic fields to result keys used during row adaptation.

```python
field_map={
    "id": "user_id",
    "name": "display_name",
}
```

These mappings may be identical in simple queries but must remain conceptually
separate.

A SQL expression used for filtering may not be selected, and a selected label
may not be suitable as a WHERE-clause source.

---

# Joins

Pushdown across joins requires careful field ownership.

Example:

```python
class UserTeamRead(BaseModel):
    user_id: int
    team_name: Annotated[str, Field(min_length=3)]
```

The compiler needs explicit mappings:

```python
pushdown_column_map={
    "user_id": users.c.id,
    "team_name": teams.c.name,
}
```

This lets SQLRules generate filters against the correct tables.

Duplicate or ambiguous names must raise a planning error.

---

# Outer Joins

Outer joins introduce null-extension semantics.

A constraint such as:

```python
team_name: Annotated[str, Field(min_length=3)]
```

pushed into a top-level WHERE clause may effectively turn a left outer join into
an inner join by rejecting rows where `team_name` is `NULL`.

RowGuard must not apply such pushdown blindly.

Possible policies:

```python
outer_join_pushdown="error"     # recommended default
outer_join_pushdown="disabled"
outer_join_pushdown="explicit"
```

Applications may opt in by providing an explicit expression or plugin that
preserves intended join semantics.

---

# Optional Fields and Nullability

Pydantic optionality does not automatically imply a SQL null predicate.

Example:

```python
name: str | None
```

This does not mean:

```sql
name IS NULL
```

or:

```sql
name IS NOT NULL
```

SQLRules should compile only explicit null-related constraints when such support
exists.

RowGuard must not infer null filtering from type optionality.

---

# Limits and Pagination

Pushdown should occur before applying `LIMIT` or application-side pagination.

Correct logical order:

```text
FROM
  → WHERE pushdown
  → ORDER BY
  → LIMIT / OFFSET
  → RowGuard validation
```

However, rejected rows after retrieval can cause a requested page of 100
database rows to contain fewer than 100 validated models.

This is unavoidable when some validation rules cannot be pushed down.

RowGuard must document the difference between:

- Database row count.
- Candidate row count.
- Valid model count.

A future "fill page" feature would require additional database fetches and must
be explicit.

---

# Counts and Aggregates

A database `COUNT(*)` after pushdown counts rows satisfying pushed SQL
constraints, not rows guaranteed to pass the complete Pydantic model.

Therefore:

```python
candidate_count
```

and:

```python
validated_count
```

are different concepts.

RowGuard should not label a pushed-down SQL count as a validated count.

To determine the true validated count, rows must be validated unless all relevant
validation semantics are proven to be represented in SQL, which RowGuard should
not assume.

---

# Ordering

Filter pushdown must not alter query ordering.

SQLRules expressions are predicates only.

User-defined `ORDER BY` clauses remain under SQLAlchemy control.

Diagnostics may preserve expression order for reproducibility, but SQL engines
may reorder predicate evaluation internally.

Applications must not rely on predicate evaluation order.

---

# Security Filters

Tenant isolation, authorization, and access-control predicates should be supplied
as explicit application filters, not inferred from Pydantic constraints.

Example:

```python
where=[
    records.c.tenant_id == current_tenant_id,
]
```

SQLRules pushdown is a validation optimization, not an authorization system.

RowGuard should never allow disabled pushdown or unsupported constraints to
weaken mandatory security filters.

A future execution policy may distinguish:

- Required application filters.
- Validation pushdown filters.
- Optional optimization filters.

---

# Semantic Equivalence

A pushed-down constraint must be semantically equivalent enough to preserve the
accepted set of values intended by the Pydantic constraint.

Potential sources of mismatch include:

- String length measured in characters vs bytes.
- Collation and case sensitivity.
- Floating-point modulo behavior.
- Decimal precision.
- Timezone handling.
- Unicode normalization.
- Regular-expression dialects.
- Enum storage representation.
- `NULL` three-valued logic.

SQLRules owns translator-level equivalence decisions.

RowGuard should expose SQLRules diagnostics and optionally allow strict policies
that reject uncertain translations.

---

# Conservative Pushdown

When semantic equivalence is uncertain, the preferred behavior is not to push
the constraint.

A false negative at the SQL layer can incorrectly remove a row that Pydantic
would accept.

A false positive merely allows an invalid candidate row to reach Pydantic, where
it is safely rejected.

Therefore, pushdown should be conservative:

> It is safer to retrieve and reject an extra row than to discard a valid row in
> the database.

---

# Pushdown Safety Classes

SQLRules may eventually classify translations.

Suggested categories:

## exact

SQL semantics are intended to match the Pydantic constraint.

## conservative

The SQL predicate may admit extra rows but should not exclude valid rows.

## dialect_dependent

Semantics depend on database configuration or dialect behavior.

## unsafe

Translation may exclude rows that Pydantic would accept.

RowGuard should apply:

- `exact` by default.
- `conservative` when explicitly allowed or proven safe.
- `dialect_dependent` only with matching dialect configuration.
- Never apply `unsafe` automatically.

This classification belongs primarily to SQLRules, but RowGuard may expose policy
controls.

---

# Execution Plan Representation

The immutable execution plan should record pushdown information.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class PushdownPlan:
    enabled: bool
    mode: PushdownMode
    rules: Mapping[str, tuple[ColumnElement[bool], ...]]
    expressions: tuple[ColumnElement[bool], ...]
    diagnostics: tuple[Diagnostic, ...]
    source: object | None
```

The full execution plan may contain:

```python
@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    statement: Select
    model: type[BaseModel]
    pushdown: PushdownPlan
    ...
```

This makes query planning observable and cacheable.

---

# Precompiled Rules

Advanced users should be able to compile rules once and reuse them.

```python
compiled_rules = sqlrules.compile(UserRead, users)

result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    compiled_rules=compiled_rules,
)
```

RowGuard should validate that precompiled rules are compatible with the
pushdown source.

It should not mutate the supplied rule dictionary or expression objects.

---

# Caching

Potential cache inputs include:

- Pydantic model identity.
- SQLRules version.
- SQLRules compiler options.
- Pushdown source identity.
- Column mapping.
- Dialect extension configuration.

Do not cache:

- Session objects.
- Transaction state.
- User-specific expression values unless they are safely parameterized.
- Mutable statements after user modification.

SQLAlchemy already handles bound parameters; RowGuard should preserve that model
rather than interpolating literal values.

---

# Observability

Pushdown should be visible through diagnostics and statistics.

Suggested statistics:

- constraints_discovered
- constraints_pushed
- constraints_skipped
- fields_with_pushdown
- pushdown_compile_time_ns
- candidate_rows_read

Useful diagnostics:

```text
pushdown.enabled
pushdown.constraint_applied
pushdown.constraint_skipped
pushdown.column_resolved
pushdown.column_ambiguous
pushdown.outer_join_blocked
```

Diagnostics should not render sensitive bound parameter values by default.

---

# Explainability

A future API may expose a pushdown explanation without executing the query.

```python
plan = rowguard.plan(
    table=users,
    model=UserRead,
)

print(plan.pushdown.summary())
```

Possible output:

```text
Applied:
- age >= 18
- age <= 65
- status IN ('active', 'pending')

Not applied:
- username pattern: no portable translator
- password policy: custom validator
```

This improves trust and debugging.

---

# Error Handling

Suggested errors:

```text
RowGuardError
└── PushdownError
    ├── PushdownConfigurationError
    ├── PushdownSourceError
    ├── PushdownColumnResolutionError
    ├── IncompatibleCompiledRulesError
    └── UnsafePushdownError
```

SQLRules compilation errors should remain SQLRules exceptions unless RowGuard
must add query-planning context.

Avoid wrapping exceptions in a way that hides the original type and traceback.

---

# Failure Policies

Suggested configuration:

```python
on_pushdown_error="raise"
on_pushdown_error="disable"
```

Recommended default:

```python
raise
```

Silently disabling pushdown can produce surprising performance behavior and hide
configuration defects.

An explicit `"disable"` policy may fall back to validation-only execution while
recording a diagnostic.

---

# Streaming

Pushdown is especially valuable for streaming because it reduces:

- Rows transferred.
- Rows adapted.
- Rows validated.
- Rejection callback volume.

Streaming semantics otherwise remain unchanged.

Every returned candidate row is still validated before being yielded.

---

# Async

Pushdown planning is synchronous because it is metadata and expression work.

The resulting statement can be executed by either:

- `Session`
- `AsyncSession`

The same `PushdownPlan` should work for sync and async execution when the
underlying SQLAlchemy statement and dialect configuration are compatible.

---

# Plugins

RowGuard should not define its own constraint translators.

Dialect or custom constraint support belongs in SQLRules plugins.

RowGuard plugins may contribute:

- Pushdown policy decisions.
- Source/column resolvers.
- Diagnostics observers.
- Plan validators.
- Security-policy checks.

They should consume SQLRules output rather than translating constraints
themselves.

---

# Testing Requirements

Tests should cover:

- Pushdown enabled and disabled.
- Supported numeric constraints.
- String length constraints.
- Literal and Enum constraints.
- Unsupported constraints.
- Pydantic validation after pushdown.
- User filter composition.
- Existing statements.
- Explicit column maps.
- Joined queries.
- Outer-join safety.
- Optional fields.
- Pagination behavior.
- Precompiled rules.
- Caching.
- Diagnostics.
- Sync and async parity.
- Multiple SQL dialects.
- Semantic edge cases such as `NULL`, decimals, Unicode, and timezones.

Integration tests should verify actual database behavior, not merely SQL string
compilation.

---

# MVP Scope

The first RowGuard release should support:

- `pushdown="safe"`.
- `pushdown="disabled"`.
- SQLRules compilation through its public API.
- SQLAlchemy table sources.
- Explicit pushdown column maps.
- Composition with user-supplied WHERE expressions.
- Structured diagnostics.
- Validation of every returned row.
- Clear planning errors for ambiguous sources.

Deferred:

- Safety classifications beyond exact portable translations.
- Outer-join-aware automatic placement.
- Optimizer passes.
- Fill-page pagination.
- Aggregate validation planning.
- Pushdown explanation UI.
- Adaptive pushdown based on runtime statistics.

---

# Design Principles

- Push down only what is safe.
- Validate every returned row.
- Prefer false positives over false negatives at the SQL layer.
- Keep SQLRules as the sole constraint compiler.
- Never confuse validation filters with authorization filters.
- Make applied and skipped pushdown visible.
- Fail rather than guess when columns or query semantics are ambiguous.
- Treat pushdown as an optimization, never as proof of validity.
