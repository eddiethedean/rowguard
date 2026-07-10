from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.sql import ColumnElement


def build_select(source: object) -> Select[Any]:
    """Build a SELECT over a Core table or selectable."""
    return cast(Select[Any], select(source))  # type: ignore[call-overload]


def apply_where(statement: Select[Any], expressions: Iterable[object]) -> Select[Any]:
    """Return a new statement with additional WHERE expressions."""
    exprs = tuple(expressions)
    if not exprs:
        return statement
    return statement.where(*exprs)  # type: ignore[arg-type]


def is_select(value: object) -> bool:
    return isinstance(value, Select)


def is_column_element(value: object) -> bool:
    return isinstance(value, ColumnElement)
