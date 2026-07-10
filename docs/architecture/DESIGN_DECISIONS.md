# DESIGN_DECISIONS.md

# RowGuard Design Decisions

## Purpose

This document records the major architectural and product decisions behind
RowGuard.

Its goal is to prevent architectural drift, reduce repeated debates, and give
contributors a clear explanation of why RowGuard is designed the way it is.

RowGuard exists to solve one focused problem:

> Execute SQLAlchemy queries, validate every returned row against a Pydantic
> contract, and handle invalid rows explicitly.

---

# Decision 1: RowGuard Is a Validation-First Query Layer

## Decision

RowGuard is a query execution and validation layer.

It is not an ORM, schema tool, migration framework, or database abstraction.

## Rationale

SQLAlchemy already provides a mature query and execution system. Pydantic already
provides a mature validation system.

RowGuard's value is in coordinating them around a stronger read-time contract.

## Consequences

RowGuard owns:

- Query planning
- SQLRules integration
- Query execution
- Row adaptation
- Pydantic validation
- Rejection handling
- Diagnostics
- Result objects

RowGuard does not own:

- ORM mapping
- Persistence
- Table creation
- Migrations
- Database drivers
- SQL parsing

---

# Decision 2: SQLAlchemy Remains the SQL Foundation

## Decision

RowGuard composes SQLAlchemy expressions and statements rather than generating
or parsing SQL itself.

## Rationale

SQLAlchemy already handles:

- Dialects
- Bound parameters
- Identifier quoting
- Statement composition
- Sessions and connections
- ORM and Core
- Async execution

Duplicating that functionality would increase risk and complexity.

## Consequences

RowGuard accepts:

- Tables
- Select statements
- ORM entities
- SQLModel classes
- Connections
- Sessions
- Raw SQLAlchemy text statements

RowGuard returns and preserves SQLAlchemy statement objects.

---

# Decision 3: Pydantic Is the Validation Authority

## Decision

Every accepted row must pass Pydantic validation.

RowGuard does not implement a parallel validation engine.

## Rationale

Pydantic already supports:

- Type validation
- Strictness
- Aliases
- Field validators
- Model validators
- Nested models
- Validation context
- Rich errors

RowGuard should not reinterpret or approximate those semantics.

## Consequences

The normal validation path is:

```python
Model.model_validate(mapping)
```

Pydantic `ValidationError` objects remain available in rejection records.

---

# Decision 4: SQLRules Is a Separate Dependency

## Decision

SQLRules remains a standalone package responsible for compiling supported
Pydantic constraints into SQLAlchemy WHERE expressions.

RowGuard depends on SQLRules through its public API.

## Rationale

Constraint compilation and query execution are separate concerns.

Keeping them separate allows:

- SQLRules to remain small and reusable
- RowGuard to focus on runtime behavior
- Independent release cycles
- Other packages to use SQLRules without RowGuard
- RowGuard to disable pushdown when needed

## Consequences

SQLRules owns:

- Constraint extraction
- SQLAlchemy rule generation
- Dialect translators

RowGuard owns:

- Applying expressions
- Executing queries
- Validating returned rows
- Handling rejections

---

# Decision 5: SQL Pushdown Is an Optimization, Not Proof

## Decision

SQLRules pushdown reduces candidate rows but never replaces Pydantic validation.

## Rationale

Many Pydantic rules cannot be represented safely in SQL, including:

- Custom validators
- Cross-field rules
- Nested-model semantics
- Context-dependent rules
- Application-specific logic

Even apparently equivalent SQL semantics may differ by dialect, collation, type
coercion, or driver behavior.

## Consequences

Every returned row is validated by Pydantic even when all known constraints were
pushed into SQL.

---

# Decision 6: Full Validation Is the Default

## Decision

RowGuard validates the complete target model by default.

Partial validation requires explicit opt-in.

## Rationale

The primary guarantee should be simple and strong:

> Every accepted row satisfies the requested model.

Implicit partial validation would weaken this guarantee and make result meaning
ambiguous.

## Consequences

Recommended pattern for projections:

```python
class UserSummary(BaseModel):
    id: int
    name: str
```

Use a dedicated projection model rather than partially validating a larger model.

---

# Decision 7: Projection Models Are Preferred Over Dynamic Partial Validation

