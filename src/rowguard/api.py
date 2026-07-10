from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.sql import Select

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import ConfigurationError
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.planning.request import QueryRequest
from rowguard.rejection.base import RejectionPolicy
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.results.query_result import QueryResult
from rowguard.validation.pydantic import PydanticValidator

T = TypeVar("T", bound=BaseModel)

_POLICIES: dict[str, type[RejectionPolicy]] = {
    "raise": RaisePolicy,
    "collect": CollectPolicy,
    "skip": SkipPolicy,
}


def select(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    table: Any,
    model: type[T],
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    use_sqlrules: bool = True,
) -> QueryResult[T]:
    """Build and execute a validation-first SQLAlchemy SELECT query."""
    request: QueryRequest[T] = QueryRequest(
        model=model,
        source=table,
        session=session,
        connection=connection,
        where=tuple(where),
        field_map=field_map,
        column_map=column_map,
        parameters=dict(parameters or {}),
        on_reject=on_reject,
        use_sqlrules=use_sqlrules,
    )
    plan = QueryPlanner[T]().compile(request)
    return SyncExecutionEngine[T]().execute(plan)


def execute(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    statement: Select[Any],
    model: type[T],
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    use_sqlrules: bool = True,
) -> QueryResult[T]:
    """Execute an existing SQLAlchemy statement and validate every row."""
    request: QueryRequest[T] = QueryRequest(
        model=model,
        source=source,
        statement=statement,
        session=session,
        connection=connection,
        where=tuple(where),
        field_map=field_map,
        column_map=column_map,
        parameters=dict(parameters or {}),
        on_reject=on_reject,
        use_sqlrules=use_sqlrules,
    )
    plan = QueryPlanner[T]().compile(request)
    return SyncExecutionEngine[T]().execute(plan)


def stream(
    *,
    session: Any,
    statement: Select[Any],
    model: type[T],
    on_reject: str = "raise",
) -> Iterable[T]:
    """Stream validated models without buffering all accepted rows.

    Deferred until 0.3.0.
    """
    raise NotImplementedError(
        "stream() is deferred to RowGuard 0.3.0; use select()/execute() for buffered results"
    )


def validate_rows(
    *,
    rows: Iterable[Mapping[str, object]],
    model: type[T],
    field_map: Mapping[str, str] | None = None,
    on_reject: str = "raise",
) -> QueryResult[T]:
    """Validate row mappings without executing SQL."""
    policy_cls = _POLICIES.get(on_reject)
    if policy_cls is None:
        raise ConfigurationError(
            f"Unsupported on_reject policy: {on_reject!r}. "
            f"Supported: {', '.join(sorted(_POLICIES))}"
        )

    plan: ExecutionPlan[T] = ExecutionPlan(
        statement=None,
        model=model,
        adapter=SQLAlchemyRowAdapter(field_map=field_map),
        validator=PydanticValidator(model),
        rejection_policy=policy_cls(),
        use_sqlrules=False,
    )
    return SyncExecutionEngine[T]().validate_rows(plan=plan, rows=rows)
