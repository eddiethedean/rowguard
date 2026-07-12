from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from rowguard.results.rejected_row import RejectedRow


@dataclass(frozen=True, slots=True)
class RejectionContext:
    """Execution snapshot passed to rejection policies (no live session)."""

    execution_id: str
    model: type[BaseModel]
    statement: object | None = None
    source_name: str | None = None
    rejection_count: int = 0
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RejectionDecision:
    continue_processing: bool
    retain_rejection: bool
    error: BaseException | None = None
    quarantine_receipt: Any | None = None


class RejectionPolicy(Protocol):
    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision: ...


class AsyncRejectionPolicy(Protocol):
    async def ahandle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision: ...


def empty_rejection_context(
    *,
    model: type[BaseModel],
    execution_id: str = "",
    statement: object | None = None,
    source_name: str | None = None,
) -> RejectionContext:
    return RejectionContext(
        execution_id=execution_id,
        model=model,
        statement=statement,
        source_name=source_name,
    )
