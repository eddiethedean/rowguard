"""Regressions for 0.2.0 correctness fixes."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, select

import rowguard
from rowguard.cache import LRUCache
from rowguard.errors import (
    ConfigurationError,
    PlanningError,
    RowAdaptationError,
    RowValidationError,
)
from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.processor import process_row
from rowguard.execution.streaming import StreamResult
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import (
    PushdownConfig,
    RejectionConfig,
)
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ValidationPlan,
)
from rowguard.planning.request import QueryRequest
from rowguard.rejection.policies import CollectPolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


def _tables() -> tuple[Table, Table]:
    metadata = MetaData()
    a = Table(
        "a",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )
    b = Table(
        "b",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("age", Integer),
    )
    return a, b


def test_pushdown_source_does_not_override_select_from() -> None:
    a, b = _tables()
    plan = rowguard.compile_plan(
        table=a,
        model=UserRead,
        pushdown_source=b,
        use_sqlrules=False,
    )
    compiled = str(plan.statement.compile(compile_kwargs={"literal_binds": False}))
    assert "FROM a" in compiled
    assert "FROM b" not in compiled


def test_plan_cache_rebinds_parameters_on_hit() -> None:
    a, _ = _tables()
    cache: LRUCache[str, ExecutionPlan[object]] = LRUCache(max_entries=8)
    planner = QueryPlanner[UserRead](cache=cache, cache_enabled=True)
    first = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            parameters={"uid": 1},
            pushdown=PushdownConfig(enabled=False),
        )
    )
    second = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            parameters={"uid": 2},
            pushdown=PushdownConfig(enabled=False),
        )
    )
    assert first.parameters == {"uid": 1}
    assert second.parameters == {"uid": 2}
    assert first.execution_id != second.execution_id


def test_plan_cache_distinguishes_column_map_values() -> None:
    a, _ = _tables()
    cache: LRUCache[str, ExecutionPlan[object]] = LRUCache(max_entries=8)
    planner = QueryPlanner[UserRead](cache=cache, cache_enabled=True)
    first = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            pushdown=PushdownConfig(enabled=True, column_map={"age": a.c.age}),
        )
    )
    second = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            pushdown=PushdownConfig(enabled=True, column_map={"age": a.c.id}),
        )
    )
    assert first.execution_id != second.execution_id
    # Distinct plans (not a wrong reuse of the first template).
    assert first.pushdown_plan is not second.pushdown_plan


def test_plan_cache_distinguishes_pushdown_source() -> None:
    a, b = _tables()
    stmt = select(a)
    cache: LRUCache[str, ExecutionPlan[object]] = LRUCache(max_entries=8)
    planner = QueryPlanner[UserRead](cache=cache, cache_enabled=True)
    first = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            statement=stmt,
            pushdown=PushdownConfig(enabled=True, source=a),
        )
    )
    second = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            statement=stmt,
            pushdown=PushdownConfig(enabled=True, source=b),
        )
    )
    assert first.pushdown_plan is not second.pushdown_plan
    assert first.execution_id != second.execution_id


def test_plan_cache_distinguishes_compiled_rules() -> None:
    a, _ = _tables()
    bridge = SQLRulesBridge()
    compiled = bridge.compile(model=UserRead, source=a)
    other = dict(compiled.compiled_rules or {})
    cache: LRUCache[str, ExecutionPlan[object]] = LRUCache(max_entries=8)
    planner = QueryPlanner[UserRead](cache=cache, cache_enabled=True)
    first = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            pushdown=PushdownConfig(enabled=True, compiled_rules=compiled.compiled_rules),
        )
    )
    second = planner.compile(
        QueryRequest(
            model=UserRead,
            source=a,
            pushdown=PushdownConfig(enabled=True, compiled_rules=other),
        )
    )
    assert first.execution_id != second.execution_id


def test_column_map_rejects_cross_table_columns() -> None:
    a, b = _tables()
    with pytest.raises(PlanningError, match="column_map columns"):
        rowguard.compile_plan(
            table=a,
            model=UserRead,
            column_map={"age": b.c.age},
            use_sqlrules=True,
        )


def test_statement_only_skipped_pushdown_disables_flag() -> None:
    a, _ = _tables()
    plan = rowguard.compile_plan(
        statement=select(a.c.id, a.c.name, a.c.age),
        model=UserRead,
        use_sqlrules=True,
    )
    assert plan.use_sqlrules is False
    assert plan.pushdown_plan.enabled is False
    assert any(d.code == "sqlrules.pushdown_skipped" for d in plan.diagnostics)


def test_close_failure_does_not_mask_validation_error() -> None:
    a, _ = _tables()

    class BoomResult:
        def __iter__(self):
            return iter([{"id": 1, "name": "Legacy", "age": 12}])

        def close(self) -> None:
            raise RuntimeError("close failed")

    class BoomSession:
        def execute(self, *_args, **_kwargs):
            return BoomResult()

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=a,
            pushdown=PushdownConfig(enabled=False),
            rejection=RejectionConfig(policy="raise"),
        )
    )
    with pytest.raises(RowValidationError):
        SyncExecutionEngine[UserRead]().execute(
            plan,
            SyncExecutionContext(session=BoomSession()),
        )


def test_validate_rows_unknown_field_map_key() -> None:
    with pytest.raises(ConfigurationError, match="field_map keys"):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada", "age": 37}],
            model=UserRead,
            field_map={"nope": "id"},
            on_reject="collect",
        )


def test_strict_true_rejects_coercion() -> None:
    result = rowguard.validate_rows(
        rows=[{"id": "1", "name": "Ada", "age": "37"}],
        model=UserRead,
        on_reject="collect",
        strict=True,
    )
    assert result.models == ()
    assert result.statistics.rows_rejected == 1


def test_public_compiled_rules_via_compile_plan() -> None:
    a, _ = _tables()
    compiled = SQLRulesBridge().compile(model=UserRead, source=a)
    plan = rowguard.compile_plan(
        table=a,
        model=UserRead,
        compiled_rules=compiled.compiled_rules,
        use_sqlrules=True,
    )
    assert plan.pushdown_plan.precompiled is True
    assert any(d.code == "planning.precompiled_rules" for d in plan.diagnostics)


def test_stream_result_raises_not_implemented() -> None:
    stream = StreamResult[UserRead]()
    with pytest.raises(NotImplementedError, match=r"0\.3\.0"):
        next(stream)


def test_cache_rejects_non_positive_max_entries() -> None:
    with pytest.raises(ValueError, match="max_entries"):
        LRUCache(max_entries=0)


def test_compile_plan_rejects_table_and_source() -> None:
    a, b = _tables()
    with pytest.raises(ConfigurationError, match="table= or source="):
        rowguard.compile_plan(table=a, source=b, model=UserRead, use_sqlrules=False)


def test_unexpected_adapter_exception_routed_to_rejection() -> None:
    class BoomAdapter:
        def adapt(self, row: object) -> object:
            raise ValueError("boom")

    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=BoomAdapter()),  # type: ignore[arg-type]
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=CollectPolicy(), policy_name="collect"),
        use_sqlrules=False,
    )
    processed = process_row(row={"id": 1}, index=0, plan=plan)
    assert processed.model is None
    assert processed.rejected is not None
    assert isinstance(processed.rejected.adaptation_error, RowAdaptationError)
    assert processed.rejected.adaptation_error.__cause__ is not None


def test_strict_via_select(session, users_table) -> None:
    # Existing rows are already ints; compile with strict to ensure the knob is accepted.
    plan = rowguard.compile_plan(
        table=users_table,
        model=UserRead,
        use_sqlrules=False,
        strict=True,
    )
    assert plan.validation_plan.strict is True
