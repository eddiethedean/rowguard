from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from rowguard.errors import QuarantineError
from rowguard.rejection.base import RejectionContext, RejectionDecision
from rowguard.rejection.redaction import json_safe, prepare_rejected_for_handoff, redact_mapping
from rowguard.results.quarantine import QuarantineReceipt, QuarantineRecord
from rowguard.results.rejected_row import RejectedRow


@dataclass(frozen=True, slots=True)
class QuarantineContext:
    execution_id: str
    source_name: str | None
    model_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class QuarantineProvider(Protocol):
    def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt: ...


class AsyncQuarantineProvider(Protocol):
    async def awrite(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt: ...


def _rejection_type(rejected: RejectedRow) -> str:
    if rejected.validation_error is not None:
        return "validation_error"
    if rejected.adaptation_error is not None:
        return "adaptation_error"
    return "unknown"


def _serialize_errors(rejected: RejectedRow) -> tuple[Mapping[str, object], ...]:
    if rejected.validation_error is not None:
        errors: list[Mapping[str, object]] = []
        for item in rejected.validation_error.errors():
            safe: dict[str, object] = {
                "type": str(item.get("type", "")),
                "loc": list(item.get("loc", ())),
                "msg": str(item.get("msg", "")),
            }
            if "ctx" in item and item["ctx"] is not None:
                safe["ctx"] = json_safe(item["ctx"])
            errors.append(safe)
        return tuple(errors)
    if rejected.adaptation_error is not None:
        return ({"type": "adaptation_error", "msg": str(rejected.adaptation_error)},)
    return ()


def build_quarantine_record(
    rejected: RejectedRow,
    *,
    context: RejectionContext,
    values: str,
    redact_fields: Set[str] | None,
) -> QuarantineRecord:
    prepared = prepare_rejected_for_handoff(
        rejected,
        values=values,
        redact_fields=redact_fields,
    )
    mapping = redact_mapping(
        prepared.mapping,
        redact_fields=redact_fields,
        mode=values,
    )
    return QuarantineRecord(
        schema_version="1",
        execution_id=context.execution_id,
        row_index=rejected.index,
        model_name=rejected.model.__name__,
        source_identity=(
            dict(rejected.source_identity) if rejected.source_identity is not None else None
        ),
        rejection_type=_rejection_type(rejected),
        mapping=dict(mapping) if mapping is not None else None,
        errors=_serialize_errors(prepared),
        metadata=dict(context.metadata),
        created_at=datetime.now(tz=timezone.utc),
    )


def _retention_flags(retention: str) -> tuple[bool, bool]:
    """Return (retain_rejection, keep_receipt)."""
    if retention == "receipt":
        return False, True
    if retention == "rejection":
        return True, False
    if retention == "both":
        return True, True
    if retention == "none":
        return False, False
    return False, True


class QuarantinePolicy:
    def __init__(
        self,
        *,
        provider: Any,
        on_quarantine_error: str = "raise",
        quarantine_values: str = "full",
        quarantine_retention: str = "receipt",
        redact_fields: Set[str] | None = None,
        async_mode: bool = False,
    ) -> None:
        self._provider = provider
        self._on_quarantine_error = on_quarantine_error
        self._quarantine_values = quarantine_values
        self._quarantine_retention = quarantine_retention
        self._redact_fields = frozenset(redact_fields) if redact_fields else None
        self._async_mode = async_mode

    def handle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        if self._async_mode and not hasattr(self._provider, "write"):
            raise QuarantineError(
                "Async quarantine provider cannot be used with sync RowGuard APIs",
                rejected=rejected,
                provider=self._provider,
                original_error=None,
            )
        record = build_quarantine_record(
            rejected,
            context=context,
            values=self._quarantine_values,
            redact_fields=self._redact_fields,
        )
        qctx = QuarantineContext(
            execution_id=context.execution_id,
            source_name=context.source_name,
            model_name=rejected.model.__name__,
            metadata=dict(context.metadata),
        )
        try:
            receipt = self._provider.write(record, qctx)
        except Exception as error:
            return self._handle_error(rejected, error)
        return self._success(rejected, receipt)

    async def ahandle(
        self,
        rejected: RejectedRow,
        context: RejectionContext,
    ) -> RejectionDecision:
        record = build_quarantine_record(
            rejected,
            context=context,
            values=self._quarantine_values,
            redact_fields=self._redact_fields,
        )
        qctx = QuarantineContext(
            execution_id=context.execution_id,
            source_name=context.source_name,
            model_name=rejected.model.__name__,
            metadata=dict(context.metadata),
        )
        try:
            if hasattr(self._provider, "awrite"):
                receipt = await self._provider.awrite(record, qctx)
            else:
                receipt = self._provider.write(record, qctx)
        except Exception as error:
            return self._handle_error(rejected, error)
        return self._success(rejected, receipt)

    def _success(
        self,
        rejected: RejectedRow,
        receipt: QuarantineReceipt,
    ) -> RejectionDecision:
        del rejected
        retain, keep_receipt = _retention_flags(self._quarantine_retention)
        return RejectionDecision(
            continue_processing=True,
            retain_rejection=retain,
            quarantine_receipt=receipt if keep_receipt else None,
        )

    def _handle_error(
        self,
        rejected: RejectedRow,
        error: BaseException,
    ) -> RejectionDecision:
        wrapped = QuarantineError(
            f"Quarantine provider failed: {error}",
            rejected=rejected,
            provider=self._provider,
            original_error=error,
        )
        wrapped.__cause__ = error
        mode = self._on_quarantine_error
        if mode == "raise":
            return RejectionDecision(
                continue_processing=False,
                retain_rejection=True,
                error=wrapped,
            )
        if mode == "log":
            import logging

            logging.getLogger("rowguard.rejection").exception(
                "Quarantine provider failed for row %s",
                rejected.index,
            )
            return RejectionDecision(continue_processing=True, retain_rejection=True)
        if mode == "collect":
            return RejectionDecision(continue_processing=True, retain_rejection=True)
        return RejectionDecision(
            continue_processing=False,
            retain_rejection=True,
            error=wrapped,
        )

    def close(self) -> None:
        close = getattr(self._provider, "close", None)
        if callable(close):
            close()

    async def aclose(self) -> None:
        close = getattr(self._provider, "aclose", None)
        if callable(close):
            await close()
            return
        sync_close = getattr(self._provider, "close", None)
        if callable(sync_close):
            sync_close()


class InMemoryQuarantineProvider:
    """Reference provider that stores records in process memory."""

    def __init__(self) -> None:
        self.records: list[QuarantineRecord] = []
        self.receipts: list[QuarantineReceipt] = []
        self._closed = False

    def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        del context
        if self._closed:
            raise RuntimeError("InMemoryQuarantineProvider is closed")
        record_id = str(uuid4())
        self.records.append(record)
        receipt = QuarantineReceipt(
            provider="memory",
            record_id=record_id,
            location=f"memory:{record_id}",
            written_at=datetime.now(tz=timezone.utc),
        )
        self.receipts.append(receipt)
        return receipt

    async def awrite(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        return self.write(record, context)

    def close(self) -> None:
        self._closed = True

    async def aclose(self) -> None:
        self.close()


class JSONLQuarantineProvider:
    """Append one JSON object per quarantine record to a file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("a", encoding="utf-8")
        self._closed = False

    def write(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        del context
        if self._closed:
            raise RuntimeError("JSONLQuarantineProvider is closed")
        import json

        record_id = str(uuid4())
        payload = {
            "schema_version": record.schema_version,
            "execution_id": record.execution_id,
            "row_index": record.row_index,
            "model_name": record.model_name,
            "source_identity": json_safe(record.source_identity),
            "rejection_type": record.rejection_type,
            "mapping": json_safe(record.mapping),
            "errors": json_safe(list(record.errors)),
            "metadata": json_safe(dict(record.metadata)),
            "created_at": record.created_at.isoformat(),
            "record_id": record_id,
        }
        self._file.write(json.dumps(payload, sort_keys=True, default=str))
        self._file.write("\n")
        self._file.flush()
        return QuarantineReceipt(
            provider="jsonl",
            record_id=record_id,
            location=str(self._path),
            written_at=datetime.now(tz=timezone.utc),
        )

    async def awrite(
        self,
        record: QuarantineRecord,
        context: QuarantineContext,
    ) -> QuarantineReceipt:
        return self.write(record, context)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._file.close()

    async def aclose(self) -> None:
        self.close()
