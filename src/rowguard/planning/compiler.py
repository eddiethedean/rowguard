from __future__ import annotations

from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.diagnostics import Diagnostic
from rowguard.errors import ConfigurationError
from rowguard.integrations.sqlalchemy_core import apply_where, build_select, is_select
from rowguard.integrations.sqlrules import SQLRulesBridge
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.planning.request import QueryRequest
from rowguard.rejection.base import RejectionPolicy
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.validation.pydantic import PydanticValidator

T = TypeVar("T", bound=BaseModel)

_POLICIES: dict[str, type[RejectionPolicy]] = {
    "raise": RaisePolicy,
    "collect": CollectPolicy,
    "skip": SkipPolicy,
}


class QueryPlanner(Generic[T]):
    def __init__(self, *, rules_bridge: SQLRulesBridge | None = None) -> None:
        self._rules_bridge = rules_bridge or SQLRulesBridge()

    def compile(self, request: QueryRequest[T]) -> ExecutionPlan[T]:
        self._validate_request(request)
        execution_id = uuid4().hex

        if request.statement is not None:
            if not is_select(request.statement):
                raise ConfigurationError(
                    f"statement must be a SQLAlchemy Select, got {type(request.statement).__name__}"
                )
            statement = request.statement
        else:
            assert request.source is not None
            statement = build_select(request.source)

        diagnostics: list[Diagnostic] = []
        pushdown_exprs: tuple[object, ...] = ()
        pushdown_source = request.source

        if request.use_sqlrules and pushdown_source is not None:
            if request.statement is not None:
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
                column_map=request.column_map,
                execution_id=execution_id,
            )
            pushdown_exprs = compiled.expressions
            diagnostics.extend(compiled.diagnostics)
        elif request.use_sqlrules and pushdown_source is None:
            diagnostics.append(
                Diagnostic(
                    code="sqlrules.pushdown_skipped",
                    severity="info",
                    execution_id=execution_id,
                    metadata={"reason": "no pushdown source available for statement-only execute"},
                )
            )

        statement = apply_where(statement, (*pushdown_exprs, *request.where))

        policy_cls = _POLICIES.get(request.on_reject)
        if policy_cls is None:
            raise ConfigurationError(
                f"Unsupported on_reject policy: {request.on_reject!r}. "
                f"Supported: {', '.join(sorted(_POLICIES))}"
            )

        return ExecutionPlan(
            statement=statement,
            model=request.model,
            adapter=SQLAlchemyRowAdapter(field_map=request.field_map),
            validator=PydanticValidator(request.model),
            rejection_policy=policy_cls(),
            use_sqlrules=request.use_sqlrules,
            parameters=dict(request.parameters),
            diagnostics=tuple(diagnostics),
            execution_id=execution_id,
            session=request.session,
            connection=request.connection,
        )

    def _validate_request(self, request: QueryRequest[T]) -> None:
        if not issubclass(request.model, BaseModel):
            raise ConfigurationError("model must be a Pydantic BaseModel subclass")

        if request.source is None and request.statement is None:
            raise ConfigurationError("Either source (table) or statement is required")

        has_session = request.session is not None
        has_connection = request.connection is not None
        if has_session == has_connection:
            raise ConfigurationError("Provide exactly one of session or connection")
