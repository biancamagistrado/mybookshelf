"""Parsing of Goodreads library exports (and close-enough CSVs)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import crud, models
from app.text import normalise_typography

MAX_ERRORS_REPORTED = 25

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "goodreads_id": ("bookid", "goodreadsid", "id"),
    "title": ("title", "booktitle", "name", "worktitle"),
    "author": (
        "author",
        "authors",
        "primaryauthor",
        "authorlf",
        "creator",
        "byauthor",
    ),
    "additional_authors": ("additionalauthors", "otherauthors", "contributors"),
    "isbn": ("isbn", "isbn10"),
    "isbn13": ("isbn13", "isbnuid", "isbns", "uid"),
    "my_rating": ("myrating", "rating", "yourrating", "starrating"),
    "average_rating": ("averagerating", "avgrating", "communityrating"),
    "publisher": ("publisher", "publishers", "publication"),
    "binding": ("binding", "format", "mediatype"),
    "number_of_pages": ("numberofpages", "pages", "pagecount", "numpages"),
    "year_published": ("yearpublished", "publicationyear", "pubdate", "published"),
    "original_publication_year": (
        "originalpublicationyear",
        "firstpublished",
        "originalyear",
    ),
    "date_read": ("dateread", "lastdateread", "datesread", "datefinished", "finished"),
    "date_added": ("dateadded", "dateentered", "entrydate", "added"),
    "bookshelves": ("bookshelves", "shelves", "collections"),
    "exclusive_shelf": (
        "exclusiveshelf",
        "shelf",
        "status",
        "readstatus",
        "collection",
    ),
    "my_review": ("myreview", "review", "comments", "notes"),
    "read_count": ("readcount", "timesread", "readtimes"),
    "owned_copies": ("ownedcopies", "owned", "copies"),
    "genre": ("genre", "genres", "category", "categories", "tags", "subjects"),
}

NOTABLE_COLUMNS: dict[str, str] = {
    "author": "author",
    "exclusive_shelf": "shelf (read / reading / to-read)",
    "date_read": "date read",
    "isbn13": "ISBN",
}


@dataclass
class ImportSummary:
    total_rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    over_limit: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def note_error(self, line: int, message: str) -> None:
        self.skipped += 1
        if len(self.errors) < MAX_ERRORS_REPORTED:
            self.errors.append(f"Row {line}: {message}")


def _normalise_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (header or "").lower())


def _build_header_map(fieldnames: list[str] | None) -> dict[str, str]:
    """Map canonical field names to the actual header text in this file."""
    if not fieldnames:
        return {}
    normalised = {_normalise_header(h): h for h in fieldnames if h}
    mapping: dict[str, str] = {}
    for canonical, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                mapping[canonical] = normalised[alias]
                break
    return mapping


def _clean(value: str | None) -> str | None:
    """Strip Goodreads' ``="..."`` spreadsheet wrapper and blank sentinels."""
    if value is None:
        return None
    text = value.strip()
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    text = text.strip().strip('"').strip()
    return normalise_typography(text) or None


def _to_int(value: str | None) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_date(value: str | None) -> dt.date | None:
    """Parse Goodreads' YYYY/MM/DD, plus a few forgiving variants."""
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%Y/%m", "%Y-%m", "%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_shelf(value: str | None) -> str:
    text = _clean(value)
    if not text:
        return "to-read"
    return text.strip().lower().replace(" ", "-").replace("_", "-")


def _split_genres(value: str | None) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    parts = re.split(r"[,;|/]", text)
    return [p.strip() for p in parts if p.strip()][:20]


