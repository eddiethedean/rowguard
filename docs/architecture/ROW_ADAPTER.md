# ROW_ADAPTER.md

# RowGuard Row Adapter

## Purpose

The Row Adapter converts database result rows into deterministic mappings that
Pydantic can validate.

It is the boundary between SQLAlchemy's result objects and RowGuard's validation
engine.

```text
SQLAlchemy Row
      │
      ▼
Row Adapter
      │
      ▼
Mapping[str, Any]
      │
      ▼
Pydantic Validation
```

The Row Adapter does not validate data, execute queries, or decide how rejected
rows are handled.

---

# Responsibilities

The Row Adapter is responsible for:

- Converting SQLAlchemy row objects into mappings.
- Preserving stable field names.
- Resolving column labels and aliases.
- Applying explicit field-to-column mappings.
- Detecting duplicate or ambiguous result keys.
- Handling ORM entities and scalar results when supported.
- Producing structured adaptation diagnostics.
- Avoiding unnecessary copies where practical.

The Row Adapter is not responsible for:

- Pydantic validation.
- SQLRules compilation.
- Query construction.
- Database execution.
- Rejection-policy decisions.
- Business-level data transformation.

---

# Core Contract

A Row Adapter accepts a raw result value and an adaptation context.

```python
class RowAdapter(Protocol):
    def adapt(
        self,
        row: object,
        context: RowAdapterContext,
    ) -> Mapping[str, object]:
        ...
```

The result must be suitable for:

```python
model.model_validate(mapping)
```

The returned mapping should be deterministic and must not silently discard
ambiguous values.

---

# Default Adapter

The default adapter should support SQLAlchemy 2.x `Row` objects using the row's
mapping interface.

Conceptually:

```python
mapping = row._mapping
```

The implementation should depend on documented SQLAlchemy behavior and isolate
SQLAlchemy-specific access behind the adapter boundary.

The default adapter may return an immutable mapping view when no renaming or
copying is required.

---

# Adaptation Context

The immutable `RowAdapterContext` should contain the information needed to map a
database result to a Pydantic model.

Suggested fields:

```python
@dataclass(frozen=True, slots=True)
class RowAdapterContext:
    model: type[BaseModel]
    field_map: Mapping[str, str]
    use_aliases: bool
    extra_columns: ExtraColumnPolicy
    missing_fields: MissingFieldPolicy
    duplicate_keys: DuplicateKeyPolicy
```

The context should be created during execution planning rather than reconstructed
for every row.

---

# Field Name Resolution

RowGuard needs a predictable strategy for matching result keys to Pydantic
fields.

Recommended resolution order:

1. Explicit field mapping supplied by the user.
2. Exact Pydantic field name.
3. Pydantic validation alias, when alias support is enabled.
4. SQLAlchemy column key.
5. SQLAlchemy column label.
6. Adapter-specific fallback, if explicitly configured.

The adapter must not use fuzzy matching.

Example:

```python
result = rowguard.select(
    session=session,
    statement=stmt,
    model=UserRead,
    field_map={
        "user_id": "id",
        "display_name": "name",
    },
)
```

The mapping direction should be documented consistently. Recommended form:

```python
{
    "pydantic_field_name": "result_key"
}
```

This makes the target contract the primary reference.

---

# Pydantic Aliases

RowGuard should distinguish between:

- Field name
- Validation alias
- Serialization alias

The Row Adapter is concerned only with input validation, so validation aliases
may be relevant while serialization aliases generally are not.

Alias handling should be explicit:

```python
use_aliases=True
```

When aliases conflict with field names or explicit mappings, explicit mappings
take precedence.

---

# SQLAlchemy Core Rows

For a typical Core query:

```python
stmt = select(
    users.c.id,
    users.c.name,
)
```

SQLAlchemy may return a row with keys such as:

```python
{
    "id": 1,
    "name": "Ada",
}
```

The adapter should preserve these keys unless a mapping policy requires
renaming.

---

# Labeled Columns

Queries often label expressions:

```python
stmt = select(
    users.c.id.label("user_id"),
    users.c.name.label("display_name"),
)
```

The adapter should expose the labels as result keys.

An explicit field map can connect them to the Pydantic model:

```python
field_map={
    "id": "user_id",
    "name": "display_name",
}
```

---

# Joined Queries

Joined queries may contain duplicate column names.

Example:

```python
select(users.c.id, teams.c.id)
```

A plain mapping may not be safe because both columns are named `id`.

RowGuard should require one of the following:

- Explicit SQLAlchemy labels.
- An explicit field map.
- A configured duplicate-key policy.

