# PERFORMANCE.md

# RowGuard Performance Architecture

## Purpose

This document defines RowGuard's performance goals, cost model, optimization
strategy, benchmarking approach, and regression policy.

RowGuard adds validation and rejection handling to database reads. That extra
correctness has a cost, but the architecture should keep the overhead
predictable, measurable, and proportional to the number of processed rows.

The guiding principle is:

> Optimize orchestration around SQLAlchemy and Pydantic without weakening
> validation guarantees.

---

# Performance Priorities

RowGuard should optimize, in order:

1. Correctness.
2. Predictability.
3. Memory efficiency.
4. Throughput.
5. Latency.
6. Extensibility.

Micro-optimizations must not:

- Skip validation.
- Change rejection semantics.
- Hide errors.
- Reorder rows.
- Weaken diagnostics unexpectedly.
- Introduce implicit coercion.
- Break sync/async parity.

---

# Cost Model

A RowGuard query has several cost centers:

```text
Planning
  + SQLRules compilation
  + SQLAlchemy execution
  + Row fetching
  + Row adaptation
  + Pydantic validation
  + Rejection handling
  + Diagnostics
  + Result assembly
```

For a result set of `n` rows and `k` selected fields, the target complexity is:

- Planning: O(fields + constraints)
- Per-row adaptation: O(k)
- Per-row validation: determined by Pydantic model complexity
- Rejection handling: O(1) per rejection, excluding external sink cost
- Buffered memory: O(valid rows + retained rejections)
- Streaming memory: O(batch size + retained rejections)

---

# Primary Performance Goals

## Planning

- No database I/O during normal planning.
- Reuse model and mapper metadata.
- Avoid repeated SQLRules compilation.
- Produce immutable reusable execution plans.

## Execution

- Add minimal overhead around SQLAlchemy.
- Preserve bound parameters and statement caching.
- Avoid rendering SQL strings on the hot path.
- Avoid duplicate result materialization.

## Adaptation

- Prefer mapping views over copies.
- Precompute field maps.
- Avoid repeated alias resolution.
- Avoid ORM introspection per row.

## Validation

- Validate each row exactly once per attempt.
- Reuse validator configuration.
- Avoid pre-validation semantic conversion.
- Measure custom validator cost separately.

## Rejection Handling

- Keep `raise` and `skip` paths lightweight.
- Avoid retaining data unless configured.
- Batch quarantine writes when supported.
- Keep external callbacks off the critical path when applications explicitly
  hand off to their own queue.

---

# Two-Phase Architecture

RowGuard separates:

## Planning Phase

- Normalize inputs.
- Build or validate SQLAlchemy statement.
- Compile SQLRules filters.
- Resolve adapters.
- Configure validation.
- Configure rejection handling.
- Build immutable `ExecutionPlan`.

## Execution Phase

- Execute prepared statement.
- Process rows.
- Update per-run state.
- Produce result or stream.

This separation enables:

- Caching.
- Reuse.
- Lower per-row overhead.
- Easier profiling.
- Cleaner sync/async implementations.

---

# Planning Performance

Planning should be fast enough to run on demand, but repeated stable queries
should benefit from cached metadata.

Potential cached artifacts:

- Pydantic field inspection.
- Validation alias resolution.
- SQLRules compiled metadata.
- ORM mapper extraction plans.
- Row adapter plans.
- Source resolution.
- Static execution-plan fragments.

Do not cache:

- Sessions.
- Connections.
- Transactions.
- Mutable validation context.
- Accepted models.
- Rejected rows.
- Live SQLAlchemy results.

---

# Execution Plan Caching

An execution plan may be cacheable when all semantic inputs are stable.

Potential cache key components:

- Target model identity.
- Source identity.
- Statement shape.
- SQLRules options.
- Pushdown mappings.
- Adapter configuration.
- Validation mode.
- Rejection policy type.
- Dialect-relevant settings.

Parameter values should remain bound at execution time and should not normally
become part of the plan cache key.

Plans containing stateful callbacks or provider instances may be only partially
cacheable.

---

# SQLRules Pushdown

Filter pushdown can reduce:

- Rows scanned by the application.
- Network transfer.
- Row adaptation cost.
- Pydantic validation cost.
- Rejection volume.
- Quarantine traffic.

