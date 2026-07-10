from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SyncExecutionContext:
    """Runtime DB handles for a single execution. Not part of ExecutionPlan."""

    session: Any | None = None
    connection: Any | None = None

    def __post_init__(self) -> None:
        has_session = self.session is not None
        has_connection = self.connection is not None
        if has_session == has_connection:
            from rowguard.errors import ConfigurationError

            raise ConfigurationError("Provide exactly one of session or connection")
