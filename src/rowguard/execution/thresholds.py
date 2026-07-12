from __future__ import annotations

from rowguard.errors import RejectionThresholdError
from rowguard.execution.state import MutableStatistics
from rowguard.planning.execution_plan import RejectionPlan
from rowguard.results.rejected_row import RejectedRow


def check_rejection_thresholds(
    *,
    statistics: MutableStatistics,
    rejection_plan: RejectionPlan,
    last_rejection: RejectedRow | None,
) -> None:
    """Raise RejectionThresholdError when configured limits are exceeded."""
    max_rejections = rejection_plan.max_rejections
    max_rate = rejection_plan.max_rejection_rate
    if max_rejections is None and max_rate is None:
        return

    rejected = statistics.rows_rejected
    read = statistics.rows_read
    if max_rejections is not None and rejected > max_rejections:
        raise RejectionThresholdError(
            f"Rejection threshold exceeded: {rejected} rejections "
            f"(max_rejections={max_rejections})",
            rows_read=read,
            rows_rejected=rejected,
            max_rejections=max_rejections,
            max_rejection_rate=max_rate,
            last_rejection=last_rejection,
        )
    if max_rate is not None and read > 0:
        rate = rejected / read
        if rate > max_rate:
            raise RejectionThresholdError(
                f"Rejection rate threshold exceeded: {rate:.4f} "
                f"(max_rejection_rate={max_rate})",
                rows_read=read,
                rows_rejected=rejected,
                max_rejections=max_rejections,
                max_rejection_rate=max_rate,
                last_rejection=last_rejection,
            )
