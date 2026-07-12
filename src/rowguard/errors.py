from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class RowGuardError(Exception):
    """Base exception for all RowGuard errors."""


class ConfigurationError(RowGuardError):
    """Invalid or incompatible RowGuard configuration."""


class PlanningError(ConfigurationError):
    """Planning-stage failure with optional stage context."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        execution_id: str | None = None,
    ) -> None:
        self.stage = stage
        self.execution_id = execution_id
        prefix = f"[{stage}] " if stage else ""
        super().__init__(f"{prefix}{message}")


class QueryExecutionError(RowGuardError):
    """SQLAlchemy query execution failed."""


class RowAdaptationError(RowGuardError):
    """A database row could not be adapted safely."""

    def __init__(
        self,
        message: str,
        *,
        model: type[Any] | None = None,
        row_index: int | None = None,
    ) -> None:
        self.model = model
        self.row_index = row_index
        super().__init__(message)


class RowValidationError(RowGuardError):
    """A row failed Pydantic validation under the raise policy."""

    def __init__(
        self,
        *,
        model: type[Any],
        validation_error: ValidationError,
        row_index: int | None = None,
    ) -> None:
        self.model = model
        self.validation_error = validation_error
        self.row_index = row_index
        super().__init__(
            f"Row {row_index!r} failed validation for {model.__name__} "
            f"with {validation_error.error_count()} error(s)."
        )


class RejectHandlerError(RowGuardError):
    """A rejection callback or quarantine provider failed."""


class CallbackError(RejectHandlerError):
    """A rejection callback failed or returned an invalid decision."""

    def __init__(
        self,
        message: str,
        *,
        rejected: Any | None = None,
        callback: Any | None = None,
        original_error: BaseException | None = None,
        callback_index: int | None = None,
    ) -> None:
        self.rejected = rejected
        self.callback = callback
        self.original_error = original_error
        self.callback_index = callback_index
        super().__init__(message)


class QuarantineError(RejectHandlerError):
    """A quarantine provider failed while writing a rejection."""

    def __init__(
        self,
        message: str,
        *,
        rejected: Any | None = None,
        provider: Any | None = None,
        original_error: BaseException | None = None,
    ) -> None:
        self.rejected = rejected
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class RejectionThresholdError(RowGuardError):
    """Execution stopped because a rejection threshold was exceeded."""

    def __init__(
        self,
        message: str,
        *,
        rows_read: int,
        rows_rejected: int,
        max_rejections: int | None = None,
        max_rejection_rate: float | None = None,
        last_rejection: Any | None = None,
    ) -> None:
        self.rows_read = rows_read
        self.rows_rejected = rows_rejected
        self.max_rejections = max_rejections
        self.max_rejection_rate = max_rejection_rate
        self.last_rejection = last_rejection
        super().__init__(message)


class ResultAssemblyError(RowGuardError):
    """An inconsistent public result was about to be created."""
