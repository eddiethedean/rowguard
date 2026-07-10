from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True, slots=True)
class RejectedRow:
    index: int
    model: type[BaseModel]
    mapping: Mapping[str, object] | None
    validation_error: ValidationError | None
    adaptation_error: Exception | None = None
    raw_row: object | None = None
    source_identity: Mapping[str, object] | None = None
