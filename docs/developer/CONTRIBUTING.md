# CONTRIBUTING.md

:::{admonition} Shipped surface first
:class: tip

Contribute against **0.5 shipped APIs** (Core, async, streaming, ORM/SQLModel).
Plugin, callback, quarantine, reflection, and raw-SQL helper work is deferred—
see [Supported vs planned](../project/supported.md). Prefer `make install` /
`make all` (matches CI).
:::

# Contributing to RowGuard

Thank you for helping build RowGuard.

RowGuard coordinates SQLAlchemy, SQLRules, and Pydantic to provide validation-
first database reads with explicit rejected-row handling. Contributions should
protect that focused mission.

---

# Project Mission

RowGuard exists to:

- Execute SQLAlchemy queries
- Apply SQLRules pushdown where safe
- Validate returned rows with Pydantic
- Classify every row as accepted or rejected
- Handle rejections explicitly
- Provide observable and typed results

RowGuard is not intended to become:

- A new ORM
- A migration tool
- A database driver
- A SQL parser
- A replacement for SQLAlchemy
- A replacement for Pydantic
- A replacement for SQLModel

---

# Ways to Contribute

Contributions may include:

- Bug reports
- Feature proposals
- Documentation
- Tests
- Performance improvements
- Examples
- Type improvements
- Security reports

Small, focused pull requests on the shipped surface are preferred.

---

# Before Starting

For significant changes:

1. Read the relevant architecture documents.
2. Search existing issues and discussions.
3. Open a design issue before implementing a broad feature.
4. Identify the package boundary involved:
   - SQLRules
   - RowGuard core
   - Plugin
   - Documentation
5. Describe compatibility and validation implications.

Do not implement major architectural changes only in code.

---

# Development Setup

Clone the repository and create a virtual environment.

```bash
git clone https://github.com/eddiethedean/rowguard.git
cd rowguard

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

Install development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev,async,sqlmodel]"
```

Additional extras may include:

```bash
python -m pip install -e ".[dev,postgresql,async]"
python -m pip install -e ".[docs]"
```

Exact extras are defined in `pyproject.toml` (`dev`, `docs`, `async`, `postgresql`,
`sqlmodel`).

To build documentation locally (Sphinx / Read the Docs):

```bash
python -m pip install -e ".[docs]"
make docs
```

See `docs/README.md` for Read the Docs project import steps.

---

# Supported Tooling

Expected development tools:

- Python
- pytest
- pytest-cov
- pytest-asyncio
- Ruff
- mypy
- pre-commit
- Docker or compatible containers for dialect tests

Optional:

- pytest-benchmark
- Hypothesis
- py-spy
- Scalene

---

# Common Commands

Run unit tests:

```bash
pytest tests/unit
```

Run all default tests:

```bash
pytest
```

Run coverage:

```bash
pytest --cov=rowguard --cov-report=term-missing
```

Run linting:

```bash
ruff check .
```

Run formatting:

```bash
ruff format .
```

Run type checking:

```bash
mypy src/rowguard
```

Run pre-commit:

```bash
pre-commit run --all-files
```

Run benchmarks:

```bash
pytest benchmarks --benchmark-only
```

---

# Architecture First

Major changes should update the relevant planning documents.

Examples:

- New rejection behavior → update `REJECTION_POLICIES.md`
- New adapter → update `ROW_ADAPTER.md`
- Cache changes → update `CACHE.md`
- Plugin changes → update `PLUGIN_SYSTEM.md`
- SQLModel changes → update `SQLMODEL.md`
- New public API → update `API.md`
- New milestone scope → update `ROADMAP.md` and `MILESTONES.md`

Documentation is part of the design, not an afterthought.

---

# Design Boundaries

## SQLAlchemy

SQLAlchemy owns:

- SQL expressions
- SQL rendering
- Sessions
- Connections
- ORM mapping
- Dialects
- Drivers

Do not reimplement SQLAlchemy behavior in RowGuard.

## SQLRules

SQLRules owns:

- Pydantic constraint extraction
- Constraint-to-SQLAlchemy translation
- Dialect-specific translators

RowGuard should depend only on SQLRules' public API.

## Pydantic

Pydantic owns:

- Type validation
- Strictness
- Aliases
- Field validators
- Model validators
- Nested models
- Validation errors

Do not create a parallel validation system.

## RowGuard

RowGuard owns:

- Planning
- Query execution
- Row adaptation
- Pydantic invocation
- Rejection handling
- Diagnostics
- Results

---

# Coding Standards

