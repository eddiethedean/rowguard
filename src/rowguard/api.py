from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.sql import Select

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.errors import ConfigurationError
from rowguard.execution.async_ import AsyncExecutionEngine
from rowguard.execution.context import AsyncExecutionContext, SyncExecutionContext
from rowguard.execution.observer import StreamObserver
from rowguard.execution.streaming import AsyncStreamEngine, SyncStreamEngine
from rowguard.execution.sync import SyncExecutionEngine
from rowguard.planning.compiler import QueryPlanner
from rowguard.planning.config import (
    AdapterConfig,
    CallbackErrorMode,
    CallbackValuesMode,
    DiagnosticsConfig,
    OrmValidationMode,
    PushdownConfig,
    QuarantineErrorMode,
    QuarantineRetentionMode,
    QuarantineTransactionMode,
    QuarantineValuesMode,
    RejectionConfig,
    RejectionPolicyName,
    StreamingConfig,
    UnloadedAttributesPolicy,
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
from rowguard.rejection.callback import CallbackPolicy
from rowguard.rejection.log import LogPolicy
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.rejection.quarantine import QuarantinePolicy
from rowguard.results.async_stream_result import AsyncStreamResult
from rowguard.results.query_result import QueryResult
from rowguard.results.stream_result import StreamResult
from rowguard.validation.pydantic import PydanticValidator

T = TypeVar("T", bound=BaseModel)

_SUPPORTED_POLICIES = ("raise", "collect", "skip", "callback", "quarantine", "log")
_CALLBACK_ERROR_MODES = frozenset({"raise", "log", "continue", "reject_handler"})
_CALLBACK_VALUES_MODES = frozenset({"full", "redacted", "metadata_only"})
_QUARANTINE_ERROR_MODES = frozenset({"raise", "collect", "log"})
_QUARANTINE_VALUES_MODES = frozenset({"full", "redacted", "metadata_only"})
_QUARANTINE_RETENTION_MODES = frozenset({"receipt", "rejection", "both", "none"})


def _rejection_config(
    *,
    on_reject: str,
    reject_callback: Any | None,
    quarantine: Any | None,
    on_callback_error: CallbackErrorMode,
    callback_values: CallbackValuesMode,
    on_quarantine_error: QuarantineErrorMode,
    quarantine_values: QuarantineValuesMode,
    quarantine_retention: QuarantineRetentionMode,
    quarantine_transaction: QuarantineTransactionMode,
    redact_fields: Iterable[str] | None,
    max_rejections: int | None,
    max_rejection_rate: float | None,
    async_execution: bool,
) -> RejectionConfig:
    if on_reject not in _SUPPORTED_POLICIES:
        raise ConfigurationError(
            f"Unsupported on_reject policy: {on_reject!r}. "
            f"Supported: {', '.join(_SUPPORTED_POLICIES)}"
        )
    if on_reject == "callback" and reject_callback is None:
        raise ConfigurationError("on_reject='callback' requires reject_callback=")
    if on_reject == "quarantine" and quarantine is None:
        raise ConfigurationError("on_reject='quarantine' requires quarantine=")
    if on_reject != "callback" and reject_callback is not None:
        raise ConfigurationError("reject_callback= is only valid with on_reject='callback'")
    if on_reject != "quarantine" and quarantine is not None:
        raise ConfigurationError("quarantine= is only valid with on_reject='quarantine'")
    if on_reject != "callback":
        if on_callback_error != "raise":
            raise ConfigurationError(
                "on_callback_error= is only valid with on_reject='callback'"
            )
        if callback_values != "full":
            raise ConfigurationError(
                "callback_values= is only valid with on_reject='callback'"
            )
    if on_reject != "quarantine":
        if on_quarantine_error != "raise":
            raise ConfigurationError(
                "on_quarantine_error= is only valid with on_reject='quarantine'"
            )
        if quarantine_values != "full":
            raise ConfigurationError(
                "quarantine_values= is only valid with on_reject='quarantine'"
            )
        if quarantine_retention != "receipt":
            raise ConfigurationError(
                "quarantine_retention= is only valid with on_reject='quarantine'"
            )
    if on_reject not in {"callback", "quarantine"} and redact_fields is not None:
        raise ConfigurationError(
            "redact_fields= is only valid with on_reject='callback' or 'quarantine'"
        )
    if on_callback_error not in _CALLBACK_ERROR_MODES:
        raise ConfigurationError(f"Unsupported on_callback_error: {on_callback_error!r}")
    if callback_values not in _CALLBACK_VALUES_MODES:
        raise ConfigurationError(f"Unsupported callback_values: {callback_values!r}")
    if on_quarantine_error not in _QUARANTINE_ERROR_MODES:
        raise ConfigurationError(
            f"Unsupported on_quarantine_error: {on_quarantine_error!r}"
        )
    if quarantine_values not in _QUARANTINE_VALUES_MODES:
        raise ConfigurationError(f"Unsupported quarantine_values: {quarantine_values!r}")
    if quarantine_retention not in _QUARANTINE_RETENTION_MODES:
        raise ConfigurationError(
            f"Unsupported quarantine_retention: {quarantine_retention!r}"
        )
    if max_rejections is not None and max_rejections < 0:
        raise ConfigurationError("max_rejections must be >= 0")
    if max_rejection_rate is not None and not (0.0 <= max_rejection_rate <= 1.0):
        raise ConfigurationError("max_rejection_rate must be between 0.0 and 1.0")
    if quarantine_transaction != "separate":
        raise ConfigurationError(
            "quarantine_transaction must be 'separate' in 0.6 "
            f"(got {quarantine_transaction!r})"
        )

    policy: RejectionPolicyName = on_reject  # type: ignore[assignment]
    return RejectionConfig(
        policy=policy,
        reject_callback=reject_callback,
        quarantine_provider=quarantine,
        on_callback_error=on_callback_error,
        callback_values=callback_values,
        on_quarantine_error=on_quarantine_error,
        quarantine_values=quarantine_values,
        quarantine_retention=quarantine_retention,
        quarantine_transaction=quarantine_transaction,
        redact_fields=frozenset(redact_fields) if redact_fields is not None else None,
        max_rejections=max_rejections,
        max_rejection_rate=max_rejection_rate,
        async_execution=async_execution,
    )


def _build_request(
    *,
    model: type[T],
    source: Any | None = None,
    statement: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    pushdown_source: Any | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
    async_execution: bool = False,
) -> QueryRequest[T]:
    if orm_validation not in {"mapping", "from_attributes"}:
        raise ConfigurationError(
            f"Unsupported orm_validation: {orm_validation!r}. "
            "Supported: mapping, from_attributes"
        )
    if unloaded_attributes != "error":
        raise ConfigurationError(
            f"Unsupported unloaded_attributes: {unloaded_attributes!r}. "
            "Supported: error"
        )
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
        validation=ValidationConfig(
            strict=strict,
            from_attributes=orm_validation == "from_attributes",
        ),
        rejection=_rejection_config(
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            async_execution=async_execution,
        ),
        diagnostics=DiagnosticsConfig(),
        adapter=AdapterConfig(
            field_map=field_map,
            attribute_map=attribute_map,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
        ),
    )


