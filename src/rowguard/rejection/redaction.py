from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any

from rowguard.results.rejected_row import RejectedRow

REDACTED = "***REDACTED***"


def redact_mapping(
    mapping: Mapping[str, object] | None,
    *,
    redact_fields: Set[str] | None,
    mode: str,
) -> Mapping[str, object] | None:
    if mapping is None:
        return None
    if mode == "metadata_only":
        return {}
    fields = set(redact_fields or ())
    if mode == "full":
        if not fields:
            return dict(mapping)
        return {key: (REDACTED if key in fields else value) for key, value in mapping.items()}
    # redacted: redact listed fields, or all values when no field list is given
    if not fields:
        return {key: REDACTED for key in mapping}
    return {key: (REDACTED if key in fields else value) for key, value in mapping.items()}


def prepare_rejected_for_handoff(
    rejected: RejectedRow,
    *,
    values: str,
    redact_fields: Set[str] | None,
) -> RejectedRow:
    """Return a RejectedRow safe for callback/quarantine handoff."""
    if values == "full" and not redact_fields:
        return rejected
    mapping = redact_mapping(
        rejected.mapping,
        redact_fields=redact_fields,
        mode=values,
    )
    raw_row: object | None = (
        None
        if values in {"metadata_only", "redacted"} or redact_fields
        else rejected.raw_row
    )
    return RejectedRow(
        index=rejected.index,
        model=rejected.model,
        mapping=mapping,
        validation_error=rejected.validation_error,
        adaptation_error=rejected.adaptation_error,
        raw_row=raw_row,
        source_identity=rejected.source_identity,
    )


def json_safe(value: Any) -> Any:
    """Convert common Python values to JSON-serializable forms."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)
