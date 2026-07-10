from __future__ import annotations

import pytest
from pydantic import BaseModel
from sqlalchemy import select

import rowguard
from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import QueryExecutionError, RowAdaptationError
from rowguard.execution.processor import process_row
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.integrations.sqlalchemy_core import is_column_element
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.planning.request import QueryRequest
from rowguard.rejection.policies import CollectPolicy, RaisePolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str


def test_process_row_adaptation_failure_collect() -> None:
    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        adapter=SQLAlchemyRowAdapter(),
        validator=PydanticValidator(UserRead),
        rejection_policy=CollectPolicy(),
        use_sqlrules=False,
    )
    processed = process_row(row=object(), index=0, plan=plan)
    assert processed.model is None
    assert processed.rejected is not None
    assert isinstance(processed.rejected.adaptation_error, RowAdaptationError)
    assert processed.retain_rejection


def test_process_row_adaptation_failure_raise() -> None:
    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        adapter=SQLAlchemyRowAdapter(),
        validator=PydanticValidator(UserRead),
        rejection_policy=RaisePolicy(),
        use_sqlrules=False,
    )
    with pytest.raises(RowAdaptationError):
        process_row(row=object(), index=0, plan=plan)


def test_raise_policy_wraps_non_adaptation_error() -> None:
    from rowguard.results.rejected_row import RejectedRow

    rejected = RejectedRow(
        index=0,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=ValueError("boom"),
    )
    with pytest.raises(RowAdaptationError, match="boom"):
        RaisePolicy().handle(rejected)


def test_is_column_element() -> None:
    from sqlalchemy import Column, Integer, MetaData, Table

    table = Table("t", MetaData(), Column("id", Integer, primary_key=True))
    assert is_column_element(table.c.id)
    assert not is_column_element("id")


def test_planner_rejects_non_select_statement() -> None:
    from rowguard.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="Select"):
        QueryPlanner[UserRead]().compile(
            QueryRequest(
                model=UserRead,
                statement=object(),
                session=object(),
                use_sqlrules=False,
            )
        )


def test_planner_skips_pushdown_without_source(users_table) -> None:
    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            statement=select(users_table.c.id, users_table.c.name),
            session=object(),
            use_sqlrules=True,
        )
    )
    assert any(d.code == "sqlrules.pushdown_skipped" for d in plan.diagnostics)


def test_execute_wraps_database_errors(session, users_table) -> None:
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=users_table,
            session=BrokenSession(),
            use_sqlrules=False,
            on_reject="collect",
        )
    )
    with pytest.raises(QueryExecutionError, match="Query execution failed"):
        SyncExecutionEngine[UserRead]().execute(plan)


def test_validate_rows_with_parameters_path(session, users_table) -> None:
    # Exercise parameter forwarding on session.execute
    result = rowguard.execute(
        session=session,
        statement=select(users_table).where(users_table.c.id == 1),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
        parameters={},
    )
    assert result.valid_count >= 0
