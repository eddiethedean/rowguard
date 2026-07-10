from pydantic import BaseModel

from rowguard.results.query_result import QueryResult


class UserRead(BaseModel):
    id: int


def consume(result: QueryResult[UserRead]) -> int:
    first = result.models[0]
    return first.id
