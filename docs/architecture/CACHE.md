# CACHE.md

:::{admonition} Design notes — plan cache is opt-in / internal
:class: caution

Public entrypoints do not enable a process-wide plan cache by default. This
document is a maintainer design note. Plugin / quarantine cache sketches are
**not shipped** in 0.5.0.
:::

# RowGuard Cache Architecture

## Purpose

This document defines what RowGuard may cache, how cache keys are constructed,
how invalidation works, and which objects must never be cached.

Caching exists to reduce repeated planning and metadata work. It must not alter
validation semantics, transaction behavior, or rejection outcomes.

The central rule is:

> Cache immutable planning artifacts, never mutable execution state.

---

# Goals

The cache architecture should:

- Reduce repeated Pydantic model inspection.
- Reduce repeated SQLRules compilation.
- Reduce repeated SQLAlchemy mapper inspection.
- Reuse row-adapter plans.
- Reuse compatible execution-plan fragments.
- Remain optional.
- Be bounded.
- Be thread-safe for concurrent reads.
- Preserve deterministic behavior.
- Expose hit/miss diagnostics.
- Avoid retaining sessions, rows, models, or sensitive data.

---

# Non-Goals

RowGuard caching does not:

- Cache query results.
- Cache database rows.
- Cache accepted Pydantic models.
- Cache rejected rows.
- Cache live SQLAlchemy `Result` objects.
- Cache sessions, connections, or transactions.
- Replace SQLAlchemy statement caching.
- Replace application-level data caching.
- Persist secrets.
- Hide model or schema changes.

---

# Cache Layers

Recommended cache layers:

```text
Model Metadata Cache
SQLRules Compilation Cache
Source Metadata Cache
Adapter Plan Cache
Validation Plan Cache
Execution Plan Cache
```

Each layer should have a separate key and lifetime.

Avoid one opaque global cache.

---

# Model Metadata Cache

Caches normalized Pydantic model information.

Possible contents:

- Field names.
- Validation aliases.
- Required/default status.
- Type annotations.
- Constraint metadata.
- Model configuration summary.
- Presence of model validators.
- Projection planning metadata.

Suggested key:

```python
ModelCacheKey(
    model=UserRead,
    pydantic_version=...,
)
```

The model class identity is normally sufficient within one process, but version
metadata improves diagnostics and persistent-cache safety.

---

# SQLRules Compilation Cache

Caches model-dependent SQLRules compilation artifacts when compatible with a
specific SQLAlchemy source.

Possible contents:

- Field-level rule groups.
- Flattened expressions.
- SQLRules diagnostics.
- Translator/plugin metadata.
- Pushdown safety classifications.

Suggested key inputs:

- Pydantic model identity.
- SQLAlchemy source identity.
- Column mapping.
- SQLRules compiler options.
- SQLRules version.
- SQLRules plugin API version.
- Active translator registry fingerprint.
- Dialect policy when relevant.

Do not cache bound parameter values as literals.

---

# Source Metadata Cache

Caches structural information about SQLAlchemy sources.

Possible contents:

- Source kind.
- Column keys.
- ORM mapper metadata.
- Primary-key extraction plan.
- Alias identity.
- Relationship exclusions.
- Unloaded-attribute policy compatibility.

Suggested sources:

- `Table`
- Alias
- Subquery
- CTE
- ORM mapped class
- SQLModel table class

The cache stores metadata, not live sessions or database state.

---

# Adapter Plan Cache

Caches precomputed instructions for converting rows into Pydantic validation
inputs.

Possible contents:

- Result-key to model-field mapping.
- Alias mapping.
- Duplicate-key policy.
- Nested mapping plan.
- ORM scalar attribute extraction plan.
- Source identity extraction plan.
- Raw-row retention policy.

Suggested key inputs:

- Model identity.
- Statement/result shape fingerprint.
- Source metadata fingerprint.
- Explicit field map.
- Adapter plugin name and version.
- Adapter configuration.
- Validation input mode.
- Retention configuration.

---

# Validation Plan Cache

Caches immutable validator configuration.

Possible contents:

- Target model.
- Bound validation method.
- Strict override.
- `from_attributes` setting.
- Error retention/redaction policy metadata.
- Static validation configuration.

Do not cache:

