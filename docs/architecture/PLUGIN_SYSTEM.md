# PLUGIN_SYSTEM.md

# RowGuard Plugin System

## Purpose

The RowGuard plugin system allows applications and third-party packages to
extend RowGuard without modifying the core package.

Plugins should integrate at narrow, documented boundaries such as:

- Row adaptation
- Rejection policies
- Callbacks
- Quarantine providers
- Diagnostics exporters
- Source resolution
- Pushdown policy validation
- Result export

The plugin system must not expose mutable execution internals or allow plugins to
silently weaken RowGuard's validation guarantees.

---

# Core Principle

> Plugins may extend RowGuard's behavior, but they must not redefine what it
> means for a row to be valid.

Pydantic remains the validation authority.

SQLRules remains the constraint compiler.

SQLAlchemy remains the SQL and execution foundation.

---

# Goals

The plugin system should:

- Keep RowGuard core small.
- Provide stable extension protocols.
- Support explicit registration.
- Avoid monkey-patching.
- Avoid global mutable state.
- Support sync and async plugins.
- Support capability declarations.
- Preserve deterministic behavior.
- Validate plugin compatibility before execution.
- Keep plugin failures observable.

---

# Non-Goals

The plugin system should not:

- Allow plugins to bypass Pydantic validation silently.
- Allow plugins to rewrite arbitrary SQL without explicit contracts.
- Expose mutable `ExecutionState`.
- Depend on import-time side effects.
- Auto-install packages.
- Download code dynamically.
- Sandbox untrusted Python.
- Guarantee compatibility with undocumented internals.
- Create a general-purpose workflow engine.

---

# Plugin Categories

Recommended public plugin categories:

```text
RowAdapter
SourceResolver
RejectionPolicy
RejectionCallback
QuarantineProvider
DiagnosticExporter
ResultExporter
PushdownPolicy
ExecutionObserver
```

Each category should have a separate protocol.

Avoid one generic `Plugin` interface with arbitrary hooks.

---

# Architecture

```text
                  RowGuard Client
                        │
                        ▼
                    Registries
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
   Adapters         Policies         Providers
        │               │                │
        └───────────────┼────────────────┘
                        ▼
                  Query Planner
                        │
                        ▼
                  Execution Plan
                        │
                        ▼
                 Execution Engine
```

Plugins are resolved during planning whenever possible.

The per-row hot path should use prebound plugin methods rather than repeated
registry lookups.

---

# Registration Model

Plugins should be registered explicitly on a `RowGuard` client or registry set.

Example:

```python
guard = RowGuard(
    adapters=AdapterRegistry(
        entries={
            "nested": NestedRowAdapter(),
        },
    ),
    quarantine_providers=QuarantineProviderRegistry(
        entries={
            "s3": S3QuarantineProvider(...),
        },
    ),
)
```

Top-level functions may delegate to a default client with built-in plugins only.

---

# Why Explicit Registration

Explicit registration provides:

- Predictable behavior.
- Easier testing.
- Clear dependency ownership.
- No import-order surprises.
- No hidden plugin activation.
- Better security review.
- Easier per-application configuration.

Automatic entry-point discovery may be added later as an opt-in convenience.

---

# Registry Design

Each plugin category should have its own immutable registry.

Example:

```python
@dataclass(frozen=True)
class AdapterRegistry:
    entries: Mapping[str, RowAdapterFactory]
```

Suggested methods:

```python
registry.get(name)
registry.contains(name)
registry.with_plugin(name, plugin)
registry.without(name)
```

Registries should return new instances rather than mutate in place where
practical.

---

# Conflict Resolution

Duplicate names should raise by default.

Potential policies:

```python
on_conflict="raise"
on_conflict="replace"
on_conflict="ignore"
```

Recommended default:

```python
raise
```

Replacement should be explicit and local to a configured client.

---

# Plugin Names

Plugin names should be stable, lowercase identifiers.

Examples:

```text
sqlalchemy-row
orm-entity
nested
jsonl
postgresql
opentelemetry
polars
```

Names should not depend on display labels.

Namespaced third-party names may use:

```text
vendor.plugin-name
```

Example:

```text
acme.secure-quarantine
```

---

# Plugin Metadata

Each plugin should expose metadata.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class PluginMetadata:
    name: str
    version: str
    api_version: str
    description: str | None
    provider: str | None
    capabilities: Mapping[str, object]
```

Metadata supports:

- Compatibility checks.
- Diagnostics.
- Debugging.
- Inventory.
- Documentation.
- Security review.

---

# Plugin API Version

RowGuard should define a plugin API version independent from the package
version.

Example:

```python
ROWGUARD_PLUGIN_API = "1"
```

Plugins declare:

```python
api_version = "1"
```

Compatibility rules:

- Same major plugin API version is required.
- Minor capability additions should remain backward compatible.
- Breaking protocol changes increment the plugin API major version.

---

# Capability Declarations

Plugins should declare what they support.

Examples:

## Row Adapter

```python
AdapterCapabilities(
    sync_supported=True,
    async_supported=True,
    streaming_supported=True,
    preserves_raw_row=False,
    may_trigger_io=False,
)
```

## Quarantine Provider

```python
QuarantineCapabilities(
    async_supported=True,
    batch_supported=True,
    receipts_supported=True,
    transactions_supported=False,
    max_record_size=1_000_000,
)
```

## Diagnostic Exporter

```python
DiagnosticCapabilities(
    structured=True,
    async_supported=False,
    batching_supported=True,
)
```

Planning should reject incompatible configurations before query execution.

---

# Row Adapter Plugins

Row Adapter plugins transform database result shapes into validation inputs.

Protocol:

```python
class RowAdapter(Protocol):
    metadata: PluginMetadata
    capabilities: AdapterCapabilities

    def adapt(
        self,
        row: object,
        context: RowAdapterContext,
    ) -> AdaptedRow:
        ...
```

Examples:

- SQLAlchemy mapping adapter
- ORM entity adapter
- Nested mapping adapter
- Positional tuple adapter
- Scalar adapter
- Geospatial adapter

Adapters must not decide whether a row is valid.

---

# Adapter Factory

Some adapters require planning-time configuration.

Protocol:

```python
class RowAdapterFactory(Protocol):
    def build(
        self,
        request: QueryRequest,
        source: ResolvedSource,
        model: type[BaseModel],
    ) -> AdapterPlan:
        ...
```

Factories may inspect:

- Result shape.
- Field mappings.
- Pydantic aliases.
- ORM mapper metadata.
- Selected labels.

They perform no query execution.

---

# Source Resolver Plugins

Source resolvers normalize new database or result-source types.

Protocol:

```python
class SourceResolver(Protocol):
    metadata: PluginMetadata

    def supports(self, source: object) -> bool:
        ...

    def resolve(self, source: object) -> ResolvedSource:
        ...
```

Potential sources:

- SQLAlchemy Core
- SQLAlchemy ORM
- SQLModel
- Custom database wrappers
- External row iterators
- Data API clients

Resolver ordering must be deterministic.

---

# Resolver Ambiguity

If multiple resolvers claim the same source, planning should fail unless explicit
precedence is configured.

Suggested error:

```python
AmbiguousSourceResolverError
```

Plugins should use precise `supports()` checks.

---

# Rejection Policy Plugins

Rejection policy plugins decide what happens after a row is rejected.

Protocol:

```python
class RejectionPolicy(Protocol):
    metadata: PluginMetadata
    capabilities: RejectionPolicyCapabilities

    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        ...
```

Examples:

- Raise
- Collect
- Skip
- Callback
- Quarantine
- Sample
- Route by error type
- Stop after threshold

Policies must not mutate accepted models or validation errors.

---

# Async Rejection Policies

Async policies should use a distinct protocol.

```python
class AsyncRejectionPolicy(Protocol):
    async def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        ...
```

A plugin may implement both sync and async interfaces.

Capabilities must declare support explicitly.

---

# Callback Plugins

Callbacks are lightweight rejection-side hooks.

A callback plugin may integrate:

- Logging
- Metrics
- Notifications
- Audit APIs
- User-defined workflows

Callbacks should receive structured immutable data.

They should not receive a live session by default.

---

# Quarantine Provider Plugins

Quarantine providers persist storage-safe rejection records.

Protocol:

```python
class QuarantineProvider(Protocol):
    metadata: PluginMetadata
    capabilities: QuarantineCapabilities

    def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        ...
