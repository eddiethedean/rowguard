from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, select

import rowguard
from rowguard.cache import LRUCache
from rowguard.errors import ConfigurationError, PlanningError
from rowguard.execution.context import SyncExecutionContext
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import AdapterConfig, PushdownConfig
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.planning.request import QueryRequest


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.fixture
def users() -> Table:
    return Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )


def test_sync_context_requires_exactly_one_handle() -> None:
    with pytest.raises(ConfigurationError, match="exactly one"):
        SyncExecutionContext()
    with pytest.raises(ConfigurationError, match="exactly one"):
        SyncExecutionContext(session=object(), connection=object())


def test_pushdown_disabled_diagnostic(users: Table) -> None:
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=users,
            pushdown=PushdownConfig(enabled=False),
        )
    )
    assert any(d.code == "planning.pushdown_disabled" for d in plan.diagnostics)
    assert plan.pushdown_plan.enabled is False


def test_resolve_select_as_pushdown_source(users: Table) -> None:
    stmt = select(users)
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            statement=stmt,
            pushdown=PushdownConfig(enabled=True, source=stmt),
        )
    )
    # Query source is unset; pushdown.source is used only for SQLRules.
    assert plan.resolved_source is None
    assert plan.pushdown_plan.enabled is True
    assert plan.use_sqlrules is True


def test_valid_field_map_and_column_map(users: Table) -> None:
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=users,
            pushdown=PushdownConfig(
                enabled=True,
                column_map={"id": users.c.id, "name": users.c.name, "age": users.c.age},
            ),
            adapter=AdapterConfig(
                field_map={"id": "id", "name": "name", "age": "age"},
            ),
        )
    )
    assert plan.adapter_plan.field_map == {"id": "id", "name": "name", "age": "age"}
    assert plan.pushdown_plan.enabled is True


def test_compile_plan_rejects_bad_policy(users: Table) -> None:
    with pytest.raises(ConfigurationError, match="on_reject"):
        rowguard.compile_plan(table=users, model=UserRead, on_reject="nope")


def test_cache_evicts_least_recently_used() -> None:
    cache: LRUCache[str, int] = LRUCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # refresh a
    cache.set("c", 3)  # evict b
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    cache.clear()
    assert cache.get("a") is None


def test_table_column_names_helpers() -> None:
    from rowguard.planning.compiler import _table_column_names

    class FakeSource:
        name = "fake"
        c = None
        columns = 123

    class BareSource:
        name = "bare"

    assert _table_column_names(FakeSource()) == {}
    assert _table_column_names(BareSource()) == {}


def test_resolve_non_table_query_source(users: Table) -> None:
    class FakeSource:
        name = "fake"
        c = None
        columns = 123

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=FakeSource(),
            statement=select(users),
            pushdown=PushdownConfig(enabled=False),
        )
    )
    assert plan.resolved_source is not None
    assert plan.resolved_source.kind == "FakeSource"
    assert plan.resolved_source.columns == {}

def test_planning_error_non_basemodel(users: Table) -> None:
    with pytest.raises(PlanningError, match="BaseModel"):
        QueryPlanner[object]().compile(  # type: ignore[type-var]
            QueryRequest(model=object, source=users)  # type: ignore[arg-type]
        )


def test_planning_error_invalid_statement(users: Table) -> None:
    with pytest.raises(PlanningError, match="must be a SQLAlchemy Select"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                statement=users,  # Table, not Select
            )
        )


def test_planning_error_missing_source_and_statement() -> None:
    with pytest.raises(PlanningError, match=r"source \(table\) or statement"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(model=UserRead, source=None, statement=None)
        )


def test_execution_plan_convenience_properties(users: Table) -> None:
    plan = rowguard.compile_plan(table=users, model=UserRead, use_sqlrules=False)
    assert plan.adapter is plan.adapter_plan.adapter
    assert plan.validator is plan.validation_plan.validator
    assert plan.rejection_policy is plan.rejection_plan.policy
    assert isinstance(plan, ExecutionPlan)