Pushdown is likely RowGuard's most important performance optimization.

However, it must remain conservative.

A pushed predicate that incorrectly removes a valid row is unacceptable.

---

# SQLAlchemy Statement Caching

RowGuard should preserve SQLAlchemy's normal statement caching behavior.

It should:

- Keep expressions parameterized.
- Avoid interpolating values.
- Avoid reconstructing semantically identical statements unnecessarily.
- Reuse immutable plans when practical.
- Avoid compiling statements to strings except for explicit diagnostics.

RowGuard should not implement a competing SQL statement cache.

---

# Column Projection

Selecting fewer columns reduces:

- Database I/O.
- Driver decoding.
- Network transfer.
- Row size.
- Adaptation work.
- Memory use.
- Validation input size.

Recommended pattern:

```python
stmt = select(
    User.id,
    User.name,
)
```

with a projection model:

```python
class UserSummary(BaseModel):
    id: int
    name: str
```

Projection models are both a performance and correctness feature.

---

# Full Entity vs Projection Performance

Full ORM entity queries can incur:

- Entity construction.
- Identity-map insertion.
- Mapper instrumentation.
- Deferred attribute checks.
- Relationship risks.
- Larger memory use.

Projected columns usually perform better for validation-first reads.

RowGuard should document three broad performance tiers:

1. SQLAlchemy Core mappings.
2. ORM projected columns.
3. Full ORM entity adaptation.

All remain supported, but projections should be recommended for high-volume
workloads.

---

# Row Adaptation Performance

The Row Adapter runs once per row.

Optimization guidelines:

- Precompute field-name mappings.
- Reuse immutable `AdapterPlan`.
- Use `Row._mapping` or mapping results when appropriate.
- Avoid converting mapping views to dictionaries unless renaming or nesting is
  required.
- Avoid repeated Pydantic field introspection.
- Avoid repeated SQLAlchemy mapper inspection.
- Avoid deep copies.
- Preserve values by reference when safe.

Target adaptation complexity:

```text
O(selected fields)
```

---

# Mapping Views vs Dictionaries

When the SQLAlchemy result already exposes the desired keys, RowGuard should
prefer a mapping view.

Copy only when required for:

- Key renaming.
- Nested structure construction.
- Redaction.
- Retention isolation.
- Mutation safety for an external plugin.

The validation engine should accept read-only mappings where Pydantic permits.

---

# Nested Adaptation

Nested models may require constructing dictionaries.

This increases allocation cost.

Recommendations:

- Precompute nesting instructions.
- Allocate only required nested dictionaries.
- Avoid recursive reflection.
- Prefer database-side JSON construction when appropriate and portable.
- Avoid building large nested graphs from ORM relationships automatically.

---

# Pydantic Validation Performance

Pydantic validation is a major per-row cost.

RowGuard should:

- Create validator objects during planning.
- Reuse the model's compiled validation machinery.
- Call validation exactly once.
- Avoid converting inputs before validation.
- Keep validation context stable.
- Avoid wrapping every success in expensive diagnostic objects.
- Preserve errors only on rejected rows.

RowGuard should not attempt to bypass Pydantic for "simple" rows, because that
would weaken the guarantee.

---

# Custom Validator Cost

Custom validators can dominate runtime.

Examples:

- Regex-heavy validation.
- Cryptographic checks.
- Network calls.
- Filesystem access.
- Database queries.
- Large nested transformations.

RowGuard should encourage pure, CPU-bounded validators.

Performance diagnostics may report:

- Total validation time.
- Average validation time.
- Maximum validation time.
- Slowest row samples, without sensitive values.

RowGuard cannot safely optimize arbitrary user validator code.

---

# Strict vs Non-Strict Validation

Strict mode may change validation cost.

The effect is model-dependent:

- It may avoid coercion.
- It may reject earlier.
- It may reduce conversion work.
- It may increase rejection handling.

Benchmarks should test both strict and default validation.

RowGuard should never select strictness solely for performance.

---

# Rejection Path Performance

The accepted-row path and rejected-row path have different costs.

Accepted path:

```text
adapt
  → validate
  → retain or yield model
```

Rejected path:

```text
adapt
  → validate
  → build rejection
  → redact
  → policy
  → diagnostics
  → optional callback/quarantine
```

