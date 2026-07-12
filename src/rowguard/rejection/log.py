from __future__ import annotations

import logging

from rowguard.rejection.base import RejectionContext, RejectionDecision
from rowguard.results.rejected_row import RejectedRow

_LOG = logging.getLogger("rowguard.rejection")


class LogPolicy:
    """Log each rejection at WARNING and continue without retaining."""

    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        del context
        reason = "validation"
        if rejected.adaptation_error is not None:
            reason = "adaptation"
        _LOG.warning(
            "RowGuard rejected row %s for %s (%s)",
            rejected.index,
            rejected.model.__name__,
            reason,
        )
        return RejectionDecision(
            continue_processing=True,
            retain_rejection=False,
        )