- Validation results.
- Mutable validation context.
- Context-dependent accepted/rejected outcomes.

If validation context changes semantics, it must remain an execution input.

---

# Execution Plan Cache

Caches complete immutable execution plans only when all semantic planning inputs
are stable.

Potential contents:

- Final SQLAlchemy statement shape.
- Pushdown plan.
- Adapter plan.
- Validation plan.
- Rejection-policy factory/configuration.
- Diagnostics plan.
- Static metadata.

Potentially excluded runtime fields:

- Execution ID.
- Session/connection.
- Bound parameter values.
- Mutable callback state.
- Provider handles.
- Runtime statistics.
- Stream resources.

A cached template may be safer than caching the exact runtime `ExecutionPlan`.

---

# Plan Template vs Execution Plan

Recommended distinction:

```python
@dataclass(frozen=True, slots=True)
class ExecutionPlanTemplate:
    statement: object
    pushdown_plan: PushdownPlan
    adapter_plan: AdapterPlan
    validation_plan: ValidationPlan
    rejection_config: RejectionConfig
    diagnostics_plan: DiagnosticsPlan
```

At runtime:

```python
plan = template.bind(
    execution_id=...,
    parameters=...,
    runtime_plugins=...,
)
```

This avoids caching per-run identity and mutable resources.

---

# Cache Key Design

Cache keys must include every input that can affect semantics.

A correct key is more important than a high hit rate.

Potential key categories:

- Model identity.
- Source identity.
- Statement shape.
- Mapping configuration.
- Pushdown mode.
- SQLRules configuration.
- Plugin versions.
- Validation mode.
- Strictness.
- Partial/full validation scope.
- Rejection-policy type.
- Dialect profile.
- Row-adapter type.
- Result projection.

Missing any semantic input can return an invalid plan.

---

# Statement Shape Fingerprints

SQLAlchemy statements may differ by:

- Selected columns.
- Labels.
- Joins.
- WHERE structure.
- ORDER BY.
- LIMIT/OFFSET.
- CTEs.
- Aliases.
- Execution options.

RowGuard should avoid inventing a brittle SQL parser for cache keys.

Potential approaches:

1. Use object identity for short-lived in-process caches.
2. Use SQLAlchemy-generated cache keys when publicly available and appropriate.
3. Cache only plans built from simpler RowGuard source requests.
4. Require explicit user-supplied cache keys for advanced statements.

The MVP should prefer conservative in-process caching over complex persistent
fingerprints.

---

# Source Identity

Source identity should distinguish:

- Base table vs alias.
- ORM class vs aliased class.
- Subquery instances.
- Reflected table objects from different metadata collections.
- Same table under different schemas.

Object identity may be sufficient for local process caches.

Persistent caches require stable structural identifiers and are deferred.

---

# Mapping Fingerprints

Mappings must be normalized before key generation.

Example:

```python
{
    "id": users.c.user_id,
    "name": users.c.display_name,
}
```

Normalize ordering by model field name.

Do not depend on insertion order accidentally.

---

# Plugin Fingerprints

Cached plans depend on plugin behavior.

A plugin fingerprint may include:

- Plugin name.
- Plugin version.
- Plugin API version.
- Relevant capability flags.
- Non-secret configuration fingerprint.

Do not include credentials or full sensitive configuration.

Stateful plugin instances should usually not be cached directly.

Cache their factory/configuration plan instead.

---

# Dialect Sensitivity

Some planning artifacts are dialect-neutral.

Examples:

- Pydantic model metadata.
- Basic adapter mappings.

Others may be dialect-sensitive.

Examples:

- SQLRules translated expressions.
- Pushdown safety.
- Streaming capability.
- Driver-specific adapter selection.

Keys must include the relevant dialect profile where semantics differ.

---

# Validation Context

Validation context may change outcomes.

Therefore:

- Do not cache validation results.
- Do not place mutable context inside reusable plans.
- Bind context at execution time.
- Include static context identifiers only when needed for diagnostics.
- If a validator plan structurally depends on context shape, include that shape
  in the key.

---

# Rejection Policy Caching

Stateless policies may be cached safely.

Examples:

- Raise.
- Skip.
- Collect configuration template.

Stateful policies require per-execution instances.

Examples:

- Callback with mutable buffer.
- Quarantine provider with open connection.
- Batch writer.
- Sampling policy with counters.

