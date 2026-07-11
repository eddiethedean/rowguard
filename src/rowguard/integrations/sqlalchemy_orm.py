"""SQLAlchemy ORM detection and metadata helpers for planning and adaptation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from sqlalchemy import Column
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import InstanceState, Mapper, Synonym
from sqlalchemy.sql import Select

ResultShape = Literal["entity", "projection", "unsupported"]


def is_mapped_class(value: object) -> bool:
    """Return True if *value* is a SQLAlchemy ORM mapped class."""
    if not isinstance(value, type):
        return False
    try:
        mapper: Mapper[Any] | None = sa_inspect(value, raiseerr=False)
    except Exception:
        return False
    return isinstance(mapper, Mapper)


def is_orm_instance(value: object) -> bool:
    """Return True if *value* is an instance of a mapped class."""
    if value is None or isinstance(value, type):
        return False
    try:
        state = sa_inspect(value, raiseerr=False)
    except Exception:
        return False
    return isinstance(state, InstanceState)


def mapped_table(mapped: type[Any]) -> Any:
    """Return the primary ``Table`` for a mapped class."""
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    return mapper.local_table


def mapped_columns(mapped: type[Any]) -> dict[str, Column[Any]]:
    """Return ``{column_key: Column}`` for all mapper columns (incl. inherited)."""
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    columns: dict[str, Column[Any]] = {}
    for column in mapper.columns:
        columns[column.key] = column
    return columns


def mapped_column_attr_keys(mapped: type[Any]) -> tuple[str, ...]:
    """Return mapper column attribute keys (scalar persistence attributes)."""
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    return tuple(mapper.column_attrs.keys())


def synonym_target(mapped: type[Any], attr_name: str) -> str | None:
    """Return the underlying attribute name for a synonym, else None."""
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    try:
        prop = mapper.attrs[attr_name]
    except KeyError:
        return None
    if isinstance(prop, Synonym):
        return prop.name
    return None


def scalar_attr_keys(mapped: type[Any]) -> set[str]:
    """Column attrs plus synonym keys that proxy column attrs."""
    keys = set(mapped_column_attr_keys(mapped))
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    for key, prop in mapper.attrs.items():
        if isinstance(prop, Synonym) and prop.name in keys:
            keys.add(key)
    return keys


def is_relationship_attr(mapped: type[Any], attr_name: str) -> bool:
    mapper = cast(Mapper[Any], sa_inspect(mapped))
    return attr_name in mapper.relationships


def classify_select_shape(statement: Select[Any]) -> ResultShape:
    """Classify a Select as single-entity, scalar projection, or unsupported."""
    descriptions = list(statement.column_descriptions)
    entity_descs = [
        desc
        for desc in descriptions
        if is_mapped_class(desc.get("expr")) or is_mapped_class(desc.get("type"))
    ]
    if len(entity_descs) == 1 and len(descriptions) == 1:
        return "entity"
    if not entity_descs:
        return "projection"
    return "unsupported"


def single_entity_class(statement: Select[Any]) -> type[Any] | None:
    """Return the mapped class for a single-entity Select, else None."""
    if classify_select_shape(statement) != "entity":
        return None
    desc = statement.column_descriptions[0]
    expr = desc.get("expr")
    if is_mapped_class(expr):
        return cast(type[Any], expr)
    typ = desc.get("type")
    if is_mapped_class(typ):
        return cast(type[Any], typ)
    return None


def extract_entity(row: object) -> object | None:
    """Extract a single ORM entity from a result row, if present."""
    if is_orm_instance(row):
        return row

    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        entities = [value for value in mapping.values() if is_orm_instance(value)]
        if len(entities) == 1 and len(mapping) == 1:
            return cast(object, entities[0])
        return None

    if isinstance(row, Mapping):
        return None

    if (
        isinstance(row, Sequence)
        and not isinstance(row, (str, bytes, bytearray))
        and len(row) == 1
        and is_orm_instance(row[0])
    ):
        return cast(object, row[0])
    return None


def unloaded_attribute_names(entity: object) -> set[str]:
    """Return attribute keys that are unloaded or expired on *entity*."""
    state = cast(InstanceState[Any], sa_inspect(entity))
    unloaded = set(getattr(state, "unloaded", ()) or ())
    expired = set(getattr(state, "expired_attributes", ()) or ())
    return unloaded | expired


def is_attribute_unloaded(entity: object, attr_name: str, mapped: type[Any]) -> bool:
    """Return True if *attr_name* is unloaded, resolving synonyms to targets."""
    unloaded = unloaded_attribute_names(entity)
    target = synonym_target(mapped, attr_name)
    check_name = target if target is not None else attr_name
    # Synonym keys often remain listed in state.unloaded even when the target
    # column is loaded — only the target (or non-synonym key) matters.
    if target is not None:
        return check_name in unloaded
    return attr_name in unloaded


def entity_source_identity(entity: object) -> dict[str, object] | None:
    """Return a primary-key dict for *entity*, or None if unavailable."""
    state = cast(InstanceState[Any], sa_inspect(entity))
    mapper = state.mapper
    identity: dict[str, object] = {}
    pk_cols = list(mapper.primary_key)
    unloaded = unloaded_attribute_names(entity)
    for column in pk_cols:
        prop = mapper.get_property_by_column(column)
        key = prop.key
        if key in unloaded:
            if state.identity is None:
                return None
            idx = pk_cols.index(column)
            identity[key] = state.identity[idx]
        else:
            identity[key] = getattr(entity, key)
    return identity


__all__ = [
    "ResultShape",
    "classify_select_shape",
    "entity_source_identity",
    "extract_entity",
    "is_attribute_unloaded",
    "is_mapped_class",
    "is_orm_instance",
    "is_relationship_attr",
    "mapped_column_attr_keys",
    "mapped_columns",
    "mapped_table",
    "scalar_attr_keys",
    "single_entity_class",
    "synonym_target",
    "unloaded_attribute_names",
]
