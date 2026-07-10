# CORE.md

# RowGuard SQLAlchemy Core Integration

## Purpose

SQLAlchemy Core is RowGuard's primary database abstraction.

RowGuard should integrate directly with SQLAlchemy Core tables, columns,
selectables, statements, sessions, connections, rows, aliases, joins, CTEs, and
subqueries without requiring ORM mappings.

This document defines that integration boundary.

---

# Goals

The Core integration should:

- Treat SQLAlchemy as the source of SQL semantics.
- Accept existing Core tables and statements.
- Compose with SQLAlchemy expressions instead of replacing them.
- Preserve bound parameters and dialect behavior.
- Support SQLRules filter pushdown.
- Adapt SQLAlchemy result rows into Pydantic validation inputs.
- Avoid ORM-specific assumptions.
- Remain compatible with synchronous and asynchronous execution.

---

# Non-Goals

The Core integration does not:

- Define database schemas.
- Create tables automatically.
- Replace SQLAlchemy's expression language.
- Parse or rewrite rendered SQL strings.
- Reflect database metadata automatically unless explicitly requested.
- Manage application transactions beyond using the supplied execution context.
- Perform ORM identity-map behavior.
- Infer relationships.

---

# Architectural Position

```text
Pydantic Model
      │
      ▼
SQLRules
      │
      ▼
SQLAlchemy Core Statement
      │
      ▼
Connection / Session
      │
      ▼
Database
      │
      ▼
SQLAlchemy Row
      │
      ▼
RowGuard Row Adapter
      │
      ▼
Pydantic Validation
```

SQLAlchemy Core owns statement construction and execution semantics.

RowGuard adds planning, validation, rejection handling, diagnostics, and typed
results.

---

# Supported Core Inputs

The initial Core integration should support:

- `Table`
- `Alias`
- `Subquery`
- `CTE`
- `Join`
- `Select`
- `CompoundSelect`
- `Connection`
- `Session`
- SQLAlchemy `Row`
- Mapping-like result rows

Support levels should be explicit because some objects are safe for automatic
query construction while others require an existing statement or explicit
mapping.

---

# Table-Based Queries

The simplest API starts from a `Table`.

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
)
```

Conceptually, RowGuard builds:

```python
stmt = select(users)
```

It then applies:

- SQLRules pushdown expressions.
- User-provided filters.
- Ordering.
- Limits and offsets.
- Column projection configuration.

The `Table` remains owned by SQLAlchemy.

---

# Existing Select Statements

RowGuard should accept a prebuilt `Select`.

```python
stmt = (
    select(
        users.c.id,
        users.c.name,
        users.c.age,
    )
    .where(users.c.enabled.is_(True))
    .order_by(users.c.name)
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

RowGuard must preserve the statement's existing:

- Columns.
- FROM clauses.
- WHERE clauses.
- JOINs.
- GROUP BY clauses.
- HAVING clauses.
- ORDER BY clauses.
- LIMIT and OFFSET.
- Bind parameters.
- Execution options.

RowGuard may produce a new immutable SQLAlchemy statement when adding filters,
but it should not mutate user-owned statement objects.

---

# Statement Validation

Before execution, RowGuard should verify that the supplied statement is
compatible with row validation.

Compilation checks may include:

- The statement returns rows.
- Expected result keys are resolvable.
- Field mappings are valid.
- Pushdown columns are unambiguous.
- Unsupported statement forms are rejected clearly.

RowGuard should not execute a statement merely to discover its shape during
planning.

---

# Column Projection

A table-based query may select all table columns by default.

```python
select(users)
```

However, applications may want narrower projections.

Potential API:

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    columns=[
        users.c.id,
        users.c.name,
        users.c.age,
    ],
)
```

The selected columns must provide enough data for Pydantic validation.

Missing fields should normally be left absent so Pydantic can apply defaults or
raise canonical validation errors.

RowGuard must not silently inject nulls for unselected columns.

---

# Field-to-Column Mapping

A Pydantic field name may differ from a database column name.

```python
class UserRead(BaseModel):
    id: int
    name: str