The default behavior should be to raise an adaptation error rather than silently
choose one value.

Recommended query:

```python
select(
    users.c.id.label("user_id"),
    teams.c.id.label("team_id"),
)
```

---

# ORM Entity Rows

SQLAlchemy ORM queries may return:

- A mapped entity.
- Multiple mapped entities.
- An entity plus scalar expressions.
- Row objects containing ORM entities.

RowGuard should not flatten arbitrary ORM object graphs implicitly.

Recommended support levels:

## Direct Entity

For a single ORM entity, the adapter may extract mapped column attributes into a
mapping.

## Entity Row

For a row containing one named entity, the adapter may delegate to an ORM entity
adapter.

## Multiple Entities

Require an explicit adapter or mapping configuration.

This avoids ambiguous nested structures and accidental lazy loading.

---

# SQLModel Compatibility

SQLModel instances are both ORM objects and Pydantic models, but RowGuard should
still treat selected database values as untrusted input.

The adapter may extract mapped values from SQLModel entities and then validate
them against the requested target model.

It should not assume that an existing SQLModel instance has already undergone
the desired read-time validation.

---

# Scalar Results

A scalar query returns a single value rather than a row mapping.

Example:

```python
select(func.count())
```

The default model-validation path expects mappings. Scalar support should
therefore be explicit.

Possible future API:

```python
rowguard.execute_scalar(
    session=session,
    statement=stmt,
    adapter=ScalarAdapter(field="count"),
    model=CountResult,
)
```

The adapter would produce:

```python
{"count": scalar_value}
```

Scalar adaptation should not be guessed automatically.

---

# Tuple and Sequence Rows

Some integrations may provide tuples or sequences without named keys.

RowGuard should require an explicit positional adapter:

```python
PositionalRowAdapter(
    fields=("id", "name", "age"),
)
```

This converts:

```python
(1, "Ada", 37)
```

into:

```python
{
    "id": 1,
    "name": "Ada",
    "age": 37,
}
```

The default adapter should reject unnamed positional rows.

---

# Extra Columns

A query may return columns not declared by the target Pydantic model.

RowGuard should provide explicit policies:

```python
extra_columns="preserve"
extra_columns="drop"
extra_columns="error"
```

Recommended default:

```python
extra_columns="preserve"
```

Pydantic's model configuration then determines whether extras are accepted,
ignored, or rejected.

This preserves Pydantic as the source of truth and avoids duplicating its extra
field semantics inside RowGuard.

An optimization mode may pre-project only required fields, but it must not alter
observable validation semantics.

---

# Missing Fields

If a result does not contain a required model field, the adapter should normally
leave it absent and allow Pydantic to produce the canonical validation error.

Policies may include:

```python
missing_fields="pydantic"  # default
missing_fields="error"
```

The default should defer required/default behavior to Pydantic.

The adapter must not insert `None` for missing values unless explicitly
configured because absence and null are semantically different.

---

# Duplicate Keys

Duplicate or ambiguous keys are dangerous because they can silently bind the
wrong database value to a model field.

Policies:

```python
duplicate_keys="error"   # default
duplicate_keys="first"
duplicate_keys="last"
```

Only `"error"` should be encouraged for production use.

If non-error modes are supported, RowGuard should emit diagnostics explaining
which value was selected.

---

# Nested Models

Flat SQL rows do not naturally represent nested Pydantic structures.

Nested adaptation should be explicit.

Example target:

```python
class UserWithTeam(BaseModel):
    id: int
    team: TeamRead
```

A future nesting adapter could accept:

```python
NestedRowAdapter(
    fields={
        "id": "user_id",
        "team": {
            "id": "team_id",
            "name": "team_name",
        },
    },
)
```

Output:

```python
{
    "id": 1,
    "team": {
        "id": 10,
        "name": "Platform",
    },
}
```

The MVP should prioritize flat mappings and avoid implicit nesting conventions.

---

# Null Values

The adapter must preserve SQL `NULL` values as Python `None`.

It should not:

- Replace nulls with defaults.
- Drop null-valued keys.
- Coerce nulls into strings or zeros.

Pydantic is responsible for deciding whether `None` is valid.

---

# Type Conversion

The adapter should perform structural adaptation, not semantic coercion.

It may:

- Rename keys.
- Reshape explicitly configured nested objects.
- Extract mapped attributes.
- Convert rows to mappings.

It should not:

- Parse dates.
- Cast strings to integers.
- Normalize enums.
- Trim strings.
- Apply application defaults.

