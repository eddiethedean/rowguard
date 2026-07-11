# PYDANTIC.md

:::{admonition} Design notes
:class: caution

Day-to-day validation behavior is covered in the [API guide](../api.md) and
[rejection policies](../guides/rejection-policies.md). Callback/quarantine
mentions below are **not shipped** in 0.5.0.
:::

# RowGuard Pydantic Integration

## Purpose

Pydantic is the validation authority inside RowGuard.

RowGuard does not reimplement Pydantic validation. Instead, it prepares database
rows as explicit validation inputs, invokes Pydantic through its public APIs,
captures the result, and routes failures through RowGuard's rejection system.

The central contract is:

> A row is accepted only after the requested Pydantic model validates it.

---

# Architectural Position

```text
Database Result
      │
      ▼
Row Adapter
      │
      ▼
Mapping[str, Any]
      │
      ▼
Pydantic model_validate()
      │
      ├── Valid Model
      └── ValidationError
              │
              ▼
       Rejection Handling
```

Pydantic owns validation semantics.

RowGuard owns orchestration, diagnostics, statistics, and rejected-row handling.

---

# Goals

The Pydantic integration should:

- Support Pydantic v2 models.
- Preserve normal Pydantic validation behavior.
- Validate every adapted row exactly once.
- Support strict and non-strict models.
- Support aliases.
- Support field validators and model validators.
- Support nested models.
- Support validation context.
- Preserve complete `ValidationError` details.
- Remain independent from SQLAlchemy result shape through the Row Adapter.
- Avoid hidden coercion outside Pydantic.

---

# Non-Goals

RowGuard does not:

- Reimplement Pydantic Core.
- Translate arbitrary Python validators into SQL.
- Replace `BaseModel`.
- Generate models automatically in the MVP.
- Modify model configuration.
- Swallow or flatten validation errors.
- Add implicit defaults.
- Repair invalid values unless an explicit repair layer is configured.
- Treat database schema constraints as equivalent to Pydantic validation.

---

# Supported Model Types

The initial integration should accept:

- Pydantic v2 `BaseModel` subclasses.
- Generic Pydantic models when fully parameterized.
- Root models where an adapter provides the expected root input.
- Pydantic dataclasses only through an explicit validator adapter in a later
  release.
- SQLModel data models because SQLModel models are Pydantic-compatible.
- SQLModel table models when explicitly selected as the validation target.

The primary public type remains:

```python
type[BaseModel]
```

---

# Primary Validation API

RowGuard should validate adapted mappings through:

```python
validated = Model.model_validate(mapping)
```

This is the default and preferred path.

Potential configuration:

```python
validated = Model.model_validate(
    mapping,
    strict=strict,
    from_attributes=from_attributes,
    context=context,
)
```

Only documented Pydantic keyword arguments should be forwarded.

---

# Mapping-Based Validation

Mapping-based validation is the RowGuard default.

```python
mapping = {
    "id": 1,
    "name": "Ada",
    "age": 37,
}

model = UserRead.model_validate(mapping)
```

Benefits:

- The exact input contract is visible.
- SQLAlchemy internals are excluded.
- Result aliases are explicit.
- ORM lazy loading is avoided.
- Core, ORM, SQLModel, and raw SQL converge on one validation path.
- Rejected rows can preserve the same mapping that Pydantic received.

---

# Attribute-Based Validation

Attribute-based validation may be enabled explicitly for ORM or SQLModel
entities.

```python
model = UserRead.model_validate(
    entity,
    from_attributes=True,
)
```

Shipped API:

```python
rowguard.select(
    ...,
    orm_validation="from_attributes",
)
```

Attribute validation should not be the default because it may:

- Access descriptors.
- Trigger lazy loads.
- Access deferred or expired attributes.
- Traverse relationships.
- Execute application-defined property code.
- Produce inputs that differ from the actual selected column set.

RowGuard diagnostics should record when attribute validation is used.

---

# Model Configuration

RowGuard must honor the target model's existing `model_config`.

Relevant Pydantic settings may include:

- `strict`
- `extra`
- `populate_by_name`
- `from_attributes`
- string transformations
- frozen models
- arbitrary type handling
- validation defaults
- alias behavior

RowGuard should not clone or rewrite the model configuration.

Execution-level options may request stricter behavior only where Pydantic's
public API supports it.

---

# Strictness

Strictness may come from:

1. The model configuration.
2. Field-level strict annotations.
3. A RowGuard execution override.

Potential API:

```python
rowguard.select(
    ...,
    strict=True,
)
```

Recommended precedence:

1. Explicit execution override.
2. Model and field configuration.
3. Pydantic default behavior.

RowGuard should pass strictness to Pydantic rather than implementing its own type
checks.

---

# Coercion

Pydantic may coerce compatible inputs depending on model configuration.

Examples may include:

- Numeric strings to integers.
- Date strings to date objects.
- Enum values to enum members.

RowGuard should not claim that accepted values were originally stored in the
same Python type as the final model field.

The result guarantee is:

> The input was accepted by the configured Pydantic model.

Applications requiring storage-type fidelity should use strict models or
execution-level strict validation.

---

# Field Aliases

The Row Adapter and Pydantic serve different roles in alias handling.

## Row Adapter

Maps result keys into the expected validation-input keys.

## Pydantic

Determines whether field names, validation aliases, or alias choices are
accepted.

RowGuard should avoid duplicating Pydantic alias logic unnecessarily.

Preferred approach:

- Preserve result labels when they already match the model's accepted input keys.
- Use explicit field maps for legacy database names.
- Let Pydantic apply validation alias semantics.

---

# Validation Aliases

Pydantic validation aliases may be used by the target model.

Example:

```python
class UserRead(BaseModel):
    id: int = Field(validation_alias="user_id")
```

A row mapping containing:

```python
{"user_id": 1}
```

may validate without RowGuard renaming.

However, RowGuard planning should still inspect accepted input names when it must:

- Determine missing fields.
- Build projections.
- Produce diagnostics.
- Resolve pushdown mappings.

Serialization aliases are not relevant to database input validation unless the
application explicitly uses them as SQL labels.

---

# Alias Choices and Paths

Advanced Pydantic alias features may accept multiple input keys or nested paths.

RowGuard should preserve these semantics by passing the adapted mapping directly
to Pydantic.

The MVP should not attempt to reproduce alias-path resolution inside the Row
Adapter.

Planning diagnostics may be conservative when a model uses complex aliases.

---

# Extra Fields

Pydantic's `extra` configuration remains authoritative.

Possible model behavior:

- Ignore extra result keys.
- Allow extra result keys.
- Reject extra result keys.

The Row Adapter should preserve extras by default and allow Pydantic to decide.

Potential optimization:

```python
projection="model_fields"
```

may select only required fields, but this must be explicit because removing
extra columns can change validation behavior for models configured with
`extra="forbid"` or custom validators that inspect extra input.

---

# Missing Fields

Missing result keys should generally remain absent.

Pydantic then determines whether:

- The field is required.
- A default applies.
- A default factory applies.
- An alias provides the value.
- Validation should fail.

RowGuard must not insert `None` for missing fields because absence and null are
different states.

---

# Defaults

Pydantic defaults and default factories should work normally.

Example:

```python
class UserRead(BaseModel):
    enabled: bool = True
```

If the adapted row omits `enabled`, Pydantic may apply the default.

Whether omitted database columns should be allowed is an application contract
decision expressed by the model.

RowGuard should report the selected and missing keys in diagnostics when
requested.

---

# Null Values

Database `NULL` values should arrive as Python `None`.

Pydantic determines whether `None` is valid.

RowGuard should not:

- Drop null-valued fields.
- Replace nulls with defaults.
- Infer optionality-based filtering.
- Convert null to empty string or zero.

---

# Field Validators

Pydantic field validators execute normally during `model_validate()`.

Example:

```python
class UserRead(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username must not be blank")
        return value
```