## Decision

Dedicated Pydantic projection models are the preferred way to represent partial
database reads.

## Rationale

Projection models are:

- Explicit
- Statically typed
- IDE-friendly
- Reusable
- Easy to test
- Easy to document

Dynamic partial validation remains useful for advanced systems such as GraphQL
or report builders, but it is not the default.

## Consequences

The documentation should encourage projection models first and partial
validation second.

---

# Decision 8: Mapping-Based Validation Is the Default

## Decision

Rows are adapted into mappings before Pydantic validation.

ORM attribute-based validation is opt-in.

## Rationale

Mapping-based validation:

- Makes the exact input visible
- Works across Core, ORM, SQLModel, and raw SQL
- Avoids SQLAlchemy internals
- Avoids accidental lazy loading
- Simplifies diagnostics
- Preserves result-shape semantics

## Consequences

Default:

```python
Model.model_validate(mapping)
```

Optional ORM mode:

```python
Model.model_validate(entity, from_attributes=True)
```

---

# Decision 9: Row Adaptation Changes Structure, Not Meaning

## Decision

The Row Adapter may reshape data structurally but should not perform semantic
type coercion.

## Rationale

Semantic conversion belongs to Pydantic, SQL expressions, or explicit repair
logic.

Hidden coercion would make validation results harder to explain.

## Consequences

The Row Adapter may:

- Rename keys
- Apply explicit field maps
- Build explicit nested mappings
- Extract ORM scalar attributes
- Wrap scalar results explicitly

It should not:

- Parse dates
- Trim strings
- Convert enums
- Parse JSON strings
- Normalize timezones
- Apply defaults

---

# Decision 10: Rejected Rows Are First-Class Results

## Decision

Invalid rows are structured outcomes, not discarded exceptions.

## Rationale

Rejected rows are valuable for:

- Data quality
- Auditing
- Migration
- Repair
- Quarantine
- Monitoring
- Governance

## Consequences

RowGuard exposes `RejectedRow` with:

- Source identity
- Adapted mapping
- Pydantic error
- Row index
- Diagnostics
- Retention/redaction-aware data

---

# Decision 11: Rejection Policy Is Explicit

## Decision

Applications explicitly choose what happens after validation failure.

## Rationale

Different workloads need different behavior.

An API request may want fail-fast behavior.

An ETL pipeline may want collection or quarantine.

## Consequences

Built-in policies include:

- raise
- collect
- skip
- callback
- quarantine

No row is silently ignored without an explicit policy.

---

# Decision 12: `raise` Is the Default Policy

## Decision

The default rejection policy is fail-fast.

## Rationale

Silent continuation can hide invalid persisted data.

Fail-fast behavior is the safest default for general application code.

## Consequences

Users must explicitly select collection, skipping, callbacks, or quarantine.

---

# Decision 13: Rejection Policies Use Strategy Objects Internally

## Decision

String options are convenience syntax, but internal behavior is implemented
through policy objects.

## Rationale

A strategy interface supports:

- Built-in policies
- Custom policies
- Sync and async variants
- Testing
- Future composition

## Consequences

Conceptual interface:

```python
class RejectionPolicy(Protocol):
    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        ...
```

---

# Decision 14: Callbacks Are Observable and Synchronous by Default

## Decision

Callbacks run within the execution lifecycle and complete before processing
continues.

## Rationale

Hidden background work creates uncertain delivery guarantees and resource
lifetimes.

## Consequences

- Callback duration is measured.
- Callback failure is explicit.
- Ordering is deterministic.
- Async APIs may use async callbacks.
- RowGuard does not promise deferred background delivery.

---

# Decision 15: Quarantine Is a Dedicated Abstraction

## Decision

Quarantine is not treated as merely another callback.

## Rationale

Durable quarantine requires:

- Schema versioning
- Serialization
- Receipts
- Transactions
- Batching
- Retry semantics
- Provider capabilities
- Redaction

That is more structured than a generic callback.

## Consequences

RowGuard defines quarantine provider protocols and storage-safe
`QuarantineRecord` objects.

---

# Decision 16: Source and Quarantine Transactions Are Separate by Default

## Decision

Quarantine writes should not automatically reuse the source query transaction.

## Rationale

Using the same transaction can:

