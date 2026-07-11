# SQLMODEL.md

:::{admonition} Status: shipped in 0.5.0
:class: tip

SQLModel table-source support ships in **0.5.0** (`pip install rowguard[sqlmodel]`).
Start with [ORM and SQLModel](../guides/orm-sqlmodel.md). See also
[Supported vs planned](../project/supported.md) and
[Why not SQLModel (positioning)](WHY_NOT_SQLMODEL.md).
:::

# RowGuard SQLModel Integration

## Purpose

RowGuard works with SQLModel applications while solving a different problem from
SQLModel itself.

SQLModel combines Pydantic and SQLAlchemy to simplify database model definition,
persistence, and querying. RowGuard adds a validation-first read layer that
explicitly validates selected database values against a requested Pydantic or
SQLModel contract and classifies every failed row.

The integration goal is:

> Keep SQLModel responsible for models, mappings, sessions, relationships, and
> persistence; use RowGuard when selected rows must be proven to satisfy a
> read-time validation contract.

RowGuard should complement SQLModel rather than fork, wrap, or replace it.

---

# Current Ecosystem Position

SQLModel is built on Pydantic and SQLAlchemy. A SQLModel table class is both a
Pydantic-compatible model and a SQLAlchemy mapped model, and SQLModel's
`Session` extends SQLAlchemy's session with the convenient `exec()` API.

SQLModel is especially effective for:

- Defining typed table models.
- Reducing duplication between API and persistence models.
- Creating and updating mapped objects.
- SQLAlchemy ORM queries with concise typing.
- FastAPI request and response models.
- Relationships and common CRUD workflows.

RowGuard is focused on a narrower read-time guarantee:

- Apply SQL-safe model constraints through SQLRules.
- Execute a query.
- Adapt the returned database values.
- Explicitly call Pydantic validation for every candidate row.
- Return accepted models and first-class rejected-row records.
- Support collect, skip, callback, quarantine, and streaming workflows.

---

# The Core Difference

## SQLModel

SQLModel primarily models and queries persisted data.

```text
SQLModel Class
      │
      ├── Pydantic-style fields
      ├── SQLAlchemy mapping
      ├── Table definition
      └── ORM persistence
```

## RowGuard

RowGuard treats database reads as validation boundaries.

```text
SQLModel / SQLAlchemy Query
           │
           ▼
       SQLRules
           │
           ▼
      Database Rows
           │
           ▼
       RowGuard
           │
           ├── Accepted model
           └── Rejected row
```

RowGuard's central question is not:

> Can SQLAlchemy materialize this row as an ORM object?

It is:

> Does the selected data satisfy the requested Pydantic contract right now?

---

# Why Read-Time Validation Matters

A mapped database row can violate the application's current model contract for
many reasons:

- The row predates a newly added rule.
- The database schema is weaker than the Pydantic model.
- Another service writes data using different rules.
- A migration partially transformed data.
- A manual update bypassed application validation.
- A view or join returns values with different semantics.
- ORM object construction follows persistence-loading behavior rather than an
  explicit application validation workflow.
- A Pydantic validator expresses logic that cannot be represented by the
  database schema.

SQLModel does not need to solve all of these cases to be successful at its own
mission. RowGuard exists specifically to make them explicit.

---

# Relationship to Pydantic Validation

Pydantic provides `model_validate()` as the explicit operation for validating
input against a model.

RowGuard's SQLModel integration should always make this validation step visible
in its architecture:

```python
validated = UserRead.model_validate(mapping)
```

or, when explicitly configured:

```python
validated = UserRead.model_validate(
    entity,
    from_attributes=True,
)
```

The default RowGuard path should prefer mapping-based validation because it
makes the selected values and result shape explicit.

---

# Recommended Model Separation

RowGuard should encourage separate persistence and read-contract models even
when SQLModel makes model reuse possible.

Example:

```python
from sqlmodel import Field, SQLModel


class UserTable(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int
    enabled: bool = True
```

Read contract:

```python
from typing import Annotated

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: int
    name: Annotated[str, Field(min_length=2, max_length=100)]
    age: Annotated[int, Field(ge=18)]
```

