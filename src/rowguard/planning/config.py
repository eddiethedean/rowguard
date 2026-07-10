from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

RejectionPolicyName = Literal["raise", "collect", "skip"]
DiagnosticsLevel = Literal["off", "summary", "detailed"]


@dataclass(frozen=True, slots=True)
class PushdownConfig:
    enabled: bool = True
    source: Any | None = None
    column_map: Mapping[str, Any] | None = None
    compiled_rules: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    strict: bool | None = None
    context: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RejectionConfig:
    policy: RejectionPolicyName = "raise"


@dataclass(frozen=True, slots=True)
class DiagnosticsConfig:
    enabled: bool = True
    level: DiagnosticsLevel = "summary"


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    field_map: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class StreamingConfig:
    """Execution-time streaming options (not part of buffered ExecutionPlan)."""

    stream_results: bool = True
    yield_per: int | None = None

    def __post_init__(self) -> None:
        if self.yield_per is not None and self.yield_per <= 0:
            from rowguard.errors import ConfigurationError

            raise ConfigurationError("yield_per must be a positive integer")