def compile_plan(
    *,
    model: type[T],
    table: Any | None = None,
    statement: Select[Any] | None = None,
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    pushdown_source: Any | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
    async_execution: bool = False,
) -> ExecutionPlan[T]:
    """Compile an immutable execution plan without running a query."""
    if table is not None and source is not None:
        raise ConfigurationError("Pass only one of table= or source=")
    if table is not None and statement is not None:
        raise ConfigurationError("Pass only one of table= or statement=")
    request = _build_request(
        model=model,
        source=table if table is not None else source,
        statement=statement,
        where=where,
        field_map=field_map,
        attribute_map=attribute_map,
        column_map=column_map,
        parameters=parameters,
        on_reject=on_reject,
        reject_callback=reject_callback,
        quarantine=quarantine,
        on_callback_error=on_callback_error,
        callback_values=callback_values,
        on_quarantine_error=on_quarantine_error,
        quarantine_values=quarantine_values,
        quarantine_retention=quarantine_retention,
        quarantine_transaction=quarantine_transaction,
        redact_fields=redact_fields,
        max_rejections=max_rejections,
        max_rejection_rate=max_rejection_rate,
        use_sqlrules=use_sqlrules,
        compiled_rules=compiled_rules,
        pushdown_source=pushdown_source,
        strict=strict,
        orm_validation=orm_validation,
        unloaded_attributes=unloaded_attributes,
        async_execution=async_execution,
    )
    return QueryPlanner[T]().compile(request)


