# DIALECT_SUPPORT.md

# RowGuard Dialect Support

## Purpose

This document defines how RowGuard supports different SQL database dialects
without becoming a SQL generator or duplicating SQLAlchemy's dialect system.

RowGuard is designed to be dialect-neutral at its core.

The responsibility boundary is:

- SQLAlchemy owns SQL rendering, parameter styles, identifier quoting, driver
  integration, and database execution.
- SQLRules owns dialect-specific translation of supported Pydantic constraints
  into SQLAlchemy expressions.
- RowGuard owns planning, execution, row adaptation, Pydantic validation,
  rejection handling, diagnostics, and results.

---

# Core Principle

```text
Pydantic Model
      │
      ▼
SQLRules
Constraint-to-expression translation
      │
      ▼
SQLAlchemy
Dialect-aware SQL rendering and execution
      │
      ▼
Database
      │
      ▼
RowGuard
Row adaptation and Pydantic validation
```

RowGuard should never generate backend-specific SQL strings when SQLAlchemy can
represent the operation.

---

# Goals

Dialect support should:

- Preserve a portable RowGuard core.
- Work with SQLAlchemy-supported databases.
- Make backend differences explicit.
- Allow dialect-specific SQLRules plugins.
- Preserve identical post-query validation semantics.
- Document driver-returned Python types.
- Test actual execution behavior across major databases.
- Avoid hidden fallback behavior.
- Keep backend-specific dependencies optional.

---

# Non-Goals

RowGuard does not:

- Implement SQL dialect compilers.
- Replace SQLAlchemy dialects.
- Normalize every backend into identical SQL behavior.
- Emulate unsupported database features in Python automatically.
- Rewrite arbitrary raw SQL.
- Guarantee identical query plans across databases.
- Hide driver-specific value types.
- Infer database capabilities from product names alone.
- Ship every database driver as a core dependency.

---

# Support Levels

RowGuard should describe dialect support using clear levels.

## Tier 1 — Fully Tested

A Tier 1 dialect has:

- Continuous integration coverage.
- Buffered execution tests.
- Streaming tests.
- SQLRules integration tests.
- Core and ORM tests where supported.
- Documented driver combinations.
- Type round-trip tests.
- Rejection-policy tests.
- Supported production guidance.

## Tier 2 — Supported

A Tier 2 dialect is expected to work through SQLAlchemy but may have a smaller
test matrix.

It should have:

- Basic integration tests.
- Core query tests.
- Pydantic validation tests.
- Documented limitations.

## Tier 3 — Community / Experimental

A Tier 3 dialect may work through SQLAlchemy but is not fully verified by the
RowGuard project.

Users should expect:

- Limited testing.
- Driver-specific behavior.
- Community-maintained guidance.
- Potential plugin requirements.

---

# Initial Dialect Targets

Recommended initial support:

| Dialect | Target Level | Primary Role |
| --- | :---: | --- |
| SQLite | Tier 1 | Local development and CI |
| PostgreSQL | Tier 1 | Primary production reference |
| MySQL | Tier 2 | Common production backend |
| MariaDB | Tier 2 | MySQL-compatible production backend |
| SQL Server | Tier 2 | Enterprise backend |
| Oracle | Tier 3 initially | Enterprise backend |
| DuckDB | Tier 2 or experimental | Analytics and local data workflows |

Support levels should be based on actual automated testing, not aspiration.

---

# Driver Matrix

Dialect support is partly driver support.

Different drivers may return different Python value types and expose different
streaming or async behavior.

The documentation should track combinations such as:

```text
PostgreSQL
  - psycopg
  - asyncpg

SQLite
  - sqlite3
  - aiosqlite

MySQL / MariaDB
  - mysqlclient
  - PyMySQL
  - asyncmy
  - aiomysql

SQL Server
  - pyodbc
  - aioodbc where applicable

Oracle
  - python-oracledb
```

