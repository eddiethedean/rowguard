from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AdaptedRow:
    mapping: Mapping[str, object]
    raw_row: object | None = None
    source_identity: Mapping[str, object] | None = None
    attributes_subject: object | None = None


class RowAdapter(Protocol):
    def adapt(self, row: object) -> AdaptedRow: ...
