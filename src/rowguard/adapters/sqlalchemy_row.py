from __future__ import annotations

from collections.abc import Mapping

from rowguard.adapters.base import AdaptedRow
from rowguard.errors import RowAdaptationError


class SQLAlchemyRowAdapter:
    """Adapt SQLAlchemy rows or mappings into Pydantic-ready dictionaries."""

    def __init__(self, field_map: Mapping[str, str] | None = None) -> None:
        self._field_map = dict(field_map) if field_map else None

    def adapt(self, row: object) -> AdaptedRow:
        source = getattr(row, "_mapping", None)
        if source is None:
            if isinstance(row, Mapping):
                source = row
            else:
                raise RowAdaptationError(f"Unsupported row type: {type(row).__name__}")

        mapping: dict[str, object] = dict(source)
        if self._field_map is not None:
            remapped: dict[str, object] = {}
            for field_name, column_key in self._field_map.items():
                if column_key in mapping:
                    remapped[field_name] = mapping[column_key]
            # Preserve unmapped keys so Pydantic can apply extras/defaults policy.
            for key, value in mapping.items():
                if key not in remapped and key not in self._field_map.values():
                    remapped[key] = value
            mapping = remapped

        return AdaptedRow(mapping=mapping, raw_row=row)
