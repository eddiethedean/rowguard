# WHY_NOT_SQLMODEL.md

# Why RowGuard Is Not SQLModel

## Purpose

This document explains the relationship between RowGuard and SQLModel.

RowGuard is **not** a replacement for SQLModel. The two libraries solve
different problems and are designed to work together.

The motivation for RowGuard comes from a gap that appears in many production
applications:

> Data may already exist in a database that no longer satisfies the Pydantic
> model the application expects.

SQLModel validates objects that *it constructs*. RowGuard validates the rows
*returned by arbitrary SQLAlchemy queries*, regardless of how those rows entered
the database.

---

# Different Responsibilities

| SQLModel | RowGuard |
| --- | --- |
| ORM + data model | Query validation layer |
| Defines tables | Consumes tables |
| Persists data | Reads data |
| Uses SQLAlchemy | Builds on SQLAlchemy |
| Uses Pydantic | Uses Pydantic |
| Validates application-created objects | Validates database-returned rows |
| CRUD-oriented | Read/query-oriented |

These responsibilities complement one another.

---

# The Long-Standing Gap

Consider a read model:

```python
class UserRead(BaseModel):
    id: int
    age: Annotated[int, Field(ge=18)]
```

Suppose legacy data exists:

```text
id=1
age=12
```

A plain SQLAlchemy or SQLModel query may successfully return this row because
the database is not required to enforce the application's Pydantic constraints.

The application now receives data that violates its own contract.

RowGuard inserts a validation step after the query:

```text
Database
   ↓
SQLAlchemy
   ↓
RowGuard
   ↓
Pydantic
   ↓
Accepted or Rejected
```

---

# SQLModel Already Validates...

Yes—but it validates objects during normal construction and persistence.

RowGuard addresses a different question:

> "Does every row returned by this query still satisfy the model I expect?"

That question becomes important when:

- legacy data exists
- multiple applications write to the same database
- migrations were incomplete
- raw SQL modified data
- ETL pipelines bypassed validation
- manual fixes occurred
- constraints changed over time

---

# Query Validation vs Persistence Validation

Persistence validation answers:

> "Can I write this object?"

RowGuard answers:

> "Can I trust what I just read?"

Those are different guarantees.

---

# Why Not Just Call `model_validate()` Yourself?

You can.

For small applications:

```python
rows = session.execute(stmt).mappings()

models = [
    UserRead.model_validate(r)
    for r in rows
]
```

RowGuard standardizes and extends this pattern with:

- SQLRules pushdown
- typed results
- rejected-row handling
- streaming
- async support
- diagnostics
- statistics
- quarantine
- callbacks
- plugin system
- planning
- caching

---

# SQLRules + RowGuard

SQLRules attempts to reduce the number of candidate rows sent back from the
database.

RowGuard **still validates every returned row with Pydantic**.

Pushdown is an optimization—not a replacement for validation.

---

# Why Not Put This Into SQLModel?

Keeping RowGuard separate has several advantages.

## Works With Plain SQLAlchemy

Many applications intentionally avoid SQLModel.

RowGuard works directly with SQLAlchemy Core and ORM.

## Multiple Read Models

One table may have many read contracts.

Examples:

- Public API
- Internal API
- Analytics
- Admin
- ETL

RowGuard validates against whichever model the query requests.

## Existing Projects

Large SQLAlchemy projects can adopt RowGuard without migrating to SQLModel.

## Separation of Concerns

SQLModel focuses on modeling and persistence.

RowGuard focuses on query correctness.

---

# Complementary Example

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
```

Later:

```python
class PublicUser(BaseModel):
    id: int
    name: Annotated[str, Field(min_length=3)]
```

Query:

```python
result = rowguard.select(
    session=session,
    statement=select(User),
    model=PublicUser,
)
```

SQLModel manages persistence.

RowGuard validates the returned data against the API contract.

---

# What RowGuard Does Not Replace

RowGuard does not replace:

- SQLModel tables
- SQLAlchemy ORM
- Sessions
- Migrations
- Relationships
- Identity map
- Persistence
- Unit of work

It simply validates query results.

---

# Choosing Between Them

Use SQLModel when you want:

- ORM models
- table definitions
- CRUD applications
- simple persistence

Use RowGuard when you need:

- validated query results
- rejected-row handling
- SQLRules pushdown
- streaming validation
- diagnostics
- data-quality auditing

Many applications will use both.

---

# Design Principles

- SQLModel and RowGuard solve different problems.
- RowGuard builds on SQLAlchemy rather than replacing it.
- Every accepted row should satisfy the requested Pydantic model.
- Validation after a query is a distinct capability from validation before a write.
- SQLRules optimizes reads; Pydantic remains the source of truth.