```

Provider plugins may target:

- SQL tables
- JSONL
- Parquet
- S3
- Azure Blob Storage
- Kafka
- SQS
- Pub/Sub
- Data quality platforms

Cloud providers should live in optional packages.

---

# Quarantine Provider Security Contract

Providers should document:

- Where data is sent.
- Encryption expectations.
- Authentication requirements.
- Retention behavior.
- Redaction expectations.
- Delivery guarantees.
- Retry semantics.
- Transaction behavior.
- Maximum record size.

RowGuard should not infer these properties.

---

# Diagnostic Exporter Plugins

Diagnostic exporters receive structured events.

Protocol:

```python
class DiagnosticExporter(Protocol):
    metadata: PluginMetadata
    capabilities: DiagnosticCapabilities

    def emit(self, diagnostic: Diagnostic) -> None:
        ...

    def close(self) -> None:
        ...
```

Examples:

- Structured logging
- Prometheus
- OpenTelemetry
- Datadog
- Custom audit systems

Exporters must not alter execution decisions.

---

# Exporter Failure Policy

Diagnostic exporter failures should not automatically change validation results.

Potential policies:

```python
on_diagnostic_error="raise"
on_diagnostic_error="disable"
on_diagnostic_error="log"
```

Recommended production behavior may differ by exporter importance.

For example:

- Audit exporter failure may be fatal.
- Debug exporter failure may disable the exporter.

The policy must be explicit.

---

# Result Exporter Plugins

Result exporters transform completed results into external representations.

Examples:

- Pandas DataFrame
- Polars DataFrame
- Arrow Table
- JSON report
- HTML report
- Metrics summary

Protocol:

```python
class ResultExporter(Protocol):
    def export(
        self,
        result: QueryResult,
        options: Mapping[str, object],
    ) -> object:
        ...
```

Exporters consume immutable results.

They do not participate in row acceptance decisions.

---

# Streaming Result Exporters

Streaming exporters may consume validated models incrementally.

Examples:

- CSV writer
- Parquet writer
- Arrow record-batch writer

They should use a separate streaming protocol rather than requiring a complete
`QueryResult`.

---

# Pushdown Policy Plugins

Pushdown policy plugins may decide whether already-compiled SQLRules expressions
are safe to apply in a specific query context.

They must not compile Pydantic constraints themselves.

Protocol:

```python
class PushdownPolicy(Protocol):
    def evaluate(
        self,
        compiled_rules: CompiledRules,
        source: ResolvedSource,
        statement: object,
        context: PushdownContext,
    ) -> PushdownDecision:
        ...
```

Examples:

- Outer join safety policy
- Dialect strictness policy
- Security review policy
- Exact-only policy

SQLRules remains the sole constraint compiler.

---

# Execution Observer Plugins

Execution observers receive lifecycle events.

Potential events:

```text
planning_started
planning_completed
execution_started
row_rejected
execution_completed
execution_failed
stream_closed
```

Observers may support:

- Tracing
- Profiling
- Audit
- Custom monitoring

Observers should not mutate execution state.

They should be treated similarly to diagnostics exporters.

---

# Plugin Lifecycle

Plugins may require setup and cleanup.

Recommended optional methods:

```python
class PluginLifecycle(Protocol):
    def open(self) -> None:
        ...

    def close(self) -> None:
        ...
```

Async:

```python
class AsyncPluginLifecycle(Protocol):
    async def open(self) -> None:
        ...

    async def close(self) -> None:
        ...
