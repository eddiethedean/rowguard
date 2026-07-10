from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, select

from rowguard.cache import LRUCache
from rowguard.errors import PlanningError
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import (
    AdapterConfig,
    PushdownConfig,
    RejectionConfig,
)
from rowguard.planning.execution_plan import ExecutionPlan
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
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=table,
            pushdown=PushdownConfig(enabled=True),
            rejection=RejectionConfig(policy="collect"),
        )
    )
    assert plan.use_sqlrules
    assert not hasattr(plan, "session") or getattr(plan, "session", None) is None
    assert plan.statement is not None
    assert plan.adapter_plan.adapter is not None
    assert plan.rejection_plan.policy_name == "collect"
    assert any(d.code == "sqlrules.pushdown_applied" for d in plan.diagnostics)
    assert any(d.code == "planning.source_resolved" for d in plan.diagnostics)


def test_planner_rejects_unknown_policy() -> None:
    with pytest.raises(PlanningError, match="on_reject"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=_users(),
                rejection=RejectionConfig(policy="quarantine"),  # type: ignore[arg-type]
            )
        )


def test_planner_requires_source_or_statement() -> None:
    with pytest.raises(PlanningError, match=r"source|statement"):
        QueryPlanner[UserRead]().compile(QueryRequest(model=UserRead))


def test_planner_rejects_non_select_statement() -> None:
    with pytest.raises(PlanningError, match="Select"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                statement=object(),
                pushdown=PushdownConfig(enabled=False),
            )
        )


def test_planner_skips_pushdown_without_source(users_table: Table) -> None:
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            statement=select(users_table.c.id, users_table.c.name, users_table.c.age),
            pushdown=PushdownConfig(enabled=True),
        )
    )
    assert any(d.code == "sqlrules.pushdown_skipped" for d in plan.diagnostics)


def test_planner_field_map_unknown_model_field() -> None:
    with pytest.raises(PlanningError, match="field_map keys"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=_users(),
                pushdown=PushdownConfig(enabled=False),
                adapter=AdapterConfig(field_map={"nope": "id"}),
            )
        )


def test_planner_field_map_unknown_column() -> None:
    with pytest.raises(PlanningError, match="source columns"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=_users(),
                pushdown=PushdownConfig(enabled=False),
                adapter=AdapterConfig(field_map={"id": "missing_col"}),
            )
        )


def test_planner_column_map_unknown_model_field() -> None:
    table = _users()
    with pytest.raises(PlanningError, match="column_map keys"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                source=table,
                pushdown=PushdownConfig(
                    enabled=True,
                    column_map={"nope": table.c.id},
                ),
            )
        )


def test_precompiled_rules_equivalence() -> None:
    table = _users()
    bridge = SQLRulesBridge()
    compiled = bridge.compile(model=UserRead, source=table)
    assert compiled.compiled_rules is not None

    live = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=table,
            pushdown=PushdownConfig(enabled=True),
        )
    )
    pre = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=table,
            pushdown=PushdownConfig(
                enabled=True,
                compiled_rules=compiled.compiled_rules,
            ),
        )
    )
    assert live.pushdown_plan.precompiled is False
    assert pre.pushdown_plan.precompiled is True
    assert len(live.pushdown_plan.expressions) == len(pre.pushdown_plan.expressions)
    assert any(d.code == "planning.precompiled_rules" for d in pre.diagnostics)


def test_plan_cache_hit() -> None:
    table = _users()
    cache: LRUCache[str, ExecutionPlan[object]] = LRUCache(max_entries=8)
    planner = QueryPlanner[UserRead](cache=cache, cache_enabled=True)
    request = QueryRequest(
        model=UserRead,
        source=table,
        pushdown=PushdownConfig(enabled=False),
    )
    first = planner.compile(request)
    second = planner.compile(request)
    assert first is second


def test_sqlrules_bridge_compiles_constraints() -> None:
    compiled = SQLRulesBridge().compile(model=UserRead, source=_users())
    assert len(compiled.expressions) >= 1
