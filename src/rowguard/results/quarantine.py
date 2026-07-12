from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    schema_version: str
    execution_id: str
    row_index: int
    model_name: str
    source_identity: Mapping[str, object] | None
    rejection_type: str
    mapping: Mapping[str, object] | None
    errors: tuple[Mapping[str, object], ...]
    metadata: Mapping[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class QuarantineReceipt:
    provider: str
    record_id: str
    location: str | None
    written_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)
