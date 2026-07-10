from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

P = TypeVar("P")


@dataclass(frozen=True)
class PluginRegistry(Generic[P]):
    entries: Mapping[str, P]

    def get(self, name: str) -> P:
        return self.entries[name]
