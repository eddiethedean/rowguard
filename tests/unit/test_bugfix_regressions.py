from __future__ import annotations

from time import sleep
from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, select

import rowguard
from rowguard.errors import RowAdaptationError, RowValidationError
from rowguard.execution.processor import process_row
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.planning.request import QueryRequest
from rowguard.rejection.policies import CollectPolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


class SlowFailAdapter:
    def adapt(self, row: object) -> object:
        sleep(0.01)
        raise RowAdaptationError("slow fail")


def test_adaptation_failure_records_timing() -> None:
    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        adapter=SlowFailAdapter(),  # type: ignore[arg-type]
        validator=PydanticValidator(UserRead),
        rejection_policy=CollectPolicy(),
        use_sqlrules=False,
    )
    processed = process_row(row={"id": 1}, index=0, plan=plan)
    assert processed.adaptation_time_ns > 0
    assert processed.validated is False


def test_validate_rows_adaptation_failure_stats() -> None:
    result = rowguard.validate_rows(
        rows=[{"user_id": 1}],  # missing mapped keys
        model=UserRead,
        field_map={"id": "id", "name": "name", "age": "age"},
        on_reject="collect",
    )
    assert result.statistics.rows_read == 1
    assert result.statistics.rows_rejected == 1
    assert result.statistics.rows_validated == 0
    assert result.has_rejections
    assert result.rejected_count == 1


def test_result_close_called_on_execute(session, users_table) -> None:
    class TrackingResult:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows
            self.closed = False

        def __iter__(self):
            return iter(self._rows)

        def close(self) -> None:
            self.closed = True

    tracking = TrackingResult([])

    class TrackingSession:
        def execute(self, *_args, **_kwargs):
            return tracking

    plan = QueryPlanner[UserRead]().compile(
        QueryRequest(
            model=UserRead,
            source=users_table,
            session=TrackingSession(),
            use_sqlrules=False,
            on_reject="collect",
        )
    )
    SyncExecutionEngine[UserRead]().execute(plan)
    assert tracking.closed is True


def test_raise_includes_row_index(session, users_table) -> None:
    with pytest.raises(RowValidationError) as exc_info:
        rowguard.select(
            session=session,
            table=users_table,
            model=UserRead,
            on_reject="raise",
            use_sqlrules=False,
        )
    assert exc_info.value.row_index == 1


def test_collect_preserves_order(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert [m.name for m in result.models] == ["Ada", "Grace"]
    assert [r.mapping["name"] for r in result.rejected if r.mapping] == ["Legacy"]


def test_skip_has_rejections_without_retained(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    assert result.has_rejections is True
    assert result.is_clean is False
    assert result.rejected_count == 0
    assert result.statistics.rows_rejected == 1


def test_parameters_forwarded_session(session, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == bindparam("uid"))
    result = rowguard.execute(
        session=session,
        statement=stmt,
        model=UserRead,
        parameters={"uid": 1},
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.models == (UserRead(id=1, name="Ada", age=37),)


def test_parameters_forwarded_connection(engine, users_table) -> None:
    stmt = select(users_table).where(users_table.c.id == bindparam("uid"))
    with engine.connect() as connection:
        result = rowguard.execute(
            connection=connection,
            statement=stmt,
            model=UserRead,
            parameters={"uid": 3},
            on_reject="collect",
            use_sqlrules=False,
        )
    assert result.models == (UserRead(id=3, name="Grace", age=45),)


def test_execute_with_source_emits_explicit_pushdown_diagnostic(session, users_table) -> None:
    result = rowguard.execute(
        session=session,
        statement=select(users_table),
        source=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    codes = {d.code for d in result.diagnostics}
    assert "sqlrules.pushdown_source_explicit" in codes
    assert "sqlrules.pushdown_applied" in codes


def test_field_map_missing_key_does_not_use_defaults() -> None:
    class UserWithDefault(BaseModel):
        id: int
        name: str = "anon"

    with pytest.raises(RowAdaptationError):
        rowguard.validate_rows(
            rows=[{"id": 1}],
            model=UserWithDefault,
            field_map={"id": "id", "name": "display_name"},
            on_reject="raise",
        )


def test_validate_rows_raise_stops() -> None:
    with pytest.raises(RowValidationError) as exc_info:
        rowguard.validate_rows(
            rows=[
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
            ],
            model=UserRead,
            on_reject="raise",
        )
    assert exc_info.value.row_index == 1


def test_adapter_rejects_defaults_path_via_validate_collect() -> None:
    class UserWithDefault(BaseModel):
        id: int
        name: str = "anon"

    result = rowguard.validate_rows(
        rows=[{"id": 1}],
        model=UserWithDefault,
        field_map={"id": "id", "name": "display_name"},
        on_reject="collect",
    )
    assert result.statistics.rows_validated == 0
    assert result.statistics.rows_rejected == 1
    assert result.models == ()