Those behaviors belong to Pydantic validators or an explicit transformation
plugin.

---

# Adaptation Result

For richer diagnostics, the internal adapter API may return an `AdaptedRow`
object:

```python
@dataclass(frozen=True, slots=True)
class AdaptedRow:
    raw: object
    mapping: Mapping[str, object]
    diagnostics: tuple[AdaptationDiagnostic, ...]
```

The public validation engine consumes `mapping`, while rejected-row reporting
can retain both the raw and adapted representations.

---

# Adaptation Errors

All public adaptation errors should derive from:

```python
RowAdaptationError
```

Suggested exceptions:

```text
RowGuardError
└── RowAdaptationError
    ├── UnsupportedRowTypeError
    ├── AmbiguousColumnError
    ├── MissingResultKeyError
    ├── InvalidFieldMapError
    └── AdapterConfigurationError
```

Adaptation errors are different from Pydantic validation failures.

A malformed or ambiguous row shape means RowGuard could not safely construct the
validation input. It should therefore fail according to an adaptation-error
policy, not a validation-rejection policy.

---

# Diagnostics

Useful adaptation diagnostics include:

- Raw result keys.
- Field mappings applied.
- Aliases used.
- Extra keys encountered.
- Missing keys.
- Duplicate keys.
- ORM attributes extracted.
- Nested structures created.

Diagnostics should be optional and low-cost when disabled.

---

# Performance

The Row Adapter runs once for every processed row, so it is performance
sensitive.

Guidelines:

- Precompute mapping plans during execution planning.
- Avoid introspecting the Pydantic model for every row.
- Avoid copying when the original mapping is already valid.
- Use immutable, slotted planning objects.
- Cache ORM attribute extraction metadata.
- Keep the common SQLAlchemy `Row._mapping` path minimal.
- Do not sacrifice correctness for micro-optimizations.

Target complexity:

- Time: O(k) per row, where k is the number of selected or mapped fields.
- Additional memory: O(k) only when remapping or reshaping is required.

---

# Adapter Registry

Future versions may provide an adapter registry keyed by row shape or explicit
adapter name.

```python
registry.register(
    "sqlalchemy-row",
    SQLAlchemyRowAdapter(),
)
```

Potential official adapters:

- `SQLAlchemyRowAdapter`
- `ORMEntityAdapter`
- `SQLModelEntityAdapter`
- `PositionalRowAdapter`
- `ScalarAdapter`
- `NestedRowAdapter`

Automatic dispatch should be conservative. Explicit adapters should win over
inferred adapters.

---

# Plugin Contract

Third-party adapters should implement a stable public protocol and declare:

- Supported input types.
- Whether they preserve raw rows.
- Whether they copy data.
- Whether they support streaming.
- Whether they may trigger lazy loading.
- Their configuration schema.

Adapters must not execute additional database queries unless explicitly
documented and enabled.

---

# Testing Requirements

Each adapter should be tested for:

- Correct key preservation.
- Explicit field mapping.
- Alias behavior.
- Missing fields.
- Extra fields.
- Null values.
- Duplicate columns.
- Labeled columns.
- Joined queries.
- ORM entities.
- Unsupported row types.
- Deterministic output.
- Streaming compatibility.
- Performance regressions.

Tests should validate both the adapted mapping and the resulting Pydantic model.

---

# Security and Correctness

Incorrect row adaptation can bind the wrong database column to a model field,
which may create subtle security or authorization bugs.

Therefore:

- Fuzzy key matching is prohibited.
- Ambiguity raises by default.
- Duplicate keys are never silently ignored by default.
- Explicit mappings are validated before execution.
- Adapter diagnostics should avoid leaking sensitive values unless configured.
- Raw rows retained in rejection objects should follow application data-handling
  policies.

---

# MVP Scope

The first RowGuard release should support:

- SQLAlchemy 2.x `Row` objects.
- Mapping-like rows.
- Explicit field maps.
- Column labels.
- Pydantic field-name matching.
- Pydantic validation aliases when enabled.
- Null preservation.
- Clear errors for ambiguous or unsupported shapes.

Deferred:

- Automatic nested model construction.
- Arbitrary ORM graph flattening.
- Positional tuples without explicit configuration.
- Scalar inference.
- Implicit semantic type conversion.
- Lazy relationship loading.

---

# Design Principles

- Adapt structure, not meaning.
- Preserve raw values.
- Prefer explicit mappings.
- Fail on ambiguity.
- Defer validation semantics to Pydantic.
- Keep the common path fast.
- Make every transformation observable.
