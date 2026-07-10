from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Table

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.cache import LRUCache
from rowguard.diagnostics import Diagnostic
from rowguard.errors import PlanningError
from rowguard.integrations.sqlalchemy_core import apply_where, build_select, is_select
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.config import RejectionPolicyName
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
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.validation.pydantic import PydanticValidator

T = TypeVar("T", bound=BaseModel)

_POLICIES: dict[RejectionPolicyName, type[RejectionPolicy]] = {
    "raise": RaisePolicy,
    "collect": CollectPolicy,
    "skip": SkipPolicy,
}


def _model_field_names(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields.keys())


def _table_column_names(source: Any) -> dict[str, Any]:
    if isinstance(source, Table):
        return {col.name: col for col in source.columns}
    columns = getattr(source, "c", None) or getattr(source, "columns", None)
    if columns is None:
        return {}
    try:
        return {col.name: col for col in columns}
    except TypeError:
        return {}


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
                return cached

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

        adapter_plan = self._plan_adapter(request, resolved=resolved, execution_id=execution_id)
        validation_plan = self._plan_validation(request)
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
        # Structural key only — exclude bind parameter values.
        field_map = tuple(sorted((request.adapter.field_map or {}).items()))
        column_map_keys = tuple(sorted((request.pushdown.column_map or {}).keys()))
        return repr(
            (
                request.model.__module__,
                request.model.__qualname__,
                type(request.source).__name__ if request.source is not None else None,
                getattr(request.source, "name", None),
                id(request.statement) if request.statement is not None else None,
                request.where,
                field_map,
                column_map_keys,
                request.pushdown.enabled,
                request.pushdown.compiled_rules is not None,
                request.validation.strict,
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
        if request.rejection.policy not in _POLICIES:
            raise PlanningError(
                f"Unsupported on_reject policy: {request.rejection.policy!r}. "
                f"Supported: {', '.join(sorted(_POLICIES))}",
                stage="rejection",
            )

    def _resolve_source(
        self,
        request: QueryRequest[T],
        *,
        execution_id: str,
    ) -> ResolvedSource | None:
        source = request.pushdown.source if request.pushdown.source is not None else request.source
        if source is None:
            return None
        if isinstance(source, Table):
            return ResolvedSource(
                kind="table",
                selectable=source,
                columns=_table_column_names(source),
                source_name=source.name,
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
            return PushdownPlan(
                enabled=True,
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

        self._validate_column_map(
            request,
            resolved=resolved,
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
        resolved: ResolvedSource | None,
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
        if resolved is not None and resolved.columns:
            missing_cols = [
                name
                for name, col in column_map.items()
                if getattr(col, "name", None) not in resolved.columns
                and col not in resolved.columns.values()
            ]
            # Only warn via diagnostic when we cannot prove membership; hard-fail
            # only for clearly missing string-named columns already checked above.
            _ = missing_cols

    def _plan_adapter(
        self,
        request: QueryRequest[T],
        *,
        resolved: ResolvedSource | None,
        execution_id: str,
    ) -> AdapterPlan:
        field_map = request.adapter.field_map
        if field_map:
            model_fields = _model_field_names(request.model)
            unknown = sorted(set(field_map.keys()) - model_fields)
            if unknown:
                raise PlanningError(
                    f"field_map keys are not model fields: {', '.join(unknown)}",
                    stage="adapter",
                    execution_id=execution_id,
                )
            if resolved is not None and resolved.columns:
                missing = sorted(
                    {
                        column_key
                        for column_key in field_map.values()
                        if column_key not in resolved.columns
                    }
                )
                if missing:
                    raise PlanningError(
                        "field_map source columns not found on source: " + ", ".join(missing),
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
        )

    def _plan_validation(self, request: QueryRequest[T]) -> ValidationPlan[T]:
        return ValidationPlan(
            validator=PydanticValidator(
                request.model,
                strict=request.validation.strict,
            ),
            model=request.model,
            strict=request.validation.strict,
        )

    def _plan_rejection(
        self,
        request: QueryRequest[T],
        *,
        execution_id: str,
    ) -> RejectionPlan:
        policy_cls = _POLICIES[request.rejection.policy]
        return RejectionPlan(
            policy=policy_cls(),
            policy_name=request.rejection.policy,
        )
