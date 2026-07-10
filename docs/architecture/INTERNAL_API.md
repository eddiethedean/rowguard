# INTERNAL_API.md

# RowGuard Internal API

## Purpose

This document defines RowGuard's internal architecture and component contracts.

The internal API is not part of the stable public compatibility surface. It may
evolve between minor releases while RowGuard is pre-1.0. Public plugins should
use documented extension protocols rather than importing private modules.

The internal design should make every major stage independently testable:

```text
Request
  → Compilation
  → Execution Plan
  → Execution
  → Row Adaptation
  → Validation
  → Rejection Handling
  → Result Assembly
```

---

# Design Goals

The internal API should:

- Separate planning from execution.
- Keep SQLAlchemy, Pydantic, and SQLRules boundaries explicit.
- Use immutable planning objects.
- Avoid global mutable state.
- Support sync and async execution with shared orchestration.
- Support buffered and streaming results.
- Allow plugins at narrow, documented seams.
- Preserve complete diagnostics.
- Keep the per-row hot path small.

---

# Package Layout

Suggested layout:

```text
src/rowguard/
├── __init__.py
├── api.py
├── client.py
├── config.py
├── errors.py
├── diagnostics.py
├── statistics.py
├── planning/
│   ├── request.py
│   ├── compiler.py
│   ├── execution_plan.py
│   ├── pushdown.py
│   ├── projection.py
│   └── mappings.py
├── execution/
│   ├── engine.py
│   ├── sync.py
│   ├── async_.py
│   ├── streaming.py
│   └── resources.py
├── adapters/
│   ├── base.py
│   ├── sqlalchemy_row.py
│   ├── orm_entity.py
│   ├── scalar.py
│   └── nested.py
├── validation/
│   ├── base.py
│   ├── pydantic.py
│   └── results.py
├── rejection/
│   ├── base.py
│   ├── policies.py
│   ├── callbacks.py
│   ├── quarantine.py
│   └── records.py
├── results/
│   ├── query_result.py
│   ├── stream_result.py
│   └── rejected_row.py
└── integrations/
    ├── sqlrules.py
    ├── sqlalchemy_core.py
    ├── sqlalchemy_orm.py
    └── sqlmodel.py
```

This is a suggested decomposition, not a requirement to create one module per
class.

---

# Public API Boundary

Public functions should remain thin wrappers.

```python
rowguard.select(...)
rowguard.execute(...)
rowguard.stream(...)
rowguard.aselect(...)
rowguard.aexecute(...)
rowguard.astream(...)
rowguard.validate_rows(...)
```

Each function should:

1. Normalize public arguments.
2. Build a `QueryRequest`.
3. Invoke the planner.
4. Pass the resulting `ExecutionPlan` to the appropriate engine.
5. Return a public result object.

Public functions should not implement row processing directly.

---

# QueryRequest

`QueryRequest` is the normalized representation of a user's request before
planning.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class QueryRequest(Generic[T]):
    model: type[T]
    source: object | None
    statement: object | None
    execution_context: object | None
    filters: tuple[object, ...]
    pushdown: PushdownConfig
    adapter: RowAdapter | None
    validation: ValidationConfig
    rejection: RejectionConfig
    diagnostics: DiagnosticsConfig
    streaming: StreamingConfig
    parameters: Mapping[str, object]
```

Invariants:

- Exactly one of `source` or `statement` is present when querying.
- `model` is a supported validation target.
- Configuration objects are immutable.
- User collections are normalized to tuples or immutable mappings.

---

# Planner

The planner converts a `QueryRequest` into an `ExecutionPlan`.

Suggested interface:

```python
class QueryPlanner(Protocol):
    def compile(
        self,
        request: QueryRequest[T],
    ) -> ExecutionPlan[T]:
        ...
```

Responsibilities:

- Validate request consistency.
- Normalize SQLAlchemy source objects.
- Build or validate statements.
- Invoke SQLRules integration.
- Resolve pushdown mappings.
- Resolve row adapter.
- Resolve validator.
- Resolve rejection policy.
- Build diagnostics plan.
- Produce an immutable execution plan.

The planner performs no database I/O unless an explicitly documented feature,
such as reflection, is requested through a separate planning service.

---

# Planning Stages

Recommended stages:

```text
QueryRequest
    │
    ▼