def parse_rows(content: bytes) -> tuple[list[dict], dict[str, str], list[str]]:
    """Decode the upload and return (rows, header map, decoding warnings)."""
    warnings: list[str] = []
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            if encoding == "latin-1":
                warnings.append(
                    "File was not valid UTF-8; decoded as latin-1. "
                    "Some characters may be wrong."
                )
            break
        except UnicodeDecodeError:
            continue
    if text is None:  # pragma: no cover
        raise ValueError("Could not decode the uploaded file as text.")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header_map = _build_header_map(reader.fieldnames)
    if "title" not in header_map:
        raise ValueError(
            "No 'Title' column found, so there is nothing to import. Export "
            "your library from Goodreads (My Books → Import and export) or "
            "StoryGraph, and upload that file."
        )

    missing = [
        label
        for field_name, label in NOTABLE_COLUMNS.items()
        if field_name not in header_map
    ]
    if missing:
        warnings.append(
            "These columns were not recognised, so that information was not "
            f"imported: {', '.join(missing)}."
        )

    return list(reader), header_map, warnings


def _row_values(cell) -> dict:
    """Map one CSV row onto Book column values."""
    title = _clean(cell("title"))
    if not title:
        raise ValueError("missing title")

    rating = _to_int(cell("my_rating"))
    return {
        "title": title[:500],
        "author": (_clean(cell("author")) or "")[:500],
        "additional_authors": _clean(cell("additional_authors")),
        "isbn": (_clean(cell("isbn")) or "")[:13] or None,
        "isbn13": (_clean(cell("isbn13")) or "")[:13] or None,
        "publisher": _clean(cell("publisher")),
        "binding": (_clean(cell("binding")) or "")[:80] or None,
        "number_of_pages": _to_int(cell("number_of_pages")),
        "year_published": _to_int(cell("year_published")),
        "original_publication_year": _to_int(cell("original_publication_year")),
        "exclusive_shelf": _to_shelf(cell("exclusive_shelf"))[:80],
        "bookshelves": _clean(cell("bookshelves")),
        "my_rating": rating if rating else None,
        "average_rating": _to_float(cell("average_rating")),
        "date_read": _to_date(cell("date_read")),
        "date_added": _to_date(cell("date_added")),
        "read_count": _to_int(cell("read_count")),
        "owned_copies": _to_int(cell("owned_copies")),
        "my_review": _clean(cell("my_review")),
    }


def _import_row(
    db: Session, cell, summary: ImportSummary, session_id: str, room: int
) -> None:
    """Upsert a single CSV row."""
    values = _row_values(cell)
    goodreads_id = _to_int(cell("goodreads_id"))
    genres = _split_genres(cell("genre"))

    existing = crud.find_duplicate(
        db,
        session_id=session_id,
        goodreads_id=goodreads_id,
        title=values["title"],
        author=values["author"],
    )

    if existing is not None:
        for key, value in values.items():
            setattr(existing, key, value)
        if goodreads_id and existing.goodreads_id is None:
            existing.goodreads_id = goodreads_id
        if genres:
            crud.set_manual_genres(db, existing, genres)
        summary.updated += 1
        return

    if summary.created >= room:
        summary.skipped += 1
        summary.over_limit += 1
        return

    book = models.Book(
        goodreads_id=goodreads_id,
        source="goodreads_csv",
        session_id=session_id,
        **values,
    )
    db.add(book)
    db.flush()
    if genres:
        crud.set_manual_genres(db, book, genres)
    summary.created += 1


def import_csv(db: Session, content: bytes, session_id: str = "default") -> ImportSummary:
    """Parse a CSV upload and upsert every readable row into the books table."""
    rows, header_map, warnings = parse_rows(content)
    summary = ImportSummary(warnings=list(warnings))
    room = crud.remaining_capacity(db, session_id)

    for offset, row in enumerate(rows, start=2):
        summary.total_rows += 1

        def cell(field_name: str, _row=row) -> str | None:
            header = header_map.get(field_name)
            return _row.get(header) if header else None

        try:
            with db.begin_nested():
                _import_row(db, cell, summary, session_id, room)
        except Exception as exc:  # noqa: BLE001
            summary.note_error(offset, str(exc)[:200])

    if summary.over_limit:
        summary.warnings.append(
            f"Your library is full, so {summary.over_limit} "
            f"{'book was' if summary.over_limit == 1 else 'books were'} not added."
        )

    db.commit()
    return summary
