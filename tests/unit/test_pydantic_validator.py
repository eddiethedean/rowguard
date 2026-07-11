from pydantic import BaseModel, ConfigDict

from rowguard.validation.pydantic import PydanticValidator


class UserRead(BaseModel):
    id: int


class AttrUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


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


def test_validator_strict_rejects_coercion() -> None:
    loose = PydanticValidator(UserRead, strict=False).validate({"id": "1"})
    assert loose.accepted
    assert loose.model == UserRead(id=1)

    strict = PydanticValidator(UserRead, strict=True).validate({"id": "1"})
    assert not strict.accepted
    assert strict.error is not None


def test_validator_from_attributes() -> None:
    class Entity:
        id = 7
        name = "Ada"

    mapping_mode = PydanticValidator(AttrUser, from_attributes=False).validate(Entity())
    assert not mapping_mode.accepted

    attrs_mode = PydanticValidator(AttrUser, from_attributes=True).validate(Entity())
    assert attrs_mode.accepted
    assert attrs_mode.model == AttrUser(id=7, name="Ada")
