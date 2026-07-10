"""SQLModel detection helpers.

SQLModel remains responsible for mapping and persistence. RowGuard treats
SQLModel table models as ORM-mapped sources for validation-first reads.
"""

from __future__ import annotations

from typing import Any

from rowguard.integrations.sqlalchemy_orm import is_mapped_class, mapped_columns, mapped_table


def is_sqlmodel_table(value: object) -> bool:
    """Return True if *value* is a SQLModel class with ``table=True``."""
    if not isinstance(value, type):
        return False
    try:
        from sqlmodel import SQLModel
    except ImportError:
        return False
    if not issubclass(value, SQLModel):
        return False
    # table=True models are SQLAlchemy-mapped and expose __table__.
    return is_mapped_class(value) and getattr(value, "__table__", None) is not None


def sqlmodel_columns(model: type[Any]) -> dict[str, Any]:
    """Return column mapping for a SQLModel table class."""
    return mapped_columns(model)


def sqlmodel_table(model: type[Any]) -> Any:
    """Return the underlying SQLAlchemy Table for a SQLModel table class."""
    return mapped_table(model)


__all__ = [
    "is_sqlmodel_table",
    "sqlmodel_columns",
    "sqlmodel_table",
]
