# BENCHMARKS.md

# RowGuard Benchmarking

## Purpose

The RowGuard benchmark suite measures the overhead and benefits of validation-
first database reads.

Benchmarks should answer:

- What does RowGuard add beyond plain SQLAlchemy?
- How much of the cost comes from Pydantic validation?
- How much does SQLRules pushdown reduce work?
- How do Core, ORM projections, and full entities compare?
- How do rejection policies affect throughput?
- Does streaming remain memory-bounded?
- Do caches materially improve repeated planning?
- Are releases introducing regressions?

Benchmarks must report measured results, not aspirational marketing numbers.

---

# Benchmark Principles

- Separate database time from RowGuard overhead.
- Compare against meaningful baselines.
- Benchmark accepted and rejected rows.
- Include cold and warm planning.
- Measure memory as well as wall-clock time.
- Avoid combining unrelated workloads into one score.
- Record hardware, Python, dependency, driver, and database versions.
- Use repeated runs and robust statistics.
- Keep correctness assertions inside benchmarks.
- Never disable validation merely to improve a headline number.

---

# Baselines

Every major benchmark should compare against:

## Plain SQLAlchemy

```python
rows = session.execute(stmt).mappings().all()
```

Measures database and SQLAlchemy result overhead.

## Manual Pydantic Validation

```python
models = [
    UserRead.model_validate(row)
    for row in session.execute(stmt).mappings()
]
```

Measures the manual pattern RowGuard formalizes.

## RowGuard Without Pushdown

```python
rowguard.execute(
    ...,
    pushdown="disabled",
)
```

Measures orchestration and rejection handling.

## RowGuard With Pushdown

```python
rowguard.execute(
    ...,
    pushdown="safe",
)
```

Measures the full intended workflow.

## SQLModel or ORM Baseline

Where relevant:

```python
session.exec(select(User)).all()
```

This is a persistence-loading baseline, not a validation-equivalent baseline.

---

# Benchmark Categories

## Planning

Measure:

- Query request normalization
- SQLRules compilation
- Adapter planning
- Validator construction
- Rejection-policy planning
- Execution-plan creation
- Cache hit and miss

## Buffered Execution

Measure:

- Small and medium result sets
- Valid rows
- Mixed rows
- All rejected
- Result assembly
- Memory retention

## Streaming

Measure:

- Large result sets
- Peak memory
- Rows per second
- Early consumer exit
- Rejection callback
- Quarantine batching

## Core

Measure SQLAlchemy Core mappings.

## ORM Projection

Measure ORM-selected scalar columns.

## Full ORM Entity

Measure entity construction, adaptation, and validation.

## Async

Measure concurrency-oriented workloads and event-loop overhead.

## Rejection Policies

Measure:

- raise
- collect
- skip
- callback
- quarantine

## Diagnostics

Measure:

- disabled
- summary
- detailed
- logging exporter
- metrics exporter

## Cache

Measure:

- disabled
- cold
- warm
- LRU contention

---

# Representative Models

## Small Model

```python
class SmallUser(BaseModel):
    id: int
    name: str
    age: int
```

## Medium Model

Include:

- 20 fields
- UUID
- Enum
- Decimal
- date/datetime
- optional values
- field validators

## Large Model

Include:

- 75 fields
- nested models
- lists
- mappings
- multiple validators
- cross-field validation

Model definitions must remain stable across benchmark history.

---

# Representative Data Quality

Use datasets with:

- 0% rejected
- 1% rejected
- 10% rejected
- 50% rejected
- 100% rejected

Rejection rate has a large effect because rejection construction, diagnostics,
and external handling cost more than successful validation.

---

# Representative Row Counts

Suggested scales:

- 10
- 100
- 1,000
- 10,000
- 100,000
- 1,000,000 for streaming-only tests

Standard pull-request benchmarks should stay fast.

Large workloads belong in scheduled performance jobs.

---

# Database Backends

Minimum:

- SQLite
- PostgreSQL

Extended:

- MySQL
- MariaDB
- SQL Server
- DuckDB

SQLite is useful for low-cost CI but should not be treated as representative of
client-server database I/O.

---

# Driver Versions

Record:

- SQLAlchemy version
- Pydantic version
- SQLRules version
- SQLModel version where relevant
- Database driver
- Server version
- Python version
- Operating system
- CPU
- Memory

Benchmark outputs without environment metadata are difficult to compare.

---

# Metrics

