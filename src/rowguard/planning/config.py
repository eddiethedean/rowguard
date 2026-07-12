from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

RejectionPolicyName = Literal["raise", "collect", "skip", "callback", "quarantine", "log"]
DiagnosticsLevel = Literal["off", "summary", "detailed"]
OrmValidationMode = Literal["mapping", "from_attributes"]
UnloadedAttributesPolicy = Literal["error"]
CallbackErrorMode = Literal["raise", "log", "continue", "reject_handler"]
CallbackValuesMode = Literal["full", "redacted", "metadata_only"]
QuarantineErrorMode = Literal["raise", "collect", "log"]
QuarantineValuesMode = Literal["full", "redacted", "metadata_only"]
QuarantineRetentionMode = Literal["receipt", "rejection", "both", "none"]
QuarantineTransactionMode = Literal["separate", "same", "external"]


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
    from_attributes: bool = False


@dataclass(frozen=True, slots=True)
class RejectionConfig:
    policy: RejectionPolicyName = "raise"
    reject_callback: Any | None = None
    quarantine_provider: Any | None = None
    on_callback_error: CallbackErrorMode = "raise"
    callback_values: CallbackValuesMode = "full"
    on_quarantine_error: QuarantineErrorMode = "raise"
    quarantine_values: QuarantineValuesMode = "full"
    quarantine_retention: QuarantineRetentionMode = "receipt"
    quarantine_transaction: QuarantineTransactionMode = "separate"
    redact_fields: frozenset[str] | None = None
    max_rejections: int | None = None
    max_rejection_rate: float | None = None
    async_execution: bool = False


@dataclass(frozen=True, slots=True)
class DiagnosticsConfig:
    enabled: bool = True
    level: DiagnosticsLevel = "summary"


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    field_map: Mapping[str, str] | None = None
    attribute_map: Mapping[str, str] | None = None
    orm_validation: OrmValidationMode = "mapping"
    unloaded_attributes: UnloadedAttributesPolicy = "error"


@dataclass(frozen=True, slots=True)
class StreamingConfig:
    """Execution-time streaming options (not part of buffered ExecutionPlan)."""

    stream_results: bool = True
    yield_per: int | None = None

    def __post_init__(self) -> None:
        if self.yield_per is not None and self.yield_per <= 0:
            from rowguard.errors import ConfigurationError

            raise ConfigurationError("yield_per must be a positive integer")
