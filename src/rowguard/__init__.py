"""RowGuard: validation-first SQLAlchemy queries with Pydantic row validation."""

from rowguard.api import (
    aexecute,
    aselect,
    astream,
    compile_plan,
    execute,
    select,
    stream,
    validate_rows,
)
from rowguard.errors import (
    CallbackError,
    ConfigurationError,
    PlanningError,
    QuarantineError,
    QueryExecutionError,
    RejectHandlerError,
    RejectionThresholdError,
    ResultAssemblyError,
    RowAdaptationError,
    RowGuardError,
    RowValidationError,
)
from rowguard.execution.observer import BaseStreamObserver, StreamObserver
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.rejection.callback import CallbackContext, CallbackDecision
from rowguard.rejection.quarantine import (
    InMemoryQuarantineProvider,
    JSONLQuarantineProvider,
    QuarantineProvider,
)
from rowguard.results.async_stream_result import AsyncStreamResult
from rowguard.results.quarantine import QuarantineReceipt, QuarantineRecord
from rowguard.results.query_result import QueryResult
from rowguard.results.rejected_row import RejectedRow
from rowguard.results.stream_result import StreamResult
from rowguard.statistics import QueryStatistics

__version__ = "0.6.0"

__all__ = [
    "AsyncStreamResult",
    "BaseStreamObserver",
    "CallbackContext",
    "CallbackDecision",
    "CallbackError",
    "ConfigurationError",
    "ExecutionPlan",
    "InMemoryQuarantineProvider",
    "JSONLQuarantineProvider",
    "PlanningError",
    "QuarantineError",
    "QuarantineProvider",
    "QuarantineReceipt",
    "QuarantineRecord",
    "QueryExecutionError",
    "QueryResult",
    "QueryStatistics",
    "RejectHandlerError",
    "RejectedRow",
    "RejectionThresholdError",
    "ResultAssemblyError",
    "RowAdaptationError",
    "RowGuardError",
    "RowValidationError",
    "StreamObserver",
    "StreamResult",
    "__version__",
    "aexecute",
    "aselect",
    "astream",
    "compile_plan",
    "execute",
    "select",
    "stream",
    "validate_rows",
]
