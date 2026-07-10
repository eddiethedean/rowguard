
# VALIDATION_ENGINE.md

# RowGuard Validation Engine

## Purpose

The Validation Engine is responsible for transforming adapted row mappings into
validated Pydantic models.

It is the heart of RowGuard's value proposition: every accepted row satisfies
the target Pydantic model, and every rejected row produces structured,
observable diagnostics.

The Validation Engine **does not** execute SQL, adapt rows, or determine how
validation failures are handled. Those responsibilities belong to the Query
Engine, Row Adapter, and Reject Handler respectively.

---

# Responsibilities

The Validation Engine:

- Accepts adapted row mappings.
- Invokes Pydantic validation.
- Produces strongly typed models.
- Captures validation failures.
- Preserves validation context.
- Emits validation diagnostics.
- Records validation metrics.

The Validation Engine does **not**:

- Compile SQLRules constraints.
- Perform SQL filtering.
- Build SQL statements.
- Execute queries.
- Decide rejection policy.
- Modify application data.

---

# Position in the Pipeline

```text
Database
    │
    ▼
Row Adapter
    │
    ▼
Validation Engine
    │
    ├── Valid Model
    └── Validation Failure
          │
          ▼
     Reject Handler
```

---

# Inputs

Each validation operation receives:

- Target Pydantic model
- Adapted row mapping
- Validation configuration
- Validation context (optional)

Example:

```python
validated = UserRead.model_validate(mapping)
```

The engine should rely on Pydantic's public APIs rather than reimplementing
validation behavior.

---

# Outputs

Successful validation returns a model instance.

Failed validation returns a structured internal object that contains:

- original mapping
- ValidationError
- target model
- validation duration
- diagnostics

The Query Engine decides whether that failure becomes a rejection, exception, or
callback.

---

# Validation Contract

The engine guarantees:

- Every accepted object is an instance of the requested model.
- Every validation failure preserves the original Pydantic error.
- Validation behavior is deterministic.
- No implicit coercion beyond Pydantic's configured behavior.

---

# Validation Modes

## Strict

Honor strict field behavior exactly as defined by the model.

## Default

Use normal Pydantic validation semantics.

## Contextual (Future)

Allow callers to pass validation context.

```python
model.model_validate(
    mapping,
    context={"request_id": "..."},
)
```

RowGuard should pass context through unchanged.

---

# Nested Models

Nested models should work naturally because validation is delegated to
Pydantic.

Example:

```python
class Address(BaseModel):
    city: str

class User(BaseModel):
    name: str
    address: Address
```

If the Row Adapter produces the expected nested mapping, the Validation Engine
requires no special logic.

---

# Validation Errors

Validation failures should preserve:

- full ValidationError
- error locations
- error messages
- input values (subject to application privacy policies)

The engine should never flatten or simplify errors unless explicitly requested.

---

# ValidationResult

Internally, validation may return a lightweight result object.

```python
@dataclass(frozen=True, slots=True)
class ValidationResult[T]:
    success: bool
    model: T | None
    error: ValidationError | None
    duration_ns: int
```

This keeps orchestration code independent from Pydantic exceptions.

---

# Statistics

Suggested metrics:

- rows_validated
- rows_valid
- rows_invalid
- validation_time
- average_validation_time

Future:

- validation throughput
- per-model metrics

---

# Performance

Validation is expected to be one of the most expensive stages after database
I/O.

Guidelines:

- Validate exactly once per row.
- Avoid copying adapted mappings.
- Reuse immutable validation configuration.
- Measure before optimizing.

Future optimizations may include batch orchestration, but validation semantics
must remain identical.

---

# Error Handling

Unexpected failures should be distinguished from ordinary validation failures.

Suggested hierarchy:

```text
RowGuardError
└── ValidationEngineError
    ├── ValidationConfigurationError
    └── UnexpectedValidationError
```

Ordinary Pydantic ValidationError objects are expected outcomes and should not
be wrapped unless additional execution context is needed.

---

# Extension Points

Future plugins may provide:

- validation observers
- metrics exporters
- tracing hooks
- alternate validation engines (experimental)

Any alternate engine must preserve RowGuard's validation contract.

---

# Testing Requirements

Tests should cover:

- successful validation
- failed validation
- nested models
- aliases
- optional fields
- extra fields
- strict mode
- context propagation
- deterministic behavior
- performance regressions

---

# MVP Scope

The initial release supports:

- Pydantic v2
- model_validate()
- deterministic validation
- structured validation failures
- validation timing
- nested model support through adapted mappings

Deferred:

- alternate validation engines
- distributed validation
- speculative validation

---

# Design Principles

- Pydantic is the source of truth.
- Validate every adapted row.
- Never suppress validation errors.
- Preserve complete error information.
- Keep validation independent from rejection policy.
- Optimize orchestration, not semantics.
