# TYPE_SUPPORT.md

# RowGuard Validation Type Support

## Purpose

This document defines the types RowGuard supports at the validation boundary.

RowGuard does not implement its own type system. It receives values from
SQLAlchemy and database drivers, adapts row structure, and delegates semantic
validation to Pydantic.

The central rule is:

> RowGuard adapts structure; Pydantic validates meaning.

Type support therefore depends on three layers:

1. The database and driver value returned by SQLAlchemy.
2. The Row Adapter's ability to preserve or reshape that value.
3. Pydantic's ability to validate the value into the requested target type.

---

# Scope

This document covers:

- Scalar Python types.
- Date and time types.
- Decimal and numeric values.
- UUID and identifier types.
- Enum and literal types.
- Collections and mappings.
- Nested Pydantic models.
- JSON and database-native structured values.
- Optional and nullable fields.
- Specialized Pydantic types.
- ORM entities and attribute-based inputs.
- Unsupported and deferred categories.

This document does not define SQLRules translation support. SQL pushdown support
is a separate concern and may be narrower than RowGuard validation support.

---

# Type Support Model

```text
Database Column
      │
      ▼
Database Driver Value
      │
      ▼
SQLAlchemy Result
      │
      ▼
Row Adapter
      │
      ▼
Pydantic Validation
      │
      ▼
Validated Model Field
```

A type is considered supported by RowGuard when:

- SQLAlchemy can return the value.
- The Row Adapter can preserve or explicitly reshape it.
- Pydantic can validate it into the target field.

---

# Core Principle: No Hidden Semantic Coercion

RowGuard should not add type conversions before Pydantic validation unless an
explicit adapter or transformation plugin is configured.

RowGuard may:

- Rename keys.
- Preserve SQLAlchemy row mappings.
- Build explicitly configured nested dictionaries.
- Extract mapped scalar attributes.
- Wrap scalar values into explicit mapping fields.

RowGuard should not:

- Parse strings into dates.
- Convert floats to decimals.
- Normalize enum names.
- Trim strings.
- Convert empty strings to null.
- Split delimited strings into lists.
- Interpret JSON strings automatically.
- Convert timezones.
- Apply application defaults.

Those behaviors belong to:

- Pydantic validation.
- Explicit SQL expressions.
- Explicit row adapters.
- Explicit repair or transformation layers.

---

# Compatibility Targets

Initial targets:

- Python 3.10+
- Pydantic v2
- SQLAlchemy 2.x
- SQLRules-compatible Pydantic models

Actual driver return types may vary by database backend and driver.

RowGuard should document those differences rather than pretending every backend
returns identical Python values.

---

# Scalar Type Matrix

| Target Type | Validation Support | Notes |
| --- | :---: | --- |
| `bool` | Yes | Driver and strictness behavior may vary |
| `int` | Yes | Pydantic controls coercion |
| `float` | Yes | Precision follows database/driver value |
| `Decimal` | Yes | Preferred for exact numeric values |
| `str` | Yes | No automatic trimming or normalization |
| `bytes` | Yes | Driver must return bytes-like data |
| `None` | Yes | Usually through optional/nullable fields |
| `UUID` | Yes | Driver may return UUID or string |
| `date` | Yes | Pydantic validates returned representation |
| `time` | Yes | Timezone behavior remains model-defined |
| `datetime` | Yes | Naive/aware rules require explicit validation |
| `timedelta` | Yes | Driver and dialect support vary |
| `Enum` | Yes | Name/value storage differences matter |
| `Literal` | Yes | Enforced by Pydantic after retrieval |

"Yes" means RowGuard can pass the value to Pydantic without adding its own
semantic conversion.

---

# Boolean Values

Database backends may represent booleans as:

- Native booleans.
- Integers such as `0` and `1`.
- Strings.
- Driver-specific values.

Target model:

```python
class FeatureRead(BaseModel):
    enabled: bool
```

Pydantic decides whether the value is accepted.

For strict storage validation:

```python
class FeatureRead(BaseModel):
    enabled: Annotated[bool, Field(strict=True)]
```

or:

```python
result = rowguard.select(
    ...,
    strict=True,
)
```

RowGuard should not normalize truthy or falsy values itself.