Source Normalization
    │
    ▼
Statement Planning
    │
    ▼
SQLRules Pushdown Planning
    │
    ▼
Result Shape / Adapter Planning
    │
    ▼
Validation Planning
    │
    ▼
Rejection Planning
    │
    ▼
ExecutionPlan
```

Each stage should have a narrow input and output contract.

---

# ExecutionPlan

The `ExecutionPlan` is the immutable contract between planning and runtime.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class ExecutionPlan(Generic[T]):
    execution_id: str
    statement: object
    parameters: Mapping[str, object]
    model: type[T]
    pushdown_plan: PushdownPlan
    adapter_plan: AdapterPlan
    validation_plan: ValidationPlan[T]
    rejection_plan: RejectionPlan
    diagnostics_plan: DiagnosticsPlan
    statistics_plan: StatisticsPlan
    execution_options: Mapping[str, object]
    metadata: Mapping[str, object]
```

The plan should contain everything required to execute without re-inspecting the
Pydantic model or SQLAlchemy source for every row.

---

# Plan Immutability

Execution plans should be immutable.

Benefits:

- Safe reuse.
- Predictable caching.
- Easier testing.
- Thread-safe reads.
- Clear separation from runtime state.
- No accidental cross-query mutation.

Mutable counters and resources belong in `ExecutionState`, not
`ExecutionPlan`.

---

# ExecutionState

`ExecutionState` holds per-run mutable state.

Suggested structure:

```python
@dataclass(slots=True)
class ExecutionState(Generic[T]):
    plan: ExecutionPlan[T]
    statistics: MutableStatistics
    diagnostics: DiagnosticCollector
    accepted: list[T]
    rejected: list[RejectedRow]
    quarantine_receipts: list[QuarantineReceipt]
    closed: bool = False
```

Buffered and streaming engines may use specialized state types.

The state must never be shared across executions.

---

# Sync Execution Engine

Suggested protocol:

```python
class SyncExecutionEngine(Protocol):
    def execute(
        self,
        plan: ExecutionPlan[T],
        context: SyncExecutionContext,
    ) -> QueryResult[T]:
        ...
```

Responsibilities:

- Execute the statement.
- Iterate rows.
- Invoke adapter.
- Invoke validator.
- Invoke rejection policy.
- Update statistics and diagnostics.
- Assemble the final result.
- Release resources.

---

# Async Execution Engine

Suggested protocol:

```python
class AsyncExecutionEngine(Protocol):
    async def execute(
        self,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
    ) -> QueryResult[T]:
        ...
```

Only I/O-specific operations should differ from sync execution.

Shared components:

- Adapter.
- Validator.
- Rejection decision logic.
- Statistics model.
- Diagnostics model.
- Result assembly.

---

# Execution Contexts

Suggested context types:

```python
@dataclass(frozen=True, slots=True)
class SyncExecutionContext:
    session: object | None
    connection: object | None


@dataclass(frozen=True, slots=True)
class AsyncExecutionContext:
    session: object | None
    connection: object | None
```

Invariants:

- Exactly one execution resource is active when required.
- RowGuard never owns caller-supplied session lifecycle.
- Contexts expose only the capabilities needed by the engine.

---

# Streaming Engine

Streaming requires a lifecycle object rather than a completed result.

Suggested protocol:

```python
class SyncStreamEngine(Protocol):
    def open(
        self,
        plan: ExecutionPlan[T],
        context: SyncExecutionContext,
    ) -> StreamResult[T]:
        ...
```

Async equivalent:

```python
class AsyncStreamEngine(Protocol):
    async def open(
        self,
        plan: ExecutionPlan[T],
        context: AsyncExecutionContext,
    ) -> AsyncStreamResult[T]:
        ...
```

The stream result owns:

- Active SQLAlchemy result resource.
- Current execution state.
- Iteration.
- Finalization.
- Provider flushing.
- Cleanup.

---

# Resource Management

Internal resource interfaces should make cleanup explicit.

```python
class ExecutionResource(Protocol):
    def close(self) -> None:
        ...
```

Async:

```python
class AsyncExecutionResource(Protocol):
    async def close(self) -> None:
        ...
```

Cleanup must occur on:

- Normal completion.
- Validation raise policy.
- Callback failure.
- Quarantine failure.
- Cancellation.
- Consumer-abandoned streams.
- Unexpected exceptions.

---

# Row Adapter Protocol

```python
class RowAdapter(Protocol):
    def adapt(
        self,
        row: object,
        context: RowAdapterContext,
    ) -> AdaptedRow:
        ...
```

Suggested `AdaptedRow`:

```python
@dataclass(frozen=True, slots=True)
class AdaptedRow:
    raw: object | None
    mapping: Mapping[str, object]
    source_identity: SourceIdentity | None
    diagnostics: tuple[Diagnostic, ...]
```

Adapters should be stateless or immutable after planning.

---

# AdapterPlan

The planner should precompute an `AdapterPlan`.

```python
@dataclass(frozen=True, slots=True)
class AdapterPlan:
    adapter: RowAdapter
    field_map: Mapping[str, str]
    expected_keys: tuple[str, ...]
    extra_policy: str
    duplicate_policy: str
    retain_raw: bool
```

This avoids repeated model and SQLAlchemy metadata inspection.

---

# Validator Protocol

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

The protocol exists to isolate Pydantic integration, not to make Pydantic
optional in the MVP.

---

# ValidationPlan

```python
@dataclass(frozen=True, slots=True)
class ValidationPlan(Generic[T]):
    validator: Validator[T]
    model: type[T]
    strict: bool | None
    from_attributes: bool
    context: Mapping[str, object] | None
    error_value_policy: str
```

The per-row path should call the preconfigured validator without rebuilding
options.

---

# ValidationResult

```python
@dataclass(frozen=True, slots=True)
class ValidationResult(Generic[T]):
    accepted: bool
    model: T | None
    error: Exception | None
    duration_ns: int
```

Invariants:

- Accepted results contain a model and no error.
- Rejected results contain an error and no model.
- Unexpected integration failures are distinguishable from ordinary Pydantic
  rejection.

---

# Rejection Policy Protocol

```python
class RejectionPolicy(Protocol):
    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        ...
```

Async protocol may expose:

```python
class AsyncRejectionPolicy(Protocol):
    async def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        ...
```

Built-in implementations:

- `RaisePolicy`
- `CollectPolicy`
- `SkipPolicy`
- `CallbackPolicy`
- `QuarantinePolicy`

---

# RejectionDecision

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class RejectionDecision:
    continue_processing: bool
    retain_rejection: bool
    receipt: QuarantineReceipt | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
```

This is clearer than overloading one enum with unrelated concerns.

---

# RejectionContext

```python
@dataclass(frozen=True, slots=True)
class RejectionContext:
    execution_id: str
    row_index: int
    statistics_snapshot: StatisticsSnapshot
    model_name: str
    source_name: str | None
    metadata: Mapping[str, object]
```

The context should not expose a live session by default.

---

# RejectedRow

Internal and public representation may be the same immutable object.

```python
@dataclass(frozen=True, slots=True)
class RejectedRow:
    index: int
    model: type[BaseModel]
    mapping: Mapping[str, object] | None
    raw_row: object | None
    validation_error: Exception | None
    adaptation_error: Exception | None
    source_identity: SourceIdentity | None
    diagnostics: tuple[Diagnostic, ...]
```

Invariants:

- Exactly one primary rejection cause is present.
- Row index is stable.
- Retention and redaction policy have already been applied to public fields.

---

# SQLRules Bridge

RowGuard should isolate SQLRules behind an integration protocol.

```python
class RulesCompiler(Protocol):
    def compile(
        self,
        model: type[BaseModel],
        source: object,
        column_map: Mapping[str, object] | None,
        options: Mapping[str, object],
    ) -> CompiledRules:
        ...
```

Default implementation:

```python
SQLRulesCompilerBridge
```

RowGuard should depend only on SQLRules' public API.

---

# CompiledRules

RowGuard may wrap SQLRules output in a normalized internal object.

```python
@dataclass(frozen=True, slots=True)
class CompiledRules:
    by_field: Mapping[str, tuple[object, ...]]
    expressions: tuple[object, ...]
    diagnostics: tuple[Diagnostic, ...]
    source_identity: object | None
