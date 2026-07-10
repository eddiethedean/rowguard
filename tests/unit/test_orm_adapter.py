from __future__ import annotations

from typing import Annotated
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

import rowguard
from rowguard.adapters.orm_entity import ORMEntityAdapter
from rowguard.errors import ConfigurationError, PlanningError, RowAdaptationError
from rowguard.integrations.sqlalchemy_orm import (
    classify_select_shape,
    entity_source_identity,
    extract_entity,
    is_mapped_class,
    is_orm_instance,
    is_relationship_attr,
    mapped_column_attr_keys,
    mapped_columns,
    mapped_table,
    single_entity_class,
    unloaded_attribute_names,
)
from rowguard.integrations.sqlmodel import (
    is_sqlmodel_table,
    sqlmodel_columns,
    sqlmodel_table,
)


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    age: Mapped[int]
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    team: Mapped[Team | None] = relationship()


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def test_is_mapped_class_and_instance() -> None:
    assert is_mapped_class(User)
    assert not is_mapped_class(object)
    assert not is_mapped_class(User(id=1, name="a", age=1))
    assert not is_mapped_class("User")
    assert is_orm_instance(User(id=1, name="a", age=1))
    assert not is_orm_instance(None)
    assert not is_orm_instance(User)
    assert not is_orm_instance(object())


def test_mapped_metadata_helpers() -> None:
    assert set(mapped_columns(User)) == {"id", "name", "age", "team_id"}
    assert mapped_table(User).name == "users"
    assert "id" in mapped_column_attr_keys(User)
    assert is_relationship_attr(User, "team")
    assert not is_relationship_attr(User, "name")


def test_classify_and_single_entity() -> None:
    assert classify_select_shape(select(User)) == "entity"
    assert classify_select_shape(select(User.id, User.name)) == "projection"
    assert classify_select_shape(select(User, User.name)) == "unsupported"
    assert single_entity_class(select(User)) is User
    assert single_entity_class(select(User.id)) is None


def test_extract_entity_shapes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=7, name="Ada", age=37))
        session.commit()
        row = session.execute(select(User)).one()
        entity = extract_entity(row)
        assert is_orm_instance(entity)
        assert extract_entity(entity) is entity
        assert extract_entity({"id": 1}) is None
        assert extract_entity((entity,)) is entity
        assert extract_entity((entity, entity)) is None


def test_entity_adapter_and_identity() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=7, name="Ada", age=37))
        session.commit()
        row = session.execute(select(User)).one()
        adapted = ORMEntityAdapter(
            attribute_keys=("id", "name", "age"),
            mapped_class=User,
        ).adapt(row)
        assert adapted.mapping == {"id": 7, "name": "Ada", "age": 37}
        assert adapted.source_identity == {"id": 7}
        assert entity_source_identity(row[0]) == {"id": 7}

        expired = session.get(User, 7)
        assert expired is not None
        session.expire(expired)
        assert "name" in unloaded_attribute_names(expired)
        identity = entity_source_identity(expired)
        assert identity == {"id": 7}


def test_entity_adapter_rejects_non_entity() -> None:
    adapter = ORMEntityAdapter(attribute_keys=("id",), mapped_class=User)
    with pytest.raises(RowAdaptationError, match="single ORM entity"):
        adapter.adapt({"id": 1})


def test_entity_adapter_rejects_bad_unloaded_policy() -> None:
    with pytest.raises(ValueError, match="unloaded_attributes"):
        ORMEntityAdapter(
            attribute_keys=("id",),
            mapped_class=User,
            unloaded_attributes="load",  # type: ignore[arg-type]
        )


def test_entity_adapter_rejects_relationship_at_runtime() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, name="Ada", age=37))
        session.commit()
        row = session.execute(select(User)).one()
        adapter = ORMEntityAdapter(
            attribute_keys=("team",),
            attribute_map={"team": "team"},
            mapped_class=User,
        )
        with pytest.raises(RowAdaptationError, match="relationship"):
            adapter.adapt(row)


def test_entity_adapter_from_attributes_subject() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, name="Ada", age=37))
        session.commit()
        row = session.execute(select(User)).one()
        adapted = ORMEntityAdapter(
            attribute_keys=("id", "name", "age"),
            mapped_class=User,
            orm_validation="from_attributes",
        ).adapt(row)
        assert adapted.attributes_subject is not None
        assert is_orm_instance(adapted.attributes_subject)


def test_entity_adapter_direct_instance() -> None:
    user = User(id=1, name="Ada", age=37)
    adapted = ORMEntityAdapter(
        attribute_keys=("id", "name", "age"),
        mapped_class=User,
    ).adapt(user)
    assert adapted.mapping["name"] == "Ada"


def test_api_rejects_bad_orm_knobs() -> None:
    with pytest.raises(ConfigurationError, match="orm_validation"):
        rowguard.compile_plan(
            model=UserRead,
            table=User,
            orm_validation="nope",  # type: ignore[arg-type]
            use_sqlrules=False,
        )
    with pytest.raises(ConfigurationError, match="unloaded_attributes"):
        rowguard.compile_plan(
            model=UserRead,
            table=User,
            unloaded_attributes="load",  # type: ignore[arg-type]
            use_sqlrules=False,
        )


def test_from_attributes_requires_entity_shape() -> None:
    with pytest.raises(PlanningError, match="from_attributes"):
        rowguard.compile_plan(
            model=UserRead,
            statement=select(User.id, User.name, User.age),
            source=User,
            orm_validation="from_attributes",
            use_sqlrules=False,
        )


def test_attribute_map_on_projection_rejected() -> None:
    with pytest.raises(PlanningError, match="attribute_map"):
        rowguard.compile_plan(
            model=UserRead,
            statement=select(User.id, User.name, User.age),
            source=User,
            attribute_map={"id": "id"},
            use_sqlrules=False,
        )


def test_sqlmodel_helpers_without_package() -> None:
    assert not is_sqlmodel_table(User)
    assert not is_sqlmodel_table(object())

    real_import = __import__

    def _fake_import(name: str, *args: object, **kwargs: object):
        if name == "sqlmodel":
            raise ImportError("no sqlmodel")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_fake_import):
        assert is_sqlmodel_table(User) is False


def test_sqlmodel_table_helpers_with_model() -> None:
    from sqlmodel import Field as SQLField
    from sqlmodel import SQLModel

    class Item(SQLModel, table=True):
        id: int | None = SQLField(default=None, primary_key=True)
        name: str

    assert is_sqlmodel_table(Item)
    assert "name" in sqlmodel_columns(Item)
    assert sqlmodel_table(Item).name == "item"


def test_inspect_exception_paths() -> None:
    with patch(
        "rowguard.integrations.sqlalchemy_orm.sa_inspect",
        side_effect=RuntimeError("boom"),
    ):
        assert is_mapped_class(User) is False
        assert is_orm_instance(User(id=1, name="a", age=1)) is False