```

Lifecycle ownership must be explicit.

---

# Lifecycle Ownership

Potential plugin ownership modes:

```text
client-owned
execution-owned
application-owned
```

## client-owned

Opened when the `RowGuard` client is created and closed with the client.

## execution-owned

Opened and closed for one query or stream.

## application-owned

The application passes an already managed plugin instance.

RowGuard should not close application-owned clients unexpectedly.

---

# Stateful Plugins

Stateful plugins must declare their concurrency behavior.

Examples:

- File writer
- Batch quarantine provider
- Metrics buffer
- Network client

Capabilities may include:

```python
thread_safe: bool
task_safe: bool
reentrant: bool
```

Planning can reject unsafe sharing patterns.

---

# Stateless Plugins

Stateless plugins are preferred where practical.

Examples:

- Mapping adapter
- Simple policy
- Source resolver
- Redaction transformer

Stateless plugins are easier to:

- Cache
- Share
- Test
- Reuse
- Run concurrently

---

# Plugin Configuration

Plugins should use typed configuration objects.

Example:

```python
@dataclass(frozen=True, slots=True)
class JSONLProviderConfig:
    path: Path
    flush_every: int = 1
    compression: str | None = None
```

Avoid unstructured dictionaries for complex plugins.

---

# Configuration Validation

Plugin configuration should be validated before execution.

Examples:

- Invalid file path.
- Async provider in sync query.
- Batch size unsupported by provider.
- Redaction mode incompatible with sink.
- Required credentials absent.
- Maximum record size too small.
- Transaction mode unsupported.

Execution should not discover obvious configuration problems halfway through a
large stream.

---

# Plugin Factories

Factories may construct plugin instances from typed configuration.

Protocol:

```python
class PluginFactory(Protocol[P, C]):
    def create(self, config: C) -> P:
        ...
```

Factories help separate:

- Immutable plan configuration.
- Runtime client instances.
- Application-owned resources.

---

# Dependency Injection

Core components should receive registries and factories explicitly.

Example:

```python
planner = DefaultQueryPlanner(
    source_resolvers=source_resolver_registry,
    adapter_factories=adapter_registry,
    rejection_policy_factories=policy_registry,
    rules_compiler=SQLRulesCompilerBridge(),
)
```

Avoid hidden service locators.

---

# Plugin Dependencies

A plugin may require another package or plugin.

Example:

```text
S3QuarantineProvider
  requires boto3
