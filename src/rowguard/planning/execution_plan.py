from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.adapters.base import RowAdapter
from rowguard.diagnostics import Diagnostic
from rowguard.rejection.base import RejectionPolicy
from rowguard.validation.base import Validator

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    kind: str
    selectable: Any | None
    columns: Mapping[str, Any] = field(default_factory=dict)
    source_name: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PushdownPlan:
    enabled: bool
    expressions: tuple[Any, ...] = ()
    compiled_rules: Mapping[str, Any] | None = None
    precompiled: bool = False
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class AdapterPlan:
    adapter: RowAdapter
    field_map: Mapping[str, str] | None = None
    expected_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationPlan(Generic[T]):
    validator: Validator[T]
    model: type[T]
    strict: bool | None = None


@dataclass(frozen=True, slots=True)
class RejectionPlan:
    policy: RejectionPolicy
    policy_name: str


@dataclass(frozen=True, slots=True)
class ExecutionPlan(Generic[T]):
    """Immutable planning output. Contains no session/connection handles."""

    statement: Any
    model: type[T]
    pushdown_plan: PushdownPlan
    adapter_plan: AdapterPlan
    validation_plan: ValidationPlan[T]
    rejection_plan: RejectionPlan
    parameters: Mapping[str, object] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    execution_id: str = ""
    resolved_source: ResolvedSource | None = None
    use_sqlrules: bool = False

    @property
    def adapter(self) -> RowAdapter:
        return self.adapter_plan.adapter

    @property
    def validator(self) -> Validator[T]:
        return self.validation_plan.validator

    @property
    def rejection_policy(self) -> RejectionPolicy:
        return self.rejection_plan.policy
