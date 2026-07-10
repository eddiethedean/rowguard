# RowGuard documentation

Validation-first database queries for SQLAlchemy and Pydantic.

RowGuard executes SQLAlchemy queries, validates every returned row against a
Pydantic model, and explicitly handles rows that fail validation.

```{toctree}
:maxdepth: 2
:caption: Start here

readme
api
spec
changelog
roadmap
```

```{toctree}
:maxdepth: 2
:caption: Architecture

architecture_overview
architecture/EXECUTION_PIPELINE
architecture/QUERY_ENGINE
architecture/QUERY_COMPILATION
architecture/FILTER_PUSHDOWN
architecture/SQLRULES_INTEGRATION
architecture/VALIDATION_ENGINE
architecture/ROW_ADAPTER
architecture/RESULT_OBJECT
architecture/STREAMING
architecture/ASYNC
architecture/PERFORMANCE
architecture/CACHE
architecture/INTERNAL_API
architecture/DESIGN_DECISIONS
architecture/PLUGIN_SYSTEM
architecture/DIALECT_SUPPORT
```

```{toctree}
:maxdepth: 2
:caption: Validation

validation/PYDANTIC
validation/TYPE_SUPPORT
validation/VALIDATION_ERRORS
validation/PARTIAL_VALIDATION
```

```{toctree}
:maxdepth: 2
:caption: Rejection

rejection/REJECTION_POLICIES
rejection/REJECTION_HANDLING
rejection/DIAGNOSTICS
rejection/CALLBACKS
rejection/QUARANTINE
```

```{toctree}
:maxdepth: 2
:caption: Integrations

integrations/CORE
integrations/ORM
integrations/SQLMODEL
integrations/WHY_NOT_SQLMODEL
integrations/REFLECTION
integrations/RAW_SQL
```

```{toctree}
:maxdepth: 2
:caption: Developer

developer/CONTRIBUTING
developer/TESTING
developer/BENCHMARKS
developer/MILESTONES
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/api
```

## Install

```bash
pip install rowguard
pip install "rowguard[async]"   # aiosqlite / async APIs
```

## Quick links

- [Public API](api.md)
- [Specification](spec.md)
- [Async architecture](architecture/ASYNC.md)
- [Contributing](developer/CONTRIBUTING.md)
