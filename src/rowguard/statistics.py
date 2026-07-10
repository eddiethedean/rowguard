from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryStatistics:
    rows_read: int
    rows_validated: int
    rows_accepted: int
    rows_rejected: int
    execution_time_ns: int = 0
    adaptation_time_ns: int = 0
    validation_time_ns: int = 0
    rejection_time_ns: int = 0

    @property
    def rejection_rate(self) -> float:
        if self.rows_read == 0:
            return 0.0
        return self.rows_rejected / self.rows_read
