"""Row adapter protocols and implementations."""

from rowguard.adapters.base import AdaptedRow, RowAdapter
from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter

__all__ = ["AdaptedRow", "RowAdapter", "SQLAlchemyRowAdapter"]
