from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from rowguard.validation.base import ValidationResult

T = TypeVar("T", bound=BaseModel)


class PydanticValidator(Generic[T]):
    def __init__(
        self,
        model: type[T],
        *,
        strict: bool | None = None,
        from_attributes: bool = False,
    ) -> None:
        self._model = model
        self._strict = strict
        self._from_attributes = from_attributes

    def validate(self, value: object) -> ValidationResult[T]:
        try:
            model = self._model.model_validate(
                value,
                strict=self._strict,
                from_attributes=self._from_attributes,
            )
        except ValidationError as error:
            return ValidationResult(model=None, error=error)
        return ValidationResult(model=model, error=None)
