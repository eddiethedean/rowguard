"""Rejection policy protocols and built-in policies."""

from rowguard.rejection.base import (
    AsyncRejectionPolicy,
    RejectionContext,
    RejectionDecision,
    RejectionPolicy,
)
from rowguard.rejection.callback import (
    AsyncRejectionCallback,
    CallbackContext,
    CallbackDecision,
    CallbackPolicy,
    RejectionCallback,
)
from rowguard.rejection.log import LogPolicy
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.rejection.quarantine import (
    AsyncQuarantineProvider,
    InMemoryQuarantineProvider,
    JSONLQuarantineProvider,
    QuarantineContext,
    QuarantinePolicy,
    QuarantineProvider,
)
from rowguard.results.quarantine import QuarantineReceipt, QuarantineRecord

__all__ = [
    "AsyncQuarantineProvider",
    "AsyncRejectionCallback",
    "AsyncRejectionPolicy",
    "CallbackContext",
    "CallbackDecision",
    "CallbackPolicy",
    "CollectPolicy",
    "InMemoryQuarantineProvider",
    "JSONLQuarantineProvider",
    "LogPolicy",
    "QuarantineContext",
    "QuarantinePolicy",
    "QuarantineProvider",
    "QuarantineReceipt",
    "QuarantineRecord",
    "RaisePolicy",
    "RejectionCallback",
    "RejectionContext",
    "RejectionDecision",
    "RejectionPolicy",
    "SkipPolicy",
]