Rejection-heavy workloads may be much slower than clean workloads.

Benchmarks must include both.

---

# Rejection Retention

Retaining rejected rows can consume substantial memory.

Potential options:

```python
retain_raw_rows=False
retain_adapted_rows=True
retain_validation_errors=True
```

For large workloads, prefer:

- `skip`
- callback
- quarantine with receipt retention
- sampled retention
- bounded collection

Unbounded `collect` should not be recommended for unknown-volume streams.

---

# Callback Performance

Callbacks execute on the rejection path.

Guidelines:

- Keep sync callbacks short.
- Use async callbacks for async I/O.
- Batch external writes when possible.
- Avoid per-row network notifications.
- Measure callback duration separately.
- Avoid blocking source database transactions.

RowGuard should not hide callback cost inside validation metrics.

---

# Quarantine Performance

Quarantine sinks may dominate rejected-row throughput.

Optimization options:

- Batch writes.
- Compress payloads.
- Use async I/O.
- Retain receipts instead of full rows.
- Redact before serialization.
- Avoid duplicate serialization.
- Use provider-managed buffering.

Delivery guarantees and performance tradeoffs must remain explicit.

---

# Buffered Execution

Buffered execution stores all accepted models.

Memory complexity:

```text
O(valid models + retained rejections + diagnostics)
```

Best for:

- Small result sets.
- API requests.
- Interactive workflows.
- Cases requiring a complete `QueryResult`.

Buffered execution should not be the default recommendation for unbounded data.

---

# Streaming Execution

Streaming should provide near-constant memory usage.

Memory complexity:

```text
O(fetch buffer + current row + retained rejection state)
```

Streaming should:

- Yield only validated models.
- Preserve order.
- Apply backpressure naturally.
- Release resources promptly.
- Flush callbacks and quarantine buffers on close.
- Avoid retaining accepted models.

Streaming is the preferred architecture for large workloads.

---

# Fetch Size and Batching

Potential configuration:

```python
fetch_size=1000
batch_size=500
```

These concepts are distinct:

- Fetch size controls database/driver row retrieval.
- Validation batch size controls application-side processing.
- Quarantine batch size controls sink writes.

The MVP may expose database streaming options and quarantine batching while
validating rows individually.

Batch validation should not be introduced unless it preserves exact per-row error
semantics.

---

# Backpressure

Streaming should not read rows significantly faster than the consumer can
process them unless explicitly configured.

Backpressure prevents:

- Unbounded memory growth.
- Large in-flight callback queues.
- Large quarantine buffers.
- Resource pressure.

The iterator/async iterator model naturally provides backpressure.

---

# Async Performance

Async improves concurrency for I/O-bound workloads.

It does not make Pydantic validation asynchronous.

Async design should:

- Await database I/O.
- Await async callbacks and providers.
- Run ordinary validation synchronously.
- Avoid thread-pool offload by default.
- Preserve row order.
- Avoid blocking the event loop with slow sync callbacks.

CPU-heavy validation may eventually support optional executor offload, but that
must be explicit and benchmarked.

---

# Parallel Validation

Parallel validation is not an MVP feature.

Potential future modes:

- Thread pool.
- Process pool.
- Partitioned streams.

Risks:

- Reordering.
- Increased serialization.
- Context propagation.
- Callback synchronization.
- Session/thread safety.
- Higher latency for small workloads.
- More complex cancellation.

Parallelism should be added only after profiling demonstrates need.

---

# Diagnostics Overhead

Diagnostics should be inexpensive when disabled.

Recommended architecture:

- No-op collector.
- Lazy metadata construction.
- Avoid formatting messages on success.
- Sample high-volume events.
- Aggregate counters instead of storing per-row events by default.
- Retain full diagnostics primarily for rejected rows.

The performance cost of diagnostics should be benchmarked separately.

---

# Logging Overhead

Per-row logging is expensive.

Recommendations:

- Do not log accepted rows by default.
- Aggregate rejection metrics.
- Sample detailed rejected-row logs.
- Use structured logging.
- Avoid rendering SQL.
- Avoid serializing full mappings.
- Avoid high-cardinality fields.

---

# Metrics Overhead

Metrics should use bounded-cardinality dimensions.

Good labels:

- Model name.
- Source name.
- Error type.
- Policy.
- Dialect.

Avoid:

- Primary key.
- Row index.
- Raw value.
- Full SQL.
- Request ID as a metric label.

Metrics exporters should support batching or aggregation.

---

# Tracing Overhead

One span per row is usually too expensive.

Recommended tracing model:

- One span per query.
- Optional events for sampled rejections.
- Aggregate row counts as span attributes.
- Separate spans for slow quarantine batches or callbacks when useful.

Raw data should not be attached to traces.

---

# Result Assembly Performance

Buffered result assembly should avoid copying already finalized collections
multiple times.

Potential approach:

- Mutable internal lists during execution.
- One conversion to immutable tuples at completion.
- One statistics snapshot.
- One diagnostics snapshot.

Result invariants should be checked without scanning large collections more than
necessary.

---

# Memory Retention

Common accidental memory-retention risks include:

- Storing raw ORM entities.
- Retaining SQLAlchemy rows and adapted mappings together.
- Keeping full Pydantic errors for millions of rows.
- Unbounded diagnostics.
- Unbounded callback buffers.
- Quarantine batches that never flush.
- Closures retaining sessions or statements.

The architecture should make retention explicit and configurable.

---

# ORM Identity Map

Full ORM entity queries can grow the identity map.

For large reads, users should prefer:

- Column projections.
- Core selects.
- Short-lived sessions.
- Streaming execution.
- Explicit session lifecycle.

RowGuard should not automatically expunge entities because that changes ORM
semantics.

---

# Raw SQL Performance

Raw SQL may be faster for specialized workloads, but RowGuard still incurs:

- Row adaptation.
- Pydantic validation.
- Rejection handling.

Automatic SQLRules pushdown is disabled for arbitrary SQL, so applications should
write efficient WHERE clauses explicitly.

---

# Reflection Performance

Reflection should occur outside the hot path.

Recommended:

- Reflect once at startup.
- Reuse `MetaData`.
- Reuse `Table`.
- Cache source resolution.

RowGuard should not reflect schemas per request.

---

# Plan Reuse

A plan may be reused when:

- Statement shape is stable.
- Model is stable.
- Mappings are stable.
- Policy configuration is stable.
- Only bound parameter values change.

Potential API:

```python
plan = rowguard.plan(
    table=users,
    model=UserRead,
)

result = rowguard.execute_plan(
    session=session,
    plan=plan,
    parameters={"tenant_id": tenant_id},
)
```

This is a future optimization and advanced API.

---

# Benchmark Categories

The benchmark suite should include:

## Clean buffered query

All rows validate.

## Rejection-heavy buffered query

A significant fraction fails validation.

## Clean streaming query

Large result set with no rejections.

## Rejection-heavy streaming query

Large result set with callback or quarantine.

## Core mapping query

SQLAlchemy Core rows.

## ORM projection query

ORM selected columns.

## Full ORM entity query

Mapped entities adapted to read models.

## SQLRules enabled vs disabled

Measure pushdown benefit.

## Strict vs default validation

Measure validation-mode cost.

## Diagnostics enabled vs disabled

Measure observability overhead.

## Sync vs async

Measure I/O and orchestration parity.

---

# Representative Model Sizes

Suggested benchmark models:

## Small

- 3–5 scalar fields.
- No custom validators.

## Medium

- 15–25 fields.
- Enums, dates, UUID, optional values.
- A few field validators.

## Large

- 50–100 fields.
- Nested models.
- Lists and mappings.
- Multiple validators.

---

# Representative Row Counts

Suggested scales:

- 10 rows
- 100 rows
- 1,000 rows
- 10,000 rows
- 100,000 rows
- 1,000,000 rows for streaming benchmarks

Large benchmarks should run separately from the standard unit-test suite.

---

# Metrics to Record

Benchmark outputs should include:

- Planning time.
- SQLRules compilation time.
- Database execution time.
- Row fetch time.
- Adaptation time.
- Validation time.
- Rejection handling time.
- Quarantine time.
- Total wall-clock time.
- Rows per second.
- Peak memory.
- Allocations where practical.
- Accepted/rejected counts.
- Plan-cache hit rate.
- Statement-cache behavior where observable.

---

# Performance Targets

Initial targets should be treated as directional until measured on representative
hardware.