---

# Integer Values

Typical sources:

- SQL integer columns.
- Small integer columns.
- Big integer columns.
- Numeric expressions.
- Count aggregates.

Target:

```python
class CountRead(BaseModel):
    count: int
```

Potential concerns:

- Driver-specific integer wrappers.
- Values outside expected application range.
- Decimal values returned from aggregate expressions.
- Boolean values accepted as integers under non-strict semantics.

Pydantic remains authoritative.

SQLRules may push supported integer constraints into SQL, but RowGuard still
validates the returned value.

---

# Floating-Point Values

Floating-point values may be returned as Python `float`.

Target:

```python
class MeasurementRead(BaseModel):
    value: float
```

Cautions:

- Binary floating-point precision.
- Backend-specific handling of special values.
- `NaN` and infinity behavior.
- Equality and modulo edge cases.
- Differences between SQL comparison semantics and Pydantic constraints.

Applications requiring exact values should prefer `Decimal`.

RowGuard should not round or normalize floats.

---

# Decimal Values

Exact numeric database columns often return `Decimal`.

Target:

```python
class InvoiceRead(BaseModel):
    total: Decimal
```

Supported concerns include:

- Precision.
- Scale.
- Maximum digits.
- Decimal constraints.
- Driver conversion.

Pydantic determines whether the returned value satisfies the field.

RowGuard must not convert decimals through float because that can lose
precision.

---

# String Values

Target:

```python
class UserRead(BaseModel):
    name: str
```

Supported Pydantic behaviors may include:

- Minimum and maximum length.
- Patterns.
- Strictness.
- Case conversion.
- Whitespace stripping.
- Custom validators.

RowGuard should preserve the driver-provided string exactly.

Potential database differences include:

- Collation.
- Character encoding.
- Padding for fixed-width types.
- Unicode normalization.
- Character vs byte length.
- Case sensitivity.

SQLRules pushdown may reduce candidates, but Pydantic validation remains final.

---

# Fixed-Width Character Data

Some databases pad fixed-width character fields.

Example database value:

```python
"ABC   "
```

RowGuard should not trim it automatically.

Applications may handle this through:

- A SQL expression such as `trim(column)`.
- A Pydantic string-transform configuration.
- A field validator.
- An explicit repair layer.

Automatic trimming would alter source data semantics and must not be hidden.

---

# Binary Values

Target types may include:

```python
bytes
bytearray
memoryview
```

MVP recommendation:

- Support `bytes` directly.
- Allow Pydantic to handle compatible bytes-like inputs.
- Preserve driver-returned binary data.
- Avoid automatic base64 conversion.

Large binary values may make rejection retention expensive.

Applications should configure:

```python
retain_raw_rows=False
error_values="omit"
```

when handling sensitive or large binary payloads.

---

# UUID Values

Database drivers may return UUID columns as:

- `uuid.UUID`.
- Strings.
- Bytes.
- Driver-specific wrappers.

Target:

```python
class RecordRead(BaseModel):
    id: UUID
```

Pydantic validates the representation.

RowGuard should not normalize UUID strings or byte order.

SQLRules may push equality or membership constraints when supported by the
database and SQLAlchemy expression type.

---

# Date Values

Target:

```python
class EventRead(BaseModel):
    event_date: date
```

Possible inputs:

- Python `date`.
- Python `datetime`.
- ISO strings.
- Driver-specific date objects.

Pydantic determines accepted conversions.

Strict models can require exact date-like inputs.

RowGuard should not truncate datetimes into dates.

---

# Time Values

Target:

```python
class ScheduleRead(BaseModel):
    starts_at: time
```

Potential concerns:

- Timezone-aware vs timezone-naive values.
- Fractional seconds.
- Backend-specific precision.
- Driver-specific time objects.

RowGuard should pass values unchanged.

Applications requiring timezone or range rules should express them through
Pydantic validators.

---

# Datetime Values

Target:

```python
class AuditRead(BaseModel):
    created_at: datetime
```

Possible backend behavior:

- Timezone-aware values.
- Timezone-naive values.
- UTC-normalized values.
- Strings.
- Driver-specific timestamp wrappers.

RowGuard should not:

