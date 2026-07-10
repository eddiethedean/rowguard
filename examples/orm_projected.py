"""Projected ORM columns validated into Pydantic models."""

from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

import rowguard


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    age: Mapped[int]


class UserRead(BaseModel):
    id: int
    name: str
    age: Annotated[int, Field(ge=18)]


engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)

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