RowGuard accepts the row only if Pydantic accepts it.

SQLRules may not be able to push this validator into SQL, but RowGuard's
post-query validation still enforces it.

---

# Model Validators

Cross-field rules remain Pydantic responsibilities.

Example:

```python
class DateRangeRead(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self
```

RowGuard cannot assume a valid SQL row satisfies this invariant unless Pydantic
validates it.

This is one of the strongest reasons RowGuard validation remains mandatory after
SQLRules pushdown.

---

# Before and Wrap Validators

Before and wrap validators may transform or inspect raw input.

RowGuard should pass the adapted input unchanged.

Because these validators can substantially alter semantics:

- SQLRules pushdown may only represent a subset of the final contract.
- Diagnostics should distinguish SQL-level filters from Pydantic-only logic.
- Strict read-contract users should review custom validator behavior carefully.

---

# Nested Models

Nested Pydantic models work when the Row Adapter produces the expected nested
structure.

Example:

```python
class TeamRead(BaseModel):
    id: int
    name: str


class UserRead(BaseModel):
    id: int
    name: str
    team: TeamRead
```

Expected input:

```python
{
    "id": 1,
    "name": "Ada",
    "team": {
        "id": 10,
        "name": "Platform",
    },
}
```

RowGuard's Validation Engine requires no nested-model-specific validation code.

Structural nesting belongs to the Row Adapter.

---

# Lists and Collections

Pydantic can validate list, tuple, set, and mapping fields inside a model.

RowGuard may validate these values when the database driver or adapter provides
the corresponding Python structures.

Examples:

- JSON arrays.
- PostgreSQL arrays.
- Aggregated JSON objects.
- Explicit nested adapters.

RowGuard should not automatically aggregate multiple database rows into one
collection-valued Pydantic model in the MVP.

That is a query-shaping concern.

---

# Enums

Pydantic validates enum values according to the target field and model
configuration.

SQLRules may push enum membership constraints into SQL.

RowGuard still validates the returned driver value into the target enum type.

Potential mismatches include:

- Enum names vs values.
- Native database enums.
- String-backed enums.
- Integer-backed enums.

The target Pydantic model remains authoritative.

---

# Date, Time, and Datetime

Database drivers may return:

- `date`
- `time`
- `datetime`
- strings
- timezone-aware values
- timezone-naive values

Pydantic validates according to field type and strictness.

RowGuard should not normalize timezones or parse date strings outside Pydantic.

Applications requiring timezone rules should express them through:

- Strict field types.
- Field validators.
- Model validators.
- Database-side explicit conversions.

---

# Decimal and Numeric Values

Database numeric types may arrive as:

- `int`
- `float`
- `Decimal`
- driver-specific numeric wrappers

Pydantic decides whether they satisfy the target type.

RowGuard should avoid converting between numeric representations before
validation.

SQLRules translator semantics and Pydantic numeric semantics may differ at edge
cases such as floating-point modulo or decimal scale; validation remains the
final authority.

---

# UUID and Specialized Types

Pydantic may validate database values into:

- UUIDs.
- IP addresses.
- URLs.
- email addresses.
- constrained strings.
- custom annotated types.

SQLRules may not push all such semantics into SQL.

RowGuard still supports them post-query because it delegates to Pydantic.

---

# Arbitrary Types

Models may allow arbitrary types.

RowGuard should pass database driver values through unchanged.

Support is limited by:

- Driver return types.
- Adapter behavior.
- Model configuration.
- Pydantic's ability to validate the type.

RowGuard should not serialize or copy arbitrary objects automatically.

---

# RootModel

Pydantic `RootModel` targets a root value rather than a field mapping.

Example:

```python
class UserIds(RootModel[list[int]]):
    pass
```

Standard SQL row validation is mapping-oriented, so `RootModel` support should
require an explicit adapter.

Example:

```python
rowguard.validate_rows(
    rows=values,
    model=UserIds,
    row_adapter=ScalarRootAdapter(),
)
```

Automatic root-model inference should be deferred.

---

# Generic Models

