"""Database access helpers shared by the routers."""

from __future__ import annotations

import datetime as dt
import re

from sqlalchemy import Select, delete, func, insert, or_, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def remaining_capacity(db: Session, session_id: str) -> int:
    """How many more books this library can hold under MAX_BOOKS_PER_LIBRARY."""
    count = (
        db.scalar(
            select(func.count())
            .select_from(models.Book)
            .where(models.Book.session_id == session_id)
        )
        or 0
    )
    return max(0, get_settings().max_books_per_library - count)


def slugify_genre(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-")


def get_or_create_genres(db: Session, names: list[str]) -> list[models.Genre]:
    """Resolve genre names to rows, creating any that are new."""
    wanted: dict[str, str] = {}
    for raw in names:
        slug = slugify_genre(raw)
        if slug and slug not in wanted:
            wanted[slug] = raw.strip()
    if not wanted:
        return []

    existing = {
        g.slug: g
        for g in db.scalars(
            select(models.Genre).where(models.Genre.slug.in_(wanted.keys()))
        )
    }
    result: list[models.Genre] = []
    for slug, display in wanted.items():
        genre = existing.get(slug)
        if genre is None:
            genre = models.Genre(slug=slug, name=display)
            db.add(genre)
            db.flush()
            existing[slug] = genre
        result.append(genre)
    return result


def _link_genres(
    db: Session, book: models.Book, genres: list[models.Genre], source: str
) -> None:
    """Insert join rows for genres not already linked to this book."""
    already = set(
        db.scalars(
            select(models.book_genres.c.genre_id).where(
                models.book_genres.c.book_id == book.id
            )
        )
    )
    rows = [
        {"book_id": book.id, "genre_id": genre.id, "source": source}
        for genre in genres
        if genre.id not in already
    ]
    if rows:
        db.execute(insert(models.book_genres), rows)


def set_manual_genres(db: Session, book: models.Book, names: list[str]) -> None:
    """Replace a book's genres with the list the user supplied."""
    db.flush()
    db.execute(delete(models.book_genres).where(models.book_genres.c.book_id == book.id))
    _link_genres(db, book, get_or_create_genres(db, names), "manual")
    db.expire(book, ["genres"])


def merge_catalogue_genres(db: Session, book: models.Book, names: list[str]) -> None:
    """Refresh the catalogue-sourced genres, leaving the user's own alone."""
    if not names:
        return
    db.flush()
    db.execute(
        delete(models.book_genres).where(
            models.book_genres.c.book_id == book.id,
            models.book_genres.c.source == "catalogue",
        )
    )
    _link_genres(db, book, get_or_create_genres(db, names), "catalogue")
    db.expire(book, ["genres"])


def find_duplicate(
    db: Session,
    *,
    session_id: str,
    goodreads_id: int | None,
    title: str,
    author: str,
) -> models.Book | None:
    """Locate an existing row for an incoming book."""
    if goodreads_id is not None:
        book = db.scalar(
            select(models.Book).where(
                models.Book.session_id == session_id,
                models.Book.goodreads_id == goodreads_id,
            )
        )
        if book:
            return book
    return db.scalar(
        select(models.Book).where(
            models.Book.session_id == session_id,
            func.lower(models.Book.title) == title.strip().lower(),
            func.lower(models.Book.author) == author.strip().lower(),
        )
    )


def apply_book_filters(
    stmt: Select,
    *,
    session_id: str,
    shelf: str | None = None,
    author: str | None = None,
    genre: str | None = None,
    search: str | None = None,
    unenriched_only: bool = False,
) -> Select:
    """Apply the dashboard's filter controls to a books SELECT."""
    stmt = stmt.where(models.Book.session_id == session_id)
    if shelf:
        stmt = stmt.where(models.Book.exclusive_shelf == shelf)
    if author:
        stmt = stmt.where(func.lower(models.Book.author) == author.strip().lower())
    if genre:
        stmt = stmt.where(
            models.Book.genres.any(models.Genre.slug == slugify_genre(genre))
        )
    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(models.Book.title).like(pattern),
                func.lower(models.Book.author).like(pattern),
                models.Book.genres.any(func.lower(models.Genre.name).like(pattern)),
            )
        )
    if unenriched_only:
        stmt = stmt.where(models.Book.enrichment_status == "pending")
    return stmt


def sort_books(stmt: Select, sort: str, direction: str) -> Select:
    columns = {
        "title": models.Book.title,
        "author": models.Book.author,
        "date_read": models.Book.date_read,
        "date_added": models.Book.date_added,
        "my_rating": models.Book.my_rating,
        "average_rating": models.Book.average_rating,
    }
    column = columns.get(sort, models.Book.date_added)
    order = column.desc() if direction == "desc" else column.asc()
    return stmt.order_by(order.nullslast(), models.Book.id.asc())


