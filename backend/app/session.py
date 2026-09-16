"""Which library a request is talking to."""

from __future__ import annotations

import re

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

DEFAULT_SESSION = "default"
SESSION_HEADER = "X-Session-Id"

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def resolve_session(
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
) -> str:
    """FastAPI dependency returning the library id for this request."""
    settings = get_settings()
    if not settings.per_visitor_libraries:
        return DEFAULT_SESSION

    if not x_session_id:
        return DEFAULT_SESSION
    if not _SESSION_RE.match(x_session_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{SESSION_HEADER} must be 16-64 characters of A-Z, a-z, 0-9, _ or -.",
        )
    return x_session_id


def current_library(
    session_id: str = Depends(resolve_session),
    db: Session = Depends(get_db),
) -> str:
    """Resolve the library and ensure it exists."""
    from app.services import sample_library

    sample_library.ensure_seeded(db, session_id)
    return session_id
