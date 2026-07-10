# ORM.md

:::{admonition} Status: not shipped in 0.4.0
:class: warning

This document is a **design draft for 0.5.0**. SQLAlchemy ORM mapped-class
integration is **not available** yet. 0.4 supports SQLAlchemy Core `Table` /
`Select` only. See [Supported vs planned](../project/supported.md).
:::

# RowGuard SQLAlchemy ORM Integration

## Purpose

RowGuard is designed to support SQLAlchemy ORM applications without becoming an
ORM itself. **This integration is planned for 0.5.0 and is not shipped in 0.4.**

When shipped, the ORM integration will allow RowGuard to:

- Query mapped classes through SQLAlchemy.
- Validate selected database values into Pydantic models.
- Apply SQLRules filters against mapped columns.
- Handle invalid rows explicitly.
- Work alongside existing `Session` workflows.

RowGuard does not replace SQLAlchemy's mapper, unit of work, identity map,
relationships, persistence model, or transaction management.

---

# Core Distinction

SQLAlchemy ORM answers:

> How are Python objects mapped to database tables and persisted?

RowGuard answers:

> Do the values returned by this query satisfy the requested Pydantic contract?

These responsibilities are complementary.

```text
SQLAlchemy ORM
      │
      ├── Mapping
      ├── Relationships
      ├── Identity map
      ├── Persistence
      └── Transactions

RowGuard
      │
      ├── Query planning
      ├── SQLRules pushdown
      ├── Row adaptation
      ├── Pydantic validation
      └── Rejection handling
```

---

# Goals

The ORM integration should:

- Accept mapped classes and ORM `Select` statements.
- Work with SQLAlchemy 2.x `Session`.
- Preserve existing ORM query semantics.
- Validate selected values into independent Pydantic models.
- Support labeled projections and explicit field mappings.
- Avoid triggering unintended lazy loads.
- Keep ORM entity state separate from validated result models.
- Support synchronous and asynchronous sessions.

---

# Non-Goals

RowGuard does not:

- Define mapped classes.
- Manage the identity map.
- Track changes.
- Flush or commit entities.
- Cascade relationship operations.
- Replace eager-loading strategies.
- Generate ORM mappings.
- Convert Pydantic models into persistent entities.
- Guarantee that an ORM entity itself is a valid Pydantic model.
- Automatically repair database state.

---

# Architectural Position

```text
Mapped Class / ORM Select
          │
          ▼
   SQLAlchemy Session
          │
          ▼
      ORM Result
          │
          ▼
   RowGuard Adapter
          │
          ▼
 Pydantic Validation
          │
          ├── Valid Model
          └── Rejected Row
```

The ORM remains responsible for database interaction.

RowGuard treats selected values as validation input.

---

# Supported ORM Inputs

The initial ORM integration should support:

- Mapped classes.
- ORM `Select` statements.
- `Session`.
- `AsyncSession`.
- Single-entity queries.
- Column projection queries.
- Entity-plus-column queries with explicit adaptation.
- Aliased mapped classes.
- Explicit eager loading where it does not alter the validation contract.

More complex shapes should require explicit adapters or mappings.

---

# Querying a Mapped Class

A simple mapped-class query may look like:

```python
result = rowguard.select(
    session=session,
    entity=User,
    model=UserRead,
)
```

Conceptually, RowGuard constructs:

```python
stmt = select(User)
```

It may then apply SQLRules expressions against mapped attributes:

```python
User.age >= 18
```

Every returned entity is adapted into a mapping and validated as `UserRead`.

---

# Existing ORM Statements

RowGuard should accept existing ORM statements.

