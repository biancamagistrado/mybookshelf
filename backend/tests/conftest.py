"""Test fixtures: a real PostgreSQL database, one rolled-back transaction per test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app

_ENV = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}

DEFAULT_TEST_URL = (
    "postgresql+psycopg://"
    f"{_ENV.get('POSTGRES_USER', 'bookshelf')}:"
    f"{_ENV.get('POSTGRES_PASSWORD', '')}@"
    f"{_ENV.get('POSTGRES_HOST', 'localhost')}:"
    f"{_ENV.get('POSTGRES_PORT', '5432')}/bookshelf_test"
)


def _create_database_if_missing(url) -> None:
    """CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT."""
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def engine():
    url = make_url(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL))
    try:
        _create_database_if_missing(url)
    except OperationalError as exc:
        pytest.fail(
            f"Cannot reach PostgreSQL at {url.host}:{url.port} as {url.username!r}.\n"
            "Start it with `docker compose up -d db`, or set TEST_DATABASE_URL to "
            "a server you can reach.\n"
            f"Original error: {exc.orig}",
            pytrace=False,
        )

    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


GOODREADS_CSV = b"""Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies
2767052,The Hunger Games,Suzanne Collins,"Collins, Suzanne",,="0439023483",="9780439023481",5,4.33,Scholastic Press,Hardcover,374,2008,2008,2024/03/14,2024/01/02,favorites,favorites (#1),read,Loved it,,,1,1
5907,The Hobbit,J.R.R. Tolkien,"Tolkien, J.R.R.",,="0618260307",="9780618260300",0,4.28,Houghton Mifflin,Paperback,366,2002,1937,,2023/11/05,,,to-read,,,,0,0
375802,Ender's Game,Orson Scott Card,"Card, Orson Scott",,="",="",4,4.30,Tor,Paperback,324,1994,1985,2025/01/20,2024/12/30,sci-fi,sci-fi (#2),currently-reading,,,,1,0
,,,,,,,,,,,,,,,,,,,,,,,
"""
