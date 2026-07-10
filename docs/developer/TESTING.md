# TESTING.md

# RowGuard Testing Strategy

## Purpose

RowGuard sits at the boundary between SQLAlchemy, SQLRules, Pydantic, database
drivers, and user-defined rejection behavior. Its test suite must prove not only
that valid rows are accepted, but also that invalid, ambiguous, unsupported, and
failing cases remain observable and deterministic.

The central testing guarantee is:

> Every accepted row satisfies the requested Pydantic contract, every rejected
> row is handled according to policy, and no execution mode changes those
> semantics.

---

# Testing Principles

- Test public behavior before implementation details.
- Test accepted and rejected paths equally.
- Test real database execution, not only compiled SQL.
- Keep Core, ORM, SQLModel, raw SQL, sync, async, buffered, and streaming
  semantics aligned.
- Preserve complete Pydantic error information.
- Fail on ambiguous mappings rather than testing permissive guesses.
- Use deterministic fixtures.
- Avoid relying on network services in the unit-test suite.
- Separate correctness tests from performance benchmarks.
- Test security-sensitive defaults such as redaction and bound parameters.

---

# Test Layers

## Unit Tests

Unit tests cover isolated components:

- Request normalization
- Query planning
- Execution-plan construction
- Field-map resolution
- Row adapters
- Pydantic validator wrapper
- Rejection policies
- Diagnostics
- Statistics
- Cache keys
- Result assembly
- Plugin registries

These tests should use lightweight fakes where database execution is not
material.

## Component Tests

Component tests exercise small groups of real components:

- Planner + SQLRules bridge
- SQLAlchemy Row + Row Adapter
- Adapter + Pydantic validator
- Validator + rejection policy
- Stream lifecycle + resource cleanup
- Quarantine serialization + provider

## Integration Tests

Integration tests execute real SQLAlchemy statements against real databases.

They cover:

- Core
- ORM
- SQLModel
- Reflection
- Raw SQL
- Dialect behavior
- Driver-returned types
- Transactions
- Streaming
- Async sessions

## End-to-End Tests

End-to-end tests start from the public API and verify complete outcomes:

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

Assertions should include:

- Accepted models
- Rejected rows
- Statistics
- Diagnostics
- Statement preservation
- Resource cleanup

---

# Test Matrix

The minimum test matrix should cover:

| Dimension | Variants |
| --- | --- |
| API | `select`, `execute`, `stream`, `validate_rows` |
| Execution | sync, async |
| Result mode | buffered, streaming |
| SQL source | Core, ORM, SQLModel, raw SQL |
| Rejection | raise, collect, skip, callback, quarantine |
| Validation | default, strict, context |
| Pushdown | enabled, disabled, unsupported constraint |
| Mapping | direct, alias, explicit map, nested |
| Data | all valid, mixed, all rejected |
| Diagnostics | disabled, summary, detailed |
| Cache | cold, warm, disabled |

Not every combination requires a separate test, but every semantic interaction
must be represented.

---

# Model Fixtures

Use representative Pydantic models.

## Small Model

```python
class UserRead(BaseModel):
    id: int
    name: str
```

## Constrained Model

```python
class AdultUserRead(BaseModel):
    id: int
    age: Annotated[int, Field(ge=18, le=120)]
```

## Strict Model

```python
class StrictUserRead(BaseModel):
    model_config = ConfigDict(strict=True)

    id: int
    enabled: bool
```

## Nested Model

```python
class TeamRead(BaseModel):
    id: int
    name: str


class UserWithTeamRead(BaseModel):
    id: int
    team: TeamRead
```

## Cross-Field Model

```python
class DateRangeRead(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("invalid range")
        return self
```

---

# Database Fixtures

Fixtures should include:

- Valid rows
- Invalid values inserted through raw SQL
- Nulls
- Missing projected fields
- Duplicate labels
- Legacy column names
- Joined rows
- Outer-joined rows
- JSON
- Decimal
- UUID
- Date and datetime
- Enum values
- Large text or binary samples

Rows that bypass Pydantic on insertion are essential because they reproduce the
problem RowGuard exists to solve.

---

# SQLRules Integration Tests

Verify:

- Supported constraints become SQLAlchemy predicates.
- User filters compose with SQLRules filters.
- Unsupported constraints still run in Pydantic.
- Pushdown-disabled mode retrieves and validates candidate rows.
- Pushdown diagnostics are preserved.
- Precompiled rules behave identically to direct compilation.
- Aliased and explicitly mapped columns resolve correctly.
- Outer-join safety blocks unsafe automatic placement.

Do not assert only on SQL strings. Execute statements and verify accepted and
rejected outcomes.

---

# Row Adapter Tests

Test:

- SQLAlchemy `Row._mapping`
- Mapping results
- Explicit field maps
- Validation aliases
- Labeled columns
- Duplicate keys
- Positional adapters
- Scalar adapters
- Nested mappings
- ORM entity extraction
- Source identity
- Null preservation
- Missing vs null
- Extra columns
- Unloaded attributes
- Lazy-load blocking

Adapters must never mutate source rows.

---

# Validation Engine Tests

Test:

- Successful `model_validate`
- Strict and non-strict behavior
- Field validators
- Model validators
- Nested models
- Validation context
- Aliases
- Defaults
- Missing fields
- Extra-field policies
- Existing model instances
- Unexpected custom-validator exceptions
- Complete `ValidationError` preservation
- Redaction behavior

Each row should be validated exactly once unless an explicit repair attempt
occurs.

---

# Rejection Policy Tests

## Raise

- Stops at first rejection
- Preserves original Pydantic error
- Cleans up resources
- Does not return a complete result

## Collect

- Retains all configured rejections
- Preserves order
- Produces correct statistics
- Honors redaction and retention

## Skip

- Continues processing
- Does not retain rows
- Counts every rejection

## Callback

- Receives immutable structured data
- Preserves order
- Handles decisions
- Surfaces callback failures
- Supports async callbacks

## Quarantine

- Writes storage-safe records
- Returns receipts
- Handles provider failures
- Flushes on completion
- Applies redaction before handoff

---

# Streaming Tests

Verify:

- Constant or bounded memory
- Accepted rows are yielded only after validation
- Rejections follow policy
- Ordering is preserved
- Context manager closes resources
- Early consumer exit closes resources
- Callback or provider failures close the stream
- Cancellation closes async resources
- Final statistics are correct
- Outstanding quarantine batches flush
- Accepted models are not retained internally

A large synthetic stream should be used to detect accidental accumulation.

---

# Async Tests

Use `pytest-asyncio` or another documented async test integration.

Verify parity with sync behavior for:

- Accepted models
- Rejections
- Statistics
- Diagnostics
- Pushdown
- Callbacks
- Quarantine
- Streaming
- Cancellation
- Cleanup

Async tests should not merely call sync code inside a coroutine.

---

# Core Integration Tests

Test:

- Table-based selects
- Existing `Select`
- Bound parameters
- Aliases
- Subqueries
- CTEs
- Joins
- Outer joins
- Aggregates
- Window functions
- Compound statements where supported
- Reflected tables
- Mapping results
- Session and Connection execution

---

# ORM Tests

Test:

- Single mapped entity
- Projected scalar columns
- Identity-map reuse
- Pending changes and autoflush
- Expired attributes
- Deferred columns
- Lazy relationships
- Eager-loaded relationships
- Aliased entities
- Polymorphic mappings
- Hybrid and column properties
- Streaming entity queries
- Raw entity retention disabled by default

---

# SQLModel Tests

Test:

- SQLModel table source
- Pydantic read target
- Non-table SQLModel read target
- Same source and target model
- SQLModel `Session`
- SQLModel `select`
- Projected reads
- Entity mapping mode
- `from_attributes` opt-in
- Relationships
- Async compatibility
- Invalid rows inserted outside SQLModel validation

---

# Raw SQL Tests

Test:

- SQLAlchemy `text()`
- Bound parameters
- Aliased columns
- Explicit field maps
- Pushdown disabled by default
- Mapping adaptation
- Streaming
- Rejections
- Parameter-value redaction

Never construct tests that normalize unsafe string interpolation into acceptable
behavior.

---

# Reflection Tests

Test:

- Reflected table execution
- Multiple schemas where available
- Legacy column names
- Explicit mappings
- Reflected joins
- SQLRules pushdown
- Cache invalidation after schema fixture recreation

RowGuard should consume reflected metadata rather than performing hidden
reflection during ordinary planning.

---

# Cache Tests

Verify:

- Cold miss and warm hit
- Semantic equivalence with cache disabled
- Model metadata reuse
- SQLRules compilation reuse
- Adapter-plan reuse
- Plan-template reuse
- Bound parameter values do not fragment structural cache keys
- Strictness and validation scope do affect keys
- Plugin versions affect keys
- Dialect identity affects relevant keys
- Sessions and results are never retained
- LRU eviction
- Clear and targeted invalidation
- Thread-safe access

---

# Plugin Tests

Core registry tests should cover:

- Registration
- Duplicate names
- Explicit replacement
- Missing plugin
- API version mismatch
- Capability mismatch
- Lifecycle
- Sync/async compatibility
- Streaming compatibility
- Failure wrapping
- Deterministic resolution
- Source resolver ambiguity
- Privacy-policy compatibility

Provide conformance suites for public plugin authors.

---

# Diagnostics Tests

Verify:

- Stable codes
- Severity
- Ordering
- Execution ID
- Row index
- Summary vs detailed modes
- No-op collector behavior
- Redaction
- Logging payloads
- Metrics cardinality safeguards
- Sync/async parity
- Plugin lifecycle diagnostics

Human-readable message text should not be over-specified unless it is a public
contract.

---

# Statistics Tests

Assert invariants:

```python
rows_read >= rows_accepted
rows_read >= rows_rejected
rows_accepted + rows_rejected == rows_classified
rows_accepted == len(result.models)
rows_retained_rejected <= rows_rejected
```

Test:

- All valid
- Mixed
- All rejected
- Skip policy
- Callback drop/retain
- Quarantine receipt retention
- Streaming finalization
- Threshold stop
- Partial execution errors

---

# Security Tests

Verify:

- Bound parameters are preserved
- Raw SQL values are not interpolated
- Authorization filters remain separate from pushdown
- Redacted fields do not appear in logs or quarantine records
- SQLAlchemy internal state is excluded
- Raw ORM entities are not retained by default
- Session access is not passed to callbacks by default
- Arbitrary objects are not stringified unsafely
- Sensitive parameter values are omitted from diagnostics

---

# Property-Based Testing

Property-based tests can strengthen invariants.

Potential targets:

- Arbitrary valid/invalid scalar values
- Missing/null combinations
- Field-map permutations
- Error-count invariants
- Cache key normalization
- Rejection-order preservation
- Nested adapter mappings
- Serialization/redaction

Hypothesis may be an optional development dependency.

---

# Golden and Snapshot Tests

Use snapshots for structured outputs such as:

- Diagnostics
- Quarantine records
- Error serialization
- Plan descriptions

Normalize unstable values:

- Timestamps
- Execution IDs
- Object identities
- Database-generated primary keys

Do not snapshot rendered SQL across all dialects unless the SQL text itself is
the subject of the test.

---

# Dialect Test Matrix

Recommended CI:

## Every Pull Request

- SQLite sync
- SQLite async
- PostgreSQL sync
- PostgreSQL async where practical

## Scheduled / Release

- MySQL
- MariaDB
- SQL Server
- DuckDB
- Oracle where practical

Each tested driver combination should be documented.

---

# Test Isolation

Tests must isolate:

- Database transactions
- Metadata
- Sessions
- Cache state
- Plugin registries
- Files
- Environment variables
- Quarantine destinations
- Async event loops

Avoid state shared across tests unless the fixture is explicitly session-scoped
and immutable.

---

# Temporary Resources

Use temporary directories for:

- JSONL quarantine files
- Cache experiments
- Exporters
- SQLite files

Always close:

- Sessions
- Connections
- Engines
- Streams
- Providers
- File handles
- Async clients

Resource-leak tests should run with warnings treated as errors where practical.

---

# Error Injection

Use deliberate fakes to simulate:

- Adapter failure
- Unexpected validator exception
- Callback failure
- Quarantine failure
- Diagnostic exporter failure
- Cache failure
- Database disconnect
- Cancellation
- Partial batch failure
- Cleanup failure

Failure-path tests are as important as success-path tests.

---

# Coverage

Coverage goals:

- Core package: at least 95% line coverage
- Critical modules: near-complete branch coverage
- Public APIs: every documented path
- Error paths: explicit tests
- Plugin protocols: conformance tests

Coverage numbers are signals, not substitutes for meaningful assertions.

---

# Type Checking

Run strict static checking on RowGuard core.

Recommended:

- mypy strict mode or equivalent
- pyright compatibility where practical
- Generic `QueryResult[T]` inference tests
- Plugin protocol implementation tests
- Sync/async overload tests

Typing examples should be executable test fixtures where possible.

---

# Linting and Formatting

Recommended tools:

- Ruff for linting
- Ruff format or Black for formatting
- Pre-commit for local enforcement

CI should reject:

- Unused imports
- Invalid type-ignore comments
- Accidental debug prints
- Mutable defaults
- Unsafe exception handling
- Import cycles where detectable

---

# Documentation Tests

Examples in documentation should be tested.

Options:

- doctest for small pure examples
- pytest examples for database-backed snippets
- generated example projects
- link checking
- API reference validation

The examples in `README.md`, `API.md`, and integration guides should not drift
from the real public API.

---

# Compatibility Tests

Test supported ranges for:

- Python
- Pydantic
- SQLAlchemy
- SQLRules
- SQLModel
- Database drivers

Use a lower-bound and latest-compatible dependency strategy.

Release workflows should verify the documented matrix.

---

# CI Workflow

Suggested jobs:

```text
lint
type-check
unit
sqlite-sync
sqlite-async
postgres-sync
postgres-async
docs
plugin-conformance
security
benchmark-smoke
```

Scheduled workflows add the broader dialect and performance matrix.

---

# Flaky Tests

Flaky tests should be treated as defects.

Guidelines:

- Do not add blind retries to unit tests.
- Use explicit timeouts for async tests.
- Avoid sleep-based synchronization.
- Control randomness with seeds.
- Separate unstable external integration tests.
- Record driver/database versions.

---

# Test Naming

Use behavior-focused names.

Good:

```python
def test_collect_policy_preserves_rejection_order() -> None:
    ...
```

Avoid:

```python
def test_policy_1() -> None:
    ...
```

---

# Test Directory Layout

Suggested structure:

```text
tests/
├── unit/
│   ├── planning/
│   ├── adapters/
│   ├── validation/
│   ├── rejection/
│   ├── cache/
│   └── plugins/
├── integration/
│   ├── core/
│   ├── orm/
│   ├── sqlmodel/
│   ├── raw_sql/
│   └── reflection/
├── dialects/
│   ├── sqlite/
│   ├── postgresql/
│   ├── mysql/
│   └── mssql/
├── async/
├── streaming/
├── security/
├── typing/
└── conformance/
```

---

# MVP Testing Requirements

Before the first public release, RowGuard should have:

- Public API tests
- SQLAlchemy Core integration tests
- Pydantic validation tests
- SQLRules pushdown tests
- Raise/collect/skip policy tests
- Callback tests
- Basic quarantine tests
- Buffered execution tests
- Sync streaming tests
- SQLite integration
- PostgreSQL integration
- Cache correctness tests
- Diagnostics and statistics tests
- Strict type checking
- At least 95% line coverage
- Tested documentation examples

---

# Release Gates

A release should not ship when:

- Public examples fail
- Accepted/rejected counts are inconsistent
- Resource cleanup is broken
- Cache changes alter semantics
- Redaction tests fail
- Required dialect integration is failing
- Type checking fails
- Performance regression exceeds the accepted threshold without review
- Plugin API compatibility tests fail

---

# Design Principles

- Test guarantees, not implementation trivia.
- Invalid data is a normal test input.
- Real execution tests complement unit tests.
- Sync and async behavior must match.
- Buffered and streaming behavior must match.
- Security defaults require explicit tests.
- Cache use must never change semantics.
- Documentation examples are executable contracts.
- Failure paths deserve first-class coverage.
