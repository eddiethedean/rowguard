"""Callback rejection policy example."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

import rowguard
from rowguard import CallbackDecision


class UserRead(BaseModel):
    id: int
    name: str
    age: int = Field(ge=18)


def main() -> None:
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("age", Integer, nullable=False),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            users.insert(),
            [
                {"id": 1, "name": "Ada", "age": 37},
                {"id": 2, "name": "Legacy", "age": 12},
            ],
        )

    retained: list[int] = []

    def on_reject(rejected: object, context: object) -> CallbackDecision:
        del context
        retained.append(rejected.index)  # type: ignore[attr-defined]
        return CallbackDecision.RETAIN

    with Session(engine) as session:
        result = rowguard.select(
            session=session,
            table=users,
            model=UserRead,
            on_reject="callback",
            reject_callback=on_reject,
            use_sqlrules=False,
        )
    print(f"accepted={result.valid_count} retained={result.rejected_count} indices={retained}")


if __name__ == "__main__":
    main()
