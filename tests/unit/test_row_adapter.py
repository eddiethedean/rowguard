from __future__ import annotations

import pytest
from pydantic import BaseModel

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import RowAdaptationError


def test_adapter_accepts_mapping() -> None:
    row = {"id": 1}
    adapted = SQLAlchemyRowAdapter().adapt(row)
    assert adapted.mapping == row
    assert adapted.raw_row is row


def test_adapter_rejects_unknown_shape() -> None:
    with pytest.raises(RowAdaptationError):
        SQLAlchemyRowAdapter().adapt(object())


def test_adapter_applies_field_map() -> None:
    adapted = SQLAlchemyRowAdapter(field_map={"id": "user_id", "name": "display_name"}).adapt(
        {"user_id": 7, "display_name": "Ada", "extra": True}
    )
    assert adapted.mapping == {"id": 7, "name": "Ada", "extra": True}


class _FakeRow:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


def test_adapter_reads_sqlalchemy_mapping() -> None:
    adapted = SQLAlchemyRowAdapter().adapt(_FakeRow({"id": 1, "name": "Ada"}))
    assert dict(adapted.mapping) == {"id": 1, "name": "Ada"}


class UserRead(BaseModel):
    id: int
