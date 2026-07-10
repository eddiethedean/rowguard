from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select

import rowguard
from rowguard.errors import RowValidationError


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


@pytest.mark.integration
async def test_aselect_collect(async_session, users_table) -> None:
    result = await rowguard.aselect(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert {m.name for m in result.models} == {"Ada", "Grace"}


@pytest.mark.integration
async def test_aselect_raise(async_session, users_table) -> None:
    with pytest.raises(RowValidationError):
        await rowguard.aselect(
            session=async_session,
            table=users_table,
            model=UserRead,
            on_reject="raise",
            use_sqlrules=False,
        )


@pytest.mark.integration
async def test_aselect_skip(async_session, users_table) -> None:
    result = await rowguard.aselect(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="skip",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert result.statistics.rows_rejected == 1


@pytest.mark.integration
async def test_aselect_sqlrules_pushdown(async_session, users_table) -> None:
    result = await rowguard.aselect(
        session=async_session,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=True,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert any(d.code == "sqlrules.pushdown_applied" for d in result.diagnostics)


@pytest.mark.integration
async def test_aexecute_statement(async_session, users_table) -> None:
    stmt = select(users_table).where(users_table.c.age >= 18)
    result = await rowguard.aexecute(
        session=async_session,
        statement=stmt,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.is_clean


@pytest.mark.integration
async def test_aselect_with_connection(async_connection, users_table) -> None:
    result = await rowguard.aselect(
        connection=async_connection,
        table=users_table,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    assert result.valid_count == 2
    assert result.rejected_count == 1
