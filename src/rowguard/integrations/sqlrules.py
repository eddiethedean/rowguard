from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from rowguard.diagnostics import Diagnostic
from rowguard.errors import PlanningError


@dataclass(frozen=True, slots=True)
class CompiledPushdown:
    expressions: tuple[Any, ...]
    diagnostics: tuple[Diagnostic, ...]
    compiled_rules: Mapping[str, Any] | None = None
    precompiled: bool = False


class SQLRulesBridge:
    """Thin adapter over SQLRules' public Compiler API."""

    def compile(
        self,
        *,
        model: type[BaseModel],
        source: Any,
        column_map: Mapping[str, Any] | None = None,
        compiled_rules: Mapping[str, Any] | None = None,
        execution_id: str = "",
    ) -> CompiledPushdown:
        try:
            import sqlrules
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise PlanningError(
                "sqlrules is required when pushdown is enabled",
                stage="pushdown",
                execution_id=execution_id,
            ) from exc

        try:
            if compiled_rules is not None:
                rules = dict(compiled_rules)
                expressions = tuple(sqlrules.where(rules))
                diagnostics: list[Diagnostic] = [
                    Diagnostic(
                        code="planning.precompiled_rules",
                        severity="info",
                        execution_id=execution_id,
                        metadata={"expression_count": len(expressions)},
                    )
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
                    compiled_rules=rules,
                    precompiled=True,
                )

            compiler = sqlrules.Compiler(on_unsupported="ignore")
            rules = compiler.compile(model, source, column_map=column_map)
            expressions = tuple(sqlrules.where(rules))
        except PlanningError:
            raise
        except Exception as exc:
            raise PlanningError(
                f"SQLRules compilation failed: {exc}",
                stage="pushdown",
                execution_id=execution_id,
            ) from exc

        diagnostics = [
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
            compiled_rules=dict(rules),
            precompiled=False,
        )