- Roll back rejection records
- Poison read transactions
- Extend locks
- Complicate streaming
- Couple unrelated systems

## Consequences

Same-transaction quarantine requires explicit opt-in.

---

# Decision 17: Planning and Execution Are Separate Phases

## Decision

RowGuard compiles a request into an immutable `ExecutionPlan` before execution.

## Rationale

This separation supports:

- Validation before database access
- Caching
- Testing
- Diagnostics
- Sync/async reuse
- Streaming reuse
- Cleaner error boundaries

## Consequences

Planning performs:

- Source normalization
- Statement construction
- SQLRules pushdown
- Adapter planning
- Validator planning
- Rejection-policy planning

Execution consumes the finished plan.

---

# Decision 18: Execution Plans Are Immutable

## Decision

`ExecutionPlan` objects are immutable.

## Rationale

Immutable plans are:

- Safe to reuse
- Easier to cache
- Easier to reason about
- Easier to share
- Less prone to cross-query state leakage

## Consequences

Mutable counters, buffers, and resources live in per-run `ExecutionState`.

---

# Decision 19: Public APIs Stay Small

## Decision

The public API should expose a few high-level functions and a configurable
client.

Core functions:

```python
rowguard.select(...)
rowguard.execute(...)
rowguard.stream(...)
rowguard.aselect(...)
rowguard.aexecute(...)
rowguard.astream(...)
rowguard.validate_rows(...)
```

## Rationale

A small API is easier to:

- Learn
- Document
- Type
- Stabilize
- Maintain

## Consequences

Advanced behavior is expressed through configuration and strategy objects rather
than many top-level functions.

---

# Decision 20: Buffered and Streaming Results Are Different Types

## Decision

A completed buffered query returns `QueryResult[T]`.

A live stream returns `StreamResult[T]` or `AsyncStreamResult[T]`.

## Rationale

A stream is incomplete until iteration finishes.

Pretending it is a complete result would create confusing statistics and
resource semantics.

## Consequences

Streaming results own:

- Active resources
- Iteration
- Finalization
- Incremental statistics
- Retained rejections
- Provider flush behavior

---

# Decision 21: Sync and Async Share the Same Core Pipeline

## Decision

Async support changes the I/O layer, not validation semantics.

## Rationale

Duplicating the pipeline would risk inconsistent behavior.

## Consequences

Shared components include:

- Planning
- SQLRules integration
- Adapters
- Pydantic validation
- Rejection decisions
- Statistics
- Diagnostics
- Result assembly

Separate components include:

- Query execution
- Row fetching
- Resource cleanup
- Async callbacks
- Async quarantine providers

---

# Decision 22: No Implicit ORM Relationship Traversal

## Decision

RowGuard does not automatically traverse SQLAlchemy or SQLModel relationships.

## Rationale

Implicit traversal can trigger:

- N+1 queries
- Lazy I/O
- Recursive graphs
- Large memory usage
- Session-state dependence

## Consequences

Nested models should use:

- Explicit projections
- Explicit eager loading
- Explicit nested adapters
- Explicit attribute validation

---

# Decision 23: Explicit Projections Are Preferred for ORM Reads

## Decision

For strict and scalable ORM validation, projected columns are preferred over
full entity queries.

## Rationale

Projections:

- Avoid unnecessary identity-map population
- Avoid lazy loading
- Clarify validation input
- Improve streaming
- Improve performance
- Reduce persistence/read-contract coupling

## Consequences

RowGuard supports full entities but documentation recommends projections for
large or high-assurance workloads.

---

# Decision 24: SQLModel Is Complementary, Not a Competitor

## Decision

RowGuard should position itself as an add-on for validation-first SQLModel reads.

## Rationale

SQLModel excels at:

- Table models
- ORM workflows
- CRUD
- FastAPI integration
- Typed sessions

RowGuard solves a different problem:

- Explicit read-time validation
- Rejected-row handling
- Quarantine
- Streaming validation
- SQL pushdown plus Pydantic verification

## Consequences

Documentation should describe SQLModel respectfully and accurately.

RowGuard should not claim SQLModel lacks validation entirely.

---

# Decision 25: Separate Persistence and Read Models Are Recommended

## Decision

Applications should normally use distinct persistence and read-contract models.

## Rationale