Fully parameterized generic models may be supported.

Example:

```python
class Envelope(BaseModel, Generic[T]):
    data: T
```

Target:

```python
Envelope[UserRead]
```

RowGuard should reject unparameterized generic targets when validation behavior
or typing would be ambiguous.

---

# Discriminated Unions

A model may contain discriminated unions.

RowGuard passes the adapted mapping to Pydantic, which selects the appropriate
branch.

This can support polymorphic read contracts when the query returns a stable
discriminator field.

Example:

```python
class CatRead(BaseModel):
    kind: Literal["cat"]
    lives: int


class DogRead(BaseModel):
    kind: Literal["dog"]
    breed: str
```

The Row Adapter must preserve the discriminator key.

---

# Validation Context

Pydantic supports validation context.

Potential RowGuard API:

```python
result = rowguard.select(
    ...,
    validation_context={
        "tenant_id": tenant_id,
        "request_id": request_id,
    },
)
```

RowGuard should pass context through:

```python
Model.model_validate(
    mapping,
    context=validation_context,
)
```

Use cases:

- Tenant-aware validators.
- Locale-aware validation.
- Policy versioning.
- Request tracing.
- Feature flags.

Context must be immutable or treated as read-only during execution.

---

# Context and Caching

Validation context can affect outcomes.

Therefore, RowGuard must not cache validated models solely by row values and
model type when context is present.

Execution-plan caches may store the fact that context is accepted, but not
context-specific validation outcomes.

---

# Revalidation of Existing Models

Pydantic may receive an existing model instance.

RowGuard's normal mapping path avoids this issue.

If the input is already an instance of the target model, RowGuard should not
blindly treat it as newly validated database data.

Potential policies:

```python
existing_model="revalidate"
existing_model="accept"
existing_model="error"
```

Recommended default for database-read workflows:

```python
revalidate
```

The exact behavior should follow Pydantic's configured revalidation semantics.

---

# Validation Result

Internally, RowGuard may normalize Pydantic outcomes into:

```python
@dataclass(frozen=True, slots=True)
class ValidationResult[T]:
    accepted: bool
    model: T | None
    error: ValidationError | None
    input_mapping: Mapping[str, object]
    duration_ns: int
```

This internal object keeps rejection policy separate from validation.

The public accepted value remains the model instance.

---

# Validation Errors

Ordinary invalid rows produce Pydantic `ValidationError`.

RowGuard should preserve:

- Error location.
- Error type.
- Error message.
- Context.
- Input fragments, subject to redaction policy.
- Target model.
- Row index.
- Source identity.

The original `ValidationError` should remain accessible from `RejectedRow`.

---

# Error Serialization

Pydantic errors can be rendered through APIs such as:

```python
error.errors()
error.json()
```

RowGuard should not pre-render errors by default.

Structured error data is more useful for:

- Programmatic handling.
- Metrics.
- Quarantine records.
- UI rendering.
- Testing.

Serialization should be explicit because errors may contain sensitive input.

---

# Privacy and Redaction

Validation errors may include portions of invalid input.

RowGuard should support redaction policies:

```python
error_values="preserve"
error_values="redact"
error_values="omit"
```

Recommended production default may depend on environment, but documentation
should warn that rejected-row diagnostics can contain sensitive data.

Redaction should affect diagnostics and serialization, not the actual Pydantic
validation process.

---

# Rejection Handling

Every Pydantic `ValidationError` becomes a RowGuard rejection event.

Depending on policy:

- `raise` propagates a RowGuard validation failure with the Pydantic error as the
  cause or payload.
- `collect` stores a `RejectedRow`.
- `skip` increments statistics and continues.
- `callback` invokes the configured handler.
- `quarantine` sends the rejected input to an explicit sink.

The Validation Engine itself does not choose the policy.

---

# Raise Policy

Under:

```python
on_reject="raise"
```

RowGuard should raise a contextual exception such as:

```python
RowValidationError
```

The exception should expose:

- The original `ValidationError`.
- Row index.
- Adapted input.
- Model type.
- Statement metadata.
- Source identity.

