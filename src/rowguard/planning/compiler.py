from __future__ import annotations

from dataclasses import replace
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Table

from rowguard.adapters.orm_entity import ORMEntityAdapter
from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.cache import LRUCache
from rowguard.diagnostics import Diagnostic
from rowguard.errors import PlanningError
from rowguard.integrations.sqlalchemy_core import apply_where, build_select, is_select
from rowguard.integrations.sqlalchemy_orm import (
    classify_select_shape,
    is_mapped_class,
    is_relationship_attr,
    mapped_columns,
    scalar_attr_keys,
    single_entity_class,
)
from rowguard.integrations.sqlmodel import is_sqlmodel_table
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ResolvedSource,
    ValidationPlan,
)
from rowguard.planning.request import QueryRequest
from rowguard.rejection.base import RejectionPolicy
from rowguard.rejection.callback import CallbackPolicy
from rowguard.rejection.log import LogPolicy
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.rejection.quarantine import QuarantinePolicy
from rowguard.validation.pydantic import PydanticValidator

T = TypeVar("T", bound=BaseModel)

_SIMPLE_POLICIES: dict[str, type[RejectionPolicy]] = {
    "raise": RaisePolicy,
    "collect": CollectPolicy,
    "skip": SkipPolicy,
    "log": LogPolicy,
}


def _model_field_names(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields.keys())


def _table_column_names(source: Any) -> dict[str, Any]:
    if isinstance(source, Table):
        return {col.name: col for col in source.columns}
    if is_sqlmodel_table(source) or is_mapped_class(source):
        return mapped_columns(source)
    if is_select(source):
        try:
            return {col.key: col for col in source.selected_columns}
        except Exception:
            return {}
    columns = getattr(source, "c", None) or getattr(source, "columns", None)
    if columns is None:
        return {}
    try:
        return {col.name: col for col in columns}
    except TypeError:
        return {}


def _source_fingerprint(source: Any | None) -> tuple[Any, ...]:
    if source is None:
        return (None,)
    return (
        id(source),
        type(source).__name__,
        getattr(source, "name", None),
        getattr(source, "__name__", None),
    )


def _column_map_fingerprint(column_map: dict[str, Any] | None) -> tuple[Any, ...]:
    if not column_map:
        return ()
    return tuple(sorted((key, id(value)) for key, value in column_map.items()))


def _rebinding_cached_plan(
    cached: ExecutionPlan[Any],
    *,
    parameters: dict[str, object],
    execution_id: str,
) -> ExecutionPlan[Any]:
    """Rebind parameters and rewrite diagnostic execution IDs on a cache hit."""
    diagnostics = tuple(
        replace(diagnostic, execution_id=execution_id) for diagnostic in cached.diagnostics
    )
    pushdown_plan = replace(
        cached.pushdown_plan,
        diagnostics=tuple(
            replace(diagnostic, execution_id=execution_id)
            for diagnostic in cached.pushdown_plan.diagnostics
        ),
    )
    return replace(
        cached,
        parameters=parameters,
        execution_id=execution_id,
        diagnostics=diagnostics,
        pushdown_plan=pushdown_plan,
    )