Persistence models and read contracts often differ in:

- Required fields
- Defaults
- Relationships
- Validators
- Public fields
- Legacy tolerance
- Security exposure

## Consequences

Recommended:

```python
UserTable
UserRead
UserSummary
```

Using the same model for all roles remains possible but is not the preferred
guidance.

---

# Decision 26: Raw SQL Is Supported but Never Rewritten

## Decision

RowGuard may execute SQLAlchemy `text()` statements but does not parse or rewrite
arbitrary SQL.

## Rationale

SQL parsing and rewriting is complex, dialect-specific, and unsafe to guess.

## Consequences

For raw SQL:

- Bound parameters are mandatory
- SQLRules pushdown is disabled by default
- Result keys must be explicit
- Pydantic validation still runs
- Aliases or field maps define the contract

---

# Decision 27: Reflection Is Delegated to SQLAlchemy

## Decision

RowGuard consumes reflected SQLAlchemy tables but does not implement reflection
itself.

## Rationale

SQLAlchemy already provides mature schema reflection.

## Consequences

Applications reflect metadata first, then pass the resulting `Table` to
RowGuard.

---

# Decision 28: Authorization Filters Are Not Validation Rules

## Decision

Tenant, permission, and authorization predicates must be supplied explicitly.

## Rationale

Pydantic constraints describe data validity, not access control.

## Consequences

Security filters remain user-authored SQLAlchemy expressions.

Disabling SQLRules pushdown must never disable authorization filters.

---

# Decision 29: Diagnostics Are Structured and Stable

## Decision

Diagnostics use stable codes and structured metadata.

## Rationale

Human-readable messages can change, but dashboards and tooling need stable
identifiers.

## Consequences

Namespaces include:

```text
planning.*
pushdown.*
execution.*
adaptation.*
validation.*
rejection.*
callback.*
quarantine.*
stream.*
```

Diagnostic codes are part of the public observability contract.

---

# Decision 30: Diagnostics Never Change Behavior

## Decision

Enabling or disabling diagnostics must not alter query results.

## Rationale

Observability should not become a semantic dependency.

## Consequences

Diagnostics are additive and side-effect-limited.

A no-op collector should keep disabled diagnostics cheap.

---

# Decision 31: Sensitive Values Are Not Emitted by Default

## Decision

Logs, metrics, traces, and quarantine records must respect explicit redaction and
retention policies.

## Rationale

Rejected data may contain malformed, unexpected, or sensitive values.

## Consequences

Default observability should emphasize:

- Model name
- Error codes
- Field paths
- Source identity
- Counts
- Timing

Raw values require explicit configuration.

---

# Decision 32: Missing and Null Remain Distinct

## Decision

The Row Adapter must preserve the difference between an absent key and a key
whose value is `None`.

## Rationale

Pydantic may treat them differently due to:

- Required fields
- Defaults
- Optionality
- Validators

## Consequences

RowGuard must not insert `None` for missing values.

---

# Decision 33: Ambiguity Fails by Default

## Decision

Ambiguous result shapes, duplicate column names, unresolved aliases, and unclear
pushdown sources should raise planning or adaptation errors.

## Rationale

Guessing can bind the wrong database value to the wrong model field.

## Consequences

Users must use:

- SQL labels
- Explicit field maps
- Explicit pushdown maps
- Custom adapters

---

# Decision 34: Exactness Is Preferred Over Aggressive Pushdown

## Decision

When SQL and Pydantic semantics may differ, RowGuard prefers not to push the
constraint.

## Rationale

A false-negative SQL filter can remove a row Pydantic would accept.

A false-positive SQL filter merely allows an extra row to be rejected later.

## Consequences

Conservative behavior is preferred:

> Retrieve and reject an extra row rather than discard a valid row in SQL.

---

# Decision 35: Query Result Objects Are Immutable

## Decision

`QueryResult`, `RejectedRow`, `QueryStatistics`, diagnostics, and quarantine
receipts should be immutable public objects where practical.

## Rationale

Immutability improves:

- Trust
- Thread safety
- Testing
- Reproducibility
- API clarity

## Consequences

Mutable collection and counter state remains internal during execution.

---

# Decision 36: Type Support Is Broader Than Pushdown Support

## Decision

