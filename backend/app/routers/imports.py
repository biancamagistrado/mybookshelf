"""CSV upload endpoint."""

from __future__ import annotations

import datetime as dt

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import SessionLocal, get_db
from app.services import csv_import, enrichment
from app.session import current_library

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/goodreads", response_model=schemas.ImportResult)
async def import_goodreads_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Goodreads library export (.csv)"),
    enrich: bool = Query(True, description="Queue enrichment for the new books"),
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> schemas.ImportResult:
    """Parse a Goodreads export and upsert its rows."""
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please upload a .csv file.")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB.",
        )

    try:
        summary = csv_import.import_csv(db, content, session_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    queued = False
    if enrich and (summary.created or summary.updated):
        background_tasks.add_task(
            enrichment.enrich_pending, SessionLocal, 500, True, session_id
        )
        queued = True

    return schemas.ImportResult(
        total_rows=summary.total_rows,
        created=summary.created,
        updated=summary.updated,
        skipped=summary.skipped,
        errors=summary.errors,
        warnings=summary.warnings,
        enrichment_queued=queued,
    )


@router.post("/list", response_model=schemas.ListImportResult)
def import_from_list(
    payload: schemas.ListImportRequest,
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> schemas.ListImportResult:
    """Add books from typed titles or ISBNs, looked up in the catalogue."""
    lines = [line.strip() for line in payload.lines if line.strip()]
    room = crud.remaining_capacity(db, session_id)
    if len(lines) > room:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your library is full."
            if room == 0
            else f"Your library only has room for {room} more "
            f"{'book' if room == 1 else 'books'}.",
        )

    created = 0
    not_found: list[str] = []
    already: list[str] = []

    for line in lines:
        try:
            matches = enrichment.search_books(line, limit=1)
        except Exception:  # noqa: BLE001
            matches = []
        if not matches:
            not_found.append(line)
            continue

        found = matches[0]
        if crud.find_duplicate(
            db,
            session_id=session_id,
            goodreads_id=None,
            title=found.title,
            author=found.author,
        ):
            already.append(found.title)
            continue

        book = models.Book(
            session_id=session_id,
            source="lookup",
            title=found.title,
            author=found.author,
            isbn13=found.isbn13,
            cover_url=found.cover_url,
            number_of_pages=found.number_of_pages,
            year_published=found.year_published,
            publisher=found.publisher,
            exclusive_shelf=payload.exclusive_shelf,
            enrichment_status="enriched",
            enrichment_source=found.source,
            enriched_at=dt.datetime.now(dt.UTC),
        )
        db.add(book)
        db.flush()
        if found.genres:
            crud.merge_catalogue_genres(db, book, found.genres)
        created += 1

    db.commit()
    return schemas.ListImportResult(
        created=created, already_on_shelf=already, not_found=not_found
    )
