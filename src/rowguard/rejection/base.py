from dataclasses import dataclass
from typing import Protocol

from rowguard.results.rejected_row import RejectedRow


@dataclass(frozen=True, slots=True)
class RejectionDecision:
    continue_processing: bool
    retain_rejection: bool
    error: BaseException | None = None


class RejectionPolicy(Protocol):
    def handle(self, rejected: RejectedRow) -> RejectionDecision: ...