Required metrics:

- Total wall-clock time
- Planning time
- SQL execution/fetch time
- Adaptation time
- Validation time
- Rejection handling time
- Result assembly time
- Rows per second
- Accepted rows
- Rejected rows
- Peak memory

Optional:

- Allocations
- CPU time
- Cache hit rate
- Quarantine bytes
- Callback latency
- P95 and P99 per-row time
- Event-loop lag

---

# Timing

Use:

```python
time.perf_counter_ns()
```

For microbenchmarks, use a framework such as `pytest-benchmark`.

For end-to-end database benchmarks, isolate stages through RowGuard's own
statistics and external wall-clock measurement.

Do not report only the fastest run.

---

# Statistical Reporting

Report:

- Median
- Mean
- Standard deviation
- Min/max
- Number of rounds
- Confidence interval where practical

Median is the primary comparison metric for noisy CI environments.

---

# Warm-Up

Warm up:

- Python imports
- Pydantic model internals
- SQLAlchemy statement caches
- Database connections
- Server query caches where possible

Report cold-start separately when it matters.

Do not mix cold and warm measurements.

---

# Planning Benchmarks

Measure:

```text
cold model metadata
warm model metadata
cold SQLRules compilation
warm SQLRules compilation
cold adapter plan
warm adapter plan
cold execution template
warm execution template
```

The benchmark should prove that caching improves repeated stable queries without
changing results.

---

# Pushdown Benchmarks

Create datasets where SQLRules can eliminate large numbers of invalid rows.

Example:

- 1,000,000 source rows
- 10% satisfy numeric constraints
- All returned rows still undergo Pydantic validation

Compare:

```text
pushdown disabled
pushdown enabled
```

Record:

- Database candidate rows
- Rows transferred
- Validation count
- Total duration
- Peak memory

---

# Projection Benchmarks

Compare:

1. `select(table)`
2. Explicit required columns
3. ORM full entity
4. ORM projected columns

Use the same target read model where semantically possible.

Record:

- Row size
- Fetch time
- Adaptation time
- Validation time
- Peak memory
- Identity-map growth for ORM entities

---

# Adapter Benchmarks

Measure:

- Direct mapping view
- Mapping copy
- Explicit key rename
- Nested mapping
- ORM scalar extraction
- `from_attributes`
- Positional adapter
- Scalar wrapper

Adapter benchmarks should include correctness assertions.

---

# Validation Benchmarks

Measure:

- Default mode
- Strict mode
- Field validators
- Model validators
- Nested models
- Validation context
- Custom type
- Large JSON

RowGuard should compare its validator wrapper with direct
`Model.model_validate()` to isolate orchestration overhead.

---

# Rejection Benchmarks

## Raise

Measure first-failure latency.

## Collect

Measure allocation and memory growth.

## Skip

Measure minimal rejection overhead.

## Callback

Measure no-op callback and realistic structured callback.

## Quarantine

Measure per-record and batched providers.

Do not compare external network providers in noisy default CI.

---

# Quarantine Benchmarks

Reference providers:

- In-memory
- JSONL
- SQL table
- Optional object storage or message queue

Measure:

- Records per second
- Serialization time
- Flush time
- Batch size
- Bytes written
- Receipt overhead
- Failure/retry path

---

# Streaming Memory Benchmark

Process at least 1,000,000 simple rows.

Assert that peak memory remains bounded relative to:

- Fetch buffer
- Rejection retention
- Quarantine batch size

The test should detect accidental retention of accepted models.

---

# Async Benchmarks

Async benchmarks should model concurrent independent queries with separate
sessions.

Measure:

- Single query overhead
- Concurrent query throughput
- Async stream throughput
- Async callback/provider cost
- Event-loop blocking from sync callbacks

Do not claim async is faster for CPU-bound validation.

---

# Cache Benchmarks

Measure:

- Key construction
- LRU get/set
- Cold planning
- Warm planning
- Concurrent cache access
- Eviction
- Disabled cache path

Cache overhead must be lower than the work it avoids for common plans.

---

# Diagnostics Benchmarks

Compare:

- No-op collector
- Summary counters
- Detailed rejection diagnostics
- Structured logging
- Metrics exporter
- Trace events

Per-row accepted diagnostics should remain disabled by default.

---

# Plugin Overhead

Conformance benchmarks should allow plugin authors to measure:

- Per-row adapter overhead
- Policy overhead
- Provider throughput
- Exporter overhead
- Lifecycle cost