Query:

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
    on_reject="collect",
)
```

This preserves a clear boundary:

- `UserTable` defines persistence.
- `UserRead` defines what the application is willing to accept from a read.
- RowGuard proves each selected row satisfies `UserRead`.

---

# Using a SQLModel Data Model as the Read Contract

A non-table SQLModel class can also serve as the validation target.

```python
class UserRead(SQLModel):
    id: int
    name: str
    age: int
```

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
)
```

This is fully compatible with RowGuard's design because non-table SQLModel
classes function as Pydantic-style data models.

RowGuard should accept any supported Pydantic `BaseModel` subclass, including
SQLModel data models.

---

# Using the Table Model as the Read Contract

RowGuard may allow the same SQLModel table class to be used as both the source
and target:

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserTable,
)
```

However, this should not be the recommended default.

Potential issues include:

- Primary keys may be optional for creation but expected on reads.
- Relationship attributes may be present on the mapped class.
- Persistence defaults and read requirements may differ.
- Table model configuration may prioritize ORM behavior over API contracts.
- Application-specific read validators may not belong on the persistence model.
- Revalidating an already materialized mapped instance may interact with object
  attribute access and session state.

Separate read models usually produce clearer semantics.

---

# Integration with SQLModel Session

SQLModel's `Session` inherits from SQLAlchemy's session and adds `exec()`.

RowGuard should support SQLModel sessions through the same SQLAlchemy session
integration used for ORM queries.

Example:

```python
from sqlmodel import Session

with Session(engine) as session:
    result = rowguard.select(
        session=session,
        table=UserTable,
        model=UserRead,
    )
```

RowGuard does not need to require `session.exec()` internally. It may use the
underlying SQLAlchemy public execution APIs as appropriate, while preserving the
caller's SQLModel session and transaction behavior.

RowGuard must not:

- Commit automatically.
- Roll back ordinary rejections.
- Close the supplied session.
- Change autoflush silently.
- Expunge or refresh SQLModel instances.
- Mutate the identity map.

---

# Existing SQLModel Select Statements

RowGuard should accept statements created with SQLModel's `select()` helper.

```python
from sqlmodel import select