```

Database columns:

```python
users.c.user_id
users.c.display_name
```

Pushdown mapping:

```python
pushdown_column_map={
    "id": users.c.user_id,
    "name": users.c.display_name,
}
```

Result mapping:

```python
field_map={
    "id": "user_id",
    "name": "display_name",
}
```

The two maps are conceptually separate:

- Pushdown mapping connects model fields to SQL expressions.
- Result mapping connects model fields to returned row keys.

---

# Column Labels

Core queries frequently label columns.

```python
stmt = select(
    users.c.user_id.label("id"),
    users.c.display_name.label("name"),
)
```

This is the preferred way to align SQL result keys with Pydantic fields.

When labels already match model field names, no explicit result field map should
be required.

RowGuard should preserve SQLAlchemy labels exactly.

---

# Aliases

Aliases should be supported explicitly.

```python
u = users.alias("u")

stmt = select(
    u.c.id,
    u.c.name,
)
```

SQLRules pushdown must compile against the alias columns, not the original table
columns.

```python
pushdown_source=u
```

or:

```python
pushdown_column_map={
    "id": u.c.id,
    "name": u.c.name,
}
```

RowGuard should never silently redirect filters from an alias to its base table.

---

# Subqueries

Subqueries may be used as pushdown and selection sources.

```python
active_users = (
    select(users)
    .where(users.c.enabled.is_(True))
    .subquery()
)

stmt = select(active_users)
```

RowGuard may use subquery columns for SQLRules pushdown if field mappings are
clear.

```python
pushdown_source=active_users
```

The Pydantic model still validates the final result row, not the original table
row.

---

# Common Table Expressions

CTEs should be treated similarly to subqueries.

```python
active_users = (
    select(users.c.id, users.c.name)
    .where(users.c.enabled.is_(True))
    .cte("active_users")
)
```

RowGuard may query the CTE through:

```python
stmt = select(active_users)
```

Automatic source detection should remain conservative.

An explicit pushdown source or field map is preferred for complex CTEs.

---

# Joins

RowGuard should support SQLAlchemy Core joins.

```python
stmt = (
    select(
        users.c.id.label("user_id"),
        users.c.name,
        teams.c.id.label("team_id"),
        teams.c.name.label("team_name"),
    )
    .select_from(
        users.join(teams, users.c.team_id == teams.c.id)
    )
)
```

Joined queries require clear result keys.

Duplicate unlabeled column names should fail planning by default.

Recommended model:

```python
class UserTeamRead(BaseModel):
    user_id: int
    name: str
    team_id: int
    team_name: str
```

RowGuard should not automatically flatten arbitrary joined entities into nested
Pydantic models without an explicit adapter.

---

# Outer Joins

Outer joins require additional care because SQLRules pushdown may change query
semantics.

Example:

```python
users.outerjoin(teams)
```

Applying:

```python
teams.c.name.is_not(None)
```

in the top-level WHERE clause may eliminate unmatched rows and effectively
convert the outer join into an inner join.

RowGuard should:

- Preserve user-authored outer join semantics.
- Avoid automatic pushdown across nullable outer-joined sides unless explicitly
  enabled.
- Require explicit mappings or filters when semantics are uncertain.
- Emit diagnostics when pushdown is blocked.

---

# Compound Selects

Core supports `UNION`, `UNION ALL`, `INTERSECT`, and `EXCEPT`.

Example:

```python
stmt = select(active_users).union_all(select(archived_users))
```

RowGuard may execute and validate compound statements if result keys are stable.

Automatic SQLRules pushdown into each branch is complex and should be deferred
unless explicitly planned.

MVP behavior:

- Existing compound statements may be executed.
- Post-query Pydantic validation is supported.
- Automatic pushdown may be disabled.
- Explicit prefiltered branches remain fully supported.

---

# Aggregates

Aggregate queries can be validated with result models.

```python
class TeamSummary(BaseModel):
    team_id: int
    user_count: int
