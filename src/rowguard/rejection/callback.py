from __future__ import annotations

from collections.abc import Set
from enum import Enum
from typing import Any, Protocol

from rowguard.errors import CallbackError
from rowguard.rejection.base import RejectionContext, RejectionDecision
from rowguard.rejection.redaction import prepare_rejected_for_handoff
from rowguard.results.rejected_row import RejectedRow


class CallbackDecision(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    RETAIN = "retain"
    DROP = "drop"


class RejectionCallback(Protocol):
    def __call__(
        self,
        rejected: RejectedRow,
        context: CallbackContext,
    ) -> CallbackDecision | None: ...


class AsyncRejectionCallback(Protocol):
    async def __call__(
        self,
        rejected: RejectedRow,
        context: CallbackContext,
    ) -> CallbackDecision | None: ...


# Public alias matching design docs.
CallbackContext = RejectionContext


def _map_decision(decision: CallbackDecision | None) -> RejectionDecision:
    if decision is None or decision is CallbackDecision.CONTINUE:
        return RejectionDecision(continue_processing=True, retain_rejection=False)
    if decision is CallbackDecision.STOP:
        return RejectionDecision(continue_processing=False, retain_rejection=False)
    if decision is CallbackDecision.RETAIN:
        return RejectionDecision(continue_processing=True, retain_rejection=True)
    if decision is CallbackDecision.DROP:
        return RejectionDecision(continue_processing=True, retain_rejection=False)
    raise CallbackError(
        f"Invalid callback decision: {decision!r}",
        rejected=None,
        callback=None,
        original_error=None,
    )


class CallbackPolicy:
    """Invoke a user callback for each rejected row."""

    def __init__(
        self,
        *,
        callback: Any,
        on_callback_error: str = "raise",
        callback_values: str = "full",
        redact_fields: Set[str] | None = None,
        async_mode: bool = False,
    ) -> None:
        self._callback = callback
        self._on_callback_error = on_callback_error
        self._callback_values = callback_values
        self._redact_fields = frozenset(redact_fields) if redact_fields else None
        self._async_mode = async_mode

    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        if self._async_mode:
            raise CallbackError(
                "Async callback cannot be used with sync RowGuard APIs",
                rejected=rejected,
                callback=self._callback,
                original_error=None,
            )
        return self._invoke_sync(rejected, context)

    async def ahandle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        if not self._async_mode:
            # Sync callback on async path is allowed (runs on the loop).
            return self._invoke_sync(rejected, context)
        return await self._invoke_async(rejected, context)

    def _payload(
        self,
        rejected: RejectedRow,
    ) -> RejectedRow:
        return prepare_rejected_for_handoff(
            rejected,
            values=self._callback_values,
            redact_fields=self._redact_fields,
        )

    def _invoke_sync(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        payload = self._payload(rejected)
        try:
            result = self._callback(payload, context)
        except Exception as error:
            return self._handle_error(rejected, error)
        if hasattr(result, "__await__"):
            return self._handle_error(
                rejected,
                TypeError("Async callback returned a coroutine on the sync path"),
            )
        try:
            return _map_decision(result)
        except CallbackError as error:
            error.rejected = rejected
            error.callback = self._callback
            raise

    async def _invoke_async(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        payload = self._payload(rejected)
        try:
            result = await self._callback(payload, context)
        except Exception as error:
            return self._handle_error(rejected, error)
        try:
            return _map_decision(result)
        except CallbackError as error:
            error.rejected = rejected
            error.callback = self._callback
            raise

    def _handle_error(
        self,
        rejected: RejectedRow,
        error: BaseException,
    ) -> RejectionDecision:
        wrapped = CallbackError(
            f"Rejection callback failed: {error}",
            rejected=rejected,
            callback=self._callback,
            original_error=error,
        )
        wrapped.__cause__ = error
        mode = self._on_callback_error
        if mode == "raise" or mode == "reject_handler":
            return RejectionDecision(
                continue_processing=False,
                retain_rejection=True,
                error=wrapped,
            )
        if mode == "log":
            import logging

            logging.getLogger("rowguard.rejection").exception(
                "Rejection callback failed for row %s",
                rejected.index,
            )
            return RejectionDecision(continue_processing=True, retain_rejection=True)
        if mode == "continue":
            return RejectionDecision(continue_processing=True, retain_rejection=True)
        return RejectionDecision(
            continue_processing=False,
            retain_rejection=True,
            error=wrapped,
        )
