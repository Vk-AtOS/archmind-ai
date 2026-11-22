from collections.abc import Iterator
from datetime import UTC, datetime
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from archmind.config import settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


@cache
def engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


@cache
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with session_factory()() as db:
        yield db
