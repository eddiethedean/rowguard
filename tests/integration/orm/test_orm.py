from __future__ import annotations

from typing import Annotated

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
from rowguard.errors import PlanningError, RowAdaptationError, RowValidationError


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


@pytest.fixture
def orm_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                User(id=1, name="Ada", age=37),
                User(id=2, name="Legacy", age=12),
                User(id=3, name="Grace", age=45),
            ]
        )
        session.commit()
    return engine


@pytest.fixture
def orm_session(orm_engine):
    with Session(orm_engine) as session:
        yield session


@pytest.mark.integration
def test_orm_projected_select_collect(orm_session: Session) -> None:
    result = rowguard.execute(
        session=orm_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert {m.name for m in result.models} == {"Ada", "Grace"}
    assert result.rejected[0].mapping is not None
    assert result.rejected[0].mapping["name"] == "Legacy"


@pytest.mark.integration
def test_orm_projected_pushdown(orm_session: Session) -> None:
    result = rowguard.execute(
        session=orm_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert result.statistics.rows_read == 2
    assert any(d.code == "sqlrules.pushdown_applied" for d in result.diagnostics)


@pytest.mark.integration
def test_orm_projected_skip_and_raise(orm_session: Session) -> None:
    skipped = rowguard.execute(
        session=orm_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    assert skipped.valid_count == 2
    assert skipped.rejected_count == 0

    with pytest.raises(RowValidationError):
        rowguard.execute(
            session=orm_session,
            statement=select(User.id, User.name, User.age),
            source=User,
            model=UserRead,
            on_reject="raise",
            use_sqlrules=False,
        )


@pytest.mark.integration
def test_orm_select_mapped_class_entity(orm_session: Session) -> None:
    result = rowguard.select(
        session=orm_session,
        table=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert result.rejected[0].source_identity == {"id": 2}
    plan = rowguard.compile_plan(model=UserRead, table=User, use_sqlrules=False)
    assert plan.adapter_plan.result_shape == "entity"


@pytest.mark.integration
def test_orm_stream_entity_collect(orm_session: Session) -> None:
    with rowguard.stream(
        session=orm_session,
        table=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    assert {m.name for m in models} == {"Ada", "Grace"}
    assert stream.rejected_count == 1
    assert stream.rejected[0].source_identity == {"id": 2}
    assert stream.closed


@pytest.mark.integration
def test_orm_entity_from_attributes(orm_session: Session) -> None:
    result = rowguard.select(
        session=orm_session,
        table=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
        orm_validation="from_attributes",
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0


@pytest.mark.integration
def test_orm_unloaded_attributes_error(orm_session: Session) -> None:
    from rowguard.execution.processor import process_row

    user = orm_session.get(User, 1)
    assert user is not None
    orm_session.expire(user)

    plan = rowguard.compile_plan(
        model=UserRead,
        table=User,
        on_reject="collect",
        use_sqlrules=False,
    )
    processed = process_row(row=user, index=0, plan=plan)
    assert processed.model is None
    assert processed.rejected is not None
    assert processed.rejected.source_identity == {"id": 1}
    assert processed.rejected.adaptation_error is not None
    assert "unloaded" in str(processed.rejected.adaptation_error).lower()

    raise_plan = rowguard.compile_plan(
        model=UserRead,
        table=User,
        on_reject="raise",
        use_sqlrules=False,
    )
    raised = process_row(row=user, index=0, plan=raise_plan)
    assert isinstance(raised.raise_error, RowAdaptationError)
    assert "unloaded" in str(raised.raise_error).lower()


@pytest.mark.integration
def test_orm_rejects_entity_plus_scalar(orm_session: Session) -> None:
    with pytest.raises(PlanningError, match=r"Multi-entity|entity\+scalar"):
        rowguard.execute(
            session=orm_session,
            statement=select(User, User.name),
            source=User,
            model=UserRead,
            use_sqlrules=False,
        )


@pytest.mark.integration
def test_orm_attribute_map(orm_session: Session) -> None:
    class Renamed(BaseModel):
        user_id: int
        display_name: str
        age: Annotated[int, Field(ge=18)]

    result = rowguard.select(
        session=orm_session,
        table=User,
        model=Renamed,
        attribute_map={
            "user_id": "id",
            "display_name": "name",
            "age": "age",
        },
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.models[0].display_name in {"Ada", "Grace"}


@pytest.mark.integration
def test_orm_relationship_attribute_map_rejected() -> None:
    class WithTeam(BaseModel):
        id: int
        name: str
        team: str

    with pytest.raises(PlanningError, match="relationship"):
        rowguard.compile_plan(
            model=WithTeam,
            table=User,
            attribute_map={"id": "id", "name": "name", "team": "team"},
            use_sqlrules=False,
        )
