from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from rowguard.validation.base import ValidationResult

T = TypeVar("T", bound=BaseModel)


class PydanticValidator(Generic[T]):
    def __init__(self, model: type[T], *, strict: bool | None = None) -> None:
        self._model = model
        self._strict = strict

    def validate(self, value: object) -> ValidationResult[T]:
        try:
            model = self._model.model_validate(value, strict=self._strict)
        except ValidationError as error:
            return ValidationResult(model=None, error=error)
        return ValidationResult(model=model, error=None)
