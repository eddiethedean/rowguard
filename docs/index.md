# RowGuard documentation

```{raw} html
<div class="rg-hero">
  <div class="rg-hero-badges">
    <span class="rg-badge rg-badge--accent">v{{ release }}</span>
    <span class="rg-badge">SQLAlchemy · Pydantic</span>
    <span class="rg-badge">Sync · Async · Streaming</span>
  </div>
  <p class="rg-hero-kicker">RowGuard documentation</p>
  <p class="rg-hero-title">Validation-first queries that never silently drop bad rows</p>
  <p class="rg-lead">Execute SQLAlchemy queries, validate every returned row against a Pydantic model, and handle rejections explicitly—with the same semantics for buffered, streaming, sync, and async APIs.</p>
  <p>
    <a class="rg-hero-cta" href="guides/quickstart.html">Quickstart →</a>
    <a class="rg-hero-cta rg-hero-cta--ghost" href="guides/start-here.html" style="margin-left:0.75rem">Start here</a>
  </p>
</div>
```

Pick the path that matches how you work:

::::{grid} 2
:gutter: 3

:::{grid-item-card} Get productive
:link: guides/quickstart
:link-type: doc

Install RowGuard and run your first validated `select` / `stream` in a few minutes.

+++
**Open quickstart →**
:::

:::{grid-item-card} Async & streaming
:link: guides/async
:link-type: doc

Use `aselect` / `astream` with `AsyncSession`, or stream large results without buffering accepted models.

+++
**Async guide →**
:::

:::{grid-item-card} Rejection policies
:link: guides/rejection-policies
:link-type: doc

Choose `raise`, `collect`, or `skip`—and understand how statistics and retained rejections differ.

+++
**Policy guide →**
:::

:::{grid-item-card} Architecture
:link: architecture_overview
:link-type: doc

How planning, SQLRules pushdown, adapters, validation, and results fit together.

+++
**Read architecture →**
:::

::::

:::{admonition} Coming from raw SQLAlchemy?
:class: tip

Keep your `Table` / `Select` and sessions. RowGuard adds planning, validation, and rejection handling around them—it does not replace SQLAlchemy.
:::

```{raw} html
<div class="rg-callout">
  <strong>Requires</strong> Python {{ python_min }}, Pydantic v2, SQLAlchemy 2.x, and SQLRules.
  Async extras: <code>pip install "rowguard[async]"</code>.
</div>
```

(documentation-map)=
## Documentation map

```{toctree}
:maxdepth: 1
:caption: Getting started

guides/start-here
guides/installation
guides/quickstart
guides/faq
guides/troubleshooting
```

```{toctree}
:maxdepth: 1
:caption: Guides

guides/rejection-policies
guides/streaming
guides/async
```

```{toctree}
:maxdepth: 1
:caption: Reference

api
spec
reference/api
```

```{toctree}
:maxdepth: 1
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
:maxdepth: 1
:caption: Validation & rejection

validation/PYDANTIC
validation/TYPE_SUPPORT
validation/VALIDATION_ERRORS
validation/PARTIAL_VALIDATION
rejection/REJECTION_POLICIES
rejection/REJECTION_HANDLING
rejection/DIAGNOSTICS
rejection/CALLBACKS
rejection/QUARANTINE
```

```{toctree}
:maxdepth: 1
:caption: Integrations

integrations/CORE
integrations/ORM
integrations/SQLMODEL
integrations/WHY_NOT_SQLMODEL
integrations/REFLECTION
integrations/RAW_SQL
```

```{toctree}
:maxdepth: 1
:caption: Project

project/changelog
project/roadmap
developer/CONTRIBUTING
developer/TESTING
developer/BENCHMARKS
developer/MILESTONES
readme
```
