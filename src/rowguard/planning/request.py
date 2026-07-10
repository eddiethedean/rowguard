from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from rowguard.planning.config import (
    AdapterConfig,
    DiagnosticsConfig,
    PushdownConfig,
    RejectionConfig,
    ValidationConfig,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class QueryRequest(Generic[T]):
    """Normalized request before planning. Contains no live DB handles."""

    model: type[T]
    source: Any | None = None
    statement: Any | None = None
    where: tuple[Any, ...] = ()
    parameters: Mapping[str, object] = field(default_factory=dict)
    pushdown: PushdownConfig = field(default_factory=PushdownConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    rejection: RejectionConfig = field(default_factory=RejectionConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)
    adapter: AdapterConfig = field(default_factory=AdapterConfig)
