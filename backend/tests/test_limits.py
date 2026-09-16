"""Request size limit, database URL handling, and per-library lookup runs."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.limits import MaxBodySizeMiddleware
from app.services import enrichment


def _app(max_bytes: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"size": len(await request.body())}

    return TestClient(app)


def test_a_body_within_the_limit_is_accepted():
    response = _app(10).post("/echo", content=b"x" * 10)
    assert response.status_code == 200
    assert response.json() == {"size": 10}


def test_a_declared_oversized_body_is_refused():
    assert _app(10).post("/echo", content=b"x" * 11).status_code == 413


def test_an_undeclared_oversized_body_is_refused():
    def chunks():
        yield b"x" * 6
        yield b"x" * 6

    assert _app(10).post("/echo", content=chunks()).status_code == 413


def test_neon_style_database_urls_get_the_psycopg_driver():
    for url in ("postgresql://u:p@host/db?sslmode=require", "postgres://u:p@host/db"):
        assert Settings(database_url=url).sqlalchemy_url.startswith(
            "postgresql+psycopg://u:p@host/db"
        )
    explicit = "postgresql+psycopg://u:p@host/db"
    assert Settings(database_url=explicit).sqlalchemy_url == explicit


def test_lookup_runs_are_per_library():
    state = enrichment._RunState()
    assert state.acquire("alice")
    assert state.acquire("bob"), "one library's run must not block another's"
    assert not state.acquire("alice"), "the same library cannot run twice at once"
    state.release("alice")
    assert state.acquire("alice")