- Assume UTC.
- Add timezone information.
- Remove timezone information.
- Convert to local time.
- Normalize daylight-saving transitions.

Timezone requirements should be explicit in the model or validators.

---

# Timedelta and Interval Values

Database interval types may return:

- Python `timedelta`.
- Strings.
- Driver-specific interval objects.
- Numeric durations.

Target:

```python
class DurationRead(BaseModel):
    duration: timedelta
```

Support depends heavily on the dialect and driver.

MVP behavior:

- Pass through `timedelta`.
- Let Pydantic validate compatible values.
- Require explicit adapters for driver-specific interval objects.

SQLRules pushdown for intervals may be deferred even when validation works.

---

# Optional and Nullable Fields

Optional type:

```python
name: str | None
```

Database `NULL` becomes Python `None`.

RowGuard should preserve `None`.

It must not infer that an optional field should be filtered with:

```sql
IS NULL
```

or:

```sql
IS NOT NULL
```

Optionality is a validation contract, not automatically a query predicate.

---

# Missing vs Null

These are distinct:

```python
{}
```

and:

```python
{"name": None}
```

Pydantic may treat them differently because:

- Missing values may use defaults.
- Null values may fail non-optional fields.
- Validators may inspect field presence.

The Row Adapter must preserve the distinction.

---

# Literal Types

Example:

```python
status: Literal["active", "pending"]
```

Pydantic validates membership.

SQLRules may push the equivalent SQL `IN` predicate.

RowGuard still validates the returned value.

Literal support applies to compatible values such as:

- Strings.
- Integers.
- Booleans.
- Enum-like scalar values.

---

# Enum Types

Example:

```python
class Status(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
```

```python
status: Status
```

Database storage may contain:

- Enum values.
- Enum names.
- Native database enum objects.
- Strings.
- Integers.

The model determines which representation is accepted.

RowGuard should not guess whether stored text means the enum name or value.

An explicit SQL expression or adapter may normalize legacy storage before
validation.

---

# Union Types

Pydantic may validate union fields.

Example:

```python
identifier: int | UUID
```

RowGuard passes the source value to Pydantic.

Potential ambiguity is resolved according to Pydantic's union semantics and
model configuration.

RowGuard should not preselect a branch.

---

# Discriminated Unions

Discriminated unions are supported when the adapted mapping contains the
required discriminator.

Example:

```python
class CatRead(BaseModel):
    kind: Literal["cat"]
    lives: int


class DogRead(BaseModel):
    kind: Literal["dog"]
    breed: str


class AnimalRead(BaseModel):
    animal: Annotated[
        CatRead | DogRead,
        Field(discriminator="kind"),
    ]
```

The Row Adapter is responsible for producing the nested shape.

Pydantic selects and validates the union branch.

---

# Lists

A field may target:

```python
list[str]
```

Sources may include:

- Database array columns.
- JSON arrays.
- Aggregate functions.
- Driver-returned lists.
- Explicit adapters.

RowGuard should preserve the sequence.

It should not split strings or aggregate multiple rows automatically.

---

# Tuples

Pydantic may validate tuple fields such as:

```python
tuple[int, str]
```

Support requires the row value itself to be a tuple-like structure.

RowGuard should not convert arbitrary database rows into tuple-valued fields
without explicit adapter configuration.

---

# Sets and Frozen Sets

Target types:

```python
set[str]
frozenset[str]
```

Pydantic may accept compatible collections.

RowGuard should preserve the original collection value.

Applications should remember that set conversion may remove duplicates and
change ordering as part of Pydantic validation semantics.

---

# Dictionaries and Mappings

Target:

```python
dict[str, object]
```

Sources may include:

- JSON object columns.
- HSTORE-like mappings.
- Driver-returned dictionaries.
- Explicit nested adapters.

RowGuard should pass mappings through.

It should not parse arbitrary JSON strings into mappings automatically.

---

# Nested Models

Nested models are fully supported when the Row Adapter builds the required
mapping shape.

Example:

```python
class AddressRead(BaseModel):
    city: str
    postal_code: str


class UserRead(BaseModel):
    id: int
    address: AddressRead
```

Required input:

```python
{
    "id": 1,
    "address": {
        "city": "Tampa",
        "postal_code": "33606",
    },
}
```

