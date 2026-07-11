# RowGuard documentation

```{raw} html
<div class="rg-hero">
  <div class="rg-hero-badges">
    <span class="rg-badge rg-badge--accent">v{{ release }}</span>
    <span class="rg-badge">SQLAlchemy · Pydantic</span>
    <span class="rg-badge">Sync · Async · Streaming</span>
  </div>
  <p class="rg-hero-kicker">RowGuard documentation</p>
  <p class="rg-hero-title">Validation-first queries with explicit accepted or rejected rows</p>
  <p class="rg-lead">Execute SQLAlchemy queries, validate every returned row against a Pydantic model, and handle rejections explicitly—with the same semantics for buffered, streaming, sync, and async APIs. Default SQLRules pushdown may filter invalid candidates in SQL before fetch.</p>
  <p>
    <a class="rg-hero-cta" href="guides/start-here.html">Start here →</a>
    <a class="rg-hero-cta rg-hero-cta--ghost" href="guides/quickstart.html" style="margin-left:0.75rem">Quickstart</a>
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

:::{grid-item-card} SQLRules defaults
:link: guides/sqlrules-pushdown
:link-type: doc

Why invalid rows can “disappear” with the default `use_sqlrules=True`—and when to turn pushdown off.

+++
**Read pushdown guide →**
:::

:::{grid-item-card} Async & streaming
:link: guides/async
:link-type: doc

Use `aselect` / `astream` with `AsyncSession`, or stream large results without buffering accepted models.

+++
**Async guide →**
:::

:::{grid-item-card} What is shipped?
:link: project/supported
:link-type: doc

0.5 vs planned 0.6+ features. Prefer this page over design drafts in the sidebar.

+++
**Supported vs planned →**
:::

::::

:::{admonition} Coming from raw SQLAlchemy?
:class: tip

Keep your `Table` / `Select` and sessions. RowGuard adds planning, validation, and rejection handling around them—it does not replace SQLAlchemy.
:::

:::{admonition} Design docs
:class: caution

Long design notes are **hidden from the main sidebar** (still built and linked).
Pages under **Future / design** describe planned work and are **not shipped** in
{{ release }}. See [Supported vs planned](project/supported.md).
:::

```{raw} html
<div class="rg-callout">
  <strong>Requires</strong> Python {{ python_min }}, Pydantic v2, SQLAlchemy 2.x, and SQLRules ≥1.0.
  Async extras: <code>pip install "rowguard[async]"</code>.
  SQLModel: <code>pip install "rowguard[sqlmodel]"</code>.
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
guides/sqlrules-pushdown
guides/faq
guides/troubleshooting
```

```{toctree}
:maxdepth: 1
:caption: Guides

guides/rejection-policies
guides/streaming
guides/async
guides/orm-sqlmodel
guides/best-practices
examples/index
```

```{toctree}
:maxdepth: 1
:caption: Reference

API guide <api>
Python autodoc <reference/api>
reference/errors
spec
```

```{toctree}
:maxdepth: 1
:caption: Architecture

architecture_overview
guides/design-philosophy
```

```{toctree}
:maxdepth: 1
:caption: Maintainer design notes
:hidden:

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
architecture/DIALECT_SUPPORT
validation/PYDANTIC
validation/TYPE_SUPPORT
validation/VALIDATION_ERRORS
validation/PARTIAL_VALIDATION
rejection/REJECTION_POLICIES
rejection/REJECTION_HANDLING
rejection/DIAGNOSTICS
```

```{toctree}
:maxdepth: 1
:caption: Integrations (shipped)

integrations/CORE
integrations/ORM
integrations/SQLMODEL
integrations/WHY_NOT_SQLMODEL
```

```{toctree}
:maxdepth: 1
:caption: Future / design (not shipped)

integrations/REFLECTION
integrations/RAW_SQL
rejection/CALLBACKS
rejection/QUARANTINE
architecture/PLUGIN_SYSTEM
```

```{toctree}
:maxdepth: 1
:caption: Project

project/supported
project/changelog
project/roadmap
project/security
project/releasing
project/code-of-conduct
developer/CONTRIBUTING
developer/TESTING
developer/BENCHMARKS
developer/MILESTONES
developer/CURSOR_PROMPT
```