def apply_book_payload(
    db: Session,
    book: models.Book,
    payload: dict,
    genres: list[str] | None,
) -> models.Book:
    """Copy a validated payload onto a Book, resolving genres if given."""
    for field, value in payload.items():
        setattr(book, field, value)
    if genres is not None:
        set_manual_genres(db, book, genres)
    return book


def shelf_counts(db: Session, session_id: str) -> list[schemas.ShelfCount]:
    rows = db.execute(
        select(models.Book.exclusive_shelf, func.count())
        .where(models.Book.session_id == session_id)
        .group_by(models.Book.exclusive_shelf)
        .order_by(func.count().desc())
    ).all()
    return [schemas.ShelfCount(shelf=shelf, count=count) for shelf, count in rows]


def author_facets(db: Session, session_id: str, limit: int) -> list[schemas.FacetCount]:
    rows = db.execute(
        select(models.Book.author, func.count())
        .where(models.Book.session_id == session_id, models.Book.author != "")
        .group_by(models.Book.author)
        .order_by(func.count().desc(), models.Book.author.asc())
        .limit(limit)
    ).all()
    return [schemas.FacetCount(value=a, count=c) for a, c in rows]


def genre_facets(db: Session, session_id: str, limit: int) -> list[schemas.FacetCount]:
    rows = db.execute(
        select(models.Genre.name, func.count(models.book_genres.c.book_id))
        .join(models.book_genres, models.Genre.id == models.book_genres.c.genre_id)
        .join(models.Book, models.Book.id == models.book_genres.c.book_id)
        .where(models.Book.session_id == session_id)
        .group_by(models.Genre.id, models.Genre.name)
        .order_by(func.count(models.book_genres.c.book_id).desc(), models.Genre.name)
        .limit(limit)
    ).all()
    return [schemas.FacetCount(value=n, count=c) for n, c in rows]


def build_stats(db: Session, session_id: str) -> schemas.StatsOut:
    this_year = dt.date.today().year
    mine = models.Book.session_id == session_id

    total_books = (
        db.scalar(select(func.count()).select_from(models.Book).where(mine)) or 0
    )
    by_shelf = {row.shelf: row.count for row in shelf_counts(db, session_id)}
    books_read = by_shelf.get("read", 0)

    books_read_this_year = (
        db.scalar(
            select(func.count())
            .select_from(models.Book)
            .where(
                mine,
                models.Book.date_read >= dt.date(this_year, 1, 1),
                models.Book.date_read <= dt.date(this_year, 12, 31),
            )
        )
        or 0
    )

    pages_read = (
        db.scalar(
            select(func.coalesce(func.sum(models.Book.number_of_pages), 0)).where(
                mine, models.Book.exclusive_shelf == "read"
            )
        )
        or 0
    )

    average_rating_given = db.scalar(
        select(func.avg(models.Book.my_rating)).where(mine, models.Book.my_rating > 0)
    )

    per_year_rows = db.execute(
        select(func.extract("year", models.Book.date_read).label("year"), func.count())
        .where(mine, models.Book.date_read.is_not(None))
        .group_by("year")
        .order_by("year")
    ).all()

    rating_rows = db.execute(
        select(models.Book.my_rating, func.count())
        .where(mine, models.Book.my_rating > 0)
        .group_by(models.Book.my_rating)
        .order_by(models.Book.my_rating)
    ).all()
    rating_map = {int(r): c for r, c in rating_rows}

    return schemas.StatsOut(
        total_books=total_books,
        books_read=books_read,
        books_read_this_year=books_read_this_year,
        currently_reading=by_shelf.get("currently-reading", 0),
        to_read=by_shelf.get("to-read", 0),
        pages_read=int(pages_read),
        average_rating_given=(
            round(float(average_rating_given), 2) if average_rating_given else None
        ),
        top_genres=[
            schemas.TopItem(name=f.value, count=f.count)
            for f in genre_facets(db, session_id, 8)
        ],
        top_authors=[
            schemas.TopItem(name=f.value, count=f.count)
            for f in author_facets(db, session_id, 8)
        ],
        books_per_year=[
            schemas.YearCount(year=int(y), count=c) for y, c in per_year_rows
        ],
        rating_distribution=[
            schemas.RatingBucket(rating=r, count=rating_map.get(r, 0))
            for r in range(1, 6)
        ],
    )
