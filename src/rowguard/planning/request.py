from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class QueryRequest(Generic[T]):
    model: type[T]
    source: Any | None = None
    statement: Any | None = None
    session: Any | None = None
    connection: Any | None = None
    where: tuple[Any, ...] = ()
    parameters: Mapping[str, object] = field(default_factory=dict)
    field_map: Mapping[str, str] | None = None
    column_map: Mapping[str, Any] | None = None
    on_reject: str = "raise"
    use_sqlrules: bool = True
