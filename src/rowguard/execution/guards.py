"""Shared execution-time guards."""

from __future__ import annotations

from typing import Any

from rowguard.errors import ConfigurationError
from rowguard.planning.execution_plan import ExecutionPlan


def require_session_for_entity_plan(
    plan: ExecutionPlan[Any],
    *,
    session: object | None,
) -> None:
    """Entity-shaped ORM selects require a Session; Connection returns Core rows."""
    if plan.adapter_plan.result_shape != "entity":
        return
    if session is not None:
        return
    raise ConfigurationError(
        "Entity-shaped ORM selects require a Session (or AsyncSession); "
        "a Connection returns Core column rows that cannot be adapted as "
        "entities. Pass session= or use an explicit column projection."
    )