def _plan_kwargs(
    *,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    async_execution: bool = False,
    **base: Any,
) -> dict[str, Any]:
    return {
        **base,
        "on_reject": on_reject,
        "reject_callback": reject_callback,
        "quarantine": quarantine,
        "on_callback_error": on_callback_error,
        "callback_values": callback_values,
        "on_quarantine_error": on_quarantine_error,
        "quarantine_values": quarantine_values,
        "quarantine_retention": quarantine_retention,
        "quarantine_transaction": quarantine_transaction,
        "redact_fields": redact_fields,
        "max_rejections": max_rejections,
        "max_rejection_rate": max_rejection_rate,
        "async_execution": async_execution,
    }


def select(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    table: Any,
    model: type[T],
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
) -> QueryResult[T]:
    """Build and execute a validation-first SQLAlchemy SELECT query.

    ``table`` may be a Core ``Table`` or an ORM / SQLModel mapped class.
    """
    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            table=table,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
        )
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
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
) -> QueryResult[T]:
    """Execute an existing SQLAlchemy statement and validate every row."""
    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            statement=statement,
            source=source,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            pushdown_source=source,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
        )
    )
    context = SyncExecutionContext(session=session, connection=connection)
    return SyncExecutionEngine[T]().execute(plan, context)


def stream(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    table: Any | None = None,
    statement: Select[Any] | None = None,
    model: type[T],
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
    yield_per: int | None = None,
    observers: Sequence[StreamObserver] | None = None,
) -> StreamResult[T]:
    """Stream validated models without buffering all accepted rows.

    Pass exactly one of ``table`` or ``statement``. Accepted models are yielded
    incrementally and never retained on the result object.
    """
    if (table is None) == (statement is None):
        raise ConfigurationError("Pass exactly one of table= or statement=")
    if table is not None and source is not None:
        raise ConfigurationError("Pass only one of table= or source=")
    if yield_per is not None and yield_per <= 0:
        raise ConfigurationError("yield_per must be a positive integer")

    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            table=table,
            statement=statement,
            source=source,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            pushdown_source=source if statement is not None else None,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
        )
    )
    context = SyncExecutionContext(session=session, connection=connection)
    return SyncStreamEngine[T]().open(
        plan,
        context,
        streaming=StreamingConfig(stream_results=True, yield_per=yield_per),
        observers=observers or (),
    )


async def aselect(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    table: Any,
    model: type[T],
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
) -> QueryResult[T]:
    """Async variant of ``select`` using AsyncSession or AsyncConnection."""
    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            table=table,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
            async_execution=True,
        )
    )
    context = AsyncExecutionContext(session=session, connection=connection)
    return await AsyncExecutionEngine[T]().execute(plan, context)


async def aexecute(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    statement: Select[Any],
    model: type[T],
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
) -> QueryResult[T]:
    """Async variant of ``execute`` using AsyncSession or AsyncConnection."""
    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            statement=statement,
            source=source,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            pushdown_source=source,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
            async_execution=True,
        )
    )
    context = AsyncExecutionContext(session=session, connection=connection)
    return await AsyncExecutionEngine[T]().execute(plan, context)


def astream(
    *,
    session: Any | None = None,
    connection: Any | None = None,
    table: Any | None = None,
    statement: Select[Any] | None = None,
    model: type[T],
    source: Any | None = None,
    where: Iterable[Any] = (),
    field_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
    column_map: Mapping[str, Any] | None = None,
    parameters: Mapping[str, object] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    use_sqlrules: bool = True,
    compiled_rules: Mapping[str, Any] | None = None,
    strict: bool | None = None,
    orm_validation: OrmValidationMode = "mapping",
    unloaded_attributes: UnloadedAttributesPolicy = "error",
    yield_per: int | None = None,
    observers: Sequence[StreamObserver] | None = None,
) -> AsyncStreamResult[T]:
    """Async stream of validated models without buffering accepted rows.

    Returns immediately; iteration starts on ``async with`` / ``async for``.
    Pydantic validation remains synchronous on the event loop.
    """
    if (table is None) == (statement is None):
        raise ConfigurationError("Pass exactly one of table= or statement=")
    if table is not None and source is not None:
        raise ConfigurationError("Pass only one of table= or source=")
    if yield_per is not None and yield_per <= 0:
        raise ConfigurationError("yield_per must be a positive integer")

    plan = compile_plan(
        **_plan_kwargs(
            model=model,
            table=table,
            statement=statement,
            source=source,
            where=where,
            field_map=field_map,
            attribute_map=attribute_map,
            column_map=column_map,
            parameters=parameters,
            on_reject=on_reject,
            reject_callback=reject_callback,
            quarantine=quarantine,
            on_callback_error=on_callback_error,
            callback_values=callback_values,
            on_quarantine_error=on_quarantine_error,
            quarantine_values=quarantine_values,
            quarantine_retention=quarantine_retention,
            quarantine_transaction=quarantine_transaction,
            redact_fields=redact_fields,
            max_rejections=max_rejections,
            max_rejection_rate=max_rejection_rate,
            use_sqlrules=use_sqlrules,
            compiled_rules=compiled_rules,
            pushdown_source=source if statement is not None else None,
            strict=strict,
            orm_validation=orm_validation,
            unloaded_attributes=unloaded_attributes,
            async_execution=True,
        )
    )
    context = AsyncExecutionContext(session=session, connection=connection)
    return AsyncStreamEngine[T]().open(
        plan,
        context,
        streaming=StreamingConfig(stream_results=True, yield_per=yield_per),
        observers=observers or (),
    )


