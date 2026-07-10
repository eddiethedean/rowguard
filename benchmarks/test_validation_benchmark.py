from pydantic import BaseModel

from rowguard.validation.pydantic import PydanticValidator


class SmallModel(BaseModel):
    id: int
    name: str
    age: int


def test_pydantic_wrapper_benchmark(benchmark) -> None:
    validator = PydanticValidator(SmallModel)
    row = {"id": 1, "name": "Ada", "age": 37}

    result = benchmark(validator.validate, row)
    assert result.accepted