A type may be fully supported by Pydantic validation even when SQLRules cannot
translate its constraints.

## Rationale

Examples include:

- Email addresses
- URLs
- Nested models
- Custom types
- JSON structures
- Context-dependent validators

## Consequences

Documentation maintains separate concepts:

- Row adaptation support
- Pydantic validation support
- SQLRules pushdown support
- Dialect support

---

# Decision 37: Strict Validation Is Explicit

## Decision

RowGuard honors Pydantic defaults unless strict validation is configured through
the model or execution options.

## Rationale

Pydantic's coercion behavior is part of its model semantics.

RowGuard should not silently force strict mode.

## Consequences

Users performing storage-quality audits can enable:

```python
strict=True
```

Accepted non-strict values prove model compatibility, not exact database storage
type fidelity.

---

# Decision 38: Repair Is Separate from Validation

## Decision

Repair workflows are explicit second-pass operations.

## Rationale

Automatically modifying values before validation would hide data quality
problems and weaken auditability.

## Consequences

Safe repair flow:

```text
Validate
  → Reject
  → Explicit repair callback
  → Revalidate
  → Accept or reject again
```

The original rejection remains part of the audit trail.

---

# Decision 39: RowGuard Does Not Write Back Automatically

## Decision

RowGuard never automatically mutates or persists repaired data.

## Rationale

Persistence requires application-specific transaction, authorization, and audit
decisions.

## Consequences

Applications decide whether a validated repair should update the source.

---

# Decision 40: Internal APIs Are Flexible; Public Protocols Are Deliberate

## Decision

Private implementation modules may evolve rapidly before 1.0.

Public plugin protocols are versioned and narrow.

## Rationale

The project needs room to improve internals without destabilizing users.

## Consequences

Plugins should use documented interfaces for:

- Row adapters
- Rejection policies
- Callbacks
- Quarantine providers
- Diagnostics exporters
- Source resolvers

They should not depend on mutable execution internals.

---

# Open Questions

## Should RowGuard Return Tuples or Lists?

Immutability suggests tuples.

Ergonomics may favor lists.

Recommended direction:

- Store immutable tuples internally and publicly.
- Provide list conversion helpers when needed.

---

## Should `bool(QueryResult)` Be Supported?

Possible meanings are ambiguous:

- Has accepted rows
- Completed successfully
- Has no rejections

Recommended direction:

- Avoid relying on truthiness.
- Expose explicit properties:
  - `has_models`
  - `has_rejections`
  - `is_clean`

---

## Should `collect` Retain Raw Rows by Default?

Retaining raw rows improves debugging but increases privacy and memory risk.

Recommended direction:

- Retain adapted mapping by default.
- Do not retain raw ORM entities by default.
- Make retention configurable.

---

## Should SQLRules Pushdown Be Enabled by Default?

Recommended direction:

- Yes, in safe mode for resolvable Core and ORM sources.
- No, for arbitrary raw SQL.
- Always preserve post-query Pydantic validation.

---

## Should RowGuard Support Non-BaseModel Targets?

Pydantic `TypeAdapter` could support:

- Dataclasses
- TypedDict
- Scalars
- Lists
- Unions

Recommended direction:

- Start with `BaseModel`.
- Add TypeAdapter support after the core API stabilizes.

---

## Should Partial Validation Ship in the MVP?

Recommended direction:

- Prefer projection models in the MVP.
- Add explicit dynamic partial validation later if real use cases demand it.

---

# Decision Review Process

New architectural decisions should be recorded here when they:

- Change public semantics.
- Add a new responsibility.
- Change package boundaries.
- Introduce a new extension point.
- Affect validation guarantees.
- Affect transaction or security behavior.
- Create compatibility commitments.

Each decision should document:

- Decision
- Rationale
- Consequences
- Alternatives considered when useful

---

# Summary

RowGuard's architecture rests on a small number of durable boundaries:

```text
SQLAlchemy owns SQL and execution primitives.
SQLRules owns constraint-to-SQL compilation.
Pydantic owns validation semantics.
RowGuard owns orchestration, classification, and rejection handling.
```

The project's most important guarantee is:

> Every accepted row has explicitly passed the requested Pydantic contract, and
> every rejected row is handled according to a visible policy.

Every design decision should strengthen that guarantee rather than dilute it.