def validate_rows(
    *,
    rows: Iterable[Mapping[str, object]],
    model: type[T],
    field_map: Mapping[str, str] | None = None,
    on_reject: str = "raise",
    reject_callback: Any | None = None,
    quarantine: Any | None = None,
    on_callback_error: CallbackErrorMode = "raise",
    callback_values: CallbackValuesMode = "full",
    on_quarantine_error: QuarantineErrorMode = "raise",
    quarantine_values: QuarantineValuesMode = "full",
    quarantine_retention: QuarantineRetentionMode = "receipt",
    quarantine_transaction: QuarantineTransactionMode = "separate",
    redact_fields: Iterable[str] | None = None,
    max_rejections: int | None = None,
    max_rejection_rate: float | None = None,
    strict: bool | None = None,
) -> QueryResult[T]:
    """Validate row mappings without executing SQL."""
    cfg = _rejection_config(
        on_reject=on_reject,
        reject_callback=reject_callback,
        quarantine=quarantine,
        on_callback_error=on_callback_error,
        callback_values=callback_values,
        on_quarantine_error=on_quarantine_error,
        quarantine_values=quarantine_values,
        quarantine_retention=quarantine_retention,
        quarantine_transaction=quarantine_transaction,
        redact_fields=redact_fields,
        max_rejections=max_rejections,
        max_rejection_rate=max_rejection_rate,
        async_execution=False,
    )

    if field_map:
        model_fields = set(model.model_fields.keys())
        unknown = sorted(set(field_map.keys()) - model_fields)
        if unknown:
            raise ConfigurationError(
                f"field_map keys are not model fields: {', '.join(unknown)}"
            )

    import inspect

    policy: RejectionPolicy
    if cfg.policy == "callback":
        callback = cfg.reject_callback
        assert callback is not None
        if inspect.iscoroutinefunction(callback):
            raise ConfigurationError(
                "Async reject_callback requires aselect/aexecute/astream"
            )
        policy = CallbackPolicy(
            callback=callback,
            on_callback_error=cfg.on_callback_error,
            callback_values=cfg.callback_values,
            redact_fields=cfg.redact_fields,
            async_mode=False,
        )
    elif cfg.policy == "quarantine":
        provider = cfg.quarantine_provider
        assert provider is not None
        if not callable(getattr(provider, "write", None)):
            raise ConfigurationError(
                "Sync APIs require a quarantine provider with write()"
            )
        policy = QuarantinePolicy(
            provider=provider,
            on_quarantine_error=cfg.on_quarantine_error,
            quarantine_values=cfg.quarantine_values,
            quarantine_retention=cfg.quarantine_retention,
            redact_fields=cfg.redact_fields,
            async_mode=False,
        )
    elif cfg.policy == "log":
        policy = LogPolicy()
    elif cfg.policy == "raise":
        policy = RaisePolicy()
    elif cfg.policy == "collect":
        policy = CollectPolicy()
    else:
        policy = SkipPolicy()

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
        rejection_plan=RejectionPlan(
            policy=policy,
            policy_name=on_reject,
            max_rejections=cfg.max_rejections,
            max_rejection_rate=cfg.max_rejection_rate,
            quarantine_retention=cfg.quarantine_retention,
        ),
        use_sqlrules=False,
    )
    return SyncExecutionEngine[T]().validate_rows(plan=plan, rows=rows)