```

```python
stmt = (
    select(
        users.c.team_id,
        func.count(users.c.id).label("user_count"),
    )
    .group_by(users.c.team_id)
)
```

RowGuard should validate aggregate rows like any other mapping.

SQLRules constraints derived from the result model should not automatically be
placed into `WHERE`, because aggregate fields often require `HAVING`.

Automatic aggregate pushdown is outside the MVP.

Applications should write explicit `HAVING` expressions.

---

# Window Functions

Window function results may be validated when labeled.

```python
stmt = select(
    users.c.id,
    func.row_number()
    .over(order_by=users.c.created_at)
    .label("row_number"),
)
```

RowGuard treats labeled window expressions as result fields.

It should not attempt to derive pushdown rules for window outputs.

---

# Textual SQL

Raw textual SQL may be useful but has a weaker structural contract.

Potential support:

```python
stmt = text(
    "SELECT user_id AS id, display_name AS name FROM users"
)
```

MVP recommendation:

- Allow execution only through an explicit raw-SQL API or option.
- Require declared result columns or an explicit field map.
- Disable automatic SQLRules pushdown.
- Preserve bound parameters.
- Validate returned mappings with Pydantic.

RowGuard must never concatenate SQL strings or interpolate user values.

---

# Execution Contexts

## Session

A synchronous `Session` is the most convenient execution context.

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

RowGuard calls the public SQLAlchemy execution API and consumes the result.

## Connection

Core-native applications may use a `Connection`.

```python
result = rowguard.execute(
    connection=connection,
    statement=stmt,
    model=UserRead,
)
```

The public API should avoid allowing both a session and connection in the same
request.

## Engine

Direct `Engine` execution should not be the preferred API because modern
SQLAlchemy expects explicit connections.

A convenience wrapper may open and close a connection, but transaction behavior
must be clear.

## AsyncConnection and AsyncSession

Async execution should use the same planning and validation components with an
async I/O adapter.

---

# Transaction Boundaries

RowGuard should not implicitly commit or roll back read-only queries.

It should execute within the transaction state of the supplied:

- `Session`
- `Connection`
- `AsyncSession`
- `AsyncConnection`

If RowGuard opens a convenience connection itself, it must document:

- Connection lifetime.
- Transaction lifetime.
- Cleanup behavior.
- Error behavior.

Rejection callbacks that write to a quarantine destination must not silently
reuse the read transaction unless explicitly configured.

---

# Execution Options

RowGuard should preserve and optionally expose SQLAlchemy execution options.

Example:

```python
stmt = stmt.execution_options(stream_results=True)
```

Potential RowGuard API:

```python
rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    execution_options={
        "stream_results": True,
    },
)
```

Execution options should be forwarded through SQLAlchemy rather than interpreted
unless RowGuard has a documented feature depending on them.

---

# Bound Parameters

SQLAlchemy bound parameters must remain intact.

Example:

```python
stmt = select(users).where(users.c.tenant_id == bindparam("tenant_id"))
```

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    parameters={"tenant_id": tenant_id},
    model=UserRead,
)
```

RowGuard must:

- Forward parameters through SQLAlchemy.
- Avoid literal interpolation.
- Preserve expanding parameters where supported.
- Avoid logging sensitive parameter values by default.

---

# Result Consumption

SQLAlchemy may expose results through:

- `Result`
- `ScalarResult`
- `MappingResult`
- `Row`
- Row mappings

RowGuard's standard model-validation path should prefer mapping results.

Conceptually:

```python
result = session.execute(stmt)
for row in result:
    mapping = row._mapping
```

The exact implementation should use documented SQLAlchemy interfaces and remain
isolated in the execution and adapter layers.

---

# Mapping Results

When practical, RowGuard may request mapping-oriented consumption:

```python
session.execute(stmt).mappings()
```

This can simplify adaptation for Core queries.

However, the choice must preserve support for:

- ORM entity rows.
- Mixed entity/scalar rows.
- Custom adapters.
- Raw row retention.

The row adapter remains the final authority on input shape.

---

# Scalar Results

A scalar result does not naturally match a Pydantic object.

Example:

```python
select(func.count())
```

RowGuard should require an explicit scalar adapter or a labeled mapping result.