```

The wrapper should not reinterpret constraint semantics.

---

# PushdownPlan

```python
@dataclass(frozen=True, slots=True)
class PushdownPlan:
    enabled: bool
    mode: str
    compiled_rules: CompiledRules | None
    user_filters: tuple[object, ...]
    diagnostics: tuple[Diagnostic, ...]
```

The final SQLAlchemy statement is created during planning.

Execution should not recompile pushdown rules.

---

# Statement Builder

Suggested protocol:

```python
class StatementBuilder(Protocol):
    def build(
        self,
        request: QueryRequest[T],
        pushdown: PushdownPlan,
    ) -> object:
        ...
```

Implementations may support:

- SQLAlchemy Core table sources.
- ORM mapped classes.
- Existing selects.
- Raw SQL pass-through.

Statement builders should preserve SQLAlchemy semantics and bound parameters.

---

# Source Resolver

The source resolver normalizes SQLAlchemy input types.

```python
class SourceResolver(Protocol):
    def resolve(
        self,
        source: object,
    ) -> ResolvedSource:
        ...
```

Suggested result:

```python
@dataclass(frozen=True, slots=True)
class ResolvedSource:
    kind: str
    selectable: object | None
    entity: object | None
    columns: Mapping[str, object]
    source_name: str | None
    metadata: Mapping[str, object]
```

Resolvers should fail rather than guess when source shape is ambiguous.

---

# Statistics

Mutable counters should be separate from immutable public snapshots.

```python
@dataclass(slots=True)
class MutableStatistics:
    rows_read: int = 0
    rows_adapted: int = 0
    rows_validated: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    ...
```

Final snapshot:

```python
@dataclass(frozen=True, slots=True)
class QueryStatistics:
    rows_read: int
    rows_adapted: int
    rows_validated: int
    rows_accepted: int
    rows_rejected: int
    execution_time_ns: int
    adaptation_time_ns: int
    validation_time_ns: int
    rejection_time_ns: int
```

Result assembly should validate statistics invariants.

---

# Diagnostics Collector

Suggested protocol:

```python
class DiagnosticCollector(Protocol):
    def emit(self, diagnostic: Diagnostic) -> None:
        ...

    def snapshot(self) -> tuple[Diagnostic, ...]:
        ...
```

A no-op collector should make disabled diagnostics inexpensive.

Collectors may fan out to:

- In-memory result diagnostics.
- Structured logging.
- Metrics.
- Tracing.

Emission failures should not silently alter validation decisions.

---

# Diagnostic Factory

Stable diagnostic codes should be centralized.

```python
class DiagnosticFactory:
    @staticmethod
    def row_rejected(...) -> Diagnostic:
        ...
```

Benefits:

- Consistent metadata.
- Stable namespaces.
- Easier testing.
- Reduced ad hoc string construction.

---

# Result Assembler

Suggested interface:

```python
class ResultAssembler(Protocol[T]):
    def assemble(
        self,
        state: ExecutionState[T],
    ) -> QueryResult[T]:
        ...
```

Responsibilities:

- Freeze accepted models.
- Freeze retained rejections.
- Freeze diagnostics.
- Create final statistics.
- Preserve statement metadata.
- Validate result invariants.

The assembler performs no query execution.

---

# QueryResult

Suggested public object:

```python
@dataclass(frozen=True, slots=True)
class QueryResult(Generic[T]):
    models: tuple[T, ...]
    rejected: tuple[RejectedRow, ...]
    statistics: QueryStatistics
    diagnostics: tuple[Diagnostic, ...]
    statement: object
    quarantine_receipts: tuple[QuarantineReceipt, ...]
```

Internal code should never expose partially built results.

---

# StreamResult

The streaming result owns lifecycle and iteration.

Suggested sync protocol:

```python
class StreamResult(Iterator[T], ContextManager["StreamResult[T]"]):
    @property
    def statistics(self) -> QueryStatistics | StatisticsSnapshot:
        ...

    @property
    def rejected(self) -> tuple[RejectedRow, ...]:
        ...
