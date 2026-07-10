from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AdaptedRow:
    mapping: Mapping[str, object]
    raw_row: object | None = None


class RowAdapter(Protocol):
    def adapt(self, row: object) -> AdaptedRow: ...