Flat SQL rows require an explicit nesting adapter or a query that returns
structured JSON.

---

# Recursive Models

Pydantic may support recursive models.

RowGuard can validate recursive structures when the database result or adapter
provides them.

Automatic recursive graph assembly from relational rows is outside the MVP.

Potential concerns:

- Cycles.
- Very deep structures.
- Large payloads.
- ORM relationship traversal.
- Memory usage.

---

# JSON Values

Database JSON columns may return:

- Python dictionaries.
- Python lists.
- Scalar JSON values.
- Strings, depending on driver and configuration.

RowGuard should preserve the returned Python value.

Target examples:

```python
metadata: dict[str, object]
tags: list[str]
payload: PayloadModel
```

Pydantic validates the structure.

RowGuard should not assume a string column containing JSON should be parsed.

---

# JSON Strings

If a database returns JSON text as `str`, RowGuard should not parse it
implicitly.

Applications may:

- Cast or decode in SQL.
- Use an explicit adapter.
- Use a Pydantic before-validator.
- Use a repair layer.

Implicit parsing can hide malformed storage and produce surprising behavior.

---

# Database Arrays

PostgreSQL and other backends may return array values as Python lists.

RowGuard can validate them into:

- Lists.
- Tuples.
- Sets.
- Nested models.
- Constrained collection types.

Support depends on the database driver.

SQLRules pushdown for array predicates belongs to dialect-specific SQLRules
extensions, not RowGuard core.

---

# Database Range Types

Some dialects expose range types through driver-specific Python objects.

MVP behavior:

- Pass the object through.
- Allow Pydantic custom types or arbitrary-type configuration to validate it.
- Require explicit adapters to convert ranges into standard structures.

Future dialect plugins may provide standard range adapters.

---

# Geospatial Types

Geospatial drivers may return:

- WKB bytes.
- WKT strings.
- Driver-specific geometry objects.
- Third-party geometry classes.

RowGuard core should not interpret geospatial values.

Applications may use:

- Pydantic custom types.
- Explicit adapters.
- Database-side conversion functions.
- Geospatial plugins.

---

# Network Types

Pydantic supports specialized network types such as:

- IPv4 and IPv6 addresses.
- Networks.
- URLs.
- Email addresses.

Database drivers often return strings or native address objects.

RowGuard passes the value to Pydantic.

SQLRules may not push all semantic checks, but post-query validation remains
available.

---

# Path and File Types

Pydantic may validate path-like values.

Database values are typically strings.

RowGuard should not:

- Access the filesystem.
- Check file existence.
- Resolve relative paths.
- Expand user directories.

Any such behavior belongs to explicit validators and should be used carefully in
large query workloads.

---

# Secret Types

Pydantic secret types may mask values during representation.

RowGuard can validate values into these target types.

However:

- Raw row mappings may still contain the original secret.
- Rejected-row diagnostics may expose invalid values.
- Logging must use redaction policies.
- Quarantine storage must be secured.

The target model's masked representation does not automatically protect retained
raw inputs.

---

# Constrained and Annotated Types

Pydantic v2 often expresses constraints through `Annotated`.

Example:

```python
age: Annotated[int, Field(ge=18, le=120)]
```

RowGuard supports these because Pydantic validates them normally.

SQLRules may push supported constraints into SQL.

Unsupported SQL pushdown does not reduce RowGuard validation support.

---

# Custom Pydantic Types

Custom types are supported when Pydantic can validate the driver value.

Examples:

- Domain identifiers.
- Money types.
- Custom date wrappers.
- Value objects.
- Third-party Pydantic-integrated classes.

RowGuard should not inspect or special-case arbitrary custom schemas in the MVP.

Custom validation cost and side effects remain the application's responsibility.

---

# Arbitrary Types

Models configured to allow arbitrary types may accept driver-specific objects.

RowGuard can pass them through, but this reduces portability.

Potential risks:

- Non-serializable result models.
- Session-bound ORM objects.
- Driver-specific APIs.
- Mutable shared state.
- Difficult testing.

Documentation should recommend explicit domain types or adapters when practical.

---

# ORM Entity Types

ORM entities are not ordinary scalar field values.