Preferred:

```python
select(func.count().label("count"))
```

Target model:

```python
class CountResult(BaseModel):
    count: int
```

Implicit scalar-to-model binding should be deferred.

---

# Duplicate Result Keys

Duplicate keys can occur in joins and broad selections.

```python
select(users.c.id, teams.c.id)
```

RowGuard should fail planning or adaptation unless:

- Columns are labeled.
- A field map disambiguates them.
- A custom adapter handles the shape.

Silent first/last wins behavior is unsafe and should not be the default.

---

# Pydantic Validation

After adaptation, Core rows are validated through:

```python
model.model_validate(mapping)
```

Core integration must not add its own semantic conversions.

It may only provide structural adaptation such as:

- Key extraction.
- Label preservation.
- Explicit renaming.
- Explicit nesting.

Pydantic remains responsible for:

- Type coercion.
- Strictness.
- Defaults.
- Validators.
- Nested model validation.
- Extra-field behavior.

---

# SQLRules Pushdown

For simple table queries:

```python
rules = sqlrules.compile(UserRead, users)
stmt = select(users).where(*sqlrules.where(rules))
```

For aliases, joins, subqueries, or complex statements, RowGuard should require a
clear pushdown source or explicit column mapping.

Pushdown must occur before execution and remain visible in the execution plan.

---

# Additional Filters

Applications may supply Core expressions directly.

```python
where=[
    users.c.tenant_id == tenant_id,
    users.c.enabled.is_(True),
]
```

These filters should compose with SQLRules expressions using normal SQLAlchemy
semantics.

Security and authorization filters should be explicit application expressions,
not inferred from the Pydantic model.

---

# Ordering

Potential API:

```python
order_by=[
    users.c.name.asc(),
    users.c.id.asc(),
]
```

RowGuard should append or preserve order expressions through SQLAlchemy.

It should not reorder database results after validation unless explicitly
requested.

Rejected rows may cause gaps in the validated result sequence, but accepted
models should preserve relative database order.

---

# Limit and Offset

Potential API:

```python
limit=100
offset=200
```

These apply to database candidate rows before Pydantic validation.

Therefore, the number of valid models may be smaller than the limit.

RowGuard should report:

- Candidate rows read.
- Valid models returned.
- Rejected rows encountered.

A "fill valid page" feature would require additional queries and should remain
outside the MVP.

---

# Locking Clauses

Existing statements may include locking behavior such as `FOR UPDATE`.

RowGuard should preserve such clauses but avoid adding them automatically.

Applications remain responsible for transaction and locking semantics.

Validation and rejection callbacks may extend lock duration, especially in
buffered processing. Documentation should warn users about this behavior.

---

# Server-Side Cursors and Streaming

The Core integration should support streaming execution through SQLAlchemy's
public streaming options.

Goals:

- Avoid buffering all rows.
- Validate one row or batch at a time.
- Preserve rejection semantics.
- Release cursors promptly.

Streaming configuration should live in the execution plan and I/O layer rather
than the validation engine.

---

# Reflection

Reflected `Table` objects should work once the application has reflected them
through SQLAlchemy.

```python
users = Table(
    "users",
    metadata,
    autoload_with=engine,
)
```

RowGuard should consume the resulting `Table` normally.

Automatic reflection inside RowGuard is not required because it introduces:

- Database I/O during planning.
- Connection management.
- Schema discovery policy.
- Caching complexity.

A future helper may support reflection explicitly.

---

# Dialects

Core integration should be dialect-neutral.

SQLAlchemy owns:

- SQL rendering.
- Parameter styles.
- Identifier quoting.
- Type adaptation.
- Driver integration.

SQLRules owns dialect-specific constraint translators.

RowGuard should expose dialect context to planning and diagnostics when needed
but avoid backend-specific SQL generation.

---

# Errors

Suggested Core integration errors:

```text
RowGuardError
└── CoreIntegrationError
    ├── UnsupportedSelectableError
    ├── InvalidStatementError
    ├── AmbiguousResultShapeError
    ├── InvalidColumnProjectionError
    ├── InvalidExecutionContextError
    ├── ParameterBindingError
    └── ResultConsumptionError
```

