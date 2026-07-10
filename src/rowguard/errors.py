from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class RowGuardError(Exception):
    """Base exception for all RowGuard errors."""


class ConfigurationError(RowGuardError):
    """Invalid or incompatible RowGuard configuration."""


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


class ResultAssemblyError(RowGuardError):
    """An inconsistent public result was about to be created."""