A model field that directly contains an ORM entity may validate only through:

- Arbitrary-type support.
- Attribute-based validation.
- Custom Pydantic integration.

RowGuard should not automatically embed ORM entities into output models.

For nested domain objects, explicit projections and nested mappings are safer.

---

# SQLModel Types

SQLModel read models are supported because they are Pydantic-compatible.

SQLModel table entities may be used as sources.

Using SQLModel table classes as target models is allowed but should be explicit,
as persistence and read contracts may differ.

The same type-support rules apply:

- Mapping-based validation preferred.
- Attribute-based validation opt-in.
- Relationships not traversed automatically.
- SQLAlchemy internal state excluded.

---

# Root Models

`RootModel` support requires the adapter to produce the expected root input.

Examples:

```python
class Tags(RootModel[list[str]]):
    pass
```

A JSON array column could be validated through a scalar/root adapter.

Automatic root-model handling is deferred beyond the MVP.

---

# TypeAdapter Targets

A future RowGuard version may accept arbitrary Pydantic-supported target types
through `TypeAdapter`.

Examples:

```python
list[UserRead]
TypedDict
dataclass
int
UUID
```

This would broaden RowGuard beyond model outputs.

Initial releases should remain focused on `BaseModel` outputs for API clarity and
typed `QueryResult[T]` behavior.

---

# ORM Attribute Extraction Types

When entity mapping is used, RowGuard should extract only planned scalar
attributes.

Potential mapped values include:

- Column values.
- Column properties.
- Loaded hybrid values.
- Composite values.
- Deferred values.

Unloaded or relationship attributes require explicit policies.

The type presented to Pydantic must reflect the extracted attribute value
without SQLAlchemy internal state.

---

# Composite Types

SQLAlchemy composite mappings may expose domain objects built from multiple
columns.

RowGuard may support them when:

- The composite is already loaded.
- The target Pydantic field accepts the object.
- An explicit adapter converts it to a mapping.
- No implicit database I/O is triggered.

Automatic composite decomposition is deferred.

---

# Large Objects

Large values include:

- BLOBs.
- CLOBs.
- Large JSON.
- Large text.
- Large arrays.

Validation is supported, but applications should consider:

- Memory usage.
- Rejection retention.
- Error serialization.
- Logging.
- Streaming.
- Quarantine payload size.

RowGuard should allow per-query controls such as:

```python
retain_raw_rows=False
retain_adapted_rows=False
error_values="omit"
```

---

# Driver-Specific Types

Database drivers may return custom objects.

Examples:

- Native range classes.
- Geometry wrappers.
- Interval wrappers.
- JSON wrappers.
- Vendor-specific LOB handles.

RowGuard's default behavior is pass-through.

Support options:

1. Pydantic validates the object directly.
2. A custom Row Adapter converts it.
3. A dialect plugin provides adaptation.
4. The query converts it in SQL.

RowGuard should not hard-code every driver-specific type in core.

---

# Unknown Types

If a value reaches Pydantic and Pydantic accepts it, RowGuard may accept the
model.

If the Row Adapter cannot preserve the value safely, adaptation fails before
validation.

If Pydantic rejects the value, the row follows the configured rejection policy.

Unknown values should not be stringified automatically.

---

# Type Mismatches

Example database row:

```python
{"age": "not-an-integer"}
```

Target:

```python
class UserRead(BaseModel):
    age: int
```

Possible outcomes:

- Pydantic rejects the value.
- RowGuard creates a `RejectedRow`.
- The rejection policy determines whether processing continues.

RowGuard should preserve the original value subject to privacy policy.

---

# Strict Storage Auditing

Applications may want to detect values that Pydantic would normally coerce.

Example:

```python
{"age": "42"}
```

Non-strict Pydantic may accept this as integer `42`.

For storage auditing, use:

```python
strict=True
```

or strict field annotations.

RowGuard should document that non-strict acceptance proves model compatibility,
not exact storage-type fidelity.

---

# Type Support vs SQL Pushdown

Validation support and SQLRules support must remain separate.

Example:

```python
email: EmailStr
```

RowGuard validation:

- Supported through Pydantic.

SQLRules pushdown:

- May have no portable equivalent.

