# MILESTONES.md

# RowGuard Milestones

## Purpose

This document defines the planned development milestones from initial
implementation through a stable 1.0 release.

Each milestone should deliver a coherent architectural capability rather than a
loose collection of features.

---

# Release Philosophy

- Each 0.x release may refine APIs.
- Every release must remain usable and documented.
- Correctness and validation guarantees take priority over feature count.
- SQLAlchemy, SQLRules, and Pydantic boundaries remain stable.
- Public compatibility becomes stricter as 1.0 approaches.
- Scope may move between milestones based on implementation evidence.

---

# 0.1.0 — Validation-First Core

## Goal

Deliver the smallest complete RowGuard workflow.

## Status

Shipped.

## Scope

- Python 3.10+
- Pydantic v2
- SQLAlchemy 2.x
- SQLRules integration
- SQLAlchemy Core `Table`
- Existing `Select`
- Synchronous `Session`
- Synchronous `Connection`
- Mapping-based row adaptation
- Full Pydantic validation
- `QueryResult[T]`
- `RejectedRow`
- `QueryStatistics`
- Rejection policies:
  - raise
  - collect
  - skip
- Basic diagnostics
- SQLite integration tests (PostgreSQL CI deferred to dialect milestone)
- Strict type checking
- Initial benchmark baseline

## Public Example

```python
result = rowguard.select(
    session=session,
    table=users,
    model=UserRead,
    on_reject="collect",
)
```

## Exit Criteria

- Every accepted row is a validated model.
- Every rejected row is counted.
- SQLRules pushdown can be enabled or disabled.
- Resource cleanup is reliable.
- Core documentation is complete.
- Test coverage exceeds the project threshold.

---

# 0.2.0 — Execution Planning

## Goal

Formalize the planning/runtime boundary.

## Status

Shipped.

## Scope

- Immutable staged `ExecutionPlan`
- Normalized `QueryRequest` and planning configs
  (`PushdownConfig`, `ValidationConfig`, `RejectionConfig`, …)
- Source resolution
- Statement planning
- Pushdown planning (including precompiled SQLRules)
- Adapter planning
- Validation planning
- Rejection planning
- Structured planning diagnostics
- Explicit pushdown maps and field maps (plan-time validation)
- Better configuration errors (`PlanningError`)
- Public `compile_plan()` for execution-plan inspection
- Session/connection on `SyncExecutionContext` only (not on the plan)
- Optional structural plan cache (opt-in; semantically equivalent to uncached)

ORM / SQLModel remain out of scope here (see **0.5.0**).

## Exit Criteria

- Planning performs no ordinary database I/O.
- Execution does not repeat model or source inspection per row.
- Plans are independently testable.
- Cached and uncached planning are semantically equivalent.
- 0.1.0 public call sites remain working.

---

# 0.3.0 — Streaming Engine (shipped)

## Goal

Support large result sets with bounded memory.

## Scope

- `stream()`
- `StreamResult[T]`
- Context-managed resource lifecycle
- SQLAlchemy streaming options
- Incremental validation
- Stable row ordering
- Rejection policies during streaming
- Final statistics
- Early-close cleanup
- Memory regression tests
- Progress/observer hooks

## Exit Criteria

- Accepted models are not retained.
- Peak memory is bounded by fetch and rejection configuration.
- Every exit path releases database resources.
- Buffered and streaming acceptance semantics match.

---

# 0.4.0 — Async Engine

## Goal

Provide first-class asynchronous execution.

## Scope

- `aselect()`
- `aexecute()`
- `astream()`
- `AsyncSession`
- `AsyncConnection`
- Async stream lifecycle
- Cancellation handling
- Sync/async parity tests
- Supported driver matrix (sqlite+aiosqlite for 0.4)

Async callback / quarantine protocols are deferred to **0.6.0** (see ASYNC.md /
ROADMAP). Ship raise / collect / skip only.

## Exit Criteria

- Async changes I/O behavior, not validation semantics.
- Cancellation closes resources.
- Sync and async results match for equivalent datasets.
- Event-loop blocking risks are documented.