```

Dependencies should be declared through package extras:

```text
rowguard-s3
```

or:

```bash
pip install rowguard[s3]
```

RowGuard core should not import optional dependencies eagerly.

---

# Plugin-to-Plugin Dependencies

Direct plugin dependency graphs should be minimized.

When required, metadata may declare:

```python
requires_plugins=("json-safe-serializer",)
```

The registry should validate requirements during client construction.

Circular dependencies should raise a configuration error.

---

# Entry Point Discovery

Future optional discovery may use Python package entry points.

Possible groups:

```text
rowguard.adapters
rowguard.source_resolvers
rowguard.rejection_policies
rowguard.quarantine_providers
rowguard.diagnostics
rowguard.result_exporters
```

Discovery should be opt-in:

```python
guard = RowGuard.discover_plugins()
```

Explicit registration remains preferred.

---

# Why Discovery Is Not Default

Automatic discovery can create:

- Slow imports.
- Hidden behavior.
- Conflicts.
- Security review complexity.
- Environment-dependent results.
- Difficult debugging.

The MVP should not auto-load third-party plugins.

---

# Plugin Selection

Users may select plugins by instance:

```python
row_adapter=NestedRowAdapter(...)
```

or by registered name:

```python
row_adapter="nested"
```

Instance selection should take precedence over registry lookup.

Named selection is useful for configuration-driven applications.

---

# Plugin Context Objects

Plugins should receive narrow immutable context objects.

Good:

```python
RowAdapterContext
RejectionContext
QuarantineContext
PushdownContext
DiagnosticContext
```

Avoid passing:

- Mutable `ExecutionState`
- Entire `RowGuard` client
- Arbitrary session access
- Internal planner objects
- Undocumented registries

Narrow contexts reduce coupling.

---

# Session and Connection Access

Plugins should not receive live sessions or connections by default.

Exceptions may include explicitly configured providers or callbacks.

Access modes:

```text
none
read_only_metadata
same_transaction
separate_transaction
application_owned
```

The mode must be declared and validated.

---

# Plugin Failure Boundaries

Plugin failures should map to category-specific errors.

Examples:

```text
AdapterPluginError
SourceResolverPluginError
RejectionPolicyError
CallbackError
QuarantineError
DiagnosticExporterError
ResultExporterError
```

Original exceptions remain available as causes.

---

# Plugin Failure Policies

Not every plugin failure should have the same effect.

Examples:

## Adapter failure

Usually fatal or row rejection, depending on error type.

## Rejection policy failure

Usually fatal because a rejected row may be lost.

## Quarantine failure

Raise by default; optional retry or collect fallback.

## Diagnostic exporter failure

Configurable; may disable exporter or raise.

## Result exporter failure

Occurs after query completion and should not change the underlying result.

Policies must be explicit per category.

---

# Validation Guarantees

Plugins must not bypass validation silently.

A plugin that wants to produce accepted models directly would need a separate,
explicitly unsafe extension category.

The core plugin API should require that all accepted rows pass the configured
validator.

No general "mark accepted" hook should exist.

---

# Unsafe Plugins

If RowGuard ever supports unsafe plugins, they must be clearly labeled.

Potential configuration:

```python
allow_unsafe_plugins=False
```

Unsafe capabilities might include:

- Skipping validation.
- Rewriting SQL text.
- Mutating accepted models.
- Accessing raw sessions.
- Running arbitrary repair before first validation.

The MVP should not support unsafe plugin categories.

---

# Determinism

Plugins should be deterministic for a fixed input and context where practical.

Plugins should document any dependence on:

- Current time.
- Randomness.
- Network services.
- Mutable external state.
- Environment variables.
- Global configuration.

Non-deterministic behavior should be visible in diagnostics.

---

# Side Effects

Plugins with side effects must declare them.

Examples:

- Writes files.
- Sends network requests.
- Updates metrics.
- Writes database records.
- Publishes messages.

Side effects should occur only at documented lifecycle points.

---

# Ordering

Plugins invoked per row should preserve database row order by default.

Concurrent plugin execution should be opt-in.

Composition order should follow explicit registration or configuration order.

---

# Plugin Composition

Some plugin categories may support composition.

Examples:

```python
CompositeDiagnosticExporter([...])
CompositeRejectionPolicy([...])
CompositeExecutionObserver([...])
```

Composition must define:

- Order.
- Failure behavior.
- Decision precedence.
- Cleanup order.
- Async behavior.
- Retention conflicts.

The MVP should keep composition limited and explicit.

---

# Security Review

Plugins execute trusted Python code in the application process.

RowGuard does not sandbox plugins.

Applications should review:

- Package source.
- Dependency chain.
- Network destinations.
- Credential access.
- Filesystem access.
- Data retention.
- Logging behavior.
- Session access.
- Serialization behavior.

Only trusted plugins should be installed and registered.

---

# Privacy Contract

Plugins receiving row or rejection data must respect RowGuard's redaction and
retention policies.

The core should apply public redaction before data reaches external exporters or
providers unless a plugin explicitly requires full values and the application
opts in.

Capabilities may declare:

```python
requires_full_values=True
```

Planning should reject such a plugin under metadata-only policy.

---

# Plugin Diagnostics

RowGuard should emit structured diagnostics for plugins.

Suggested codes:

```text
plugin.registered
plugin.selected
plugin.compatibility_checked
plugin.opened
plugin.closed
plugin.failed
plugin.capability_mismatch
plugin.api_version_mismatch
```

Metadata may include:

- Plugin name.
- Version.
- API version.
- Category.
- Capability summary.

---

# Plugin Inventory

A configured client may expose:

```python
guard.plugins()
```

or:

```python
guard.describe_plugins()
```

This is useful for:

- Debugging.
- Security inventory.
- Reproducibility.
- Support reports.
- Diagnostics.

Inventory should not expose secrets from plugin configuration.

---

# Compatibility Checks

Before execution, RowGuard should verify:

- Plugin API version.
- Sync/async compatibility.
- Streaming compatibility.
- Transaction capability.
- Batch capability.
- Redaction compatibility.
- Source compatibility.
- Result-shape compatibility.

Failures should happen during planning, not after many rows have been processed.

---

# Thread Safety

Plugins must declare thread safety.

RowGuard should not share non-thread-safe plugin instances across concurrent sync
executions unless protected or cloned.

Registries may store factories instead of singleton instances when plugins are
stateful.

---

# Async Safety

Async plugins must declare task safety.

One provider instance may or may not support concurrent executions.

The client should either:

- Create one instance per execution.
- Serialize access.
- Reject unsafe sharing.
- Require application-owned lifecycle.

---

# Performance

Plugin abstraction should add minimal overhead.

Guidelines:

- Resolve plugins during planning.
- Prebind hot-path methods.
- Avoid repeated metadata checks.
- Avoid registry lookup per row.
- Use no-op implementations for disabled features.
- Keep context objects small.
- Measure external plugin time separately.

---

# Plugin Benchmarking

Plugin authors should benchmark:

- Per-row overhead.
- Batch throughput.
- Serialization cost.
- Memory retention.
- Open/close cost.
- Sync vs async behavior.
- Failure-path cost.

RowGuard may provide a conformance benchmark suite.

---

# Conformance Test Suite

RowGuard should provide reusable plugin tests.

Example:

```python
from rowguard.testing import adapter_conformance