Cache policy factories/configuration, not active state.

---

# Quarantine Provider Caching

Application-owned providers may be reused intentionally.

RowGuard-owned providers should follow explicit lifecycle rules.

Do not place live provider connections inside a generic plan cache.

Potential template:

```python
QuarantineProviderFactory
```

creates a runtime provider per execution or client lifecycle.

---

# Diagnostics Exporter Caching

Stateless exporters may be shared.

Stateful exporters must declare thread/task safety and lifecycle.

Cache configuration and factory references rather than hidden mutable buffers.

---

# Cache Scope

Potential scopes:

## Per-call

No effective reuse; useful for testing no-cache behavior.

## Per-client

Recommended default.

Each `RowGuard` client owns bounded caches.

## Process-wide

Possible for immutable model metadata only.

Global process caches increase coupling and should be used sparingly.

## Persistent

Deferred.

Requires stable serialization, versioning, invalidation, and security design.

---

# Recommended Default Scope

Use per-client caches.

Benefits:

- Isolation.
- Predictable lifetime.
- Easy testing.
- No cross-application contamination.
- Explicit configuration.
- Easy cleanup.

Top-level functions may use a default singleton client, but advanced
applications should be able to construct isolated clients.

---

# Cache Interface

Suggested protocol:

```python
class Cache(Protocol[K, V]):
    def get(self, key: K) -> V | None:
        ...

    def set(self, key: K, value: V) -> None:
        ...

    def delete(self, key: K) -> None:
        ...

    def clear(self) -> None:
        ...
```

Optional methods:

```python
stats()
contains()
get_or_create()
```

The core should not depend on one cache implementation.

---

# Bounded LRU Cache

A bounded in-memory LRU cache is a good default for planning artifacts.

Configuration:

```python
CacheConfig(
    max_entries=1024,
)
```

Benefits:

- Prevents unbounded model/source retention.
- Simple eviction.
- Good fit for repeated application query patterns.
- No serialization.

---

# Weak References

Weak-reference caches may help avoid retaining dynamically created model or
source objects.

Potential uses:

- Model metadata keyed by class.
- ORM mapper metadata keyed by mapped class.
- Table metadata keyed by table object.

Weak references are not suitable for every key/value type and can complicate
behavior.

They should be used only where measured benefits justify them.

---

# Time-Based Expiration

TTL expiration may be useful for:

- Dynamically generated models.
- Plugin configurations.
- Reflected schema metadata.
- Long-running development processes.

However, immutable in-process planning artifacts do not inherently expire with
time.

LRU bounds are more important than TTL for the MVP.

---

# Schema Changes

Cached plans may become stale when the database schema changes.

RowGuard cannot automatically detect every migration.

Recommended guidance:

- Recreate or clear client caches after schema migrations.
- Restart application processes after production migrations.
- Include explicit schema version in cache configuration where available.
- Avoid persistent cache reuse across deployments without versioning.

Potential key metadata:

```python
schema_version="alembic-revision-id"
```

---

# Model Changes

In a running process, Python model classes generally do not change.

Development hot reload can replace classes.

Object-identity-based keys naturally treat reloaded classes as new keys.

Persistent caches would require source/version fingerprints and are deferred.

---

# Plugin Changes

Plugin upgrades can change behavior.

Cache keys should include plugin version metadata.

Application deployments should clear in-memory caches naturally through process
restart.

Hot-swapping plugin implementations in one client should invalidate dependent
caches.

---

# SQLRules Changes

SQLRules version and plugin registry fingerprint must be part of SQLRules cache
keys.

RowGuard should not reuse compiled rules across incompatible SQLRules versions.

---

# Pydantic Changes

Pydantic version changes may affect:

- Model metadata.
- Alias behavior.
- Validation semantics.
- Error structure.

In-process caches are naturally rebuilt after deployment.

Persistent caches must include Pydantic version and are not part of the MVP.

---

# SQLAlchemy Changes

SQLAlchemy version changes may affect:

- Statement cache keys.
- Mapper metadata.
- Result shape.
- Dialect behavior.

Cache compatibility should be scoped to one process and installed version.

Do not serialize SQLAlchemy objects for persistent cache reuse in the MVP.

---

# Cache Invalidation API

Suggested client API:

```python
guard.clear_caches()
```

