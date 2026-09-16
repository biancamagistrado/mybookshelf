"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.limits import MaxBodySizeMiddleware
from app.routers import books, enrichment, imports, lookup, sample_library, stats

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

settings = get_settings()

DESCRIPTION = """
A personal reading tracker: import a Goodreads library export, enrich it with
genres and cover art from Google Books / Open Library, then browse, filter and
measure your shelves.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to database")
    except Exception:
        logger.exception("Database connection failed at startup")
        raise

    if settings.per_visitor_libraries:
        logger.info("Per-visitor libraries: each visitor gets their own copy")
    yield


app = FastAPI(
    title=settings.api_title,
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

if "*" in settings.cors_origin_list:
    raise RuntimeError(
        "CORS_ORIGINS must list explicit origins, not '*'. "
        "A wildcard lets any site on the internet call this API."
    )

app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-Id"],
)

app.include_router(books.router)
app.include_router(imports.router)
app.include_router(enrichment.router)
app.include_router(stats.router)
app.include_router(lookup.router)
app.include_router(sample_library.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Liveness probe used by docker-compose's healthcheck."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