```python
stmt = (
    select(User)
    .where(User.enabled.is_(True))
    .order_by(User.name)
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

RowGuard must preserve:

- Existing WHERE clauses.
- Loader options.
- ORDER BY clauses.
- LIMIT and OFFSET.
- Joins.
- Aliases.
- Bound parameters.
- Execution options.

It may create a new SQLAlchemy statement when adding pushdown filters, but it
must not mutate the caller's statement.

---

# Entity Validation Strategy

A mapped ORM entity is not automatically a safe Pydantic validation input.

The default ORM adapter should extract mapped column attributes into a mapping.

Example:

```python
{
    "id": entity.id,
    "name": entity.name,
    "age": entity.age,
}
```

RowGuard should avoid passing arbitrary ORM objects directly to Pydantic unless
the user explicitly selects attribute-based validation.

Recommended default:

```python
model.model_validate(mapping)
```

Optional advanced mode:

```python
model.model_validate(entity, from_attributes=True)
```

Mapping-based validation is preferred because it:

- Makes selected values explicit.
- Avoids accidental relationship traversal.
- Reduces lazy-loading risk.
- Keeps result-shape behavior consistent with Core.

---

# from_attributes Support

Pydantic can validate from object attributes.

RowGuard may expose:

```python
orm_validation="mapping"         # default
orm_validation="from_attributes"
```

## mapping

Extract mapped columns according to the row-adaptation plan.

## from_attributes

Pass the entity to Pydantic with attribute-based validation enabled.

`from_attributes` should be opt-in because it may:

- Access hybrid properties.
- Access descriptors.
- Trigger lazy loads.
- Traverse relationships.
- Execute application code.
- Produce different results from selected database columns.

Diagnostics should report which mode was used.

---

# Selected Columns vs Full Entities

A projected ORM query is often preferable to loading full entities.

```python
stmt = select(
    User.id,
    User.name,
    User.age,
)
```

This returns row mappings instead of fully managed entities.

Advantages:

- Lower memory overhead.
- No identity-map population for entity instances.
- Clear result shape.
- Reduced accidental lazy loading.
- Better streaming behavior.

RowGuard should encourage projected queries for read-contract validation.

---

# Identity Map

When a query returns ORM entities, SQLAlchemy may reuse existing instances from
the session identity map.

This means the in-memory entity may:

- Already exist before the query.
- Contain pending changes.
- Have expired attributes.
- Reflect session state beyond the selected statement.

RowGuard must not imply that entity validation proves the persisted database row
is identical to the in-memory object.

For strict database-read validation, projected column queries are preferred.

Potential API:

```python
entity_source="session_state"
entity_source="selected_columns"
```

The MVP may simply document the distinction and recommend projections.

---

# Pending Changes and Autoflush

SQLAlchemy sessions may autoflush pending changes before a query.

RowGuard should preserve the session's configured behavior.

It must not:

- Disable autoflush silently.
- Trigger additional flushes beyond normal SQLAlchemy execution.
- Commit pending changes.

Applications may use:

```python
with session.no_autoflush:
    result = rowguard.select(...)
```

when needed.

Diagnostics may record that an ORM session was used, but RowGuard should not
attempt to inspect arbitrary pending state.

---

# Expired Attributes

Mapped entity attributes may be expired.

Accessing an expired attribute can cause SQLAlchemy to issue another query.

The default ORM adapter should avoid unplanned attribute access when possible.

Preferred approaches:

1. Validate projected columns.
2. Use mapper metadata to extract only known loaded column attributes.
3. Detect unloaded or expired attributes.
4. Raise or report a clear adaptation error instead of silently loading them.

Potential policy:

```python
unloaded_attributes="error"      # recommended
unloaded_attributes="load"
unloaded_attributes="omit"
```

The MVP should prefer `"error"` or projected queries.

---

# Lazy-Loaded Relationships

RowGuard must not automatically traverse relationships.

Example:

```python
class UserRead(BaseModel):
    team: TeamRead
```

Accessing:

```python
user.team
```

may trigger a database query.

Automatic relationship traversal can create:

- N+1 queries.
- Unexpected I/O during validation.
- Transaction surprises.
- Performance instability.
- Recursive object graphs.

Therefore, nested ORM validation should require one of:

- Explicit eager loading.
- Explicit joined projection.
- A custom ORM adapter.
- Opt-in `from_attributes` behavior.

---

# Eager Loading

Applications may use SQLAlchemy loader options:

```python
stmt = (
    select(User)
    .options(selectinload(User.team))
)
```

RowGuard should preserve loader options.

However, the presence of eager loading does not automatically mean relationships
should be included in validation.

The target Pydantic model and adapter configuration remain the source of truth.

---

# Relationship Projections

For deterministic nested models, RowGuard should favor explicit projections.

```python
stmt = (
    select(
        User.id.label("user_id"),
        User.name.label("user_name"),
        Team.id.label("team_id"),
        Team.name.label("team_name"),
    )
    .join(User.team)
)
```

A nested adapter can then produce:

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

This avoids implicit ORM graph traversal.

---

# Aliased Classes

SQLAlchemy aliased classes should be supported.

```python
Manager = aliased(User)

