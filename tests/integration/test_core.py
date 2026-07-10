from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard
from rowguard.errors import ConfigurationError, RowValidationError


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.mark.integration
def test_select_collect_without_pushdown(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert result.statistics.rows_read == 3
    assert result.statistics.rows_accepted == 2
    assert result.statistics.rows_rejected == 1
    assert {m.name for m in result.models} == {"Ada", "Grace"}
    assert result.rejected[0].mapping is not None
    assert result.rejected[0].mapping["name"] == "Legacy"
    assert result.statement is not None


@pytest.mark.integration
def test_select_raise_policy(session, users_table) -> None:
    with pytest.raises(RowValidationError):
        rowguard.select(
            session=session,
            table=users_table,
            model=UserRead,
            on_reject="raise",
            use_sqlrules=False,
        )


@pytest.mark.integration
def test_select_skip_policy(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert result.statistics.rows_rejected == 1


@pytest.mark.integration
def test_select_with_sqlrules_pushdown(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert result.statistics.rows_read == 2
    assert any(d.code == "sqlrules.pushdown_applied" for d in result.diagnostics)


@pytest.mark.integration
def test_execute_existing_statement(session, users_table) -> None:
    stmt = select(users_table).where(users_table.c.age >= 18)
    result = rowguard.execute(
        session=session,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.is_clean


@pytest.mark.integration
def test_execute_with_connection(engine, users_table) -> None:
    with engine.connect() as connection:
        result = rowguard.select(
            connection=connection,
            table=users_table,
            model=UserRead,
            on_reject="collect",
            use_sqlrules=False,
        )
    assert result.valid_count == 2
    assert result.rejected_count == 1


@pytest.mark.integration
def test_select_with_user_where(session, users_table) -> None:
    result = rowguard.select(
        session=session,
        table=users_table,
        model=UserRead,
        where=[users_table.c.name == "Ada"],
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.models == (UserRead(id=1, name="Ada", age=37),)


@pytest.mark.integration
def test_validate_rows_collect() -> None:
    result = rowguard.validate_rows(
        rows=[
            {"id": 1, "name": "Ada", "age": 37},
            {"id": 2, "name": "Legacy", "age": 12},
        ],
        model=UserRead,
        on_reject="collect",
    )
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert result.statement is None


@pytest.mark.integration
def test_validate_rows_invalid_policy() -> None:
    with pytest.raises(ConfigurationError):
        rowguard.validate_rows(
            rows=[{"id": 1, "name": "Ada", "age": 37}],
            model=UserRead,
            on_reject="callback",
        )


@pytest.mark.integration
def test_stream_collect(session, users_table) -> None:
    with rowguard.stream(
        session=session,
        statement=select(users_table),
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    ) as stream:
        models = list(stream)
    assert len(models) == 2
    assert stream.rejected_count == 1
    assert stream.statistics.rows_read == 3


@pytest.mark.integration
def test_field_map_with_labeled_columns(session, users_table) -> None:
    class LegacyUser(BaseModel):
        id: int
        name: str
        age: Annotated[int, Field(ge=18)]

    stmt = select(
        users_table.c.id.label("user_id"),
        users_table.c.name.label("display_name"),
        users_table.c.age,
    )
    result = rowguard.execute(
        session=session,
        statement=stmt,
        model=LegacyUser,
        field_map={"id": "user_id", "name": "display_name"},
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.models[0].name in {"Ada", "Grace"}