RowGuard should test supported dialect/driver pairs explicitly.

---

# Portable Core Features

The following RowGuard capabilities should be portable when SQLAlchemy supports
the underlying database operation:

- Existing `Select` execution.
- Table-based queries.
- Bound parameters.
- Basic WHERE predicates.
- Ordering.
- Limit and offset.
- Inner joins.
- Labeled result columns.
- Row mapping adaptation.
- Pydantic validation.
- Rejection policies.
- Buffered execution.
- Streaming where the driver supports it.
- ORM projected-column queries.
- SQLRules portable constraint pushdown.

---

# Portable SQLRules Constraints

Portable SQLRules translations may include:

- Greater than.
- Greater than or equal.
- Less than.
- Less than or equal.
- Literal membership.
- Enum membership.
- Minimum length.
- Maximum length.
- Basic modulo-based `multiple_of`, subject to numeric semantics.

Even portable-looking constraints can differ by backend.

Examples:

- String length semantics.
- Floating-point modulo.
- Collation.
- Enum storage.
- Date comparison.
- Null behavior.

Pydantic validation remains mandatory.

---

# Dialect-Specific SQLRules Extensions

Dialect-specific predicate support belongs in SQLRules plugins.

Potential packages:

```text
sqlrules-postgresql
sqlrules-sqlite
sqlrules-mysql
sqlrules-mssql
sqlrules-oracle
sqlrules-duckdb
```

Potential features:

- Regular expressions.
- JSON operators.
- Array operators.
- Range operators.
- Full-text search predicates.
- Geospatial predicates.
- Database-native enum behavior.
- Backend-specific date/time operations.

RowGuard consumes the compiled SQLAlchemy expressions through SQLRules' public
API.

---

# RowGuard Dialect Plugins

RowGuard dialect plugins should not compile Pydantic constraints.

They may provide:

- Capability detection.
- Row adapters for driver-specific values.
- Streaming configuration.
- Type-normalization adapters when explicitly enabled.
- Quarantine providers using backend-native features.
- Pushdown safety policies.
- Diagnostics.
- Reflection helpers.
- Backend-specific integration tests.

The boundary remains:

> SQLRules translates validation constraints; RowGuard dialect extensions adapt
> execution and result behavior.

---

# Capability Model

RowGuard should represent backend capabilities explicitly.

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class DialectCapabilities:
    dialect_name: str
    driver_name: str | None
    async_supported: bool
    server_side_streaming: bool
    native_json: bool
    native_arrays: bool
    native_uuid: bool
    native_enum: bool
    native_interval: bool
    returning_supported: bool
    regexp_support: bool
    reflection_supported: bool
