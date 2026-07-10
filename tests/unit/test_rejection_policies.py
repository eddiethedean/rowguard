from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from rowguard.errors import RowAdaptationError, RowValidationError
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


def test_collect_retains() -> None:
    decision = CollectPolicy().handle(make_rejected())
    assert decision.continue_processing
    assert decision.retain_rejection


def test_skip_does_not_retain() -> None:
    decision = SkipPolicy().handle(make_rejected())
    assert decision.continue_processing
    assert not decision.retain_rejection


def test_raise_stops() -> None:
    with pytest.raises(RowValidationError) as exc_info:
        RaisePolicy().handle(make_rejected())
    assert exc_info.value.row_index == 0
    assert exc_info.value.model is UserRead


def test_raise_adaptation_error() -> None:
    rejected = RejectedRow(
        index=1,
        model=UserRead,
        mapping=None,
        validation_error=None,
        adaptation_error=RowAdaptationError("bad shape"),
    )
    with pytest.raises(RowAdaptationError, match="bad shape"):
        RaisePolicy().handle(rejected)


def test_raise_requires_error() -> None:
    rejected = RejectedRow(
        index=0,
        model=UserRead,
        mapping={},
        validation_error=None,
        adaptation_error=None,
    )
    with pytest.raises(RuntimeError, match="requires a validation or adaptation error"):
        RaisePolicy().handle(rejected)