stmt = (
    select(User, Manager)
    .join(Manager, User.manager_id == Manager.id)
)
```

Automatic adaptation is ambiguous when multiple entities of the same mapped
class are selected.

RowGuard should require:

- Explicit entity aliases.
- Explicit field mappings.
- A custom adapter.
- Labeled column projections.

Automatic flattening should fail by default.

---

# ORM Joins

ORM joins should work through existing statements.

```python
stmt = (
    select(User.id, User.name, Team.name.label("team_name"))
    .join(User.team)
)
```

The same principles as Core joins apply:

- Use stable result labels.
- Avoid duplicate keys.
- Keep pushdown mappings explicit.
- Validate final row shape, not relationship intent.

---

# Outer Joins

Outer joins have the same semantic risk as Core outer joins.

A pushed-down filter on the nullable side may eliminate null-extended rows.

RowGuard should not automatically add such filters without an explicit safe
mapping or policy.

The ORM integration should reuse the same outer-join pushdown safeguards as the
Core integration.

---

# Polymorphic Mappings

SQLAlchemy supports inheritance and polymorphic loading.

A query may return different mapped subclasses.

RowGuard should validate each returned shape against the requested Pydantic
model.

Potential behaviors:

- One common Pydantic base model.
- Discriminated Pydantic unions.
- Model selection through a plugin or callback.

The MVP should support validation of common projected columns and defer automatic
polymorphic model dispatch.

---

# Hybrid Properties

Hybrid properties may be usable in SQL expressions and as Python attributes.

They introduce dual semantics:

- SQL expression behavior during query construction.
- Python descriptor behavior during entity access.

RowGuard should not automatically treat every hybrid property as a model field.

Support should require:

- Explicit projection and label.
- Explicit pushdown column/expression map.
- Opt-in attribute validation.

This keeps behavior deterministic.

---

# Column Properties

Mapped `column_property()` values may be selected and adapted when they are part
of the query result or loaded entity state.

RowGuard should treat them like other mapped scalar attributes, subject to
loaded-state checks.

---

# Synonyms and Descriptors

ORM synonyms or custom descriptors may hide application logic.

Automatic adaptation should rely primarily on mapper metadata and explicit
configuration.

Custom attributes should require opt-in `from_attributes` validation or an
adapter plugin.

---

# Deferred Columns

Deferred mapped columns may not be loaded.

Accessing them may trigger additional queries.

RowGuard should:

- Prefer projection queries when validating specific contracts.
- Detect deferred/unloaded fields when validating entities.
- Avoid silent loads by default.
- Allow explicit policies for loading or omission.

---

# SQLRules Pushdown

SQLRules can compile against mapped class attributes.

Example:

```python
rules = sqlrules.compile(
    UserRead,
    User,
)
```

Potential expressions:

```python
User.age >= 18
User.status.in_(["active", "pending"])
```

RowGuard adds them to the ORM `Select`.

For aliases:

```python
rules = sqlrules.compile(
    UserRead,
    UserAlias,
)
```

The alias must be used consistently.

---

# Field Mapping

A Pydantic model may not use ORM attribute names.

Example:

```python
class UserRead(BaseModel):
    user_id: int
    display_name: str
```

Mapped class:

```python
User.id
User.name
```

Pushdown map:

```python
pushdown_column_map={
    "user_id": User.id,
    "display_name": User.name,
}
```

Entity adaptation map:

```python
attribute_map={
    "user_id": "id",
    "display_name": "name",
}
```

Projected-query labels can eliminate the need for an adaptation map:

```python
select(
    User.id.label("user_id"),
    User.name.label("display_name"),
)
```

---

# Result Shapes

ORM queries may return several shapes.

## Single Entity

```python
select(User)
```

Result row contains one `User` entity.

## Entity plus Scalar

```python
select(User, func.count(Address.id))
```

Requires explicit adaptation.

## Multiple Entities

```python
select(User, Team)
```

Requires explicit adaptation or projection.

## Scalar Columns

```python
select(User.id, User.name)
```

Handled like Core row mappings.

## Scalar Entity Result

```python
session.scalars(select(User))
```

May be supported by an entity adapter, but RowGuard's standard execution path
should preserve access to result shape metadata.

---

# Session Integration

The synchronous ORM API should accept a `Session`.

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

RowGuard must preserve:

- Current transaction.
- Autoflush behavior.
- Identity-map behavior.
- Bound parameters.
- Execution options.
- Loader options.

It should not commit, rollback, expunge, refresh, merge, or close the session.

---

# AsyncSession Integration

Async ORM support should mirror synchronous behavior.

```python
result = await rowguard.aexecute(
    session=async_session,
    statement=stmt,
    model=UserRead,
)
```

Pydantic validation remains synchronous and CPU-bound.

Only SQLAlchemy I/O is awaited.

The async adapter must remain careful about lazy loading because implicit async
I/O from attribute access can be especially error-prone.

Projected queries are strongly preferred.

---

# Streaming ORM Results

Entity streaming can populate the identity map and retain ORM instances longer
than expected.

For large result sets, RowGuard should recommend projected scalar-column queries
rather than full entity queries.

Potential streaming safeguards:

- Yield-per execution options.
- Explicit result partitions.
- Session expiration policies documented by the application.
- No retention of accepted ORM entities after Pydantic model construction.
- Minimal raw-row retention.

RowGuard should yield Pydantic models, not managed entities.

---

# Validation Target

The target of RowGuard validation should normally be a separate Pydantic model.

```python
class UserRead(BaseModel):
    id: int
    name: str
