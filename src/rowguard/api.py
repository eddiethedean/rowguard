from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.sql import Select

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import ConfigurationError
from rowguard.execution.context import SyncExecutionContext
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import (
    AdapterConfig,
    DiagnosticsConfig,
    PushdownConfig,
    RejectionConfig,
    RejectionPolicyName,
    ValidationConfig,
)
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ValidationPlan,
)
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


def _build_request(
    *,
    model: type[T],
    source: Any | None = None,
    statement: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    pushdown_source: Any | None = None,
    strict: bool | None = None,
) -> QueryRequest[T]:
    if on_reject not in _POLICIES:
        raise ConfigurationError(
            f"Unsupported on_reject policy: {on_reject!r}. "
            f"Supported: {', '.join(sorted(_POLICIES))}"
        )
    policy: RejectionPolicyName = on_reject  # type: ignore[assignment]
    return QueryRequest(
        model=model,
        source=source,
        statement=statement,
        where=tuple(where),
        parameters=dict(parameters or {}),
        pushdown=PushdownConfig(
            enabled=use_sqlrules,
            source=pushdown_source,
            column_map=column_map,
            compiled_rules=compiled_rules,
        ),
        validation=ValidationConfig(strict=strict),
        rejection=RejectionConfig(policy=policy),
        diagnostics=DiagnosticsConfig(),
        adapter=AdapterConfig(field_map=field_map),
    )


def compile_plan(
    *,
    model: type[T],
    table: Any | None = None,
    statement: Select[Any] | None = None,
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    pushdown_source: Any | None = None,
    strict: bool | None = None,
) -> ExecutionPlan[T]:
    """Compile an immutable execution plan without running a query."""
    if table is not None and source is not None:
        raise ConfigurationError("Pass only one of table= or source=")
    request = _build_request(
        model=model,
        source=table if table is not None else source,
        statement=statement,
        where=where,
        field_map=field_map,
        column_map=column_map,
        parameters=parameters,
        on_reject=on_reject,
        use_sqlrules=use_sqlrules,
        compiled_rules=compiled_rules,
        pushdown_source=pushdown_source,
        strict=strict,
    )
    return QueryPlanner[T]().compile(request)


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
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
) -> QueryResult[T]:
    """Build and execute a validation-first SQLAlchemy SELECT query."""
    plan = compile_plan(
        model=model,
        table=table,
        where=where,
        field_map=field_map,
        column_map=column_map,
        parameters=parameters,
        on_reject=on_reject,
        use_sqlrules=use_sqlrules,
        compiled_rules=compiled_rules,
        strict=strict,
    )
    context = SyncExecutionContext(session=session, connection=connection)
    return SyncExecutionEngine[T]().execute(plan, context)


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
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
) -> QueryResult[T]:
    """Execute an existing SQLAlchemy statement and validate every row."""
    plan = compile_plan(
        model=model,
        statement=statement,
        source=source,
        where=where,
        field_map=field_map,
        column_map=column_map,
        parameters=parameters,
        on_reject=on_reject,
        use_sqlrules=use_sqlrules,
        compiled_rules=compiled_rules,
        pushdown_source=source,
        strict=strict,
    )
    context = SyncExecutionContext(session=session, connection=connection)
    return SyncExecutionEngine[T]().execute(plan, context)


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
    strict: bool | None = None,
) -> QueryResult[T]:
    """Validate row mappings without executing SQL."""
    policy_cls = _POLICIES.get(on_reject)
    if policy_cls is None:
        raise ConfigurationError(
            f"Unsupported on_reject policy: {on_reject!r}. "
            f"Supported: {', '.join(sorted(_POLICIES))}"
        )

    if field_map:
        model_fields = set(model.model_fields.keys())
        unknown = sorted(set(field_map.keys()) - model_fields)
        if unknown:
            raise ConfigurationError(
                f"field_map keys are not model fields: {', '.join(unknown)}"
            )

    plan: ExecutionPlan[T] = ExecutionPlan(
        statement=None,
        model=model,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(
            adapter=SQLAlchemyRowAdapter(field_map=field_map),
            field_map=dict(field_map) if field_map else None,
        ),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(model, strict=strict),
            model=model,
            strict=strict,
        ),
        rejection_plan=RejectionPlan(policy=policy_cls(), policy_name=on_reject),
        use_sqlrules=False,
    )
    return SyncExecutionEngine[T]().validate_rows(plan=plan, rows=rows)
