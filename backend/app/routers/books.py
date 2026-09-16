"""CRUD endpoints for books, plus the filter facets the UI needs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.services import sample_library
from app.session import current_library

router = APIRouter(prefix="/api/books", tags=["books"])


def _owned_book(db: Session, book_id: int, session_id: str) -> models.Book:
    """Fetch a book from this library, or 404."""
    book = db.get(models.Book, book_id)
    if book is None or book.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    return book


@router.get("", response_model=schemas.BookPage)
def list_books(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
    shelf: str | None = Query(None, description="Exclusive shelf, e.g. 'read'"),
    author: str | None = Query(None),
    genre: str | None = Query(None, description="Genre name or slug"),
    search: str | None = Query(None, description="Substring of title or author"),
    unenriched_only: bool = Query(False),
    sort: schemas.SortField = Query("date_added"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(48, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> schemas.BookPage:
    """Paginated, filtered list of books for the shelf."""
    filters = {
        "session_id": session_id,
        "shelf": shelf,
        "author": author,
        "genre": genre,
        "search": search,
        "unenriched_only": unenriched_only,
    }

    total = (
        db.scalar(
            crud.apply_book_filters(
                select(func.count()).select_from(models.Book), **filters
            )
        )
        or 0
    )

    stmt = crud.apply_book_filters(select(models.Book), **filters)
    stmt = crud.sort_books(stmt, sort, direction).limit(limit).offset(offset)
    items = list(db.scalars(stmt).unique())

    return schemas.BookPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/shelves", response_model=list[schemas.ShelfCount])
def list_shelves(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> list[schemas.ShelfCount]:
    """Every shelf present in the library with its book count."""
    return crud.shelf_counts(db, session_id)


@router.get("/authors", response_model=list[schemas.FacetCount])
def list_authors(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
    limit: int = Query(200, ge=1, le=1000),
) -> list[schemas.FacetCount]:
    return crud.author_facets(db, session_id, limit)


@router.get("/genres", response_model=list[schemas.FacetCount])
def list_genres(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
    limit: int = Query(200, ge=1, le=1000),
) -> list[schemas.FacetCount]:
    return crud.genre_facets(db, session_id, limit)


@router.get("/{book_id}", response_model=schemas.BookOut)
def get_book(
    book_id: int,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> models.Book:
    return _owned_book(db, book_id, session_id)


@router.post("", response_model=schemas.BookOut, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: schemas.BookCreate,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> models.Book:
    """Add a book by hand."""
    existing = crud.find_duplicate(
        db,
        session_id=session_id,
        goodreads_id=None,
        title=payload.title,
        author=payload.author,
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"'{payload.title}' by {payload.author or 'unknown'} is already on your shelves.",
        )

    if crud.remaining_capacity(db, session_id) < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your library is full.")

    data = payload.model_dump(exclude={"genres"})
    book = models.Book(source="manual", session_id=session_id, **data)
    db.add(book)
    crud.set_manual_genres(db, book, payload.genres)
    db.commit()
    db.refresh(book)
    return book


@router.patch("/{book_id}", response_model=schemas.BookOut)
def update_book(
    book_id: int,
    payload: schemas.BookUpdate,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> models.Book:
    book = _owned_book(db, book_id, session_id)

    data = payload.model_dump(exclude_unset=True, exclude={"genres"})
    crud.apply_book_payload(db, book, data, payload.genres)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> Response:
    book = _owned_book(db, book_id, session_id)
    db.delete(book)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("")
def clear_library(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> dict:
    """Delete every book in this library."""
    return {"deleted": sample_library.clear(db, session_id)}
