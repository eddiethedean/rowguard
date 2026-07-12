from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from rowguard.errors import ResultAssemblyError, RowAdaptationError, RowValidationError
from rowguard.rejection.base import RejectionContext, empty_rejection_context
from rowguard.rejection.policies import CollectPolicy, RaisePolicy, SkipPolicy
from rowguard.results.rejected_row import RejectedRow


class UserRead(BaseModel):
    id: int


def make_rejected() -> RejectedRow:
    try:
        UserRead.model_validate({"id": "bad"})
    except ValidationError as error:
        return RejectedRow(
            index=0,
            model=UserRead,
            mapping={"id": "bad"},
            validation_error=error,
        )
    raise AssertionError("expected validation failure")


def _ctx() -> RejectionContext:
    return empty_rejection_context(model=UserRead)


def test_collect_retains() -> None:
    decision = CollectPolicy().handle(make_rejected(), _ctx())
    assert decision.continue_processing
    assert decision.retain_rejection
    assert decision.error is None


def test_skip_does_not_retain() -> None:
    decision = SkipPolicy().handle(make_rejected(), _ctx())
    assert decision.continue_processing
    assert not decision.retain_rejection
    assert decision.error is None


def test_raise_stops() -> None:
    decision = RaisePolicy().handle(make_rejected(), _ctx())
    assert not decision.continue_processing
    assert not decision.retain_rejection
    assert isinstance(decision.error, RowValidationError)
    assert decision.error.row_index == 0
    assert decision.error.model is UserRead


def test_raise_adaptation_error() -> None:
    rejected = RejectedRow(
        index=1,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=RowAdaptationError("bad shape"),
    )
    decision = RaisePolicy().handle(rejected, _ctx())
    assert isinstance(decision.error, RowAdaptationError)
    assert decision.error.row_index == 1
    assert decision.error.model is UserRead
    assert str(decision.error) == "bad shape"


def test_raise_requires_error() -> None:
    rejected = RejectedRow(
        index=0,
        model=UserRead,
        mapping={},
        validation_error=None,
        adaptation_error=None,
    )
    with pytest.raises(ResultAssemblyError, match="requires a validation or adaptation error"):
        RaisePolicy().handle(rejected, _ctx())
