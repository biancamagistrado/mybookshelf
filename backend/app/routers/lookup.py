"""Catalogue search, so a book can be added by title or ISBN."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app import schemas
from app.services import enrichment

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


@router.get("", response_model=list[schemas.BookSuggestion])
def lookup_books(
    q: str = Query(..., min_length=2, max_length=200, description="Title or ISBN"),
    limit: int = Query(8, ge=1, le=20),
) -> list[schemas.BookSuggestion]:
    """Find candidate books, so the add form can be filled in from a catalogue."""
    try:
        candidates = enrichment.search_books(q, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The book catalogue is unavailable right now. You can still add the "
            "book by typing its details.",
        ) from exc

    return [schemas.BookSuggestion(**vars(candidate)) for candidate in candidates]
