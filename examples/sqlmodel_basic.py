"""SQLModel table source with RowGuard validation-first reads."""

from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel

import rowguard


class User(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    age: int


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


engine = create_engine("sqlite+pysqlite:///:memory:")
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all(
        [
            User(id=1, name="Ada", age=37),
            User(id=2, name="Legacy", age=12),
        ]
    )
    session.commit()

    result = rowguard.execute(
        session=session,
        statement=select(User.id, User.name, User.age),
        source=User,
        model=UserRead,
        on_reject="collect",
        use_sqlrules=False,
    )
    print("accepted:", result.models)
    print("rejected:", result.rejected)
