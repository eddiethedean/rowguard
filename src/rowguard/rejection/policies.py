from __future__ import annotations

from rowguard.errors import RowAdaptationError, RowValidationError
from rowguard.rejection.base import RejectionDecision
from rowguard.results.rejected_row import RejectedRow


class RaisePolicy:
    def handle(self, rejected: RejectedRow) -> RejectionDecision:
        if rejected.validation_error is not None:
            raise RowValidationError(
                model=rejected.model,
                validation_error=rejected.validation_error,
                row_index=rejected.index,
            )
        if rejected.adaptation_error is not None:
            message = str(rejected.adaptation_error)
            cause = rejected.adaptation_error
            raise RowAdaptationError(
                message,
                model=rejected.model,
                row_index=rejected.index,
            ) from cause
        raise RuntimeError("RaisePolicy requires a validation or adaptation error")


class CollectPolicy:
    def handle(self, rejected: RejectedRow) -> RejectionDecision:
        return RejectionDecision(
            continue_processing=True,
            retain_rejection=True,
        )


class SkipPolicy:
    def handle(self, rejected: RejectedRow) -> RejectionDecision:
        return RejectionDecision(
            continue_processing=True,
            retain_rejection=False,
        )