stmt = (
    select(UserTable)
    .where(UserTable.enabled.is_(True))
    .order_by(UserTable.name)
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

Because SQLModel's select expressions are based on SQLAlchemy, RowGuard should
preserve:

- Existing filters.
- Ordering.
- Joins.
- Loader options.
- Limits and offsets.
- Bound parameters.
- Aliases.
- Execution options.

---

# Preferred Query Shape: Explicit Projection

For strict validation and predictable performance, explicit projections are
often preferable to selecting full mapped instances.

```python
stmt = select(
    UserTable.id,
    UserTable.name,
    UserTable.age,
)
```

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

Advantages:

- The exact validation input is visible.
- No relationship traversal is needed.
- No accidental lazy loading occurs.
- Identity-map behavior is minimized.
- Streaming is more memory efficient.
- Result labels can align directly with Pydantic field names.
- The model is validated from fresh selected values rather than a larger managed
  object graph.

RowGuard documentation should recommend this approach for data quality,
integration, and ETL workloads.

---

# Entity-Based Validation

Selecting the full SQLModel entity is still useful:

```python
stmt = select(UserTable)
```

RowGuard should offer two explicit entity-validation modes.

## Mapping Mode

Recommended default:

```python
orm_validation="mapping"
```

RowGuard extracts planned mapped scalar attributes into a mapping and then
calls:

```python
UserRead.model_validate(mapping)
```

Benefits:

- Explicit input shape.
- Reduced lazy-loading risk.
- Consistency with SQLAlchemy Core.
- Easy alias and field-map handling.
- No SQLAlchemy internal attributes passed to Pydantic.

## Attribute Mode

Opt-in:

```python
orm_validation="from_attributes"
```

RowGuard calls:

```python
UserRead.model_validate(
    entity,
    from_attributes=True,
)
```

This can be convenient but may access:

- Deferred attributes.
- Expired attributes.
- Relationships.
- Hybrid properties.
- Custom descriptors.

Attribute mode must therefore be observable and conservative.

---

# SQLModel Instances Are Not Automatically Trusted

A SQLModel entity returned from a query is a mapped persistence object.

RowGuard should not treat the mere existence of that object as proof that all
current Pydantic constraints, field validators, and model validators were
explicitly evaluated for the requested read contract.

The RowGuard guarantee starts only when RowGuard performs its configured
validation step.

This is the central reason the integration exists.

---

# SQLRules Pushdown with SQLModel

SQLRules should be able to compile supported model constraints against SQLModel
mapped attributes.

Example read contract:

```python
class UserRead(SQLModel):
    id: int
    name: Annotated[str, Field(min_length=2)]
    age: Annotated[int, Field(ge=18, le=120)]
```

Pushdown source:

```python
UserTable
```

Conceptually, SQLRules produces:

```python
UserTable.age >= 18
UserTable.age <= 120
func.length(UserTable.name) >= 2
```

RowGuard applies these to the SQLModel/SQLAlchemy statement and still validates
every returned row afterward.

---

# Separate Pushdown and Adaptation Maps

Legacy SQLModel mappings may use different attribute and result names from the
read contract.

Persistence model:

```python
class UserTable(SQLModel, table=True):
    user_id: int | None = Field(default=None, primary_key=True)
    display_name: str
```

Read model:

```python
class UserRead(SQLModel):
    id: int
    name: str
```

Pushdown mapping:

```python
pushdown_column_map={
    "id": UserTable.user_id,
    "name": UserTable.display_name,
}
```

Entity attribute mapping:

```python
attribute_map={
    "id": "user_id",
    "name": "display_name",
}
```

Projected query alternative:

```python
stmt = select(
    UserTable.user_id.label("id"),
    UserTable.display_name.label("name"),
)
```

Labels are generally the cleanest approach for read contracts.

---

# Relationships

SQLModel relationships are SQLAlchemy ORM relationships.

RowGuard should not automatically traverse them during validation.

Example:

```python
class UserTable(SQLModel, table=True):
    ...
    team: "TeamTable | None" = Relationship(back_populates="users")
```

Target:

```python
class UserWithTeamRead(SQLModel):
    id: int
    team: TeamRead | None
```

Implicit access to `entity.team` may trigger lazy loading.

Recommended approach:

1. Build an explicit joined or eager-loaded query.
2. Project stable labeled columns.
3. Use an explicit nested row adapter.
4. Validate the resulting nested mapping.

Example:

```python
stmt = (
    select(
        UserTable.id.label("user_id"),
        UserTable.name.label("user_name"),
        TeamTable.id.label("team_id"),
        TeamTable.name.label("team_name"),
    )
    .join(TeamTable, UserTable.team_id == TeamTable.id)
)
```

The nested adapter can produce:

```python
{
    "id": row.user_id,
    "name": row.user_name,
    "team": {
        "id": row.team_id,
        "name": row.team_name,
    },
}
```

---

# Lazy Loading

RowGuard should block accidental lazy loading by default in entity-validation
workflows.

Shipped in 0.5:

```python
unloaded_attributes="error"  # only supported value
```

Design / future (not shipped):

```python
unloaded_attributes="load"
unloaded_attributes="omit"
```

For async SQLModel applications, implicit lazy loading is particularly
problematic because attribute access may require asynchronous I/O that cannot
occur transparently in ordinary validation code.

Projected queries should be the preferred async pattern.

---

# Response Models vs RowGuard

FastAPI response models validate and filter data at the API response boundary.

RowGuard validates data at the database-read boundary.

These boundaries are complementary:

```text
Database
    │
    ▼
RowGuard
Read-time validation and rejection handling
    │
    ▼
Application Logic
    │
    ▼
FastAPI Response Model
Response serialization and API contract
```

A FastAPI response model does not replace RowGuard when the application needs to:

- Detect invalid database rows before business logic.
- Collect or quarantine rejected records.
- Stream validated models.
- Run outside FastAPI.
- Audit data quality.
- Fail a job based on rejection thresholds.
- Preserve detailed row-level diagnostics.

Likewise, RowGuard does not replace FastAPI's response-model responsibilities.

---

# Multiple SQLModel Classes

SQLModel encourages separate models for common operations, such as:

- Table model.
- Create model.
- Update model.
- Public/read model.

RowGuard should fit naturally into this pattern.

Example:

```python
class UserBase(SQLModel):
    name: str
    age: int


class UserTable(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
```

RowGuard targets `UserRead`:

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
)
```

This is likely the recommended integration pattern.

---

# Read Contracts Can Be Stricter Than Table Models

A RowGuard read model may intentionally be stricter than the persistence model.

Example:

```python
class UserTable(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str | None = None
```

Application read contract:

```python
class ActiveUserRead(SQLModel):
    id: int
    email: EmailStr
```

RowGuard can:

- Push down `email IS NOT NULL` only when explicitly represented by a supported
  rule or user filter.
- Validate `EmailStr` after retrieval.
- Collect legacy rows containing malformed addresses.
- Keep invalid records out of downstream application logic.

This is a core RowGuard use case.

---

# Read Contracts Can Be Narrower Than Table Models

A read model may expose only a subset of columns.

```python
class UserSummary(SQLModel):
    id: int
    name: str
```

Projected query:

```python
stmt = select(
    UserTable.id,
    UserTable.name,
)
```

RowGuard validates only the selected contract.

This avoids loading or exposing persistence-only fields.

---

# Cross-Field and Model Validators

SQLRules can push down only supported field-level constraints.

Pydantic model validators remain post-query rules.

Example:

```python
class DateRangeRead(SQLModel):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self
```

RowGuard must validate this after retrieval.

Rejected rows retain the Pydantic validation error and source identity.

---

# Rejection Handling

All RowGuard rejection policies should work with SQLModel queries:

- `raise`
- `collect`
- `skip`
- `log`
- `callback`
- `quarantine`

Example:

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
    on_reject="collect",
)
```

Each `RejectedRow` may include:

- Primary-key identity.
- Table/model name.
- Adapted mapping.
- Pydantic validation error.
- SQLRules diagnostics.
- Statement metadata.
- Raw entity reference only when explicitly retained.

---

# Raw SQLModel Entity Retention

Retaining full SQLModel entities in rejection records should be disabled by
default.

Reasons:

- The entity remains tied to session state.
- Relationships may be lazily loaded later.
- The object may contain persistence-only fields.
- Serialization can expose internal or sensitive data.
- Large entity graphs increase memory use.

Recommended defaults (shipped behavior):

```python
# Live entities are not retained on RejectedRow by default.
# Primary-key identity is exposed as RejectedRow.source_identity.
```

Design / future knobs (not shipped):

```python
retain_raw_entity=False
retain_identity=True
retain_mapping=True
```

---

# Repair and Write-Back

RowGuard may eventually support explicit repair callbacks, but SQLModel
integration must not automatically write repaired values back to the database.

Safe future workflow:

```text
Rejected SQLModel row
        │
        ▼
Repair callback proposes mapping
        │
        ▼
Pydantic validates repaired mapping
        │
        ▼
Application explicitly decides whether to update entity
```

RowGuard should not:

- Mutate the entity silently.
- Add it to the session.
- Flush it.
- Commit it.
- Delete invalid rows.

Persistence remains an application decision.

---

# Session and Transaction Behavior

RowGuard executes within the caller's SQLModel session.

Ordinary rejected rows should not automatically roll back the transaction.

Under `on_reject="raise"`, RowGuard raises an exception and leaves transaction
management to the caller.

Callbacks and quarantine writers that perform database writes should use an
explicitly configured transaction strategy.

Potential strategies:

```python
quarantine_transaction="separate"
quarantine_transaction="same"
```

A separate transaction or external sink is often safer for quarantine data.

---

# Autoflush

SQLModel sessions inherit SQLAlchemy autoflush behavior.

Executing a RowGuard query may trigger a normal session autoflush if pending
changes exist.

RowGuard should not change this implicitly.

Applications that want a database snapshot unaffected by pending state may use
the session's standard no-autoflush controls or a separate session.

---

# Identity Map Considerations

When selecting full SQLModel entities, the session identity map may return an
already-present object containing:

- Pending in-memory changes.
- Expired attributes.
- Previously loaded relationships.
- State that differs from a clean projected database read.

For the strongest read-time validation guarantee, RowGuard should recommend
selecting explicit columns rather than validating a full managed entity.

The documentation should distinguish:

- Validation of selected database values.
- Validation of current session entity state.

These are not always identical.

---

# Async SQLModel

SQLModel applications may use SQLAlchemy's async session patterns.

RowGuard's async API should support compatible `AsyncSession` instances:

```python
result = await rowguard.aselect(
    session=async_session,
    table=UserTable,
    model=UserRead,
)
```

Async guidance:

- Prefer explicit column projections.
- Avoid attribute-based validation that can trigger lazy I/O.
- Use explicit eager loading when relationships are required.
- Keep Pydantic validation synchronous.
- Await only database and async callback operations.

---

# Streaming SQLModel Queries

RowGuard should support streaming SQLModel query results.

```python
with rowguard.stream(
    session=session,
    table=UserTable,
    model=UserRead,
    on_reject="callback",
) as stream:
    for user in stream:
        process(user)
```

For large streams:

- Prefer projected columns.
- Avoid full entity identity-map accumulation.
- Do not retain accepted entities.
- Retain rejected mappings only according to policy.
- Use SQLAlchemy streaming execution options.
- Release result resources promptly.

RowGuard should yield validated Pydantic/SQLModel read models, not persistent
table entities.

---

# SQLModel `session.exec()` Compatibility

Applications may build and inspect queries using SQLModel's normal `session.exec`
workflow outside RowGuard.

RowGuard does not need to expose a replacement `exec()` method.

Its value is the stronger result contract:

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    on_reject="collect",
)
```

This returns RowGuard's typed result and rejection metadata instead of the normal
SQLAlchemy/SQLModel result wrapper.

---

# Direct Pydantic Revalidation

A SQLModel user could manually write:

```python
rows = session.exec(stmt).all()
validated = [UserRead.model_validate(row) for row in rows]
```

RowGuard adds structure around that manual pattern:

- SQLRules pushdown.
- Mapping and alias planning.
- ORM-state safeguards.
- Rejection policies.
- Rejected-row context.
- Streaming.
- Statistics.
- Diagnostics.
- Sync/async symmetry.
- Plugin extension points.
- Consistent error contracts.

RowGuard's value is not merely calling `model_validate`; it is making validation
a complete query-execution discipline.

---

# API Examples

## SQLModel Table to SQLModel Read Model

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
    on_reject="collect",
)
```