## Planning

- Small model: sub-millisecond to low single-digit milliseconds.
- Medium model: low single-digit milliseconds.
- Cached planning: substantially faster than cold planning.

## Per-row overhead

- Adaptation overhead should be materially lower than Pydantic validation cost on
  ordinary models.
- Disabled diagnostics should add negligible overhead.
- `skip` rejection policy should remain lightweight.
- Streaming memory should remain approximately constant with result size.

## Throughput

The project should publish measured baselines rather than marketing unsupported
numbers.

---

# Baseline Comparison

Benchmarks should compare RowGuard against:

1. Plain SQLAlchemy row iteration.
2. SQLAlchemy plus manual `model_validate()`.
3. SQLModel/ORM query without explicit revalidation.
4. RowGuard with pushdown disabled.
5. RowGuard with pushdown enabled.

This clarifies the cost of:

- Validation itself.
- RowGuard orchestration.
- Rejection handling.
- SQL pushdown benefit.

---

# Performance Regression Policy

CI should include lightweight regression benchmarks.

Recommended policy:

- Track baseline medians.
- Use repeated runs.
- Avoid failing on tiny noisy changes.
- Flag significant regressions for review.
- Run larger benchmarks on scheduled workflows.
- Store benchmark history.

Potential thresholds:

- >10% regression: warning.
- >20% regression: blocking review, subject to noise analysis.

Exact thresholds should be tuned after baseline data exists.

---

# Profiling

Recommended tools and techniques:

- `cProfile` for broad call analysis.
- `py-spy` for low-overhead sampling.
- `scalene` for CPU and memory.
- `tracemalloc` for allocation tracking.
- SQLAlchemy engine timing hooks for query timing.
- Pydantic-specific microbenchmarks for model cost.

Profile real workloads before optimizing.

---

# Hot Path Rules

The per-row hot path should avoid:

- Model introspection.
- Mapper introspection.
- SQL compilation.
- String formatting.
- Logging.
- Deep copying.
- Dynamic registry lookup where prebinding is possible.
- Repeated policy parsing.
- Repeated alias resolution.
- Repeated context construction.

These operations belong in planning.

---

# Prebinding

Execution plans should prebind:

- Adapter method.
- Validator method.
- Rejection policy method.
- Diagnostic collector.
- Source identity extractor.
- Field mapping plan.

This reduces indirection inside the row loop.

---

# Dataclasses and Slots

Internal immutable plan objects may use:

```python
@dataclass(frozen=True, slots=True)
```

Mutable runtime state may use:

```python
@dataclass(slots=True)
```

Benefits:

- Lower memory overhead.
- Clear field definitions.
- Faster attribute access in some cases.

Use only where it improves clarity and measured performance.

---

# Generators and Iterators

Streaming should use iterators rather than building intermediate lists.

However, generators should not obscure resource cleanup.

Context-managed stream objects are preferred when database cursors and provider
buffers require deterministic finalization.

---

# Error Construction Cost

Detailed rejection objects are expensive.

Optimize by:

- Building them only on rejection.
- Applying redaction once.
- Avoiding full SQL rendering.
- Avoiding raw row retention unless configured.
- Reusing static model/source metadata.
- Serializing only when required by a sink.

Accepted rows should not pay rejection-object construction cost.

---

# Quarantine Serialization Cost

Serialization can dominate quarantine throughput.

Recommendations:

- Convert common types deterministically.
- Avoid repeated Pydantic dumps.
- Batch records.
- Compress at provider level.
- Avoid retaining both serialized and structured forms.
- Track payload size.

---

# Large Payload Handling

Large JSON, binary, and text values require special care.

Potential policies:

```python
max_retained_value_size=1_000_000
oversize_value_policy="omit"
```

This can prevent rejection records from exhausting memory or storage.

Such limits must be explicit and diagnosable.

---

# Time Measurement

Use monotonic high-resolution clocks.

Recommended:

```python
time.perf_counter_ns()
```

Measure separately:

- Planning.
- Execution.
- Adaptation.
- Validation.
- Rejection handling.
- Callback.
- Quarantine.
- Total.

Avoid timing every micro-stage when diagnostics are disabled if the timing
overhead is material.

---

# Sampling Timers

