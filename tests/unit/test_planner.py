from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table

from rowguard.errors import ConfigurationError
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.request import QueryRequest


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _users() -> Table:
    return Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )


def test_planner_builds_select_with_pushdown() -> None:
    table = _users()
    session = object()
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=table,
            session=session,
            use_sqlrules=True,
            on_reject="collect",
        )
    )
    assert plan.use_sqlrules
    assert plan.session is session
    assert plan.statement is not None
    assert any(d.code == "sqlrules.pushdown_applied" for d in plan.diagnostics)


def test_planner_rejects_missing_execution_context() -> None:
    with pytest.raises(ConfigurationError, match="session or connection"):
        QueryPlanner[UserRead]().compile(QueryRequest(model=UserRead, source=_users()))


def test_planner_rejects_both_session_and_connection() -> None:
    with pytest.raises(ConfigurationError, match="exactly one"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=_users(),
                session=object(),
                connection=object(),
            )
        )


def test_planner_rejects_unknown_policy() -> None:
    with pytest.raises(ConfigurationError, match="on_reject"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=_users(),
                session=object(),
                on_reject="quarantine",
            )
        )


def test_planner_requires_source_or_statement() -> None:
    with pytest.raises(ConfigurationError, match=r"source|statement"):
        QueryPlanner[UserRead]().compile(QueryRequest(model=UserRead, session=object()))


def test_sqlrules_bridge_compiles_constraints() -> None:
    compiled = SQLRulesBridge().compile(model=UserRead, source=_users())
    assert len(compiled.expressions) >= 1