- Use Python 3.10+ syntax according to project support.
- Add type annotations to public and internal APIs.
- Prefer small, composable functions.
- Prefer immutable planning objects.
- Keep mutable state scoped to one execution.
- Avoid global mutable registries.
- Preserve original exception causes.
- Avoid broad `except Exception` unless wrapping at a deliberate boundary.
- Never silently discard a rejected row.
- Never interpolate SQL values.
- Avoid import-time side effects.
- Keep optional dependencies lazy.

---

# Type Checking

Core code should pass strict type checking.

Requirements:

- No untyped public functions
- Generic result types preserve target models
- Protocol implementations type-check
- Sync and async APIs have accurate signatures
- `type: ignore` comments include a reason
- Avoid `Any` where a protocol or generic can express the contract

Typing changes should include typing tests when inference behavior matters.

---

# Public API Changes

A public API change must include:

- Motivation
- Examples
- Type signature
- Error behavior
- Sync/async implications
- Streaming implications
- Backward compatibility
- Documentation
- Tests

Before 1.0, changes are possible but should still be deliberate.

After 1.0, semantic versioning applies.

---

# Error Design

New public errors should:

- Inherit from the correct subsystem base
- Preserve original exceptions
- Include structured context
- Avoid leaking sensitive values
- Have stable behavior
- Be documented
- Be tested

Do not use a new exception when an existing structured error fits.

---

# Diagnostics

New diagnostic codes should:

- Use the correct namespace
- Be stable and machine-readable
- Avoid raw sensitive values
- Include only bounded metadata
- Be documented
- Have tests

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
cache.*
plugin.*
```

---

# Security

Never:

- Construct SQL through value interpolation
- Log raw rejected rows by default
- Expose credentials in diagnostics
- Pass sessions to plugins implicitly
- Stringify arbitrary objects for quarantine
- Disable authorization filters through validation configuration
- Treat Pydantic constraints as access-control rules
- Retain raw ORM entities without explicit configuration

Security-sensitive fixes should follow the private reporting process.

---

# Testing Requirements

Every behavior change should include tests.

At minimum:

- Success path
- Failure path
- Statistics
- Diagnostics where relevant
- Sync/async parity where relevant
- Buffered/streaming parity where relevant
- Security behavior where relevant
- Cache-enabled/disabled equivalence where relevant

Bug fixes should include a regression test that fails before the fix.

---

# Test Style

Prefer behavior-focused tests.

```python
def test_collect_policy_preserves_rejection_order() -> None:
    ...
