from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ValidationResult(Generic[T]):
    model: T | None
    error: ValidationError | None

    @property
    def accepted(self) -> bool:
        return self.model is not None


class Validator(Protocol[T]):
    def validate(self, value: object) -> ValidationResult[T]: ...
