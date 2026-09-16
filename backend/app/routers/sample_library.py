"""Restore a visitor's copy of the sample library."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services import sample_library
from app.session import current_library

router = APIRouter(prefix="/api/sample-library", tags=["meta"])


@router.post("/reset", status_code=status.HTTP_202_ACCEPTED)
def reset_sample_library(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> dict:
    """Restore this visitor's sample library."""
    if not get_settings().per_visitor_libraries:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    return {"status": "reset", "books": sample_library.reset(db, session_id)}