More targeted methods:

```python
guard.clear_model_cache()
guard.clear_plan_cache()
guard.invalidate_model(UserRead)
guard.invalidate_source(users)
```

Targeted invalidation is useful for tests and dynamic systems.

---

# Automatic Invalidation

Automatic invalidation may occur when:

- A client registry is replaced.
- Plugin configuration changes.
- Dialect profile changes.
- Default validation configuration changes.
- Cache namespace version changes.

Immutable client configuration can avoid many invalidation problems by creating
a new client instead.

---

# Cache Namespaces

Use versioned namespaces for internal cache entries.

Example:

```text
rowguard:model-metadata:v1
rowguard:sqlrules-plan:v1
rowguard:adapter-plan:v1
rowguard:execution-template:v1
```

Namespace versions can invalidate entire artifact families after internal format
changes.

---

# Thread Safety

Per-client caches may be accessed by concurrent executions.

Requirements:

- Thread-safe reads and writes.
- Atomic get-or-create where practical.
- No partial value publication.
- No mutable cached values.
- Bounded lock contention.

A simple lock around a small LRU may be sufficient initially.

---

# Async Safety

Async tasks may share a client cache.

Cache operations should remain synchronous and fast.

Avoid awaiting ordinary in-memory cache access.

If persistent async caches are introduced later, isolate them behind a separate
interface.

---

# Cache Stampede

Multiple concurrent requests may compute the same plan.

Potential approaches:

- Accept duplicate computation for simplicity.
- Per-key locks.
- Atomic `get_or_create`.
- Future memoization layer.

Planning should be cheap enough that duplicate work is tolerable initially.

Avoid complex locking before measurement.

---

# Negative Caching

RowGuard may cache some planning failures.

Examples:

- Unsupported adapter/source combination.
- Missing plugin.
- Invalid static mapping.

Risks:

- Configuration may change.
- Error objects may retain sensitive context.
- Dynamic registries may be updated.

Negative caching should not be part of the MVP.

---

# Sensitive Data

Cache keys and values must not retain:

- Bound parameter values.
- Authentication tokens.
- Raw rows.
- Validation context secrets.
- Rejected data.
- Quarantine payloads.
- Full rendered SQL with literals.

Planning caches should contain structure and configuration only.

---

# Query Results Must Never Be Cached

RowGuard is not a result cache.

Reasons:

- Database state changes.
- Transaction visibility.
- Authorization context.
- Validation context.
- Rejection policy side effects.
- Streaming semantics.
- Memory and privacy risks.

Applications wanting result caching should use a separate explicit layer after
RowGuard returns validated models.

---

# Accepted Model Caching

Accepted Pydantic models must not be stored in internal planning caches.

Potential external application caching is allowed but outside RowGuard's core
responsibility.

---

# Rejection Caching

Rejected rows must not be cached in planning caches.

Quarantine is durable storage, not cache.

In-memory `collect` retention belongs to one execution result.

---

# SQLAlchemy Session Safety

Never cache:

- Session.
- AsyncSession.
- Connection.
- AsyncConnection.
- Transaction.
- Result.
- ScalarResult.
- ORM entity instance.

These objects have lifecycle and concurrency constraints.

---

# Cache Diagnostics

Suggested diagnostics:

```text
cache.hit
cache.miss
cache.set
cache.evicted
cache.invalidated
cache.cleared
cache.error
```

Metadata:

- Cache layer.
- Key category.
- Artifact type.
- Eviction reason.
- Size after operation.

Do not emit full keys if they include object representations or sensitive
configuration.

---

# Cache Statistics

Suggested metrics:

- Hits.
- Misses.
- Hit rate.
- Sets.
- Evictions.
- Current entries.
- Maximum entries.
- Build time saved estimate.
- Get latency.
- Set latency.

Track statistics per cache layer.

---

# Cache Failures

An in-memory cache failure should not normally make query execution impossible.

Potential policy:

```python
on_cache_error="bypass"
on_cache_error="raise"
```

Recommended default:

```python
bypass
```

The planner recomputes the artifact and emits a diagnostic.

Persistent cache failures, if added later, may have separate policies.

---

# Determinism

Cached and uncached planning must produce semantically equivalent execution
plans.

Tests should compare:

- Final statement structure.
- Pushdown expressions.
- Adapter behavior.
- Validation behavior.
- Rejection behavior.
- Diagnostics, allowing cache-specific events.
- Result statistics.

Cache use must not change row acceptance.

---

# Performance Tradeoffs

Caching has costs:

- Memory.
- Locking.
- Key construction.
- Invalidation complexity.
- Retaining model/source objects.
- Debugging complexity.

Small applications may disable caches.

Potential configuration:

```python
CacheConfig(enabled=False)
```

---

# Development Mode

Development and hot-reload environments may prefer:

```python
CacheConfig(
    enabled=True,
    max_entries=128,
    clear_on_reload=True,
)
```

RowGuard itself cannot universally detect code reloads.

Framework integrations may clear client caches explicitly.

---

# Testing Mode

Tests may need deterministic cache control.

Utilities:

```python
guard.clear_caches()
guard.cache_stats()
with guard.caches_disabled():
    ...
```

Tests should avoid hidden cross-test cache contamination.

---

# Persistent Caching

Persistent caches are deferred.

Challenges include:

- Serializing SQLAlchemy expressions.
- Version compatibility.
- Plugin compatibility.
- Schema invalidation.
- Security.
- Cross-process locking.
- Database migration coordination.
- Pydantic and SQLRules upgrades.

A future persistent cache may store only serialized intermediate metadata rather
than complete execution plans.

---

# Distributed Caching

Distributed caches such as Redis are not an MVP feature.

Planning artifacts are generally process-local and cheap relative to database
queries.

Distributed caching would add:

- Serialization.
- Network latency.
- Security concerns.
- Invalidation complexity.
- Cross-version compatibility.

It should be justified by measured workloads.

---

# Cache Plugin Interface

A custom cache backend may implement the public cache protocol.

Potential use cases:

- Instrumented cache.
- Shared local cache.
- Framework-integrated cache.
- Persistent metadata cache.

Custom backends must document:

- Thread safety.
- Async safety.
- Serialization.
- Eviction.
- Security.
- Failure behavior.

---

# Default Cache Configuration

Suggested defaults:

```python
RowGuardCacheConfig(
    model_metadata_entries=512,
    source_metadata_entries=512,
    sqlrules_entries=1024,
    adapter_plan_entries=1024,
    execution_template_entries=512,
)
```

Exact defaults should be based on benchmarks and real usage.

Users should be able to disable each layer independently.

---

# Cache Key Example

Conceptual key:

```python
ExecutionTemplateKey(
    model_id=id(UserRead),
    source_id=id(users),
    statement_key=statement_cache_key,
    pushdown_mode="safe",
    sqlrules_version="0.1",
    adapter_name="sqlalchemy-row",
    adapter_version="1",
    validation_mode="full",
    strict=None,
    rejection_policy="collect",
    dialect_name="postgresql",
)
```

Implementation should prefer stable typed key objects over concatenated strings.

---

# Object Identity vs Structural Identity

## Object identity

Advantages:

- Simple.
- Fast.
- Safe within one process.
- Naturally invalidates reloaded objects.

Disadvantages:

- Lower hit rate for structurally equivalent reconstructed objects.
- Not persistent.

## Structural identity

Advantages:

- Higher reuse.
- Potential persistence.

Disadvantages:

- Harder to compute correctly.
- More fragile across versions.
- More expensive.
- Greater collision risk.

The MVP should favor object identity and SQLAlchemy-provided cache keys where
appropriate.

---

# Execution ID

Execution IDs are runtime values and must not be part of reusable cache keys.

A cached plan template receives a new execution ID during binding.

---

# Bound Parameters

Bound parameter names and statement structure may affect plan identity.

Bound parameter values usually should not.

Example:

```python
tenant_id=1
tenant_id=2
```

should reuse the same structural plan when all other semantics match.

Validation context values are separate and may affect only runtime validation.

---

# Partial Validation

Cache keys must include validation scope.

Examples:

- Full model.
- Projection model.
- Dynamic field subset.

Two different partial field sets must not share the same validation or adapter
plan.

---

# Strictness

Cache keys must include:

- Explicit strict override.
- Attribute-vs-mapping mode.
- Relevant model configuration fingerprint when not captured by model identity.

Strict and non-strict plans are not interchangeable.

---

# Redaction and Retention

