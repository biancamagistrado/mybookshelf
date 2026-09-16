"""Book enrichment: fill in genre and cover art that Goodreads exports omit."""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import crud, models
from app.config import get_settings
from app.text import normalise_typography

logger = logging.getLogger(__name__)

_KEY_PARAM = re.compile(r"([?&]key=)[^&\s'\"]+")


def _safe_error(exc: BaseException) -> str:
    """Describe a failed request without the API key."""
    return _KEY_PARAM.sub(r"\1[redacted]", str(exc))


USER_AGENT = "MyBookshelf/1.0 (+https://github.com/biancamagistrado/mybookshelf)"

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"

_GENRE_STOPWORDS = {"general", "unknown", "none", "misc", "miscellaneous"}
MAX_GENRES_PER_BOOK = 5

CANONICAL_GENRES: tuple[str, ...] = (
    "Fantasy",
    "Science Fiction",
    "Mystery",
    "Thriller",
    "Horror",
    "Romance",
    "Historical Fiction",
    "Literary Fiction",
    "Young Adult",
    "Children's",
    "Graphic Novel",
    "Poetry",
    "Drama",
    "Short Stories",
    "Dystopian",
    "Adventure",
    "Crime",
    "Classics",
    "Biography",
    "Memoir",
    "Autobiography",
    "History",
    "Philosophy",
    "Psychology",
    "Science",
    "Nature",
    "Technology",
    "Business",
    "Economics",
    "Politics",
    "Self-Help",
    "Health",
    "Travel",
    "Cooking",
    "Art",
    "Music",
    "Religion",
    "True Crime",
    "Essays",
    "Humor",
    "Fiction",
    "Nonfiction",
)

_GENRE_SYNONYMS: dict[str, str] = {
    "sci-fi": "Science Fiction",
    "scifi": "Science Fiction",
    "sf": "Science Fiction",
    "juvenile-fiction": "Children's",
    "juvenile-literature": "Children's",
    "childrens-fiction": "Children's",
    "ya": "Young Adult",
    "young-adult-fiction": "Young Adult",
    "comics-graphic-novels": "Graphic Novel",
    "detective-and-mystery-stories": "Mystery",
    "biography-autobiography": "Biography",
    "self-help": "Self-Help",
    "body-mind-spirit": "Health",
    "social-science": "Politics",
    "literary-collections": "Essays",
    "non-fiction": "Nonfiction",
}

_CANONICAL_BY_SLUG = {crud.slugify_genre(name): name for name in CANONICAL_GENRES}


def _canonical_genre(raw: str) -> str | None:
    """Map a catalogue subject onto a browsable genre, or None if it is noise."""
    slug = crud.slugify_genre(raw)
    if not slug:
        return None
    if slug in _GENRE_SYNONYMS:
        return _GENRE_SYNONYMS[slug]
    if slug in _CANONICAL_BY_SLUG:
        return _CANONICAL_BY_SLUG[slug]
    words = slug.split("-")
    for canonical_slug, display in _CANONICAL_BY_SLUG.items():
        target = canonical_slug.split("-")
        span = len(target)
        for start in range(len(words) - span + 1):
            if words[start : start + span] == target:
                return display
    return None


@dataclass
class Candidate:
    """One search result offered when adding a book by title or ISBN."""

    title: str
    author: str = ""
    isbn13: str | None = None
    cover_url: str | None = None
    genres: list[str] = field(default_factory=list)
    number_of_pages: int | None = None
    year_published: int | None = None
    publisher: str | None = None
    source: str = ""


@dataclass
class Enrichment:
    genres: list[str]
    cover_url: str | None = None
    description: str | None = None
    page_count: int | None = None
    publisher: str | None = None
    source: str = ""


