"""Per-visitor libraries."""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from functools import lru_cache
from pathlib import Path

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import crud, models
from app.config import get_settings
from app.session import DEFAULT_SESSION

logger = logging.getLogger(__name__)

_seed_lock = threading.Lock()

_DATE_FIELDS = ("date_read", "date_added")

_TOUCH_EVERY = dt.timedelta(hours=1)


@lru_cache
def seed_books() -> list[dict]:
    """Load and cache the pre-enriched sample library."""
    path = Path(get_settings().seed_library_path)
    if not path.is_file():
        logger.warning("Seed library not found at %s", path.resolve())
        return []
    return json.loads(path.read_text())


def library_is_empty(db: Session, session_id: str) -> bool:
    return not db.scalar(select(exists().where(models.Book.session_id == session_id)))


def book_count(db: Session, session_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(models.Book)
            .where(models.Book.session_id == session_id)
        )
        or 0
    )


def _mark_seeded(db: Session, session_id: str) -> None:
    db.execute(
        insert(models.SeededLibrary)
        .values(session_id=session_id)
        .on_conflict_do_nothing(index_elements=["session_id"])
    )


def _delete_libraries(db: Session, session_ids: list[str]) -> None:
    if not session_ids:
        return
    book_ids = select(models.Book.id).where(models.Book.session_id.in_(session_ids))
    db.execute(
        delete(models.book_genres).where(models.book_genres.c.book_id.in_(book_ids))
    )
    db.execute(delete(models.Book).where(models.Book.session_id.in_(session_ids)))
    db.execute(
        delete(models.SeededLibrary).where(
            models.SeededLibrary.session_id.in_(session_ids)
        )
    )


def prune(db: Session) -> int:
    """Delete idle libraries, then the least recently used past the cap."""
    settings = get_settings()
    library = models.SeededLibrary
    shared = library.session_id != DEFAULT_SESSION

    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=settings.library_max_idle_days)
    doomed = list(
        db.scalars(
            select(library.session_id).where(shared, library.last_seen_at < cutoff)
        )
    )
    _delete_libraries(db, doomed)

    total = db.scalar(select(func.count()).select_from(library).where(shared)) or 0
    excess = total - settings.max_libraries + 1
    if excess > 0:
        oldest = list(
            db.scalars(
                select(library.session_id)
                .where(shared)
                .order_by(library.last_seen_at)
                .limit(excess)
            )
        )
        _delete_libraries(db, oldest)
        doomed += oldest

    db.commit()
    if doomed:
        logger.info("Deleted %s unused libraries", len(doomed))
    return len(doomed)


def _touch(db: Session, library: models.SeededLibrary) -> None:
    now = dt.datetime.now(dt.UTC)
    if library.last_seen_at < now - _TOUCH_EVERY:
        library.last_seen_at = now
        db.commit()


def _delete_books(db: Session, session_id: str) -> int:
    count = book_count(db, session_id)
    book_ids = select(models.Book.id).where(models.Book.session_id == session_id)
    db.execute(
        delete(models.book_genres).where(models.book_genres.c.book_id.in_(book_ids))
    )
    db.execute(delete(models.Book).where(models.Book.session_id == session_id))
    return count


def _to_book(row: dict, session_id: str) -> models.Book:
    values = {k: v for k, v in row.items() if k != "genres"}
    for field in _DATE_FIELDS:
        if values.get(field):
            values[field] = dt.date.fromisoformat(values[field])
    return models.Book(
        session_id=session_id,
        enrichment_status="enriched",
        enrichment_source="seed",
        enriched_at=dt.datetime.now(dt.UTC),
        **values,
    )


def seed_library(db: Session, session_id: str) -> int:
    """Give one library its own copy of the sample books.

    Written as two bulk inserts rather than one per book. Seeding crosses the
    network to a managed database, where several hundred round trips take long
    enough that the first visitor's request times out.
    """
    rows = seed_books()
    if not rows:
        return 0

    now = dt.datetime.now(dt.UTC)
    # Every row must carry the same keys. Rows differ in the wild, since not
    # every book has an ISBN or a rating, and SQLAlchemy can only batch rows of
    # the same shape: 263 books were going out as 134 separate INSERTs.
    columns = {key for row in rows for key in row if key != "genres"}
    values = []
    for row in rows:
        book = {key: row.get(key) for key in columns}
        for field in _DATE_FIELDS:
            if book.get(field):
                book[field] = dt.date.fromisoformat(book[field])
        book.update(
            session_id=session_id,
            enrichment_status="enriched",
            enrichment_source="seed",
            enriched_at=now,
        )
        values.append(book)

    # .values(...) compiles every row into one statement. Passing the rows as a
    # list to execute() instead makes SQLAlchemy send them two at a time, which
    # was 136 round trips to a database on the other side of the internet.
    # The library is empty here, so reading the ids back in order matches.
    db.execute(insert(models.Book).values(values))
    book_ids = list(
        db.scalars(
            select(models.Book.id)
            .where(models.Book.session_id == session_id)
            .order_by(models.Book.id)
        )
    )

    names = [name for row in rows for name in row.get("genres") or []]
    genre_id = {genre.slug: genre.id for genre in crud.get_or_create_genres(db, names)}
    links = [
        {"book_id": book_id, "genre_id": genre_id[slug], "source": "catalogue"}
        for book_id, row in zip(book_ids, rows, strict=True)
        for slug in dict.fromkeys(
            crud.slugify_genre(name) for name in row.get("genres") or []
        )
        if slug in genre_id
    ]
    if links:
        db.execute(insert(models.book_genres), links)

    _mark_seeded(db, session_id)
    db.commit()
    logger.info("Seeded %s books for library %s", len(rows), session_id[:8])
    return len(rows)


def ensure_seeded(db: Session, session_id: str) -> None:
    """Give a library the sample books on its first visit."""
    if not get_settings().per_visitor_libraries:
        return
    library = db.get(models.SeededLibrary, session_id)
    if library is not None:
        _touch(db, library)
        return
    with _seed_lock:
        if db.get(models.SeededLibrary, session_id) is not None:
            return
        prune(db)
        if library_is_empty(db, session_id):
            seed_library(db, session_id)
        else:
            _mark_seeded(db, session_id)
            db.commit()


def clear(db: Session, session_id: str) -> int:
    """Delete every book in one library."""
    deleted = _delete_books(db, session_id)
    _mark_seeded(db, session_id)
    db.commit()
    return deleted


def reset(db: Session, session_id: str) -> int:
    """Wipe one library and re-seed it from the sample data."""
    _delete_books(db, session_id)
    db.commit()
    return seed_library(db, session_id)