adapter_conformance(MyAdapter())
```

Potential suites:

- Row adapter conformance.
- Rejection policy conformance.
- Quarantine provider conformance.
- Diagnostic exporter conformance.
- Source resolver conformance.

Conformance tests should verify both behavior and invariants.

---

# Adapter Conformance Requirements

Adapters should be tested for:

- Deterministic mappings.
- No mutation of input.
- Duplicate-key behavior.
- Null preservation.
- Source identity.
- Streaming compatibility.
- Redaction compatibility.
- Declared I/O behavior.

---

# Rejection Policy Conformance Requirements

Policies should be tested for:

- Correct decision.
- Statistics behavior.
- Retention behavior.
- Error propagation.
- Ordering.
- Sync/async capability.
- Immutability.
- No accepted-row mutation.

---

# Quarantine Provider Conformance Requirements

Providers should be tested for:

- Record schema.
- Receipt semantics.
- Error propagation.
- Resource cleanup.
- Redaction.
- Serialization.
- Batch behavior.
- Async behavior.
- Delivery guarantee documentation.

---

# Diagnostic Exporter Conformance Requirements

Exporters should be tested for:

- Stable event handling.
- No execution-state mutation.
- Privacy compliance.
- Close behavior.
- Failure policy.
- Batching.
- Thread/task safety.

---

# Public Plugin Package Naming

Recommended naming:

```text
rowguard-postgresql
rowguard-s3
rowguard-kafka
rowguard-opentelemetry
rowguard-polars
```

Third-party packages should avoid implying official ownership unless maintained
by the RowGuard project.

---

# Official vs Community Plugins

Documentation should distinguish:

- Core built-ins.
- Official optional plugins.
- Community plugins.

Official plugins may receive:

- Compatibility testing.
- Coordinated release policy.
- Security review.
- Documentation integration.

Community plugins remain independently maintained.

---

# Built-in Plugins

Likely built-ins:

## Adapters

- SQLAlchemy row mapping adapter.
- ORM scalar attribute adapter.
- Explicit field-map adapter.
- Scalar wrapper adapter.
- Basic nested adapter.

## Policies

- Raise.
- Collect.
- Skip.
- Callback.
- Quarantine.

## Providers

- In-memory quarantine provider.
- JSONL quarantine provider.

## Diagnostics

- In-memory collector.
- Structured logging exporter.
- No-op exporter.

Core built-ins should not require heavy optional dependencies.

---

# Plugin Configuration Serialization

Applications may want configuration files.

Named plugin configuration might look like:

```yaml
quarantine:
  provider: jsonl
  options:
    path: quarantine/users.jsonl
    flush_every: 100