SQLAlchemy execution exceptions should preserve the original exception as the
cause.

---

# Diagnostics

Useful Core diagnostics include:

- Input selectable type.
- Final statement identity.
- Columns selected.
- Result keys expected.
- Field maps applied.
- Pushdown source selected.
- Execution options forwarded.
- Streaming enabled.
- Duplicate-key checks.
- Dialect name.

Diagnostics should not render SQL or parameter values unless explicitly enabled.

---

# Performance

Core integration should minimize overhead around SQLAlchemy.

Guidelines:

- Reuse immutable execution plans.
- Precompute row mapping plans.
- Prefer mapping views over copies.
- Avoid compiling SQL strings for normal execution.
- Validate each row exactly once.
- Stream for large datasets.
- Let SQLAlchemy manage statement and driver optimizations.

---

# Security

The Core integration must:

- Preserve bound parameters.
- Never interpolate user values into SQL strings.
- Keep authorization filters separate from validation pushdown.
- Fail on ambiguous mappings.
- Avoid logging sensitive row and parameter values by default.
- Respect application transaction boundaries.

RowGuard improves data validation but is not an authorization framework.

---

# Testing Requirements

Tests should cover:

- Table-based selects.
- Existing `Select` statements.
- Column labels.
- Explicit field maps.
- SQLRules pushdown.
- User-provided filters.
- Aliases.
- Subqueries.
- CTEs.
- Inner joins.
- Outer joins.
- Duplicate result keys.
- Aggregates.
- Window functions.
- Compound selects.
- Bound parameters.
- Sessions.
- Connections.
- Streaming.
- Reflected tables.
- Multiple dialect compilation paths.
- Sync/async parity.
- Transaction preservation.
- Error propagation.

Integration tests should execute against at least SQLite and PostgreSQL in the
long term.

---

# MVP Scope

The first release should support:

- SQLAlchemy 2.x `Table`.
- Existing `Select`.
- Synchronous `Session`.
- Synchronous `Connection`.
- Labeled columns.
- Explicit result field maps.
- Explicit pushdown column maps.
- Inner joins with unambiguous labels.
- SQLRules pushdown for table and explicitly mapped sources.
- Bound parameters.
- Mapping-style result adaptation.
- Buffered execution.
- Basic synchronous streaming.

Deferred:

- Automatic pushdown into compound statements.
- Automatic aggregate-to-HAVING compilation.
- Implicit nested join adaptation.
- Automatic reflection.
- Raw textual SQL convenience APIs.
- Automatic outer-join predicate placement.
- Scalar inference.
- Relationship semantics.
- ORM identity-map integration.

---

# Recommended Public Examples

## Basic Table Query

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

## Existing Statement

```python
stmt = (
    select(
        users.c.id,
        users.c.name,
    )
    .where(users.c.enabled.is_(True))
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

## Labeled Legacy Columns

```python
stmt = select(
    users.c.user_id.label("id"),
    users.c.display_name.label("name"),
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

## Joined Query

```python
stmt = (
    select(
        users.c.id.label("user_id"),
        users.c.name,
        teams.c.id.label("team_id"),
        teams.c.name.label("team_name"),
    )
    .select_from(
        users.join(teams, users.c.team_id == teams.c.id)
    )
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserTeamRead,
)
```

## Explicit Pushdown Mapping

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    pushdown_source=users,
    pushdown_column_map={
        "id": users.c.user_id,
        "name": users.c.display_name,
    },
)
```

---

# Design Principles

- SQLAlchemy Core is the primary database abstraction.
- Compose expressions; do not generate SQL strings.
- Preserve user-authored statement semantics.
- Use labels and explicit mappings instead of guessing.
- Separate pushdown mapping from result mapping.
- Defer type and business validation to Pydantic.
- Preserve transactions, parameters, and execution options.
- Fail safely on ambiguous result shapes.
- Keep the integration dialect-neutral.
- Make validation additive to SQLAlchemy rather than competitive with it.