```

Avoid tests that assert private call order unless that order is a documented
invariant.

Use real Pydantic and SQLAlchemy objects when their semantics matter.

---

# Database Tests

SQLite is useful but not sufficient for all behavior.

Features involving:

- Server-side streaming
- UUID
- JSONB
- Arrays
- Native enums
- Driver-specific values
- Async drivers

should include the relevant database integration test.

---

# Async Contributions

Async changes must not duplicate the entire sync pipeline.

Share:

- Planning
- Adaptation
- Validation
- Rejection decisions
- Statistics
- Diagnostics
- Result assembly

Separate only I/O and lifecycle operations.

Test cancellation and cleanup.

---

# Streaming Contributions

Streaming changes must prove:

- Accepted models are not retained
- Resources close on all exits
- Ordering remains stable
- Rejections behave consistently
- Memory remains bounded for the chosen policy (`collect` retains rejects)

(Quarantine batch flush is a **0.6+** concern, not required for 0.5 PRs.)

---

# Performance Contributions

Performance changes must include:

- Benchmark before
- Benchmark after
- Correctness tests
- Explanation of tradeoffs
- Memory impact
- Accepted/rejected path impact

Do not merge optimizations that weaken guarantees.

---

# Plugin Contributions

:::{admonition} Deferred to 0.7
:class: caution

There is no public plugin API in 0.5. Do not open PRs that invent plugin
registries unless an issue explicitly scopes that milestone.
:::

Public plugins should:

- Implement documented protocols
- Declare metadata and capabilities
- Validate configuration
- Avoid global mutable state
- Document lifecycle
- Document privacy behavior
- Document transaction behavior
- Pass conformance tests
- Keep heavy dependencies optional

New official plugins require a maintenance commitment.

---

# Dialect Contributions

A dialect contribution should include:

- Supported database versions
- Supported drivers
- Sync/async status
- Streaming status
- Type-return notes
- Integration tests
- Known limitations
- Documentation
- SQLRules plugin dependency when relevant

Do not claim full support from SQL compilation tests alone.

---

# Documentation Style

Documentation should:

- Be precise
- Use complete examples
- Distinguish current behavior from planned behavior
- Avoid overstating SQLModel limitations
- Explain security and transaction implications
- Prefer explicit contracts over vague promises
- Keep package boundaries clear

Examples should be tested where practical.

---

# Commit Style

Use focused commits with descriptive messages.

Examples:

```text
Add nested row adapter planning
Fix async stream cleanup on callback failure
Document PostgreSQL array behavior
```

Avoid combining unrelated refactors and features.

---

# Pull Requests

A pull request should include:

- Problem statement
- Proposed solution
- Alternatives considered
- Public API impact
- Tests
- Documentation
- Performance impact
- Security/privacy impact
- Compatibility notes

Keep pull requests reviewable.

Large changes may be split into:

1. Architecture/docs
2. Internal interfaces
3. Implementation
4. Integrations
5. Examples

---

# Pull Request Checklist

- [ ] Scope is focused
- [ ] Architecture documents updated
- [ ] Public API documented
- [ ] Tests added
- [ ] Failure paths tested
- [ ] Sync/async parity considered
- [ ] Streaming considered
- [ ] Security and redaction considered
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Benchmarks added or reviewed where relevant
- [ ] Changelog entry added when appropriate
- [ ] No unnecessary dependency added

---

# Review Priorities

Reviewers should prioritize:

1. Correctness
2. Validation guarantees
3. Security/privacy
4. Resource cleanup
5. API clarity
6. Type safety
7. Compatibility
8. Performance
9. Style

---

# Backward Compatibility

Before 1.0:

- Public APIs may evolve
- Changes should include migration notes
- Avoid unnecessary churn

After 1.0:

- Breaking public changes require a major release
- Public result objects and errors are compatibility commitments
- Plugin API major versions are explicit

Private modules remain unstable unless documented.

---

# Deprecation

Deprecations should:

- Emit a clear warning
- Include replacement guidance
- Be documented
- Include a migration example
- Remain for a reasonable transition period
- Avoid silent behavior changes

---

# Dependency Policy

New dependencies should be justified.

Prefer:

- Standard library
- Existing core dependencies
- Optional extras
- Small focused packages

Avoid adding heavy cloud, analytics, or observability dependencies to core.

---

# Release Notes

User-visible changes should be recorded under categories such as:

- Added
- Changed
- Fixed
- Deprecated
- Removed
- Security
- Performance

Mention:

- Validation behavior changes
- Rejection-policy changes
- Dialect changes
- Plugin API changes
- Dependency range changes

---

# Issue Reports

A good bug report includes:

- RowGuard version
- Python version
- SQLAlchemy version
- Pydantic version
- SQLRules version
- SQLModel version where relevant
- Database and driver
- Minimal model
- Minimal query
- Rejection policy
- Expected behavior
- Actual behavior
- Traceback with sensitive values removed

---

# Feature Requests

A feature request should answer:

- What problem does it solve?
- Why is RowGuard the correct layer?
- Could it be a plugin?
- Does it affect validation guarantees?
- Does it affect SQLRules?
- What are sync/async and streaming implications?
- What is the smallest useful API?

---

# Security Reports

Do not open a public issue for a vulnerability involving:

- SQL injection
- Redaction bypass
- Credential exposure
- Cross-tenant data exposure
- Unsafe plugin execution
- Quarantine data leakage

Use the repository's documented private security contact.

---

# Code of Conduct

Contributors must follow the project's [Code of Conduct](../../CODE_OF_CONDUCT.md).

Security reports: see [SECURITY.md](../../SECURITY.md) (do not open public issues
for vulnerabilities).

Technical disagreement should remain respectful, specific, and grounded in the
project's goals and evidence.

---

# Good First Contributions

Prefer work on the **shipped** 0.5 surface:

- Improve documentation examples and guides
- Add missing rejection / streaming / ORM tests
- Add typing stubs under `tests/typing`
- Add SQLite edge-case tests
- Improve diagnostics messages (without leaking row values)
- Improve error messages without exposing values
- Benchmark reporting for existing APIs

Avoid starting with deferred milestones (plugins, reflection, raw SQL helpers,
callback/quarantine) unless an issue explicitly scopes that work.

---

# Maintainer Responsibilities

Maintainers should:

- Protect project scope
- Review validation guarantees carefully
- Keep architecture docs current
- Avoid unsupported compatibility claims
- Publish transparent benchmark results
- Maintain plugin and dialect support levels honestly
- Provide migration guidance
- Treat security and privacy as core concerns

---

# Design Principles

- Focus on validation-first reads.
- Extend SQLAlchemy; do not replace it.
- Delegate validation to Pydantic.
- Delegate SQL constraint compilation to SQLRules.
- Make rejections explicit.
- Prefer immutable plans and narrow protocols.
- Keep optional integrations outside core.
- Test failure paths as seriously as success paths.
- Document before adding complexity.