class _RunState:
    """Tracks which libraries have a bulk enrichment pass in flight."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: set[str] = set()

    def is_running(self, key: str) -> bool:
        with self._lock:
            return key in self._running

    def acquire(self, key: str) -> bool:
        with self._lock:
            if key in self._running:
                return False
            self._running.add(key)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._running.discard(key)


run_state = _RunState()


def _clean_genres(raw: list[str]) -> list[str]:
    """Turn catalogue categories/subjects into short, filterable genre names."""
    parts: list[str] = []
    for entry in raw:
        if not entry:
            continue
        for part in str(entry).split("/"):
            name = part.strip().strip(",").strip()
            if name and len(name) <= 60 and name.lower() not in _GENRE_STOPWORDS:
                parts.append(name)

    canonical: dict[str, str] = {}
    for name in parts:
        match = _canonical_genre(name)
        if match and match not in canonical:
            canonical[match] = match
    return list(canonical)[:MAX_GENRES_PER_BOOK]


def _https(url: str | None) -> str | None:
    """Normalise a catalogue cover URL, or reject it."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    if not url.startswith("https://"):
        logger.warning("Discarding cover URL with unexpected scheme: %.60s", url)
        return None
    return url


_SERIES_SUFFIX_RE = re.compile(
    r"\s*\((?:[^()]*(?:#\s*[\d.]+|\bbook\s+\d+|\bvol(?:ume)?\.?\s*\d+)[^()]*)\)\s*$",
    re.IGNORECASE,
)


def search_title(title: str) -> str:
    """Strip a trailing series marker so the title is searchable."""
    cleaned = title
    for _ in range(3):
        stripped = _SERIES_SUFFIX_RE.sub("", cleaned).strip()
        if stripped == cleaned:
            break
        cleaned = stripped
    return cleaned or title


def _google_queries(book: models.Book) -> list[str]:
    """The queries to try, in order: exact ISBN first, then title and author."""
    queries = []
    isbn = (book.isbn13 or book.isbn or "").strip()
    if isbn:
        queries.append(f"isbn:{isbn}")
    query = f'intitle:"{search_title(book.title)}"'
    if book.author:
        query += f' inauthor:"{book.author}"'
    queries.append(query)
    return queries


def fetch_google_books(client: httpx.Client, book: models.Book) -> Enrichment | None:
    settings = get_settings()

    info: dict | None = None
    for query in _google_queries(book):
        params: dict[str, str | int] = {"q": query, "maxResults": 1}
        if settings.google_books_api_key:
            params["key"] = settings.google_books_api_key

        response = client.get(GOOGLE_BOOKS_URL, params=params)
        response.raise_for_status()
        items = response.json().get("items") or []
        if items:
            info = items[0].get("volumeInfo", {})
            break
    if info is None:
        return None

    images = info.get("imageLinks") or {}
    return Enrichment(
        genres=_clean_genres(info.get("categories") or []),
        cover_url=_https(
            images.get("thumbnail")
            or images.get("smallThumbnail")
            or images.get("medium")
        ),
        description=(info.get("description") or None),
        page_count=info.get("pageCount"),
        publisher=info.get("publisher"),
        source="google_books",
    )


def _open_library_queries(book: models.Book) -> list[dict[str, str | int]]:
    """ISBN first, then title and author, see :func:`_google_queries`."""
    queries: list[dict[str, str | int]] = []
    isbn = (book.isbn13 or book.isbn or "").strip()
    if isbn:
        queries.append({"q": f"isbn:{isbn}", "limit": 1})
    by_title: dict[str, str | int] = {"title": search_title(book.title), "limit": 1}
    if book.author:
        by_title["author"] = book.author
    queries.append(by_title)
    return queries


def fetch_open_library(client: httpx.Client, book: models.Book) -> Enrichment | None:
    doc: dict | None = None
    for params in _open_library_queries(book):
        params["fields"] = (
            "key,title,author_name,subject,cover_i,number_of_pages_median,publisher"
        )
        response = client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
        response.raise_for_status()
        docs = response.json().get("docs") or []
        if docs:
            doc = docs[0]
            break
    if doc is None:
        return None

    cover_id = doc.get("cover_i")
    publishers = doc.get("publisher") or []
    return Enrichment(
        genres=_clean_genres((doc.get("subject") or [])[:80]),
        cover_url=(
            f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
        ),
        description=None,
        page_count=doc.get("number_of_pages_median"),
        publisher=publishers[0] if publishers else None,
        source="open_library",
    )


OPEN_LIBRARY_COVER = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"


def fetch_isbn_cover(client: httpx.Client, book: models.Book) -> str | None:
    """Resolve a cover straight from the ISBN, with no search step."""
    for raw in (book.isbn13, book.isbn):
        if not raw:
            continue
        isbn = re.sub(r"[^0-9Xx]", "", raw)
        if len(isbn) not in (10, 13):
            continue
        url = OPEN_LIBRARY_COVER.format(isbn=isbn)
        try:
            response = client.head(f"{url}?default=false", follow_redirects=True)
        except httpx.HTTPError as exc:
            logger.warning("ISBN cover lookup failed for %s: %s", isbn, _safe_error(exc))
            continue
        if response.status_code == 200:
            return url
    return None