```

Capabilities should be descriptive.

They should not imply that RowGuard uses every feature automatically.

---

# Capability Detection

Capability detection may use:

- SQLAlchemy dialect metadata.
- Driver identity.
- Explicit plugin declarations.
- User overrides.
- Database version when already available.

RowGuard should avoid issuing capability-probing queries during normal planning
unless the feature explicitly requires it.

Potential API:

```python
dialect_profile = rowguard.inspect_dialect(engine)
```

This may be a separate explicit operation.

---

# User Overrides

Applications may need to override capabilities due to:

- Database extensions.
- Restricted permissions.
- Custom driver configuration.
- Proxy layers.
- Hosted database limitations.

Example:

```python
DialectOverrides(
    regexp_support=False,
    server_side_streaming=True,
)
```

Overrides should be recorded in diagnostics.

---

# SQLite

SQLite is ideal for:

- Local development.
- Unit tests.
- Lightweight applications.
- CI.

Important considerations:

- Dynamic typing can allow inconsistent stored values.
- Boolean values are often represented numerically.
- Date/time behavior depends on column and driver configuration.
- Regular expressions are not available by default without an extension.
- JSON support depends on SQLite build features and SQLAlchemy usage.
- In-memory database connection scope matters.
- Limited concurrency affects some integration tests.

RowGuard is especially useful with SQLite because weak storage typing may allow
values that violate application Pydantic contracts.

---

# SQLite In-Memory Databases

An in-memory SQLite database usually exists per connection.

Tests must manage:

- Connection pooling.
- Shared connection configuration.
- Transaction boundaries.
- Async adapter behavior.

RowGuard itself should not special-case in-memory lifetime, but its test
utilities may provide safe fixtures.

---

# SQLite Type Behavior

SQLite may return values according to:

- Declared affinity.
- Inserted value.
- SQLAlchemy type configuration.
- Driver converters.

Tests should include values inserted through raw SQL to verify RowGuard catches
legacy or weakly typed records.

---

# SQLite Streaming

SQLite drivers may not offer server-side cursors in the same sense as client-
server databases.

RowGuard can still iterate results incrementally, but memory and fetch behavior
may differ.

Documentation should avoid promising identical streaming internals across
dialects.

---

# PostgreSQL

PostgreSQL is the recommended primary production reference dialect.

Strengths include:

- Strong type system.
- Native UUID.
- Native JSON and JSONB.
- Arrays.
- Ranges.
- Enums.
- Intervals.
- Server-side cursor support through appropriate SQLAlchemy patterns.
- Rich operator ecosystem.

Potential SQLRules plugins may support:

- Regex operators.
- JSONB containment.
- Array containment.
- Range predicates.
- Full-text search.
- Case-insensitive matching.

RowGuard should still validate all returned values with Pydantic.

---

# PostgreSQL JSON

PostgreSQL JSON/JSONB values typically arrive as Python mappings, lists, and
scalars through supported drivers.

RowGuard can pass these directly to Pydantic.

Potential concerns:

- Decimal vs float inside decoded JSON.
- Large payloads.
- Custom JSON serializers.
- Driver configuration.
- JSON null vs SQL null.

These behaviors should be covered by driver-specific tests.

---

# PostgreSQL Arrays

Array values may arrive as Python lists.

Pydantic may validate them into:

- Lists.
- Tuples.
- Sets.
- Nested types.
- Custom models.

Array predicate pushdown belongs in a PostgreSQL SQLRules plugin.

---

# PostgreSQL Enums

Native enums may arrive as:

- Strings.
- Python enum members when custom type configuration is used.
- Driver-specific representations.

The Pydantic target remains authoritative.

RowGuard should not guess whether the database stores enum names or values.

---

# PostgreSQL Timezones

PostgreSQL distinguishes timestamp types with and without time zone.

Driver behavior and SQLAlchemy type configuration determine returned Python
datetimes.

RowGuard does not normalize timezone awareness.

Pydantic validators should express application requirements.

---

# MySQL and MariaDB

MySQL and MariaDB support common RowGuard workflows through SQLAlchemy.

Important considerations:

- SQL mode can affect data acceptance and coercion.
- Boolean columns may be represented as small integers.
- JSON support depends on version and backend.
- String comparison depends on collation.
- Invalid date behavior varies by mode and version.
- Streaming support depends on driver.
- Decimal behavior should be tested carefully.
- Native enum and set types have backend-specific semantics.

RowGuard diagnostics should record dialect and driver.

---

# MySQL SQL Modes

Server SQL modes can change:

- Strictness.
- Invalid date acceptance.
- Truncation behavior.
- Division behavior.
- Grouping semantics.

RowGuard should not attempt to infer application guarantees from the dialect
alone.

Pydantic validation provides a consistent application-side contract after
retrieval.

---

# MySQL Collations

Case sensitivity and comparison behavior depend on collation.

A SQLRules string predicate may admit or reject a different set of values than a
Python validator.

Conservative pushdown policy is especially important.

---

# SQL Server

SQL Server support should build on SQLAlchemy and supported ODBC drivers.

Important considerations:

- Driver configuration.
- Unicode string types.
- Decimal precision.
- `uniqueidentifier` mapping.
- Date/time variants.
- JSON represented through text functions rather than a native JSON type.
- Offset/limit rendering.
- Server cursor behavior.
- `BIT` boolean handling.

RowGuard should test actual result types returned by supported drivers.

---

# SQL Server UUID Values

`uniqueidentifier` columns may return strings or UUID-compatible values depending
on driver and SQLAlchemy configuration.

Pydantic validates the final target type.

RowGuard should not normalize the representation before validation.

---

# SQL Server Date/Time Types

SQL Server exposes multiple temporal types with different precision and timezone
semantics.

Tests should cover:

- `date`
- `time`
- `datetime`
- `datetime2`
- `datetimeoffset`

RowGuard should preserve driver-returned values.

---

# Oracle

Oracle support may initially be community or experimental.

Important considerations:

- Driver-specific numeric behavior.
- Empty string and null semantics.
- LOB handling.
- Date and timestamp types.
- Interval types.
- Identifier casing.
- Fetch arrays and cursor configuration.
- JSON capabilities by server version.
- Reflection differences.

Large objects may require explicit materialization before Pydantic validation.

---

# Oracle Empty String Semantics

Oracle commonly treats empty strings as null in SQL string contexts.

This can differ from Pydantic's distinction between:

```python
""
```

and:

```python
None
```

Applications should account for this explicitly in read contracts and tests.

RowGuard cannot restore a distinction the database does not preserve.

---

# DuckDB

DuckDB is useful for:

- Local analytics.
- Embedded workloads.
- Parquet-backed queries.
- Data engineering.
- Testing analytical result shapes.

Important considerations:

- Nested structures.
- Lists and structs.
- Arrow integration.
- Decimal behavior.
- Timestamp variants.
- Driver-specific result representations.

DuckDB may become a strong optional integration target for RowGuard's ETL use
cases.

---

# Other SQLAlchemy Dialects

RowGuard may work with additional SQLAlchemy dialects such as:

- CockroachDB.
- Snowflake.
- BigQuery.
- Redshift.
- Databricks SQL.
- Trino.
- ClickHouse through third-party dialects.
- Firebird.
- IBM Db2.

Support depends on:

- SQLAlchemy dialect quality.
- Driver behavior.
- Result-row compatibility.
- Streaming support.
- Type mappings.
- Community testing.

RowGuard should not claim official support without a maintained test matrix.

---

# Cloud and Warehouse Dialects

Cloud warehouses often differ from transactional databases.

Potential concerns:

- High query latency.
- Large result sets.
- Arrow-native results.
- Asynchronous job execution.
- Limited transactions.
- Driver-specific polling.
- Large nested types.
- Cost per query.
- Server-side result staging.

These systems may require dedicated source resolvers or execution adapters.

They should not force complexity into RowGuard core.

---

# Type Differences Across Dialects

The same logical SQL type may arrive differently.

Examples:

| Logical Type | Possible Python Values |
| --- | --- |
| Boolean | `bool`, `int` |
| UUID | `UUID`, `str`, `bytes` |
| JSON | `dict`, `list`, `str`, custom wrapper |
| Decimal | `Decimal`, `float`, custom numeric |
| Date/time | native types, strings |
| Interval | `timedelta`, string, custom object |
| Binary | `bytes`, `memoryview`, LOB handle |

RowGuard preserves the value and delegates validation to Pydantic unless an
explicit adapter is configured.

---

# Driver-Specific Row Adapters

A dialect/driver plugin may provide adapters for values such as:

- Oracle LOBs.
- PostgreSQL ranges.
- Geometry objects.
- Warehouse-specific structs.
- Arrow values.
- Driver-specific intervals.

Adapters must be explicit about:

- Whether they perform I/O.
- Whether they allocate.
- Whether they preserve raw values.
- Whether they change semantics.
- Sync/async support.

---

# String Length Semantics

SQL length functions may count:

- Characters.
- Code points.
- Bytes.
- Backend-specific units.

Pydantic string length is based on Python string behavior.

SQLRules translators should classify whether a backend's length predicate is
exact or conservative.

RowGuard should preserve translation diagnostics.

---

# Collation and Case Sensitivity

Database collations affect:

- Equality.
- Ordering.
- Pattern matching.
- Case sensitivity.
- Accent sensitivity.

Pydantic validates returned strings in Python and does not apply database
collation semantics automatically.

SQL pushdown involving text must remain conservative and dialect-aware.

---

# Null Semantics

SQL uses three-valued logic.

Pydantic receives Python `None`.

A SQL predicate involving null may behave differently from ordinary Python
boolean logic.

RowGuard should not infer null predicates from Pydantic optionality.

Explicit null-related rules belong in SQLRules or user-authored filters.

---

# Numeric Semantics

Potential dialect differences include:

- Integer overflow.
- Decimal precision and scale.
- Float special values.
- Modulo behavior.
- Division behavior.
- Implicit numeric casts.

SQLRules numeric pushdown should use SQLAlchemy expressions and dialect-aware
tests.

Pydantic remains the final check.

---

# Date and Time Semantics

Potential differences include:

- Timezone storage.
- Fractional-second precision.
- Session timezone.
- Driver conversion.
- Date truncation.
- Invalid date acceptance.
- Interval representation.

RowGuard should not normalize temporal values outside explicit adapters or
validators.

---

# Enum Semantics

Enum storage may be:

- Native enum.
- String value.
- String name.
- Integer.
- Check-constrained text.

SQLRules membership pushdown must align with the actual stored representation.

RowGuard's field mapping and Pydantic target must remain explicit.

---

# JSON Semantics

JSON support varies widely.

Differences include:

- Native type vs text.
- Null handling.
- Number decoding.
- Key ordering.
- Duplicate keys.
- Path syntax.
- Containment operators.
- Index support.

RowGuard validation supports JSON-like Python values regardless of whether
pushdown is available.

---

# Regular Expressions

Regex syntax and availability vary significantly.

Examples:

- PostgreSQL native regex operators.
- MySQL regex functions/operators.
- SQLite extension-defined behavior.
- SQL Server pattern alternatives.
- Oracle regex functions.

Regex pushdown should not be part of RowGuard core.

It belongs in SQLRules dialect plugins with documented semantic limits.

---

# Streaming Differences

Streaming behavior depends on:

- Dialect.
- Driver.
- SQLAlchemy execution options.
- Server-side cursor support.
- Fetch buffer configuration.
- Transaction lifetime.

RowGuard should expose one streaming abstraction while documenting that backend
resource behavior differs.

Capabilities should report whether server-side streaming is supported.

---

# Async Differences

Async support depends on SQLAlchemy's async-capable dialect/driver combinations.

RowGuard should not simulate async by running synchronous drivers in a hidden
thread pool by default.

Supported async combinations must be tested explicitly.

---

# Reflection Differences

SQLAlchemy reflection support varies by backend.

Differences may include:

- View metadata.
- Computed columns.
- Identity columns.
- Enum reflection.
- Check constraints.
- Schema names.
- Case folding.
- Temporary tables.

RowGuard consumes reflected objects but does not normalize all reflection
differences.

---

# Raw SQL Differences

Raw SQL is dialect-specific by definition.

RowGuard:

- Executes through SQLAlchemy `text()`.
- Preserves bound parameters.
- Disables automatic SQLRules pushdown by default.
- Validates returned mappings with Pydantic.
- Does not rewrite SQL text.

Applications remain responsible for backend-specific SQL syntax.

---

# Transaction Differences

Read transaction behavior varies.

Examples:

- Autocommit defaults.
- Snapshot behavior.
- Server-side cursor transaction requirements.
- Read-only transactions.
- Isolation levels.
- DDL transaction behavior.
- Quarantine write compatibility.

RowGuard preserves caller-owned transaction configuration.

It does not impose a cross-dialect transaction model.

---

# Quarantine Dialect Considerations

A SQL-backed quarantine provider may use a different dialect from the source.

Recommended default:

- Separate engine.
- Separate transaction.
- Portable storage schema.
- JSON-safe serialized payloads.

Dialect-specific quarantine providers may use:

- Native JSON.
- Bulk insert.
- Copy APIs.
- Table-valued parameters.
- Array binding.

These optimizations belong in provider plugins.

---

# Dialect Diagnostics

Every execution should be able to report:

- SQLAlchemy dialect name.
- Driver name.
- Server version when already known.
- Capability profile.
- SQLRules dialect plugin used.
- Pushdown features applied.
- Streaming mode.
- Result adapter selected.
- User capability overrides.

Diagnostics should avoid issuing extra queries merely to collect metadata.

---

# Dialect Profile

Suggested structure:

```python
@dataclass(frozen=True, slots=True)
class DialectProfile:
    name: str
    driver: str | None
    server_version: tuple[int, ...] | None
    capabilities: DialectCapabilities
    sqlrules_plugin: str | None
    rowguard_plugins: tuple[str, ...]
    overrides: Mapping[str, object]
