from __future__ import annotations

import pytest
from pydantic import BaseModel
from sqlalchemy import select

import rowguard
from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import QueryExecutionError, RowAdaptationError
from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.processor import process_row
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.integrations.sqlalchemy_core import is_column_element
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import PushdownConfig, RejectionConfig
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ValidationPlan,
)
from rowguard.planning.request import QueryRequest
from rowguard.rejection.policies import CollectPolicy, RaisePolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str


def _plan(*, policy: CollectPolicy | RaisePolicy) -> ExecutionPlan[UserRead]:
    name = "collect" if isinstance(policy, CollectPolicy) else "raise"
    return ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=policy, policy_name=name),
        use_sqlrules=False,
    )


def test_process_row_adaptation_failure_collect() -> None:
    processed = process_row(row=object(), index=0, plan=_plan(policy=CollectPolicy()))
    assert processed.model is None
    assert processed.rejected is not None
    assert isinstance(processed.rejected.adaptation_error, RowAdaptationError)
    assert processed.retain_rejection


def test_process_row_adaptation_failure_raise() -> None:
    with pytest.raises(RowAdaptationError) as exc_info:
        process_row(row=object(), index=3, plan=_plan(policy=RaisePolicy()))
    assert exc_info.value.row_index == 3
    assert exc_info.value.model is UserRead


def test_raise_policy_wraps_non_adaptation_error() -> None:
    from rowguard.results.rejected_row import RejectedRow

    rejected = RejectedRow(
        index=4,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=ValueError("boom"),
    )
    with pytest.raises(RowAdaptationError, match="boom") as exc_info:
        RaisePolicy().handle(rejected)
    assert exc_info.value.row_index == 4
    assert exc_info.value.model is UserRead


def test_parameters_forwarded_nonempty(session, users_table) -> None:
    from sqlalchemy import bindparam

    class FullUser(BaseModel):
        id: int
        name: str
        age: int

    stmt = select(users_table).where(users_table.c.id == bindparam("uid"))
    result = rowguard.execute(
        session=session,
        statement=stmt,
        model=FullUser,
        on_reject="collect",
        use_sqlrules=False,
        parameters={"uid": 1},
    )
    assert result.valid_count == 1
    assert result.models[0].id == 1


def test_is_column_element() -> None:
    from sqlalchemy import Column, Integer, MetaData, Table

    table = Table("t", MetaData(), Column("id", Integer, primary_key=True))
    assert is_column_element(table.c.id)
    assert not is_column_element("id")


def test_execute_wraps_database_errors(users_table) -> None:
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=users_table,
            pushdown=PushdownConfig(enabled=False),
            rejection=RejectionConfig(policy="collect"),
        )
    )
    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        SyncExecutionEngine[UserRead]().execute(
            plan,
            SyncExecutionContext(session=BrokenSession()),
        )


def test_validate_rows_with_parameters_path(session, users_table) -> None:
    result = rowguard.execute(
        session=session,
        statement=select(users_table).where(users_table.c.id == 1),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={},
    )
    assert result.valid_count >= 0


def test_compile_plan_public_api(users_table) -> None:
    plan = rowguard.compile_plan(
        table=users_table,
        model=UserRead,
        use_sqlrules=False,
        on_reject="collect",
    )
    assert isinstance(plan, ExecutionPlan)
    assert plan.rejection_plan.policy_name == "collect"
    assert plan.resolved_source is not None