```

This creates a clear read contract independent of persistence behavior.

Using the mapped class itself as the validation target should be supported only
when it is also a Pydantic-compatible model, such as SQLModel, and even then the
read-time validation path must remain explicit.

---

# Rejected Rows

When entity-based adaptation fails or Pydantic validation rejects a row,
`RejectedRow` should preserve relevant context.

Possible retained fields:

- Entity identity key.
- Primary-key values.
- Raw entity reference, when allowed.
- Adapted mapping.
- Pydantic error.
- Loaded/unloaded attribute diagnostics.
- Statement metadata.

Raw ORM entity retention should be configurable because entities:

- Remain associated with a session.
- May expose lazy-loaded state.
- May retain large graphs.
- May not be safely serializable.

Recommended default:

```python
retain_raw_entity=False
retain_identity=True
retain_mapping=True
```

---

# Identity Metadata

For diagnostics, RowGuard may record SQLAlchemy identity information without
retaining the full entity.

Example:

```python
{
    "mapper": "User",
    "identity": (123,),
}
```

This helps operators locate the invalid database row.

Identity extraction should use SQLAlchemy mapper state rather than assumptions
about column names.

---

# Rejection Callbacks

A rejection callback must not mutate or delete ORM entities implicitly.

If an application wants to repair or quarantine data, it should do so through
an explicit callback with clearly documented transaction behavior.

Potential callback context:

```python
def on_reject(rejected, context):
    ...
```

The callback may receive the session only when explicitly enabled.

This reduces accidental writes during read validation.

---

# Transaction Semantics

RowGuard executes within the caller's ORM transaction.

It should not:

- Commit after validation.
- Roll back on ordinary row rejection.
- Flush repaired entities automatically.
- Open nested transactions for callbacks unless configured.

Ordinary validation failure is a data-classification event, not necessarily a
transaction failure.

A `raise` rejection policy may propagate an exception while leaving transaction
handling to the caller.

---

# ORM Events

RowGuard should not depend on SQLAlchemy ORM event hooks for core behavior.

Reasons:

- Hidden global behavior.
- Difficult lifecycle management.
- Interference with unrelated queries.
- Harder testing.
- Unexpected performance impact.

Optional observability plugins may use events carefully, but the default
integration should remain explicit and local to each execution.

---

# Mapper Introspection

The ORM adapter may use SQLAlchemy mapper inspection to:

- Identify mapped scalar attributes.
- Discover primary-key identity.
- Detect relationship properties.
- Detect unloaded attributes.
- Resolve column expressions.
- Build deterministic extraction plans.

Mapper introspection should occur during query compilation rather than once per
row whenever possible.

---

# Pydantic Aliases

ORM attribute names may differ from Pydantic validation aliases.

Resolution order should remain explicit:

1. User-provided attribute map.
2. Pydantic field name.
3. Pydantic validation alias, when enabled.
4. Mapped attribute key.
5. Selected result label.

Fuzzy matching is prohibited.

---

# Extra Attributes

Full ORM entities contain state beyond the Pydantic model.

The adapter should extract only the planned attributes by default.

This avoids passing internal SQLAlchemy state such as:

```python
_sa_instance_state
```

to Pydantic.

RowGuard must never expose SQLAlchemy internal state as model input.

---

# Missing Attributes

If the Pydantic model requires a field that the entity adapter cannot resolve,
RowGuard should fail planning when possible.

If the field exists but is unloaded, behavior follows the unloaded-attribute
policy.

If a projected result omits the field, Pydantic should normally report the
canonical missing-field error.

---

# Performance

ORM entity validation can be more expensive than Core projection validation.

Potential overhead includes:

- Identity-map population.
- Entity construction.
- Mapper instrumentation.
- Attribute state checks.
- Relationship loading risks.

Performance guidance:

- Prefer projected columns for large reads.
- Precompute extraction plans.
- Avoid `from_attributes` unless needed.
- Avoid retaining raw entities.
- Stream carefully.
- Validate each row exactly once.
- Do not traverse relationships implicitly.

---

# Diagnostics

Useful ORM diagnostics include:

- Mapped class name.
- Mapper identity.
- Query result shape.
- Validation mode.
- Attributes extracted.
- Attributes unloaded.
- Relationships skipped.
- Alias used.
- Identity-map entity reuse, when detectable.
- Pushdown source.
- Loader options present.

Diagnostics should not serialize entity state automatically.

---

# Errors

Suggested ORM integration error hierarchy:

```text
RowGuardError
└── ORMIntegrationError
    ├── UnmappedClassError
    ├── UnsupportedORMResultShapeError
    ├── UnloadedAttributeError
    ├── AmbiguousEntityError
    ├── LazyLoadBlockedError
    ├── InvalidAttributeMapError
    └── ORMAdaptationError