class QueryPlanner(Generic[T]):
    def __init__(
        self,
        *,
        rules_bridge: SQLRulesBridge | None = None,
        cache: LRUCache[str, ExecutionPlan[Any]] | None = None,
        cache_enabled: bool = False,
    ) -> None:
        self._rules_bridge = rules_bridge or SQLRulesBridge()
        self._cache = cache
        self._cache_enabled = cache_enabled and cache is not None

    def compile(self, request: QueryRequest[T]) -> ExecutionPlan[T]:
        self._validate_request(request)
        cache_key: str | None = None
        if self._cache_enabled:
            cache_key = self._cache_key(request)
            assert self._cache is not None
            cached = self._cache.get(cache_key)
            if cached is not None:
                execution_id = uuid4().hex
                return _rebinding_cached_plan(
                    cached,
                    parameters=dict(request.parameters),
                    execution_id=execution_id,
                )

        execution_id = uuid4().hex
        diagnostics: list[Diagnostic] = []

        resolved = self._resolve_source(request, execution_id=execution_id)
        if resolved is not None and request.diagnostics.enabled:
            diagnostics.append(
                Diagnostic(
                    code="planning.source_resolved",
                    severity="info",
                    execution_id=execution_id,
                    metadata={
                        "kind": resolved.kind,
                        "source_name": resolved.source_name,
                    },
                )
            )

        statement = self._plan_statement(request, resolved)
        pushdown_plan = self._plan_pushdown(
            request,
            resolved=resolved,
            execution_id=execution_id,
        )
        diagnostics.extend(pushdown_plan.diagnostics)

        statement = apply_where(
            statement,
            (*pushdown_plan.expressions, *request.where),
        )

        adapter_plan = self._plan_adapter(
            request,
            resolved=resolved,
            statement=statement,
            execution_id=execution_id,
        )
        validation_plan = self._plan_validation(request, adapter_plan=adapter_plan)
        rejection_plan = self._plan_rejection(request, execution_id=execution_id)

        plan = ExecutionPlan(
            statement=statement,
            model=request.model,
            pushdown_plan=pushdown_plan,
            adapter_plan=adapter_plan,
            validation_plan=validation_plan,
            rejection_plan=rejection_plan,
            parameters=dict(request.parameters),
            diagnostics=tuple(diagnostics),
            execution_id=execution_id,
            resolved_source=resolved,
            use_sqlrules=pushdown_plan.enabled,
        )
        if self._cache_enabled and cache_key is not None:
            assert self._cache is not None
            self._cache.set(cache_key, plan)
        return plan

    def _cache_key(self, request: QueryRequest[T]) -> str:
        # Structural key only — exclude bind parameter values (rebound on hit).
        field_map = tuple(sorted((request.adapter.field_map or {}).items()))
        attribute_map = tuple(sorted((request.adapter.attribute_map or {}).items()))
        compiled_rules = request.pushdown.compiled_rules
        return repr(
            (
                request.model.__module__,
                request.model.__qualname__,
                _source_fingerprint(request.source),
                id(request.statement) if request.statement is not None else None,
                request.where,
                field_map,
                attribute_map,
                request.adapter.orm_validation,
                request.adapter.unloaded_attributes,
                _column_map_fingerprint(
                    dict(request.pushdown.column_map) if request.pushdown.column_map else None
                ),
                request.pushdown.enabled,
                id(compiled_rules) if compiled_rules is not None else None,
                _source_fingerprint(request.pushdown.source),
                request.validation.strict,
                request.adapter.orm_validation,
                request.diagnostics.enabled,
                request.rejection.policy,
            )
        )

    def _validate_request(self, request: QueryRequest[T]) -> None:
        if not issubclass(request.model, BaseModel):
            raise PlanningError(
                "model must be a Pydantic BaseModel subclass",
                stage="request",
            )
        if request.source is None and request.statement is None:
            raise PlanningError(
                "Either source (table) or statement is required",
                stage="request",
            )
        supported = sorted({*_SIMPLE_POLICIES, "callback", "quarantine"})
        if request.rejection.policy not in supported:
            raise PlanningError(
                f"Unsupported on_reject policy: {request.rejection.policy!r}. "
                f"Supported: {', '.join(supported)}",
                stage="rejection",
            )
        if request.rejection.policy == "callback" and request.rejection.reject_callback is None:
            raise PlanningError(
                "on_reject='callback' requires reject_callback=",
                stage="rejection",
            )
        if (
            request.rejection.policy == "quarantine"
            and request.rejection.quarantine_provider is None
        ):
            raise PlanningError(
                "on_reject='quarantine' requires quarantine=",
                stage="rejection",
            )
        if request.rejection.max_rejections is not None and request.rejection.max_rejections < 0:
            raise PlanningError(
                "max_rejections must be >= 0",
                stage="rejection",
            )
        if request.rejection.max_rejection_rate is not None and not (
            0.0 <= request.rejection.max_rejection_rate <= 1.0
        ):
            raise PlanningError(
                "max_rejection_rate must be between 0.0 and 1.0",
                stage="rejection",
            )
        if request.rejection.quarantine_transaction != "separate":
            raise PlanningError(
                "quarantine_transaction must be 'separate' in 0.6 "
                f"(got {request.rejection.quarantine_transaction!r})",
                stage="rejection",
            )
        if request.adapter.orm_validation not in {"mapping", "from_attributes"}:
            raise PlanningError(
                f"Unsupported orm_validation: {request.adapter.orm_validation!r}. "
                "Supported: mapping, from_attributes",
                stage="adapter",
            )
        if request.adapter.unloaded_attributes != "error":
            raise PlanningError(
                f"Unsupported unloaded_attributes: {request.adapter.unloaded_attributes!r}. "
                "Supported in 0.5: error",
                stage="adapter",
            )
        if (
            request.adapter.attribute_map is not None
            and request.adapter.orm_validation == "from_attributes"
        ):
            raise PlanningError(
                "attribute_map cannot be combined with orm_validation='from_attributes'; "
                "use orm_validation='mapping' when remapping entity attributes",
                stage="adapter",
            )

    def _resolve_source(
        self,
        request: QueryRequest[T],
        *,
        execution_id: str,
    ) -> ResolvedSource | None:
        """Resolve the query selectable from request.source only.

        pushdown.source is handled exclusively in ``_plan_pushdown``.
        """
        source = request.source
        if source is None:
            return None
        if isinstance(source, Table):
            return ResolvedSource(
                kind="table",
                selectable=source,
                columns=_table_column_names(source),
                source_name=source.name,
            )
        if is_sqlmodel_table(source):
            table = mapped_columns(source)
            return ResolvedSource(
                kind="sqlmodel",
                selectable=source,
                columns=table,
                source_name=getattr(getattr(source, "__table__", None), "name", None)
                or getattr(source, "__tablename__", None),
                metadata={"execution_id": execution_id},
            )
        if is_mapped_class(source):
            return ResolvedSource(
                kind="orm",
                selectable=source,
                columns=mapped_columns(source),
                source_name=getattr(getattr(source, "__table__", None), "name", None)
                or getattr(source, "__tablename__", None),
                metadata={"execution_id": execution_id},
            )
        if is_select(source):
            return ResolvedSource(
                kind="select",
                selectable=source,
                columns={},
                source_name=None,
            )
        columns = _table_column_names(source)
        return ResolvedSource(
            kind=type(source).__name__,
            selectable=source,
            columns=columns,
            source_name=getattr(source, "name", None),
            metadata={"execution_id": execution_id},
        )

    def _plan_statement(
        self,
        request: QueryRequest[T],
        resolved: ResolvedSource | None,
    ) -> Any:
        if request.statement is not None:
            if not is_select(request.statement):
                raise PlanningError(
                    "statement must be a SQLAlchemy Select, "
                    f"got {type(request.statement).__name__}",
                    stage="statement",
                )
            return request.statement
        if resolved is None or resolved.selectable is None:
            raise PlanningError("No selectable source available", stage="statement")
        # A Select passed as source= is already the statement.
        if resolved.kind == "select" and is_select(resolved.selectable):
            return resolved.selectable
        return build_select(resolved.selectable)

    def _plan_pushdown(
        self,
        request: QueryRequest[T],
        *,
        resolved: ResolvedSource | None,
        execution_id: str,
    ) -> PushdownPlan:
        if not request.pushdown.enabled:
            return PushdownPlan(
                enabled=False,
                diagnostics=(
                    Diagnostic(
                        code="planning.pushdown_disabled",
                        severity="info",
                        execution_id=execution_id,
                        metadata={},
                    ),
                ),
            )

        pushdown_source = (
            request.pushdown.source
            if request.pushdown.source is not None
            else (resolved.selectable if resolved is not None else None)
        )
        if pushdown_source is None:
            if (
                request.pushdown.compiled_rules is not None
                or request.pushdown.column_map is not None
            ):
                raise PlanningError(
                    "compiled_rules and column_map require a pushdown source "
                    "(table= or source=); statement-only queries cannot apply pushdown",
                    stage="pushdown",
                    execution_id=execution_id,
                )
            return PushdownPlan(
                enabled=False,
                diagnostics=(
                    Diagnostic(
                        code="sqlrules.pushdown_skipped",
                        severity="info",
                        execution_id=execution_id,
                        metadata={
                            "reason": "no pushdown source available for statement-only execute"
                        },
                    ),
                ),
            )

        pushdown_columns = _table_column_names(pushdown_source)
        self._validate_column_map(
            request,
            columns=pushdown_columns,
            execution_id=execution_id,
        )

        diagnostics: list[Diagnostic] = []
        if request.statement is not None and (
            request.source is not None or request.pushdown.source is not None
        ):
            diagnostics.append(
                Diagnostic(
                    code="sqlrules.pushdown_source_explicit",
                    severity="info",
                    execution_id=execution_id,
                    metadata={
                        "reason": (
                            "pushdown compiled against explicit source= "
                            "and applied to the provided statement"
                        )
                    },
                )
            )

        compiled = self._rules_bridge.compile(
            model=request.model,
            source=pushdown_source,
            column_map=request.pushdown.column_map,
            compiled_rules=request.pushdown.compiled_rules,
            execution_id=execution_id,
        )
        diagnostics.extend(compiled.diagnostics)
        return PushdownPlan(
            enabled=True,
            expressions=compiled.expressions,
            compiled_rules=compiled.compiled_rules,
            precompiled=compiled.precompiled,
            diagnostics=tuple(diagnostics),
        )

    def _validate_column_map(
        self,
        request: QueryRequest[T],
        *,
        columns: dict[str, Any],
        execution_id: str,
    ) -> None:
        column_map = request.pushdown.column_map
        if not column_map:
            return
        model_fields = _model_field_names(request.model)
        unknown = sorted(set(column_map.keys()) - model_fields)
        if unknown:
            raise PlanningError(
                f"column_map keys are not model fields: {', '.join(unknown)}",
                stage="pushdown",
                execution_id=execution_id,
            )
        if columns:
            missing_cols = sorted(
                name for name, col in column_map.items() if col not in columns.values()
            )
            if missing_cols:
                raise PlanningError(
                    "column_map columns are not members of the pushdown source: "
                    + ", ".join(missing_cols),
                    stage="pushdown",
                    execution_id=execution_id,
                )

    def _plan_adapter(
        self,
        request: QueryRequest[T],
        *,
        resolved: ResolvedSource | None,
        statement: Any,
        execution_id: str,
    ) -> AdapterPlan:
        field_map = request.adapter.field_map
        attribute_map = request.adapter.attribute_map
        if field_map:
            model_fields = _model_field_names(request.model)
            unknown = sorted(set(field_map.keys()) - model_fields)
            if unknown:
                raise PlanningError(
                    f"field_map keys are not model fields: {', '.join(unknown)}",
                    stage="adapter",
                    execution_id=execution_id,
                )

        if attribute_map:
            model_fields = _model_field_names(request.model)
            unknown = sorted(set(attribute_map.keys()) - model_fields)
            if unknown:
                raise PlanningError(
                    f"attribute_map keys are not model fields: {', '.join(unknown)}",
                    stage="adapter",
                    execution_id=execution_id,
                )

        shape = classify_select_shape(statement) if is_select(statement) else "projection"
        if shape == "unsupported":
            raise PlanningError(
                "Multi-entity or entity+scalar result shapes are not supported. "
                "Use a single-entity select(User) or an explicit column projection.",
                stage="adapter",
                execution_id=execution_id,
            )

        orm_validation = request.adapter.orm_validation
        if shape == "entity":
            entity_cls = single_entity_class(statement)
            if entity_cls is None and resolved is not None and is_mapped_class(
                resolved.selectable
            ):
                entity_cls = resolved.selectable
            if entity_cls is None:
                raise PlanningError(
                    "Could not resolve mapped class for entity select",
                    stage="adapter",
                    execution_id=execution_id,
                )
            if field_map:
                raise PlanningError(
                    "field_map is only valid for projected column results; "
                    "use attribute_map for single-entity ORM selects",
                    stage="adapter",
                    execution_id=execution_id,
                )

            known_attrs = scalar_attr_keys(entity_cls)
            if attribute_map:
                for attr_name in attribute_map.values():
                    if is_relationship_attr(entity_cls, attr_name):
                        raise PlanningError(
                            f"attribute_map must not target relationship "
                            f"{attr_name!r}; RowGuard does not traverse relationships",
                            stage="adapter",
                            execution_id=execution_id,
                        )
                    if attr_name not in known_attrs:
                        raise PlanningError(
                            f"attribute_map target {attr_name!r} is not a mapped "
                            f"scalar attribute on {entity_cls.__name__}",
                            stage="adapter",
                            execution_id=execution_id,
                        )
                expected = tuple(attribute_map.keys())
                planned_attrs = dict(attribute_map)
            else:
                field_names = sorted(_model_field_names(request.model))
                for field_name in field_names:
                    if is_relationship_attr(entity_cls, field_name):
                        raise PlanningError(
                            f"Model field {field_name!r} matches ORM relationship "
                            f"on {entity_cls.__name__}; RowGuard does not traverse "
                            "relationships — remove the field or use a projection",
                            stage="adapter",
                            execution_id=execution_id,
                        )
                expected = tuple(field_names)
                planned_attrs = {name: name for name in expected}

            return AdapterPlan(
                adapter=ORMEntityAdapter(
                    attribute_keys=expected,
                    attribute_map=planned_attrs if attribute_map else None,
                    mapped_class=entity_cls,
                    unloaded_attributes=request.adapter.unloaded_attributes,
                    orm_validation=orm_validation,
                ),
                field_map=None,
                attribute_map=dict(attribute_map) if attribute_map else None,
                expected_keys=expected,
                result_shape="entity",
                orm_validation=orm_validation,
                unloaded_attributes=request.adapter.unloaded_attributes,
            )

        if orm_validation == "from_attributes":
            raise PlanningError(
                "orm_validation='from_attributes' requires a single-entity select; "
                "use select(MappedClass) or pass a projected statement with "
                "orm_validation='mapping'",
                stage="adapter",
                execution_id=execution_id,
            )
        if attribute_map:
            raise PlanningError(
                "attribute_map is only valid for single-entity ORM results; "
                "use field_map for projected column rows",
                stage="adapter",
                execution_id=execution_id,
            )

        expected = (
            tuple(field_map.keys())
            if field_map
            else tuple(sorted(_model_field_names(request.model)))
        )
        return AdapterPlan(
            adapter=SQLAlchemyRowAdapter(field_map=field_map),
            field_map=dict(field_map) if field_map else None,
            expected_keys=expected,
            result_shape="projection",
            orm_validation="mapping",
            unloaded_attributes=request.adapter.unloaded_attributes,
        )

    def _plan_validation(
        self,
        request: QueryRequest[T],
        *,
        adapter_plan: AdapterPlan,
    ) -> ValidationPlan[T]:
        # Single source of truth: AdapterConfig.orm_validation.
        from_attributes = (
            adapter_plan.result_shape == "entity"
            and adapter_plan.orm_validation == "from_attributes"
        )
        return ValidationPlan(
            validator=PydanticValidator(
                request.model,
                strict=request.validation.strict,
                from_attributes=from_attributes,
            ),
            model=request.model,
            strict=request.validation.strict,
            from_attributes=from_attributes,
        )

    def _plan_rejection(
        self,
        request: QueryRequest[T],
        *,
        execution_id: str,
    ) -> RejectionPlan:
        del execution_id
        import inspect

        cfg = request.rejection
        policy: RejectionPolicy
        if cfg.policy == "callback":
            callback = cfg.reject_callback
            assert callback is not None
            is_async = inspect.iscoroutinefunction(callback)
            if is_async and not cfg.async_execution:
                raise PlanningError(
                    "Async reject_callback requires aselect/aexecute/astream",
                    stage="rejection",
                )
            policy = CallbackPolicy(
                callback=callback,
                on_callback_error=cfg.on_callback_error,
                callback_values=cfg.callback_values,
                redact_fields=cfg.redact_fields,
                async_mode=is_async,
            )
        elif cfg.policy == "quarantine":
            provider = cfg.quarantine_provider
            assert provider is not None
            has_sync = callable(getattr(provider, "write", None))
            has_async = callable(getattr(provider, "awrite", None))
            if cfg.async_execution:
                if not has_async and not has_sync:
                    raise PlanningError(
                        "quarantine provider must implement write or awrite",
                        stage="rejection",
                    )
            elif not has_sync:
                raise PlanningError(
                    "Sync APIs require a quarantine provider with write()",
                    stage="rejection",
                )
            policy = QuarantinePolicy(
                provider=provider,
                on_quarantine_error=cfg.on_quarantine_error,
                quarantine_values=cfg.quarantine_values,
                quarantine_retention=cfg.quarantine_retention,
                redact_fields=cfg.redact_fields,
                async_mode=cfg.async_execution and has_async and not has_sync,
            )
        else:
            policy_cls = _SIMPLE_POLICIES[cfg.policy]
            policy = policy_cls()
        return RejectionPlan(
            policy=policy,
            policy_name=cfg.policy,
            max_rejections=cfg.max_rejections,
            max_rejection_rate=cfg.max_rejection_rate,
            quarantine_retention=cfg.quarantine_retention,
        )