Another example:

```python
tags: list[str]
```

RowGuard validation:

- Supported if driver returns a list.

SQLRules pushdown:

- Depends on dialect-specific array or JSON support.

The project should maintain separate matrices for:

- Validation support.
- Row adaptation support.
- SQLRules pushdown support.
- Dialect support.

---

# Type Support Classification

Recommended documentation categories:

## Native

Works through the default row adapter and Pydantic without extra configuration.

Examples:

- `int`
- `str`
- `bool`
- `Decimal`
- `date`
- `datetime`
- `UUID`
- `Enum`
- `Literal`

## Driver-Dependent

Works when the database driver returns a compatible Python value.

Examples:

- Arrays.
- Intervals.
- Native ranges.
- JSON.
- Large objects.

## Adapter-Required

Requires explicit structural conversion.

Examples:

- Flat rows into nested models.
- Positional tuples.
- Scalar rows into named model fields.
- Driver-specific geometry objects.
- Root models.

## Deferred

Not part of the initial scope.

Examples:

- Automatic relational aggregation into collections.
- Automatic ORM graph conversion.
- Automatic geospatial normalization.
- Automatic JSON string parsing.

---

# Validation Type Matrix

| Category | Examples | Default Adapter | Pydantic Validation | SQLRules Pushdown |
| --- | --- | :---: | :---: | :---: |
| Primitive scalar | `int`, `str`, `bool`, `float` | Yes | Yes | Often |
| Exact numeric | `Decimal` | Yes | Yes | Often |
| Temporal | `date`, `time`, `datetime` | Yes | Yes | Often |
| Identifier | `UUID` | Yes | Yes | Dialect-dependent |
| Enum/Literal | `Enum`, `Literal` | Yes | Yes | Often |
| Optional/null | `T | None` | Yes | Yes | Explicit only |
| JSON mapping | `dict`, nested model | Driver-dependent | Yes | Dialect-dependent |
| JSON array | `list[T]` | Driver-dependent | Yes | Dialect-dependent |
| Database array | `list[T]` | Driver-dependent | Yes | Plugin-dependent |
| Nested relational model | `UserWithTeam` | Adapter-required | Yes | Partial |
| ORM entity | mapped class | ORM adapter | Conditional | Not applicable as value |
| Geospatial | geometry types | Plugin/adapter | Custom | Plugin-dependent |
| Root model | `RootModel[T]` | Adapter-required | Yes | Not automatic |
| Arbitrary type | custom class | Pass-through | Model-dependent | Rare |

---

# Row Adapter Responsibilities

The Row Adapter determines whether a type arrives in a form Pydantic can
understand.

Examples:

## No Adaptation Required

```python
{"id": 1, "name": "Ada"}
```

## Key Renaming

```python
{"user_id": 1}
```

becomes:

```python
{"id": 1}
```

## Explicit Nesting

```python
{
    "user_id": 1,
    "team_id": 10,
}
```

becomes:

```python
{
    "id": 1,
    "team": {
        "id": 10,
    },
}
```

## Scalar Wrapping

```python
42
```

becomes:

```python
{"count": 42}
```

Structural adaptation should be explicit and deterministic.

---

# Error Handling

Type-related failures can occur in different stages.

## Adaptation Error

The value cannot be safely shaped for validation.

Examples:

- Ambiguous duplicate keys.
- Unsupported row object.
- Missing explicit scalar field name.
- Failed driver-specific adapter.

## Validation Error

Pydantic receives the input but rejects it.

Examples:

- Invalid integer.
- Malformed UUID.
- Invalid enum value.
- Nested model failure.

## Unexpected Validation Error

A custom validator raises an unexpected exception.

These categories must remain distinct for diagnostics and rejection policies.

---

# Error Redaction

Type errors may include sensitive values.

Examples:

- Password hashes.
- Tokens.
- Personal data.
- Binary payloads.
- Large documents.

RowGuard should support:

```python
error_values="preserve"
error_values="redact"
error_values="omit"
```

Redaction applies to retained diagnostics, logs, and serialization.

It must not alter validation input.

---

# Serialization Considerations

A validated Pydantic model may contain types that are not directly JSON
serializable without Pydantic serialization.