Adapter and rejection-plan keys may need to include:

- Raw-row retention.
- Adapted-row retention.
- Error-value policy.
- Redacted field set.
- Quarantine value mode.

These options affect runtime object construction.

---

# Streaming

Buffered and streaming plan templates may share:

- Source metadata.
- SQLRules compilation.
- Adapter plan.
- Validation plan.

They differ in:

- Execution strategy.
- Resource lifecycle.
- Rejection retention defaults.
- Result assembly.

Cache layers should maximize safe reuse without conflating modes.

---

# Sync and Async

Sync and async planning artifacts may share:

- Model metadata.
- SQLRules compilation.
- Adapter plans.
- Validation plans.

Execution templates must account for:

- Sync vs async provider compatibility.
- Callback type.
- Execution resource type.
- Streaming capabilities.

---

# Result Shape Changes

A statement whose selected labels change must generate a new adapter plan.

Applications dynamically constructing statements should expect lower plan-cache
hit rates.

Explicit stable projections improve both clarity and caching.

---

# Cache Conformance Tests

A custom cache backend should pass tests for:

- Set/get.
- Eviction.
- Clear.
- Invalidation.
- Thread safety.
- Immutable value handling.
- Error policy.
- Statistics.
- Bounded memory behavior.
- No sensitive key logging.

---

# Testing Requirements

Core cache tests should cover:

- Model metadata hits and misses.
- SQLRules compilation reuse.
- Adapter-plan reuse.
- Execution-template reuse.
- Different model classes.
- Reloaded model classes.
- Different aliases.
- Different field maps.
- Different dialects.
- Different plugins.
- Different strictness.
- Different validation scopes.
- Different rejection policies.
- Bound parameter value reuse.
- Session exclusion.
- Clear and targeted invalidation.
- LRU eviction.
- Cache disabled mode.
- Cache error bypass.
- Threaded access.
- Async task access.
- Cached/uncached semantic equivalence.
- No result/rejection retention.
- Plugin replacement invalidation.
- Schema-version keying.

---

# MVP Scope

The first cache implementation should include:

- Per-client bounded in-memory caches.
- Model metadata cache.
- Source metadata cache.
- SQLRules compilation cache.
- Adapter plan cache.
- Execution plan template cache for simple stable requests.
- Object-identity-based keys.
- SQLAlchemy cache-key use where safe and documented.
- Immutable cached values.
- Cache hit/miss diagnostics.
- Cache statistics.
- Clear-all API.
- Targeted model/source invalidation.
- Cache-disabled mode.
- Bypass-on-cache-error default.
- No persistent or distributed caching.

Near-term additions:

- Weak-reference metadata caches.
- More complete execution-template caching.
- Plugin fingerprint utilities.
- Schema-version namespaces.
- Per-key get-or-create locking.
- Framework reload hooks.
- Custom cache backend protocol stabilization.

Deferred:

- Persistent cache.
- Redis/distributed cache.
- Cross-process execution-plan serialization.
- Query-result caching.
- Rejection caching.
- Automatic schema migration detection.
- Cost-based cache admission.
- Negative caching.
- Durable cache warming.

---

# Recommended API Examples

## Default Per-Client Cache

```python
guard = RowGuard()
```

## Disable Caching

```python
guard = RowGuard(
    cache=RowGuardCacheConfig(enabled=False),
)
```

## Bounded Configuration

```python
guard = RowGuard(
    cache=RowGuardCacheConfig(
        model_metadata_entries=256,
        sqlrules_entries=512,
        adapter_plan_entries=512,
        execution_template_entries=256,
    ),
)
```

## Clear After Migration

```python
guard.clear_caches()
```

## Inspect Statistics

```python
stats = guard.cache_stats()
```

## Targeted Invalidation

```python
guard.invalidate_model(UserRead)
guard.invalidate_source(users)
```

---

# Design Principles

- Cache immutable plans, not data.
- Never cache sessions, connections, rows, models, or rejections.
- Correct keys matter more than hit rate.
- Per-client scope is the default.
- Bound parameter values stay runtime-bound.
- Plugin and dialect behavior participate in cache identity.
- Cached and uncached execution must be semantically equivalent.
- Caches are bounded and observable.
- Cache failures should usually fall back to recomputation.
- Persistent caching requires a separate future design.