For extremely high-volume workloads, detailed per-row timing may be sampled.

Potential configuration:

```python
timing_sample_rate=0.01
```

Aggregate counters remain exact.

Sampling behavior must be documented.

---

# Thread Safety

Execution plans and immutable registries may be shared.

Per-run execution state is isolated.

RowGuard must not imply that SQLAlchemy sessions are thread-safe.

Parallel query execution requires separate sessions/connections according to
SQLAlchemy best practices.

---

# Process Safety

Plans containing SQLAlchemy expression objects may not be safely serializable
across processes.

Process-based parallel validation may require:

- Serializable row mappings.
- Reconstructed validators.
- Separate execution architecture.

This is deferred.

---

# Startup Cost

Import and client-construction overhead should remain modest.

Avoid:

- Eager loading of optional integrations.
- Importing every cloud provider.
- Reflecting schemas automatically.
- Building global registries with side effects.
- Connecting to databases on import.

Optional providers should use extras and lazy imports.

---

# Optional Dependencies

Performance-oriented integrations may require optional dependencies.

Examples:

- Orjson for quarantine serialization.
- OpenTelemetry exporters.
- Cloud SDKs.
- DataFrame libraries.

Core RowGuard should not require heavy optional packages.

---

# Rust or Native Acceleration

Native acceleration is not an initial goal.

Potential future candidates:

- Mapping transformation.
- Redaction.
- Error serialization.
- Bulk diagnostics aggregation.

Before considering native code, benchmark and optimize the Python architecture.

Pydantic already benefits from native internals, so RowGuard may not need its own
native layer.

---

# Performance Documentation

User-facing documentation should explain:

- When to use buffered vs streaming.
- Why projections outperform full entities.
- How SQLRules pushdown helps.
- How rejection policies affect throughput.
- Why collecting every rejection uses memory.
- Why callbacks and quarantine sinks may dominate runtime.
- How strict mode changes semantics.
- How to benchmark an application's own models.

---

# Testing Requirements

Performance-related tests should verify:

- Execution plans avoid repeated introspection.
- Streaming does not retain accepted models.
- Disabled diagnostics use the no-op path.
- Raw ORM entities are not retained by default.
- Plan reuse produces equivalent results.
- Pushdown reduces candidate rows in integration tests.
- Buffered and streaming semantics match.
- Sync and async results match.
- Rejection counts remain exact under sampling.
- Resource cleanup occurs under slow callbacks and failures.
- Batch quarantine flushes correctly.

---

# MVP Performance Scope

The first implementation should include:

- Two-phase planning and execution.
- Immutable execution plans.
- Precomputed adapter mappings.
- Preconfigured Pydantic validator.
- SQLRules pushdown.
- Buffered and streaming modes.
- No-op diagnostics collector.
- Separate timing counters.
- Configurable rejection retention.
- Lightweight raise/skip policies.
- Benchmark suite for Core and ORM projections.
- Memory tests for streaming.
- Basic regression tracking.

Deferred:

- Parallel validation.
- Process pools.
- Native acceleration.
- Adaptive batching.
- Automatic query optimization.
- Persistent cross-process plan cache.
- Dynamic cost-based planner.
- Background quarantine delivery.
- Distributed execution.
- Automatic model simplification.

---

# Recommended Performance Defaults

Suggested defaults:

```python
pushdown="safe"
validation="full"
on_reject="raise"
diagnostics="summary"
retain_raw_rows=False
retain_adapted_rows=True
streaming=False
```

For high-volume ETL:

```python
pushdown="safe"
streaming=True
on_reject="quarantine"
retain_raw_rows=False
retain_adapted_rows=False
diagnostics="summary"
```

For data-quality audits:

```python
pushdown="disabled"  # optionally audit all source rows
strict=True
streaming=True
on_reject="quarantine"
diagnostics="detailed"
```

---

# Design Principles

- Correctness precedes speed.
- Push down safe work to the database.
- Plan once; execute many times.
- Keep per-row work minimal.
- Validate exactly once.
- Prefer projections for high-volume reads.
- Stream unbounded results.
- Retain only what the application needs.
- Measure callbacks and quarantine separately.
- Keep diagnostics cheap when disabled.
- Publish measured benchmarks, not unsupported claims.
- Optimize only after profiling real workloads.