```

Async equivalent implements `AsyncIterator` and `AsyncContextManager`.

---

# Configuration Objects

Configuration should use small immutable dataclasses.

Examples:

```python
PushdownConfig
ValidationConfig
RejectionConfig
DiagnosticsConfig
StreamingConfig
RetentionConfig
SecurityConfig
```

Avoid a single unstructured dictionary.

Benefits:

- Type checking.
- Validation.
- Discoverability.
- Stable defaults.
- Clear ownership.

---

# Configuration Validation

Configuration should be validated during planning.

Examples:

- Async callback in sync execution.
- Quarantine policy without provider.
- Conflicting source and statement.
- Invalid retention mode.
- Unsupported partial validation configuration.
- Ambiguous column map.
- Unsupported raw SQL pushdown.

Execution should assume the plan is valid.

---

# Registries

Potential internal registries:

- Source resolvers.
- Row adapters.
- Rejection policies.
- Quarantine providers.
- Diagnostic exporters.

Registries should:

- Be immutable after construction.
- Reject duplicate registrations by default.
- Support explicit replacement.
- Avoid global mutable singletons.
- Be scoped to a `RowGuard` client or planner.

---

# RowGuard Client

A configurable client may own reusable dependencies.

```python
@dataclass(frozen=True)
class RowGuard:
    planner: QueryPlanner
    sync_engine: SyncExecutionEngine
    async_engine: AsyncExecutionEngine
    registries: Registries
    defaults: RowGuardDefaults
```

Top-level functions may delegate to a default client.

Advanced users can construct isolated clients with custom plugins.

---

# Dependency Injection

Core components should receive dependencies explicitly.

Example:

```python
planner = DefaultQueryPlanner(
    rules_compiler=SQLRulesCompilerBridge(),
    source_resolvers=...,
    adapter_registry=...,
    validator_factory=...,
    rejection_policy_factory=...,
)
```

This improves:

- Testing.
- Plugin support.
- Alternate providers.
- Version compatibility.
- Isolation.

Avoid service locators and hidden global state.

---

# Error Boundaries

Each stage should expose stage-specific errors.

```text
PlanningError
ExecutionError
RowAdaptationError
ValidationEngineError
RejectHandlerError
ResultAssemblyError
```

Errors should preserve original causes.

Ordinary Pydantic validation failures are expected rejection outcomes, not
internal engine errors.

---

# Internal Assertions

Internal invariants should be enforced.

Examples:

- A validation result cannot contain both model and error.
- Accepted count equals number of accepted models in buffered mode.
- Rejected count is not less than retained rejection count.
- Closed stream cannot yield rows.
- A plan cannot contain both sync-only and async-only handlers.
- Pushdown expressions are finalized before execution.

Invariant failures should raise `InternalRowGuardError` or a specific assembly
error.

---

# Caching

Potential caches:

- Pydantic model inspection.
- SQLRules compilation.
- ORM mapper extraction plans.
- Row adapter plans.
- Execution plans for stable statement shapes.

Cache keys must include all semantic inputs.

Do not cache:

- Sessions.
- Connections.
- Transaction state.
- Accepted models.
- Rejected rows.
- Mutable validation context.
- User-specific parameter values unless safely parameterized.

Caches should be optional and bounded.

---

# Concurrency

Immutable plans and registries may be shared across threads.

Per-execution state must not be shared.

Sync engines should not assume SQLAlchemy sessions are thread-safe.

Async engines should not share one active session across concurrent tasks unless
the application and SQLAlchemy usage explicitly support it.

Callbacks and providers must declare their own concurrency capabilities.

---

# Sync and Async Code Sharing

Shared logic should include:

- Planning.
- Row adaptation.
- Pydantic validation.
- Rejection decision rules.
- Statistics updates.
- Diagnostics.
- Result assembly.

Separate logic should include:

- Statement execution.
- Row fetching.
- Resource closing.
- Async callbacks.
- Async quarantine providers.
- Cancellation handling.

Do not duplicate the entire pipeline for async support.

---

# Buffered and Streaming Code Sharing

Shared per-row operation:

```python
def process_row(
    row: object,
    state: ExecutionState[T],
) -> ProcessedRow[T]:
    ...
```

Possible outcomes:

```python
AcceptedRow[T]
RejectedOutcome
StopExecution
```

Buffered engines append accepted models.

Streaming engines yield accepted models.

This shared processor helps keep behavior consistent.

---

# Per-Row Processor

Suggested pipeline:

```text
Increment rows_read
      │
      ▼
Adapt row
      │
      ├── adaptation failure → reject
      ▼
