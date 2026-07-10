from __future__ import annotations

from pydantic import BaseModel

from rowguard.adapters.sqlalchemy_row import SQLAlchemyRowAdapter
from rowguard.execution.processor import process_row
from rowguard.planning.execution_plan import ExecutionPlan
from rowguard.rejection.policies import CollectPolicy, SkipPolicy
from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int
    name: str


def _plan(*, on_reject: str = "collect") -> ExecutionPlan[UserRead]:
    policy = CollectPolicy() if on_reject == "collect" else SkipPolicy()
    return ExecutionPlan(
        statement=None,
        model=UserRead,
        adapter=SQLAlchemyRowAdapter(),
        validator=PydanticValidator(UserRead),
        rejection_policy=policy,
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