---

# 0.5.0 — ORM and SQLModel Integration

## Goal

Make RowGuard natural in mapped applications.

## Scope

- SQLAlchemy ORM mapped classes
- ORM `Select`
- Projected-column validation
- Single-entity mapping adapter
- `from_attributes` opt-in
- Primary-key source identity
- Lazy-load safeguards
- Deferred/unloaded attribute errors
- SQLModel table sources
- SQLModel data/read targets
- SQLModel `Session`
- SQLModel documentation and examples

## Exit Criteria

- ORM projections work as reliably as Core mappings.
- Full entity behavior is explicit and documented.
- No implicit relationship traversal.
- SQLModel positioning remains complementary and accurate.

---

# 0.6.0 — Rejection Platform

## Status

Shipped.

## Goal

Expand rejected-row handling into a complete workflow.

## Scope

- Callback policy
- Callback decisions
- Structured callback context
- Quarantine policy
- `QuarantineRecord`
- `QuarantineReceipt`
- In-memory provider
- JSONL provider
- Redaction policies
- Retention policies
- Rejection thresholds
- Callback/quarantine timing
- Failure policies

## Exit Criteria

- Provider failures never erase original rejections.
- Redaction occurs before external handoff.
- Streaming flushes providers correctly.
- Transaction behavior is explicit.
- No hidden background delivery promises.

---

# 0.7.0 — Plugin System

## Goal

Open narrow, stable extension points.

## Scope

- Plugin API version 1
- Plugin metadata
- Capability declarations
- Immutable registries
- Adapter plugins
- Source resolver plugins
- Rejection policy plugins
- Quarantine providers
- Diagnostic exporters
- Conformance tests
- Explicit registration
- Plugin inventory

## Exit Criteria

- Plugins do not access mutable execution internals.
- Incompatible plugins fail during planning.
- Public protocols are documented and typed.
- Optional dependencies remain outside core.

---

# 0.8.0 — Dialects, Reflection, and Raw SQL

## Goal

Broaden database compatibility without compromising the portable core.

## Scope

- Dialect profiles
- Capability detection
- SQLite Tier 1
- PostgreSQL Tier 1
- MySQL/MariaDB support
- SQL Server support
- DuckDB integration
- Reflected tables
- Raw SQLAlchemy `text()`
- Driver-specific type documentation
- Portable/native/strict dialect policies
- Expanded cross-dialect test matrix

## Exit Criteria

- Official support levels match real automated tests.
- Raw SQL remains parameterized and non-rewritten.
- Reflection remains delegated to SQLAlchemy.
- Backend differences are visible in diagnostics.

---

# 0.9.0 — Stabilization and Release Candidate

## Goal

Freeze the 1.0 contract and harden production behavior.

## Scope

- Public API freeze
- Public error hierarchy freeze
- Query/result object freeze
- Plugin API freeze
- Performance tuning
- Cache hardening
- Security review
- Documentation completion
- Migration guides
- Full dialect matrix
- Long-running streaming tests
- Failure injection
- Release-candidate benchmark report
- Dependency lower-bound and latest tests

## Exit Criteria

- No unresolved critical correctness issues.
- No unresolved resource leaks.
- No known redaction bypass.
- Stable plugin API.
- Performance regressions reviewed.
- Documentation examples tested.
- Production readiness checklist complete.

---

# 1.0.0 — Stable Release

## Goal

Deliver a production-ready validation-first query layer.

## Stable Public Surface

- `select`
- `execute`
- `stream`
- `aselect`
- `aexecute`
- `astream`
- `validate_rows`
- `RowGuard` client
- `QueryResult[T]`
- `StreamResult[T]`
- `RejectedRow`
- `QueryStatistics`
- Public errors
- Public plugin protocols

## Supported Foundation

- Python 3.10+
- Pydantic v2
- SQLAlchemy 2.x
- Stable SQLRules API
- SQLAlchemy Core
- SQLAlchemy ORM
- SQLModel integration
- Sync and async
- Buffered and streaming
- Rejection policies
- Quarantine
- Plugins
- Dialect profiles
- Caching
- Diagnostics