Validate mapping
      │
      ├── validation failure → reject
      ▼
Increment accepted
      │
      ▼
Return accepted model
```

The processor should not own SQLAlchemy cursor iteration.

---

# Plugin Boundaries

Public plugin interfaces should be narrow and versioned.

Good extension points:

- Row adapter.
- Rejection policy.
- Quarantine provider.
- Diagnostics exporter.
- Source resolver.
- Pushdown policy validator.

Avoid exposing:

- Mutable execution state.
- Internal planner stages.
- SQLRules internals.
- Raw result assembler internals.

Plugins should consume immutable context objects.

---

# Internal vs Public Modules

Suggested convention:

```text
rowguard.api
rowguard.models
rowguard.protocols
```

are public.

```text
rowguard._internal.*
```

or undocumented implementation modules are private.

If public plugin protocols live in implementation packages, they should be
re-exported from a documented stable namespace.

---

# Versioning Policy

Before 1.0:

- Internal APIs may change in minor releases.
- Public protocols should still change deliberately and with migration notes.

After 1.0:

- Public function signatures, public result objects, public errors, and public
  plugin protocols follow semantic versioning.
- Private modules remain unstable unless documented otherwise.

---

# Testing Strategy

Each internal component should be testable independently.

## Planner tests

- Request normalization.
- Statement creation.
- SQLRules integration.
- Mapping resolution.
- Configuration errors.
- Immutable plans.

## Adapter tests

- SQLAlchemy rows.
- ORM entities.
- Aliases.
- Duplicate keys.
- Nested mapping.
- Source identity.

## Validator tests

- Accepted models.
- Pydantic errors.
- Strict mode.
- Context.
- Unexpected exceptions.

## Rejection tests

- Raise.
- Collect.
- Skip.
- Callback.
- Quarantine.
- Decisions.
- Failures.

## Engine tests

- Buffered sync.
- Buffered async.
- Streaming sync.
- Streaming async.
- Resource cleanup.
- Cancellation.
- Statistics.

## Result tests

- Invariants.
- Immutability.
- Typing.
- Diagnostics.
- Receipt retention.

---

# Performance Requirements

The internal API should keep the per-row hot path minimal.

Guidelines:

- Precompute plans.
- Use slotted dataclasses where beneficial.
- Avoid repeated model introspection.
- Avoid repeated mapper inspection.
- Avoid unnecessary row copies.
- Keep diagnostics no-op when disabled.
- Validate exactly once per attempt.
- Avoid rendering SQL strings during normal execution.
- Stream large result sets.

Optimization must not weaken correctness.

---

# Security Requirements

Internal components must preserve:

- Bound SQL parameters.
- Redaction before external emission.
- Explicit authorization filters.
- No implicit raw entity retention.
- No accidental session exposure to callbacks.
- No arbitrary object stringification in quarantine serialization.
- Clear source identity without leaking full row contents.
- Deterministic error handling.

---

# MVP Internal Components

The first implementation should include:

- `QueryRequest`
- `QueryPlanner`
- `ExecutionPlan`
- `ExecutionState`
- Core `StatementBuilder`
- SQLRules bridge
- SQLAlchemy row adapter
- Pydantic validator
- Raise/collect/skip policies
- Callback policy
- Basic quarantine protocol
- Sync buffered engine
- Sync streaming engine
- Async engine interfaces
- Statistics collector
- Diagnostics collector
- Result assembler
- Immutable `QueryResult`
- Immutable `RejectedRow`

Deferred:

- Advanced plan caching.
- Concurrent callback execution.
- Automatic optimizer passes.
- Distributed execution.
- Complex plugin dependency resolution.
- General DAG pipeline engine.
- Background delivery.
- Alternate validation engines.
- Automatic repair planning.

---

# Design Principles

- Public APIs are thin.
- Planning is separate from execution.
- Execution plans are immutable.
- Per-run state is isolated.
- SQLAlchemy owns SQL behavior.
- SQLRules owns constraint compilation.
- Pydantic owns validation semantics.
- RowGuard owns orchestration and rejection handling.
- Plugins use narrow protocols.
- Sync, async, buffered, and streaming modes share core behavior.
- Errors preserve stage boundaries and original causes.
- Internal flexibility must not leak complexity into the public API.