It should not erase Pydantic's error type or traceback.

---

# Validation Thresholds

Future workflows may allow processing to continue until a threshold is exceeded.

Examples:

```python
max_rejections=100
max_rejection_rate=0.01
```

Threshold evaluation belongs to execution and rejection policy, not Pydantic
integration.

Each row still undergoes ordinary Pydantic validation.

---

# Repair Workflows

A future repair layer may transform a rejected mapping and then submit it for a
second explicit Pydantic validation pass.

Safe sequence:

```text
Original mapping
      │
      ▼
Pydantic validation fails
      │
      ▼
Explicit repair callback
      │
      ▼
Repaired mapping
      │
      ▼
Pydantic validation again
```

RowGuard must record:

- Original failure.
- Repair applied.
- Repaired input.
- Final validation outcome.

Repair should not be hidden inside the Validation Engine's default path.

---

# SQLRules Relationship

SQLRules reads supported Pydantic field constraints and compiles SQLAlchemy
predicates.

Pydantic remains broader than SQLRules.

Examples of Pydantic behavior that may remain application-side:

- Custom validators.
- Model validators.
- Nested model semantics.
- Complex aliases.
- Specialized network and email types.
- Context-dependent rules.
- Cross-field invariants.
- Arbitrary Python validation logic.

Therefore:

> SQLRules reduces candidate rows; Pydantic determines acceptance.

---

# Schema Introspection

RowGuard may inspect Pydantic model metadata during query planning to support:

- Field mapping.
- Required-field diagnostics.
- Alias recognition.
- Projection planning.
- SQLRules integration.
- Type hints.

This introspection must not become a parallel validation implementation.

Pydantic's runtime validation remains authoritative.

---

# Projection Planning

RowGuard may use the Pydantic model to determine a minimal set of selected
columns.

Potential API:

```python
projection="model_fields"
```

This optimization is safe only when the planner accounts for:

- Validation aliases.
- Default values.
- Model validators.
- Extra-field behavior.
- Contextual validation.
- Fields derived from SQL expressions.
- Nested adapters.

The MVP should prefer explicit projections over aggressive automatic pruning.

---

# Model Validators and Projection Risks

A model validator may inspect fields that appear optional or have defaults.

Reducing the SQL projection based only on required fields could change
validation behavior.

Therefore, RowGuard must be conservative when deriving projections from model
metadata.

Explicit user selection remains the safest approach.

---

# Serialization Is Separate

Pydantic validation and Pydantic serialization are different phases.

RowGuard returns validated model instances.

It should not automatically call:

```python
model_dump()
model_dump_json()
```

unless the user invokes an explicit export helper.

Serialization options such as aliases, include/exclude, and computed fields do
not affect the core database-read validation contract.

---

# Computed Fields

Pydantic computed fields may appear during serialization but are not necessarily
database inputs.

RowGuard should not attempt to map database columns to computed fields unless
the target model explicitly accepts them as validation input through another
field or alias.

Computed values remain model behavior after validation.

---

# Private Attributes

Pydantic private attributes are not validation inputs.

RowGuard must not map database columns into private attributes automatically.

---

# Frozen Models

Frozen Pydantic models should work naturally.

RowGuard constructs them through normal validation and does not mutate accepted
models afterward.

This aligns well with RowGuard's preference for immutable result objects.

---

# Dataclasses and TypeAdapter

Future versions may support non-`BaseModel` targets through Pydantic
`TypeAdapter`.

Examples:

- Pydantic dataclasses.
- TypedDict.
- Plain dataclasses.
- Lists and unions.
- Scalar validated types.

Potential abstraction:

```python
validator = TypeAdapter(target_type)
validated = validator.validate_python(input_value)
```

This broadens RowGuard beyond model-only outputs, but should remain outside the
initial MVP to preserve a focused API.

---

# Validator Adapter Interface

Even though Pydantic is the default and primary engine, RowGuard should isolate
it behind a small internal protocol.

