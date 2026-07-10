from pydantic import BaseModel

from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int


def test_validator_accepts_valid_mapping() -> None:
    result = PydanticValidator(UserRead).validate({"id": 1})
    assert result.accepted
    assert result.model == UserRead(id=1)
    assert result.error is None


def test_validator_rejects_invalid_mapping() -> None:
    result = PydanticValidator(UserRead).validate({"id": "invalid"})
    assert not result.accepted
    assert result.model is None
    assert result.error is not None
