from collections.abc import Iterator
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StreamResult(Generic[T], Iterator[T]):
    def __iter__(self) -> "StreamResult[T]":
        return self

    def __next__(self) -> T:
        raise StopIteration