def fetch_enrichment(
    client: httpx.Client,
    book: models.Book,
    rate_limited: set[str] | None = None,
) -> Enrichment | None:
    """Look a book up with the configured provider, falling back to the other."""
    settings = get_settings()
    if settings.enrichment_provider == "open_library":
        providers = (fetch_open_library, fetch_google_books)
    else:
        providers = (fetch_google_books, fetch_open_library)

    last_error: Exception | None = None
    for provider in providers:
        name = provider.__name__
        if rate_limited is not None and name in rate_limited:
            continue
        try:
            result = provider(client, book)
            if result and (result.genres or result.cover_url):
                if not result.cover_url:
                    result.cover_url = fetch_isbn_cover(client, book)
                return result
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 429 and rate_limited is not None:
                rate_limited.add(name)
                logger.warning(
                    "%s is rate limited; skipping it for the rest of this run. "
                    "Set GOOGLE_BOOKS_API_KEY to raise the quota.",
                    name,
                )
            else:
                logger.warning(
                    "Enrichment provider %s failed for %r: %s",
                    name,
                    book.title,
                    _safe_error(exc),
                )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Enrichment provider %s failed for %r: %s",
                name,
                book.title,
                _safe_error(exc),
            )
    cover = fetch_isbn_cover(client, book)
    if cover:
        return Enrichment(genres=[], cover_url=cover, source="open_library")

    if last_error is not None:
        raise last_error
    return None


def apply_enrichment(db: Session, book: models.Book, data: Enrichment) -> None:
    """Merge a lookup result onto a book without overwriting the user's data."""
    if data.genres:
        crud.merge_catalogue_genres(db, book, data.genres)
    if data.cover_url and not book.cover_url:
        book.cover_url = data.cover_url
    if data.description and not book.description:
        book.description = data.description[:4000]
    if data.page_count and not book.number_of_pages:
        book.number_of_pages = data.page_count
    if data.publisher and not book.publisher:
        book.publisher = data.publisher

    book.enrichment_status = "enriched"
    book.enrichment_source = data.source
    book.enriched_at = dt.datetime.now(dt.UTC)


