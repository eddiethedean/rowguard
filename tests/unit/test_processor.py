from __future__ import annotations

from pydantic import BaseModel

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.execution.processor import process_row
from rowguard.planning.execution_plan import (
    AdapterPlan,
    ExecutionPlan,
    PushdownPlan,
    RejectionPlan,
    ValidationPlan,
)
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str


def _plan(*, on_reject: str = "collect") -> ExecutionPlan[UserRead]:
    if on_reject == "collect":
        policy: CollectPolicy | SkipPolicy | RaisePolicy = CollectPolicy()
    elif on_reject == "skip":
        policy = SkipPolicy()
    else:
        policy = RaisePolicy()
    return ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=policy, policy_name=on_reject),
        use_sqlrules=False,
    )


def test_process_row_accepts_valid_mapping() -> None:
    processed = process_row(
        row={"id": 1, "name": "Ada"},
        index=0,
        plan=_plan(),
    )
    assert processed.model == UserRead(id=1, name="Ada")
    assert processed.rejected is None


def test_process_row_collects_invalid_mapping() -> None:
    processed = process_row(
        row={"id": "bad", "name": "Ada"},
        index=2,
        plan=_plan(on_reject="collect"),
    )
    assert processed.model is None
    assert processed.rejected is not None
    assert processed.rejected.index == 2
    assert processed.retain_rejection
    assert processed.continue_processing


def test_process_row_skip_does_not_retain() -> None:
    processed = process_row(
        row={"id": "bad", "name": "Ada"},
        index=1,
        plan=_plan(on_reject="skip"),
    )
    assert processed.model is None
    assert processed.retain_rejection is False


def test_process_row_raise_on_validation_failure() -> None:
    from rowguard.errors import RowValidationError

    processed = process_row(
        row={"id": "bad", "name": "Ada"},
        index=4,
        plan=_plan(on_reject="raise"),
    )
    assert processed.model is None
    assert processed.retain_rejection is False
    assert processed.continue_processing is False
    assert isinstance(processed.raise_error, RowValidationError)
    assert processed.raise_error.row_index == 4
    assert processed.raise_error.model is UserRead


def test_process_row_custom_stop_without_error() -> None:
    from rowguard.rejection.base import RejectionDecision

    class StopQuietly:
        def handle(self, rejected: object) -> RejectionDecision:
            return RejectionDecision(
                continue_processing=False,
                retain_rejection=False,
                error=None,
            )

    plan = ExecutionPlan(
        statement=None,
        model=UserRead,
        pushdown_plan=PushdownPlan(enabled=False),
        adapter_plan=AdapterPlan(adapter=SQLAlchemyRowAdapter()),
        validation_plan=ValidationPlan(
            validator=PydanticValidator(UserRead),
            model=UserRead,
        ),
        rejection_plan=RejectionPlan(policy=StopQuietly(), policy_name="stop"),
        use_sqlrules=False,
    )
    processed = process_row(row={"id": "bad", "name": "Ada"}, index=0, plan=plan)
    assert processed.model is None
    assert processed.raise_error is None
    assert processed.continue_processing is False
    assert processed.retain_rejection is False
