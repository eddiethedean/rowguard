"""Adapt single ORM entities into Pydantic-ready mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rowguard.adapters.base import AdaptedRow
from rowguard.errors import RowAdaptationError
from rowguard.integrations.sqlalchemy_orm import (
    entity_source_identity,
    extract_entity,
    is_orm_instance,
    is_relationship_attr,
    unloaded_attribute_names,
)


class ORMEntityAdapter:
    """Extract planned scalar attributes from a single ORM entity.

    Never traverses relationships. Unloaded or deferred attributes raise
    ``RowAdaptationError`` when ``unloaded_attributes=\"error\"`` (the only
    supported policy in 0.5).
    """

    def __init__(
        self,
        *,
        attribute_keys: Sequence[str],
        attribute_map: Mapping[str, str] | None = None,
        mapped_class: type[object] | None = None,
        unloaded_attributes: str = "error",
        orm_validation: str = "mapping",
    ) -> None:
        if unloaded_attributes != "error":
            raise ValueError(
                "unloaded_attributes must be 'error' in RowGuard 0.5 "
                f"(got {unloaded_attributes!r})"
            )
        self._attribute_keys = tuple(attribute_keys)
        self._attribute_map = dict(attribute_map) if attribute_map else None
        self._mapped_class = mapped_class
        self._unloaded_attributes = unloaded_attributes
        self._orm_validation = orm_validation

    def adapt(self, row: object) -> AdaptedRow:
        entity = extract_entity(row)
        if entity is None:
            if is_orm_instance(row):
                entity = row
            else:
                raise RowAdaptationError(
                    "Expected a single ORM entity row; got "
                    f"{type(row).__name__}. Multi-entity or entity+scalar "
                    "results are not supported — use an explicit projection."
                )

        mapped_class = self._mapped_class or type(entity)
        planned = self._planned_attributes()

        for attr_name in planned.values():
            if is_relationship_attr(mapped_class, attr_name):
                raise RowAdaptationError(
                    f"Refusing to traverse ORM relationship {attr_name!r}. "
                    "Use an explicit projection or nested adapter instead."
                )

        unloaded = unloaded_attribute_names(entity) & set(planned.values())
        if unloaded:
            names = ", ".join(sorted(unloaded))
            raise RowAdaptationError(
                f"ORM entity has unloaded attributes: {names}. "
                "Load them in the query, use a column projection, or avoid "
                "expired/deferred attributes during validation."
            )

        mapping: dict[str, object] = {}
        for field_name, attr_name in planned.items():
            mapping[field_name] = getattr(entity, attr_name)

        identity = entity_source_identity(entity)
        attributes_subject = entity if self._orm_validation == "from_attributes" else None
        return AdaptedRow(
            mapping=mapping,
            raw_row=row,
            source_identity=identity,
            attributes_subject=attributes_subject,
        )

    def _planned_attributes(self) -> dict[str, str]:
        """Return model-field → entity-attribute mapping."""
        if self._attribute_map is not None:
            return dict(self._attribute_map)
        return {name: name for name in self._attribute_keys}