```

The profile may be attached to the execution plan.

---

# Strict Dialect Mode

Potential option:

```python
dialect_policy="portable"
dialect_policy="native"
dialect_policy="strict"
```

## portable

Use only portable, exact features.

Recommended default.

## native

Allow registered dialect-specific SQLRules and RowGuard plugins.

## strict

Fail planning when required dialect capabilities or plugins are unavailable.

This can be useful for applications depending on backend-native behavior.

---

# Fallback Behavior

Fallbacks must be explicit.

Examples:

- Unsupported regex pushdown → validate in Pydantic.
- Unsupported server-side streaming → client-side iteration with diagnostic.
- Unsupported native JSON adapter → use driver-returned value.
- Missing dialect plugin → portable mode or planning error based on policy.

RowGuard should never silently change acceptance semantics.

---

# Version-Specific Features

Some database features depend on server version.

Plugins should declare:

- Minimum server version.
- Tested versions.
- Fallback behavior.
- Capability detection method.

If the server version is unknown, conservative behavior is preferred.

---

# Optional Dependencies

Dialect and driver packages should remain optional.

Examples:

```bash
pip install rowguard[postgresql]
pip install rowguard[sqlite]
pip install rowguard[mysql]
pip install rowguard[mssql]
pip install rowguard[oracle]
pip install rowguard[duckdb]
```

SQLRules dialect plugins may have their own extras or packages.

Core RowGuard should install without database drivers.

---

# Plugin Registration

Example:

```python
guard = RowGuard(
    dialect_plugins=[
        PostgreSQLRowGuardPlugin(),
    ],
)
```

SQLRules plugin:

```python
rules_registry.register(
    PostgreSQLSQLRulesPlugin(),
)
```

The two plugins have separate responsibilities.

---

# Compatibility Validation

During planning, RowGuard should verify:

- Dialect plugin matches active dialect.
- Driver is supported by the plugin.
- Async mode is supported.
- Streaming capability exists when required.
- Result adapter supports driver-returned values.
- SQLRules translation safety level matches policy.
- Quarantine provider transaction mode is compatible.

Failures should occur before large queries begin.

---

# Error Hierarchy

Suggested dialect errors:

```text
RowGuardError
└── DialectSupportError
    ├── UnsupportedDialectError
    ├── UnsupportedDriverError
    ├── DialectCapabilityError
    ├── DialectPluginMismatchError
    ├── DialectVersionError
    ├── StreamingNotSupportedError
    ├── AsyncDialectNotSupportedError
    └── DialectConfigurationError
