from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class CompiledPushdown:
    expressions: tuple[Any, ...]
    diagnostics: tuple[Diagnostic, ...]


class SQLRulesBridge:
    """Thin adapter over SQLRules' public Compiler API."""

    def compile(
        self,
        *,
        model: type[BaseModel],
        source: Any,
        column_map: Mapping[str, Any] | None = None,
        execution_id: str = "",
    ) -> CompiledPushdown:
        try:
            import sqlrules
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise ConfigurationError("sqlrules is required when use_sqlrules=True") from exc

        try:
            compiler = sqlrules.Compiler(on_unsupported="ignore")
            rules = compiler.compile(model, source, column_map=column_map)
            expressions = tuple(sqlrules.where(rules))
        except Exception as exc:
            raise ConfigurationError(f"SQLRules compilation failed: {exc}") from exc

        diagnostics: list[Diagnostic] = [
            Diagnostic(
                code=item.code or "sqlrules.diagnostic",
                severity=item.severity,
                execution_id=execution_id,
                metadata={
                    "message": item.message,
                    "field": item.field,
                    "operator": item.operator,
                },
            )
            for item in compiler.diagnostics
        ]
        if expressions:
            diagnostics.append(
                Diagnostic(
                    code="sqlrules.pushdown_applied",
                    severity="info",
                    execution_id=execution_id,
                    metadata={"expression_count": len(expressions)},
                )
            )

        return CompiledPushdown(
            expressions=expressions,
            diagnostics=tuple(diagnostics),
        )