## Existing SQLModel Statement

```python
stmt = (
    select(UserTable)
    .where(UserTable.enabled.is_(True))
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

## Preferred Projection

```python
stmt = select(
    UserTable.id,
    UserTable.name,
    UserTable.age,
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

## Legacy Column Names

```python
stmt = select(
    UserTable.user_id.label("id"),
    UserTable.display_name.label("name"),
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

## Disable Pushdown

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
    pushdown="disabled",
)
```

## Attribute Validation

```python
result = rowguard.select(
    session=session,
    table=UserTable,
    model=UserRead,
    orm_validation="from_attributes",
    unloaded_attributes="error",
)
```

---

# Error Model

Suggested SQLModel-specific errors should inherit from the broader ORM
integration hierarchy.

```text
RowGuardError
└── ORMIntegrationError
    └── SQLModelIntegrationError
        ├── InvalidSQLModelSourceError
        ├── SQLModelResultShapeError
        ├── SQLModelAttributeError
        ├── SQLModelLazyLoadBlockedError
        └── SQLModelConfigurationError
```

Most failures should use shared ORM or row-adaptation errors rather than
introducing SQLModel-only types unnecessarily.

---

# Diagnostics

Useful SQLModel diagnostics include:

- Source table model.
- Target read model.
- Table vs non-table target.
- Statement type.
- Projection vs entity selection.
- Validation mode.
- SQLRules expressions applied.
- Attribute mappings.
- Unloaded fields.
- Relationships skipped.
- Entity identity.
- Rejection policy.
- Session type.
- Sync or async execution.

Diagnostics should avoid dumping full entities or sensitive values by default.

---

# Performance Guidance

## Prefer Projections

Projected scalar columns avoid unnecessary ORM object construction and identity
map growth.

## Cache Plans

Cache:

- Model field maps.
- Mapper extraction metadata.
- SQLRules compilation.
- Adapter plans.

Do not cache:

- Session state.
- Managed entities.
- Transaction state.

## Stream Large Reads

Use streaming for large tables and configure rejection retention carefully.

## Avoid Relationship Traversal

Nested relationship validation can multiply query count and memory usage.

## Validate Once

Each adapted row should undergo one Pydantic validation pass.

---

# Security and Correctness

The SQLModel integration must:

- Preserve explicit authorization filters.
- Never infer tenant or permission rules from Pydantic constraints.
- Preserve SQLAlchemy bound parameters.
- Avoid implicit lazy loads by default.
- Exclude SQLAlchemy internal state from validation inputs.
- Avoid logging raw sensitive rows.
- Keep repaired values separate from automatic persistence.
- Distinguish session entity state from fresh database projections.
- Fail on ambiguous result shapes.

---

# Testing Requirements

Tests should cover:

- SQLModel table models.
- SQLModel non-table read models.
- Pure Pydantic read models.
- Same-model source and target.
- SQLModel `Session`.
- SQLModel-created select statements.
- Projected column queries.
- Entity-based mapping validation.
- Opt-in `from_attributes`.
- SQLRules pushdown.
- Disabled pushdown.
- Field and attribute maps.
- Relationships.
- Lazy-loading safeguards.
- Eager-loading behavior.
- Deferred and expired attributes.
- Identity-map reuse.
- Autoflush behavior.
- Rejection policies.
- Primary-key diagnostics.
- Async sessions.
- Streaming.
- FastAPI-compatible result serialization.
- Legacy invalid rows.
- Cross-field validators.
- Multiple database dialects.

Tests should include rows inserted through paths that bypass Pydantic-level
validation to prove RowGuard catches invalid persisted data.

---

# MVP Scope

The first SQLModel integration should support:

- Current SQLModel table classes built on SQLAlchemy 2.x and Pydantic v2.
- SQLModel `Session`.
- SQLModel-generated `Select`.
- Separate Pydantic or non-table SQLModel read models.
- Single-entity queries.
- Explicit column projections.
- Mapping-based validation.
- SQLRules pushdown against mapped scalar fields.
- Explicit pushdown and attribute maps.
- Structured rejections with primary-key identity.
- Clear lazy-loading and unloaded-attribute errors.
- Buffered synchronous execution.

Near-term additions:

- AsyncSession support.
- Streaming.
- Nested adapters for explicitly projected relationships.
- SQLModel-focused examples and FastAPI integration guides.

Deferred:

- Automatic relationship traversal.
- Automatic persistence repair.
- Automatic model generation.
- Deep ORM graph validation.
- Automatic response-model integration.
- Implicit transaction management.
- Replacement for `session.exec()`.
- Reimplementation of SQLModel CRUD features.

---

# What RowGuard Must Never Claim

RowGuard documentation should not claim that:

- SQLModel is broken.
- SQLModel has no validation.
- SQLModel cannot use separate response or data models.
- SQLModel should validate every database row automatically for all users.
- RowGuard replaces SQLModel.
- SQLRules pushdown fully represents Pydantic validation.

The accurate positioning is:

> SQLModel provides a combined Pydantic and SQLAlchemy modeling experience.
> RowGuard adds an explicit validation-and-rejection workflow for database reads
> when applications need stronger evidence that selected data satisfies a
> current read contract.

---

# Recommended Positioning

## One Sentence

> RowGuard adds validation-first SELECT workflows and rejected-row handling to
> SQLModel applications.

## Longer Positioning

> Continue using SQLModel for table models, relationships, sessions, and CRUD.
> Use RowGuard when selected data must be explicitly revalidated against a
> Pydantic or SQLModel read contract, with SQL pushdown, structured diagnostics,
> streaming, and configurable handling for invalid persisted rows.

---

# Design Principles

- Complement SQLModel; do not replace it.
- Validate selected values explicitly.
- Prefer separate read contracts.
- Prefer projections for strict and scalable reads.
- Keep SQLModel persistence behavior under SQLAlchemy's control.
- Avoid lazy loading during validation.
- Treat SQLRules pushdown as an optimization, not proof of validity.
- Preserve SQLModel sessions and transactions.
- Make rejected database rows first-class outcomes.
- Describe SQLModel accurately and respectfully.