```

SQLAlchemy and driver exceptions remain available as causes.

---

# Testing Strategy

Dialect support requires both compilation and execution tests.

## Unit Tests

- Capability profiles.
- Plugin selection.
- Fallback decisions.
- Version checks.
- Configuration errors.

## SQL Compilation Tests

- Portable predicates.
- Dialect-specific SQLRules expressions.
- Bound parameters.
- Identifier quoting.

## Integration Tests

- Real database execution.
- Driver-returned types.
- Nulls.
- Dates and times.
- Decimal.
- UUID.
- JSON.
- Enum.
- Streaming.
- Async.
- Reflection.
- ORM projections.
- Rejection handling.
- Quarantine provider behavior.

---

# Containerized Test Matrix

CI may use containers for:

- PostgreSQL.
- MySQL.
- MariaDB.
- SQL Server where licensing and CI support permit.
- Oracle Free where practical.

SQLite and DuckDB can run in-process.

Large dialect matrices may run on scheduled or release workflows.

---

# Golden Behavior Tests

The same logical dataset and Pydantic model should be tested across dialects.

Compare:

- Accepted model count.
- Rejected row count.
- Error categories.
- Pushdown diagnostics.
- Driver-returned values.
- Ordering where deterministic.

SQL strings need not be identical.

Application-visible validation outcomes should match where source semantics are
equivalent.

---

# Dialect Documentation Requirements

Each officially supported dialect should document:

- Supported drivers.
- Supported server versions.
- Sync support.
- Async support.
- Streaming behavior.
- Type-return notes.
- SQLRules plugin features.
- Known semantic differences.
- Reflection limitations.
- Raw SQL guidance.
- Test coverage level.
- Optional dependency installation.

---

# MVP Scope

The first RowGuard dialect architecture should include:

- Dialect-neutral core.
- SQLite Tier 1 support.
- PostgreSQL Tier 1 support.
- MySQL/MariaDB basic support.
- SQL Server basic support.
- Dialect profile and capability model.
- Explicit driver diagnostics.
- Portable pushdown policy.
- Optional dialect plugin registration.
- Cross-dialect type tests.
- Streaming capability diagnostics.
- No automatic SQL generation outside SQLAlchemy.

Near-term additions:

- DuckDB integration.
- Async driver matrix.
- PostgreSQL result adapters.
- SQL Server and Oracle driver-specific adapters.
- Official quarantine provider optimizations.
- Native-mode pushdown policy.
- Version-specific capability profiles.

Deferred:

- Automatic installation of drivers.
- Full support for every SQLAlchemy dialect.
- Query-plan normalization across databases.
- Automatic SQL feature emulation.
- Arbitrary raw SQL translation.
- Hidden fallback to Python-side query filtering.
- Cost-based dialect optimization.
- Universal driver-type canonicalization.

---

# Recommended Configuration Examples

## Portable Mode

```python
guard = RowGuard(
    dialect_policy="portable",
)
```

## PostgreSQL Native Mode

```python
guard = RowGuard(
    dialect_policy="native",
    dialect_plugins=[
        PostgreSQLRowGuardPlugin(),
    ],
)
```

## Strict Capability Requirement

```python
result = guard.stream(
    session=session,
    table=events,
    model=EventRead,
    require_capabilities={
        "server_side_streaming": True,
        "native_json": True,
    },
)
```

## Explicit Override

```python
guard = RowGuard(
    dialect_overrides=DialectOverrides(
        regexp_support=False,
    ),
)
```

---

# Design Principles

- SQLAlchemy owns dialect rendering and execution.
- SQLRules owns dialect-specific constraint translation.
- RowGuard remains portable by default.
- Driver behavior is part of dialect support.
- Post-query Pydantic validation is always authoritative.
- Backend differences must be visible in diagnostics.
- Fallbacks are explicit.
- Conservative semantics are preferred.
- Optional drivers and plugins stay outside core dependencies.
- Official support claims require real integration tests.