```python
class Validator(Protocol[T]):
    def validate(
        self,
        value: object,
        context: ValidationContext,
    ) -> ValidationResult[T]:
        ...
```

Default implementation:

```python
PydanticModelValidator
```

Benefits:

- Centralized Pydantic integration.
- Easier testing.
- Future Pydantic version adaptation.
- Optional `TypeAdapter` support.
- Clear separation from execution and rejection logic.

This is not intended to make Pydantic optional in the initial product.

---

# Validator Construction

A validator should be created during query compilation, not once per row.

It may precompute:

- Target model.
- Validation mode.
- Strict override.
- Attribute mode.
- Context pass-through.
- Error redaction policy.
- Model identity for diagnostics.

The per-row hot path should be minimal.

---

# Thread Safety

Pydantic model validation is normally safe to invoke concurrently when model
classes and shared configuration are not mutated.

RowGuard should:

- Treat model classes as immutable configuration.
- Avoid mutating validation context.
- Keep per-row result state local.
- Use immutable execution plans.
- Avoid global validator state.

---

# Async Behavior

Pydantic validation is synchronous and CPU-bound.

RowGuard async APIs should call it synchronously after awaiting database I/O.

RowGuard should not automatically offload every validation call to a thread pool,
because thread scheduling may cost more than validation for common rows.

Future optional batching or executor offload may be useful for unusually
expensive validators, but it must preserve:

- Ordering.
- Context.
- Error handling.
- Cancellation semantics.

---

# Streaming Behavior

Streaming validates one adapted row at a time.

A row must pass Pydantic validation before it is yielded.

```text
Fetch row
  → adapt
  → validate
  → yield accepted model
```

Rejected rows follow the configured streaming rejection policy.

No unvalidated row may be yielded.

---

# Performance

Pydantic validation is expected to be a significant application-side cost.

Guidelines:

- Validate exactly once per attempt.
- Reuse validator objects.
- Avoid copying mappings before validation.
- Use SQLRules pushdown to reduce candidate rows.
- Prefer explicit projections to reduce row size.
- Avoid hidden relationship loading.
- Keep diagnostics optional.
- Measure custom validator cost.
- Stream large datasets.

RowGuard should optimize orchestration around Pydantic, not attempt to bypass
Pydantic semantics.

---

# Statistics

Suggested validation metrics:

- Rows submitted to Pydantic.
- Rows accepted.
- Rows rejected.
- Total validation time.
- Average validation time.
- Maximum validation time.
- Validation error counts by type.
- Validation error counts by field path.
- Target model name.

High-cardinality values and raw inputs should not become metric labels.

---

# Diagnostics

Useful Pydantic diagnostics include:

- Target model.
- Validation mode.
- Strict override.
- Attribute mode.
- Context enabled.
- Alias configuration detected.
- Number of model fields.
- Presence of model validators.
- Error count.
- Error locations.
- Validation duration.

Diagnostics should avoid depending on undocumented Pydantic internals.

---

# Error Hierarchy

Suggested RowGuard validation errors:

```text
RowGuardError
└── ValidationEngineError
    ├── InvalidValidationTargetError
    ├── ValidationConfigurationError
    ├── RowValidationError
    ├── ValidationContextError
    └── UnexpectedValidationError
```

Ordinary invalid inputs should retain the original Pydantic `ValidationError`.

`UnexpectedValidationError` is reserved for non-validation exceptions raised by
misbehaving custom validators or integration bugs.

---

# Custom Validator Exceptions

Custom validators may raise exceptions other than the standard validation
exceptions Pydantic expects.

RowGuard should distinguish:

- A normal Pydantic `ValidationError`.
- An unexpected exception escaping validation.

Unexpected exceptions should normally stop execution under a dedicated error
policy because they may indicate:

- Application bugs.
- External service failures inside validators.
- Non-deterministic validator behavior.
- Resource errors.

They should not be silently classified as ordinary bad rows unless explicitly
configured.

---

# Determinism

RowGuard assumes validation is deterministic for a fixed:

