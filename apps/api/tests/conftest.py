"""Integration tests run against a real Postgres (compose: 127.0.0.1:55432, CI: service container).
A separate database `archmind_test` is recreated per test session from the Alembic migrations."""

import os

TEST_URL = os.environ.get(
    "ARCHMIND_TEST_DATABASE_URL", "postgresql+psycopg://archmind:archmind@localhost:55432/archmind_test"
)
os.environ["ARCHMIND_DATABASE_URL"] = TEST_URL  # must happen before archmind modules read settings

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

API_DIR = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def database() -> Iterator[None]:
    url = make_url(TEST_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(API_DIR, "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def client(database: None) -> Iterator[TestClient]:
    from archmind.main import app

    with TestClient(app) as c:
        yield c