## Success Criteria

- Clear package boundaries
- Predictable validation semantics
- Complete accepted/rejected accounting
- Stable typing
- Excellent documentation
- Comprehensive tests
- Honest performance data
- Production-grade resource cleanup
- Explicit security and privacy controls

---

# Post-1.0 Roadmap

## 1.1 — Developer Experience

Potential scope:

- Better plan explanations
- Richer error summaries
- CLI audit tool
- FastAPI helpers
- Improved SQLModel examples
- Configuration loaders
- IDE-friendly diagnostics

## 1.2 — Data Engineering Integrations

Potential scope:

- Pandas exporter
- Polars exporter
- Arrow integration
- Dagster resources
- Airflow operators
- Prefect tasks
- dbt-adjacent audit workflows

## 1.3 — Advanced Quarantine and Replay

Potential scope:

- SQL provider
- S3/Azure Blob providers
- Kafka/SQS providers
- Replay CLI
- Repair audit trail
- Rejection fingerprints
- Deduplication
- Schema migration tools

## 1.4 — Advanced Planning

Potential scope:

- Partial validation
- Dynamic projections
- Plan templates
- Better statement-shape caching
- Pushdown explanations
- Aggregate/HAVING planning
- Outer-join-aware policies

## 2.0 — Broader Validation Targets

Potential scope:

- Pydantic `TypeAdapter`
- Dataclasses
- TypedDict
- Scalar targets
- Collection targets
- Revised plugin API if required

---

# Cross-Cutting Workstreams

The following continue across every milestone:

## Documentation

- Keep planning documents current.
- Test examples.
- Publish migration guidance.
- Document limitations honestly.

## Testing

- Expand dialect matrix.
- Maintain failure-path tests.
- Maintain security tests.
- Maintain typing tests.
- Maintain benchmark baselines.

## Performance

- Profile real workloads.
- Prevent regressions.
- Keep streaming memory bounded.
- Keep diagnostics inexpensive.

## Security

- Preserve bound parameters.
- Maintain redaction.
- Avoid session leakage.
- Review provider data handling.
- Keep authorization separate from validation.

## Compatibility

- Track Python
- Pydantic
- SQLAlchemy
- SQLRules
- SQLModel
- Drivers
- Databases

---

# Milestone Dependencies

```text
0.1 Core
  │
  ▼
0.2 Planning
  │
  ├─────────────┐
  ▼             ▼
0.3 Streaming  0.4 Async
  │             │
  └──────┬──────┘
         ▼
0.5 ORM / SQLModel
         │
         ▼
0.6 Rejection Platform
         │
         ▼
0.7 Plugins
         │
         ▼
0.8 Dialects / Reflection / Raw SQL
         │
         ▼
0.9 Stabilization
         │
         ▼
1.0 Stable
```

Some implementation may overlap, but release gates should preserve architectural
order.

---

# Scope Control

A feature should move to a later milestone when:

- It is not required for the milestone's core guarantee.
- It introduces a new package responsibility.
- It lacks a stable design.
- It depends on unimplemented infrastructure.
- It materially delays correctness or documentation.
- It is better implemented as a plugin.
- It lacks tests across relevant modes.

---

# Release Checklist

Every release should verify:

- [ ] Public API documented
- [ ] Tests passing
- [ ] Type checking passing
- [ ] Linting passing
- [ ] Examples passing
- [ ] Security tests passing
- [ ] Resource cleanup verified
- [ ] Benchmark changes reviewed
- [ ] Dependency matrix reviewed
- [ ] Changelog updated
- [ ] Migration notes included when needed
- [ ] Milestone exit criteria met

---

# Design Principles

- Milestones deliver coherent capabilities.
- Correctness comes before feature count.
- Streaming and async are architectural features, not wrappers.
- SQLModel support remains complementary.
- Plugins follow a stable, narrow API.
- Official dialect claims require real tests.
- 1.0 freezes a trustworthy contract, not merely a version number.
