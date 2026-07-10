from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel

import rowguard


class User(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    age: int


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.fixture
def sqlmodel_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
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
def sqlmodel_session(sqlmodel_engine):
    with Session(sqlmodel_engine) as session:
        yield session


@pytest.mark.integration
def test_sqlmodel_projected_select(sqlmodel_session: Session) -> None:
    result = rowguard.execute(
        session=sqlmodel_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1


@pytest.mark.integration
def test_sqlmodel_pushdown(sqlmodel_session: Session) -> None:
    result = rowguard.execute(
        session=sqlmodel_session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert any(d.code == "sqlrules.pushdown_applied" for d in result.diagnostics)


@pytest.mark.integration
def test_sqlmodel_entity_select(sqlmodel_session: Session) -> None:
    result = rowguard.select(
        session=sqlmodel_session,
        table=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert result.rejected[0].source_identity == {"id": 2}
    plan = rowguard.compile_plan(model=UserRead, table=User, use_sqlrules=False)
    assert plan.resolved_source is not None
    assert plan.resolved_source.kind == "sqlmodel"