```

RowGuard may offer configuration loading later.

The plugin system itself should not require YAML, TOML, or environment parsing.

---

# Reproducibility

A query result or diagnostic summary should be able to record:

- Plugin names.
- Plugin versions.
- Plugin API versions.
- Relevant non-secret configuration.
- RowGuard version.
- SQLRules version.

This helps reproduce data-quality behavior.

---

# Dependency Isolation

Optional plugins should minimize dependency conflicts.

Strategies:

- Separate packages.
- Version ranges.
- Lazy imports.
- Extras.
- Small provider-specific modules.
- No import-time network or database access.

---

# Deprecation

Public plugin protocols should follow a documented deprecation process.

Recommended:

1. Announce deprecation.
2. Emit structured warning.
3. Provide migration guide.
4. Maintain for at least one minor release when feasible.
5. Remove only in a major plugin API version.

---

# Error Hierarchy

Suggested plugin errors:

```text
RowGuardError
└── PluginError
    ├── PluginRegistrationError
    ├── PluginConflictError
    ├── PluginNotFoundError
    ├── PluginAPIVersionError
    ├── PluginCapabilityError
    ├── PluginConfigurationError
    ├── PluginLifecycleError
    └── PluginExecutionError
```

Category-specific errors may inherit from both `PluginError` and their subsystem
base where appropriate.

---

# Testing Requirements

Core plugin-system tests should cover:

- Explicit registration.
- Duplicate registration.
- Replacement.
- Missing plugin.
- API version mismatch.
- Capability mismatch.
- Sync/async compatibility.
- Streaming compatibility.
- Lifecycle open/close.
- Application-owned lifecycle.
- Plugin failure wrapping.
- Deterministic selection.
- Resolver ambiguity.
- Privacy policy compatibility.
- Thread/task safety declarations.
- Registry immutability.
- Named vs instance selection.
- Entry-point discovery when added.
- Plugin inventory.
- Diagnostic emission.
- Optional dependency errors.
- Conformance suites.

---

# MVP Scope

The first plugin system should support:

- Separate registries by category.
- Explicit registration.
- Plugin metadata.
- Plugin API version `1`.
- Capability declarations.
- Row adapter plugins.
- Source resolver plugins.
- Rejection policy plugins.
- Callback plugins.
- Quarantine provider plugins.
- Diagnostic exporter plugins.
- Immutable registry configuration.
- Duplicate-name errors.
- Planning-time compatibility validation.
- Category-specific plugin errors.
- In-memory conformance helpers.
- No automatic third-party discovery.

Near-term additions:

- Result exporters.
- Async provider protocols.
- Batch provider capabilities.
- Optional entry-point discovery.
- Plugin inventory reports.
- More complete conformance suites.
- Official cloud and observability plugins.

Deferred:

- Unsafe plugins.
- Dynamic code download.
- Remote plugin execution.
- General workflow hooks.
- Mutable global registry.
- Arbitrary execution-state access.
- Automatic dependency installation.
- Complex plugin dependency solver.
- Hot reloading.
- Plugin sandboxing.

---

# Recommended Usage Examples

## Custom Adapter

```python
guard = RowGuard(
    adapter_registry=AdapterRegistry().with_plugin(
        "legacy-row",
        LegacyRowAdapterFactory(),
    ),
)

result = guard.execute(
    session=session,
    statement=stmt,
    model=UserRead,
    row_adapter="legacy-row",
)
```

## Custom Rejection Policy

```python
guard = RowGuard(
    rejection_policy_registry=RejectionPolicyRegistry().with_plugin(
        "route-by-error",
        RouteByErrorPolicyFactory(),
    ),
)
```

## Quarantine Provider

```python
provider = S3QuarantineProvider(
    bucket="data-quality",
    prefix="users/",
)

result = guard.select(
    session=session,
    table=users,
    model=UserRead,
    rejection_policy=QuarantinePolicy(provider),
)
```

## Diagnostic Exporter

```python
guard = RowGuard(
    diagnostic_exporters=[
        StructuredLoggingExporter(logger),
        OpenTelemetryExporter(tracer),
    ],
)
```

---

# Design Principles

- Use narrow protocols, not a generic hook bag.
- Register plugins explicitly.
- Resolve plugins during planning.
- Keep mutable execution state private.
- Preserve Pydantic validation guarantees.
- Keep SQLRules as the only constraint compiler.
- Declare capabilities and compatibility.
- Make lifecycle and side effects explicit.
- Fail early on incompatible configuration.
- Treat plugins as trusted code.
- Keep optional dependencies outside core.
- Provide conformance tests for plugin authors.
