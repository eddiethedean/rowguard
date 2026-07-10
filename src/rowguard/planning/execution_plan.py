from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from rowguard.adapters.base import RowAdapter
from rowguard.diagnostics import Diagnostic
from rowguard.rejection.base import RejectionPolicy
from rowguard.validation.base import Validator

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ExecutionPlan(Generic[T]):
    statement: Any
    model: type[T]
    adapter: RowAdapter
    validator: Validator[T]
    rejection_policy: RejectionPolicy
    use_sqlrules: bool
    parameters: Mapping[str, object] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    execution_id: str = field(default_factory=lambda: uuid4().hex)
    session: Any | None = None
    connection: Any | None = None