def enrich_book(
    db: Session,
    book: models.Book,
    client: httpx.Client | None = None,
    rate_limited: set[str] | None = None,
) -> str:
    """Enrich one book."""
    settings = get_settings()
    owns_client = client is None
    client = client or httpx.Client(
        timeout=settings.enrichment_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        data = fetch_enrichment(client, book, rate_limited)
        if data is None:
            book.enrichment_status = "not_found"
            book.enriched_at = dt.datetime.now(dt.UTC)
        else:
            apply_enrichment(db, book, data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Enrichment failed for %r: %s", book.title, _safe_error(exc))
        book.enrichment_status = "failed"
    finally:
        if owns_client:
            client.close()
    return book.enrichment_status


def enrich_pending(
    session_factory,
    limit: int = 100,
    only_pending: bool = True,
    session_id: str | None = None,
) -> dict:
    """Background pass over books awaiting enrichment."""
    key = session_id if session_id is not None else "*"
    if not run_state.acquire(key):
        return {"status": "already_running", "processed": 0}

    settings = get_settings()
    processed = enriched = 0
    rate_limited: set[str] = set()
    try:
        with session_factory() as db:
            stmt = select(models.Book)
            if session_id is not None:
                stmt = stmt.where(models.Book.session_id == session_id)
            if only_pending:
                stmt = stmt.where(models.Book.enrichment_status == "pending")
            else:
                stmt = stmt.where(
                    models.Book.enrichment_status.in_(["pending", "failed", "not_found"])
                )
            books = list(db.scalars(stmt.order_by(models.Book.id).limit(limit)))

            with httpx.Client(
                timeout=settings.enrichment_timeout_seconds,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                for book in books:
                    status = enrich_book(
                        db, book, client=client, rate_limited=rate_limited
                    )
                    processed += 1
                    if status == "enriched":
                        enriched += 1
                    try:
                        db.commit()
                    except SQLAlchemyError:
                        db.rollback()
                        continue
                    if settings.enrichment_delay_seconds:
                        time.sleep(settings.enrichment_delay_seconds)
        logger.info(
            "Enrichment run finished: %s processed, %s enriched", processed, enriched
        )
        return {"status": "completed", "processed": processed, "enriched": enriched}
    finally:
        run_state.release(key)


_ISBN_RE = re.compile(r"^(?:\d[\d -]{8,16}[\dXx])$")


def looks_like_isbn(query: str) -> str | None:
    """Return the bare digits if the query is an ISBN-10/13, else None."""
    text = query.strip()
    if not _ISBN_RE.match(text):
        return None
    digits = re.sub(r"[^0-9Xx]", "", text)
    return digits if len(digits) in (10, 13) else None


def _search_google(client: httpx.Client, query: str, limit: int) -> list[Candidate]:
    settings = get_settings()
    isbn = looks_like_isbn(query)
    params: dict[str, str | int] = {
        "q": f"isbn:{isbn}" if isbn else query,
        "maxResults": limit,
        "printType": "books",
    }
    if settings.google_books_api_key:
        params["key"] = settings.google_books_api_key

    response = client.get(GOOGLE_BOOKS_URL, params=params)
    response.raise_for_status()

    results: list[Candidate] = []
    for item in response.json().get("items") or []:
        info = item.get("volumeInfo") or {}
        title = (info.get("title") or "").strip()
        if not title:
            continue
        images = info.get("imageLinks") or {}
        identifiers = {
            i.get("type"): i.get("identifier")
            for i in info.get("industryIdentifiers") or []
        }
        published = (info.get("publishedDate") or "")[:4]
        results.append(
            Candidate(
                title=normalise_typography(title)[:500],
                author=normalise_typography(", ".join(info.get("authors") or []))[:500],
                isbn13=identifiers.get("ISBN_13"),
                cover_url=_https(images.get("thumbnail") or images.get("smallThumbnail")),
                genres=_clean_genres(info.get("categories") or []),
                number_of_pages=info.get("pageCount"),
                year_published=int(published) if published.isdigit() else None,
                publisher=info.get("publisher"),
                source="google_books",
            )
        )
    return results


def _search_open_library(client: httpx.Client, query: str, limit: int) -> list[Candidate]:
    isbn = looks_like_isbn(query)
    params: dict[str, str | int] = {
        "q": f"isbn:{isbn}" if isbn else query,
        "limit": limit,
        "fields": (
            "title,author_name,isbn,cover_i,number_of_pages_median,"
            "first_publish_year,publisher,subject"
        ),
    }
    response = client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
    response.raise_for_status()

    results: list[Candidate] = []
    for doc in response.json().get("docs") or []:
        title = (doc.get("title") or "").strip()
        if not title:
            continue
        cover_id = doc.get("cover_i")
        isbns = doc.get("isbn") or []
        publishers = doc.get("publisher") or []
        results.append(
            Candidate(
                title=normalise_typography(title)[:500],
                author=normalise_typography(
                    ", ".join((doc.get("author_name") or [])[:3])
                )[:500],
                isbn13=next((i for i in isbns if len(i) == 13), None),
                cover_url=(
                    f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                    if cover_id
                    else None
                ),
                genres=_clean_genres((doc.get("subject") or [])[:80]),
                number_of_pages=doc.get("number_of_pages_median"),
                year_published=doc.get("first_publish_year"),
                publisher=publishers[0] if publishers else None,
                source="open_library",
            )
        )
    return results


def search_books(query: str, limit: int = 8) -> list[Candidate]:
    """Find candidate books by title or ISBN, for the add-a-book form."""
    query = query.strip()
    if len(query) < 2:
        return []

    settings = get_settings()
    providers = (
        (_search_open_library, _search_google)
        if settings.enrichment_provider == "open_library"
        else (_search_google, _search_open_library)
    )

    last_error: Exception | None = None
    any_provider_answered = False

    with httpx.Client(
        timeout=settings.enrichment_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for provider in providers:
            try:
                results = provider(client, query, limit)
                any_provider_answered = True
                if results:
                    return results
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Search via %s failed: %s", provider.__name__, _safe_error(exc)
                )

    if not any_provider_answered and last_error is not None:
        raise last_error
    return []