Examples:

- `Decimal`
- `UUID`
- `datetime`
- bytes
- arbitrary types

RowGuard returns models, not serialized payloads.

Export helpers should use Pydantic's serialization APIs and explicit policies.

The type being valid does not imply that every export format is supported.

---

# Performance Considerations

Some types are more expensive to validate:

- Large nested JSON.
- Deep models.
- Long collections.
- Custom validators.
- Regex-heavy strings.
- Large decimals.
- Binary payloads.

Guidelines:

- Use SQL projection to avoid unused large columns.
- Stream large result sets.
- Disable raw row retention when not needed.
- Avoid duplicate conversion.
- Push supported constraints into SQL through SQLRules.
- Measure custom type and validator cost.
- Keep adapters simple and preplanned.

---

# Async Considerations

Pydantic type validation remains synchronous.

Driver-specific values may expose lazy or async behavior, especially ORM
attributes and LOB handles.

RowGuard should not permit implicit async I/O during type validation.

Values requiring I/O should be materialized during the execution/adaptation
stage before Pydantic validation.

---

# Testing Requirements

Tests should cover:

- `bool`
- `int`
- `float`
- `Decimal`
- `str`
- `bytes`
- `UUID`
- `date`
- `time`
- `datetime`
- `timedelta`
- `Enum`
- `Literal`
- Optional fields
- Missing vs null
- Unions
- Discriminated unions
- Lists
- Tuples
- Sets
- Dictionaries
- Nested models
- JSON objects and arrays
- Database arrays where supported
- Strict vs non-strict behavior
- Driver-specific values
- Custom types
- Arbitrary types
- Large values
- Root-model adapters
- Mapping and attribute validation
- Error redaction
- Sync and async parity
- SQLRules pushdown followed by Pydantic validation

Cross-dialect tests should document actual driver return types.

---

# MVP Scope

Initial validation support should include:

- Primitive scalars.
- `Decimal`.
- Strings and bytes.
- `UUID`.
- Date, time, and datetime.
- Optional fields.
- Enum and Literal.
- Lists, tuples, sets, and dictionaries when already returned as Python
  structures.
- Nested Pydantic models with explicit nested mappings.
- SQLModel and Pydantic model targets.
- Strict and non-strict validation.
- Complete Pydantic error preservation.
- Mapping-based validation.
- Explicit ORM attribute validation.
- Driver-provided JSON values.
- Structured type-support diagnostics.

Deferred:

- Automatic JSON string parsing.
- Automatic ORM relationship graph conversion.
- Automatic relational aggregation into collections.
- Generic `TypeAdapter` result targets.
- Geospatial normalization.
- Database range normalization.
- Automatic interval normalization.
- Driver-specific plugin catalog.
- Cross-driver type canonicalization.
- Automatic root-model inference.
- Automatic large-object materialization.

---

# Recommended Public Examples

## Strict Numeric Validation

```python
class PaymentRead(BaseModel):
    amount: Annotated[Decimal, Field(strict=True, gt=0)]
```

```python
result = rowguard.select(
    session=session,
    table=payments,
    model=PaymentRead,
    on_reject="collect",
)
```

## Nested JSON Validation

```python
class MetadataRead(BaseModel):
    source: str
    tags: list[str]


class EventRead(BaseModel):
    id: UUID
    metadata: MetadataRead
```

## Explicit Nested Relational Adaptation

```python
result = rowguard.execute(
    session=session,
    statement=stmt,
    model=UserWithTeamRead,
    row_adapter=NestedRowAdapter(
        fields={
            "id": "user_id",
            "team": {
                "id": "team_id",
                "name": "team_name",
            },
        },
    ),
)
```

## Strict Storage Audit

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    strict=True,
    on_reject="collect",
)
```

---

# Design Principles

- Pydantic owns semantic type validation.
- RowGuard preserves database values unless adaptation is explicit.
- Structure and meaning are separate concerns.
- Missing and null must remain distinct.
- Strictness should be explicit.
- Driver differences should be documented, not hidden.
- Validation support is broader than SQL pushdown support.
- Unknown values are never stringified automatically.
- Large and sensitive values require deliberate retention policies.
- Type behavior must remain deterministic and observable.