- Input.
- Model.
- Model configuration.
- Validation context.
- Application environment.

Custom validators can violate this assumption by using:

- Current time.
- Randomness.
- Network calls.
- Mutable global state.
- Database queries.

RowGuard cannot prevent such validators, but documentation should discourage
I/O and non-determinism inside read-contract validation.

---

# Side Effects

Pydantic validators should ideally be pure.

RowGuard may validate thousands or millions of rows, retry repaired rows, or run
in streaming and async environments.

Validators with side effects can cause:

- Duplicate effects.
- Poor performance.
- Transaction coupling.
- Non-repeatable results.
- Difficult testing.

RowGuard should not attempt to manage validator side effects.

---

# Version Compatibility

Initial target:

- Pydantic v2.
- Public `BaseModel` and `model_validate()` APIs.
- Supported Pydantic releases declared in package metadata.

RowGuard should avoid relying on undocumented internal schema structures for
runtime validation.

Model introspection used for planning should be isolated so Pydantic version
changes can be handled centrally.

---

# Pydantic v1

Pydantic v1 should not be supported in the initial RowGuard core.

Reasons:

- Different validation APIs.
- Different field metadata.
- Increased test matrix.
- SQLRules is already designed around Pydantic v2.
- Supporting both would complicate early architecture.

A future compatibility adapter may be considered if demand justifies it.

---

# Testing Requirements

Tests should cover:

- Basic `BaseModel` validation.
- Strict and non-strict behavior.
- Field aliases.
- Validation aliases.
- Missing fields.
- Defaults and default factories.
- Null values.
- Extra-field modes.
- Field validators.
- Model validators.
- Before and wrap validators.
- Nested models.
- Lists and mappings.
- Enums.
- Dates and datetimes.
- Decimal.
- UUID.
- Specialized Pydantic types.
- Validation context.
- Mapping vs attribute validation.
- Existing model instances.
- Generic models.
- Discriminated unions.
- Frozen models.
- Validation error preservation.
- Error redaction.
- Unexpected validator exceptions.
- Streaming.
- Async parity.
- SQLRules pushdown followed by full validation.
- Performance regressions.

Tests should include invalid database rows inserted through paths that bypass
Pydantic validation.

---

# MVP Scope

The first RowGuard release should support:

- Pydantic v2 `BaseModel` targets.
- Mapping-based `model_validate()`.
- Strict override.
- Validation aliases through normal Pydantic behavior.
- Field and model validators.
- Nested models when the adapter provides nested input.
- Complete `ValidationError` preservation.
- Validation context.
- Validation timing and counts.
- Structured `RejectedRow` integration.
- Synchronous and asynchronous query APIs using the same validator component.

Deferred:

- General `TypeAdapter` targets.
- Pydantic dataclasses.
- TypedDict outputs.
- Automatic root-model adapters.
- Automatic repair.
- Parallel validation.
- Validation result caching.
- Pydantic v1 compatibility.
- Automatic projection optimization based on CoreSchema.
- Alternate validation engines.

---

# Recommended Public Examples

## Standard Validation

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

## Strict Validation

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    strict=True,
)
```

## Validation Context

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    validation_context={
        "tenant_id": tenant_id,
        "policy_version": "2026-07",
    },
)
```

## ORM Attribute Validation

```python
result = rowguard.select(
    session=session,
    table=User,
    model=UserRead,
    orm_validation="from_attributes",
)
```

## Inspecting a Pydantic Rejection

```python
rejected = result.rejected[0]

print(rejected.validation_error.errors())
print(rejected.mapping)
print(rejected.model)
```

---

# Design Principles

- Pydantic is the final authority on row acceptance.
- Validate adapted inputs, not database assumptions.
- Preserve normal Pydantic semantics.
- Keep mapping-based validation as the default.
- Make attribute validation explicit.
- Never suppress complete validation errors.
- Separate validation from rejection policy.
- Treat SQLRules pushdown as an optimization only.
- Avoid hidden coercion outside Pydantic.
- Keep validators reusable, observable, and fast.