RowGuard may publish recommended maximum overhead ranges after real data exists.

---

# Benchmark Dataset Generation

Dataset generation should be deterministic.

Use:

- Fixed seeds
- Stable schemas
- Pre-generated fixtures where practical
- Separate setup time from measured execution
- Explicit transaction boundaries

Invalid rows should be intentionally generated by error category.

---

# Correctness During Benchmarks

Every benchmark must assert:

- Accepted count
- Rejected count
- Model type
- Ordering where required
- Policy behavior
- Statistics invariants

A fast incorrect benchmark is meaningless.

---

# Tooling

Recommended:

- `pytest-benchmark`
- `pyperf` for stable microbenchmarks
- `tracemalloc`
- `py-spy`
- `scalene`
- `psutil` where needed
- Database-specific monitoring for deeper analysis

Avoid requiring every profiling tool for normal development.

---

# Benchmark Directory

Suggested layout:

```text
benchmarks/
├── conftest.py
├── models.py
├── datasets.py
├── test_planning.py
├── test_core_buffered.py
├── test_core_streaming.py
├── test_orm_projection.py
├── test_orm_entity.py
├── test_validation.py
├── test_rejection.py
├── test_quarantine.py
├── test_cache.py
├── test_async.py
└── reports/
```

---

# CI Strategy

## Pull Requests

Run smoke benchmarks:

- Small model
- 1,000 rows
- Core mapping
- Manual validation baseline
- RowGuard disabled/enabled cache
- No-op diagnostics

Purpose: detect severe regressions.

## Scheduled

Run larger matrix:

- Medium and large models
- 100,000+ rows
- PostgreSQL
- streaming memory
- rejection rates
- ORM variants
- async
- quarantine batching

## Release

Run full documented matrix and archive results.

---

# Regression Policy

Initial policy:

- Under 5%: informational
- 5–10%: investigate if repeated
- 10–20%: warning requiring explanation
- Over 20%: block release unless justified

CI noise must be considered.

Use repeated historical baselines rather than one prior run.

---

# Benchmark History

Store:

- JSON benchmark output
- Environment metadata
- Commit hash
- Package versions
- Database versions
- Summary report

A trend dashboard may be added later.

---

# Performance Budgets

Budgets should be based on measured baselines.

Potential budgets:

- Warm planning overhead should be small relative to query execution.
- Direct mapping adaptation should remain materially cheaper than Pydantic
  validation.
- No-op diagnostics should add negligible overhead.
- Streaming memory should not grow linearly with accepted row count.
- Skip policy should be the lightest continuing rejection policy.
- RowGuard orchestration overhead over manual Pydantic validation should remain
  modest and justified by features.

Do not publish hard numeric budgets before representative measurements exist.

---

# Benchmark Reporting

Reports should clearly distinguish:

- Database time
- Pydantic validation time
- RowGuard orchestration time
- External side-effect time
- Memory

Avoid a single composite score.

---

# User-Facing Benchmarks

Public performance documentation should include:

- Exact environment
- Exact code
- Dataset shape
- Rejection rate
- Pushdown mode
- Result mode
- Comparison baseline
- Limitations

Avoid implying results generalize to every model and database.

---

# Profiling Workflow

When a regression appears:

1. Reproduce locally.
2. Compare cold/warm behavior.
3. Separate database and application time.
4. Profile planning.
5. Profile row loop.
6. Inspect allocations.
7. Compare accepted and rejected paths.
8. Check diagnostics and cache configuration.
9. Verify correctness.
10. Add a targeted regression benchmark.

---

# MVP Benchmark Requirements

Before 0.1.0:

- Plain SQLAlchemy baseline
- Manual Pydantic validation baseline
- RowGuard Core buffered benchmark
- RowGuard Core streaming benchmark
- Pushdown enabled/disabled comparison
- Raise/collect/skip comparison
- Cold/warm planning benchmark
- Cache benchmark
- Peak-memory streaming test
- SQLite and PostgreSQL coverage
- Environment-recording script
- Archived baseline report

---

# Design Principles

- Measure before optimizing.
- Compare against realistic baselines.
- Separate validation cost from orchestration.
- Include rejected rows.
- Measure memory, not just speed.
- Keep correctness assertions active.
- Report environment and configuration.
- Treat CI numbers as noisy evidence, not absolute truth.
- Publish transparent benchmarks rather than unsupported claims.
