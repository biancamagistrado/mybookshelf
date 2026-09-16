"""Endpoints that drive genre/cover lookups."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal, get_db
from app.services import enrichment as enrichment_service
from app.session import current_library

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


@router.get("/status", response_model=schemas.EnrichmentStatus)
def enrichment_status(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> schemas.EnrichmentStatus:
    """Counts by enrichment state, so the UI can show progress."""
    rows = db.execute(
        select(models.Book.enrichment_status, func.count())
        .where(models.Book.session_id == session_id)
        .group_by(models.Book.enrichment_status)
    ).all()
    counts = dict(rows)
    return schemas.EnrichmentStatus(
        pending=counts.get("pending", 0),
        enriched=counts.get("enriched", 0),
        not_found=counts.get("not_found", 0),
        failed=counts.get("failed", 0),
        running=enrichment_service.run_state.is_running(session_id),
    )


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_enrichment(
    payload: schemas.EnrichmentRunRequest,
    background_tasks: BackgroundTasks,
    session_id: str = Depends(current_library),
) -> dict:
    """Kick off a background enrichment pass over books that need one."""
    if enrichment_service.run_state.is_running(session_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An enrichment run is already in progress."
        )
    background_tasks.add_task(
        enrichment_service.enrich_pending,
        SessionLocal,
        payload.limit,
        payload.only_pending,
        session_id,
    )
    return {"status": "queued", "limit": payload.limit}


@router.post("/books/{book_id}", response_model=schemas.BookOut)
def enrich_single_book(
    book_id: int,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> models.Book:
    """Enrich one book synchronously, used by the 'refresh' button on a card."""
    book = db.get(models.Book, book_id)
    if book is None or book.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")

    result = enrichment_service.enrich_book(db, book)
    db.commit()
    db.refresh(book)
    if result == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The catalogue lookup failed. Try again in a moment.",
        )
    return book
