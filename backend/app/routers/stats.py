"""Reading statistics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.session import current_library

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=schemas.StatsOut)
def get_stats(
    db: Session = Depends(get_db),
    session_id: str = Depends(current_library),
) -> schemas.StatsOut:
    """Totals, this-year progress, and top genres/authors for the stats view."""
    return crud.build_stats(db, session_id)