```

SQLAlchemy exceptions should remain available as causes.

---

# Security and Correctness

ORM integration can introduce hidden behavior if implemented carelessly.

RowGuard must:

- Avoid implicit lazy loading by default.
- Never include SQLAlchemy internal state in validation input.
- Keep authorization filters explicit.
- Preserve bound parameters.
- Fail on ambiguous entity shapes.
- Avoid retaining sensitive entities unnecessarily.
- Document transaction and callback behavior.
- Distinguish in-memory entity state from persisted database state.

---

# Testing Requirements

Tests should cover:

- Single mapped entity queries.
- Projected column queries.
- Existing ORM statements.
- SQLRules pushdown against mapped attributes.
- Aliased classes.
- Inner and outer joins.
- Entity-plus-scalar results.
- Multiple entities.
- `from_attributes` opt-in.
- Pydantic aliases.
- Attribute maps.
- Unloaded attributes.
- Deferred columns.
- Expired attributes.
- Lazy relationships.
- Eager-loaded relationships.
- Hybrid properties.
- Column properties.
- Polymorphic mappings.
- Identity-map reuse.
- Pending changes and autoflush.
- Session transaction preservation.
- AsyncSession parity.
- Streaming behavior.
- Rejected-row identity metadata.
- Error propagation.

---

# MVP Scope

The first ORM release should support:

- SQLAlchemy 2.x mapped classes.
- Synchronous `Session`.
- Existing ORM `Select`.
- Single-entity queries.
- Projected scalar-column queries.
- SQLRules pushdown against mapped scalar attributes.
- Explicit attribute maps.
- Explicit column labels.
- Mapping-based Pydantic validation.
- Primary-key identity diagnostics.
- Clear errors for unloaded or ambiguous entity state.
- No implicit relationship traversal.

Deferred:

- Automatic nested relationship adaptation.
- Full polymorphic model dispatch.
- Implicit scalar/entity combination flattening.
- Automatic repair of entities.
- ORM write-back.
- Event-driven integration.
- Lazy-load-enabled validation by default.
- Deep entity graph validation.
- Relationship-aware SQLRules compilation.

---

# Recommended Usage Patterns

## Preferred: Projected Read Contract

```python
stmt = select(
    User.id,
    User.name,
    User.age,
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
)
```

This is the clearest and most predictable ORM integration.

## Supported: Single Entity

```python
result = rowguard.select(
    session=session,
    entity=User,
    model=UserRead,
    orm_validation="mapping",
)
```

The adapter extracts planned scalar attributes.

## Explicit Aliased Entity

```python
UserAlias = aliased(User)

stmt = select(
    UserAlias.id.label("id"),
    UserAlias.name.label("name"),
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    pushdown_source=UserAlias,
)
```

## Explicit Nested Projection

```python
stmt = (
    select(
        User.id.label("user_id"),
        User.name.label("user_name"),
        Team.id.label("team_id"),
        Team.name.label("team_name"),
    )
    .join(User.team)
)

result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserWithTeamRead,
    row_adapter=NestedRowAdapter(...),
)
```

---

# Design Principles

- Integrate with the ORM; do not become one.
- Prefer projected columns over implicit entity traversal.
- Validate read contracts independently of persistence models.
- Avoid lazy loading by default.
- Keep identity-map semantics visible.
- Preserve caller-owned sessions and transactions.
- Use mapper metadata instead of guessing.
- Separate mapped attributes from Pydantic fields explicitly.
- Never confuse a managed ORM entity with a validated read model.
- Keep the Core and ORM execution pipelines as consistent as practical.
