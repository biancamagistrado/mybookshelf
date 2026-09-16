"""Tests for turning catalogue metadata into usable genres."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

from app import models
from app.services import enrichment


def test_open_library_thematic_subjects_are_filtered_to_real_genres():
    subjects = [
        "severe poverty",
        "starvation",
        "oppression",
        "effects of war",
        "Science fiction",
        "Young adult fiction",
    ]
    assert enrichment._clean_genres(subjects) == ["Science Fiction", "Young Adult"]


def test_google_hierarchical_categories_are_split():
    assert enrichment._clean_genres(["Fiction / Fantasy / Epic"]) == [
        "Fiction",
        "Fantasy",
    ]


def test_genre_matching_does_not_fire_on_substrings():
    assert enrichment._canonical_genre("Heartbreak") is None
    assert enrichment._canonical_genre("Particle physics") is None


def test_specific_genres_win_over_the_catch_alls():
    assert enrichment._canonical_genre("Fantasy fiction") == "Fantasy"
    assert enrichment._canonical_genre("Science fiction") == "Science Fiction"
    assert enrichment._canonical_genre("English fiction") == "Fiction"


def test_unrecognised_subjects_are_dropped():
    """Open Library subjects are a tag soup; only the vocabulary survives."""
    result = enrichment._clean_genres(
        [
            "Series:Crave",
            "Award:Hugo_Award=Novel",
            "Amyotrophic Lateral Sclerosis",
            "Romantsy",
            "Fantasy",
        ]
    )
    assert result == ["Fantasy"]


def test_a_book_with_no_recognised_genre_gets_none():
    assert enrichment._clean_genres(["Kansas City (Mo.)", "1893, Chicago"]) == []


def test_genres_are_capped():
    many = [f"Subject {n}" for n in range(50)]
    assert len(enrichment._clean_genres(many)) <= enrichment.MAX_GENRES_PER_BOOK


def test_http_thumbnails_are_upgraded_to_https():
    assert enrichment._https("http://books.google.com/x.jpg").startswith("https://")
    assert enrichment._https(None) is None


_REAL_CLIENT = httpx.Client


def _mock_client_factory(handler):
    """Stand in for httpx.Client so search_books talks to a mock transport."""

    def factory(*_args, **_kwargs):
        return _REAL_CLIENT(transport=httpx.MockTransport(handler))

    return factory


def _book(**kwargs) -> models.Book:
    return models.Book(title="Test Book", author="A. Writer", **kwargs)


def test_rate_limited_provider_is_skipped_for_the_rest_of_the_run():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if "googleapis" in request.url.host:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(
            200,
            json={"docs": [{"subject": ["Fantasy"], "cover_i": 1}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rate_limited: set[str] = set()

    enrichment.fetch_enrichment(client, _book(), rate_limited)
    assert "fetch_google_books" in rate_limited

    calls.clear()
    enrichment.fetch_enrichment(client, _book(), rate_limited)
    assert not any("googleapis" in host for host in calls)


def test_enrichment_falls_back_to_the_second_provider(db_session):
    def handler(request: httpx.Request) -> httpx.Response:
        if "googleapis" in request.url.host:
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={"docs": [{"subject": ["Science fiction"], "cover_i": 42}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    book = _book()
    db_session.add(book)
    db_session.flush()

    status = enrichment.enrich_book(db_session, book, client=client)

    assert status == "enriched"
    assert book.enrichment_source == "open_library"
    assert book.cover_url == "https://covers.openlibrary.org/b/id/42-M.jpg"
    assert [g.name for g in book.genres] == ["Science Fiction"]


def test_enrichment_never_overwrites_data_the_user_already_has(db_session):
    book = _book(cover_url="https://example.test/mine.jpg", publisher="My Publisher")
    db_session.add(book)
    db_session.flush()

    enrichment.apply_enrichment(
        db_session,
        book,
        enrichment.Enrichment(
            genres=["Fantasy"],
            cover_url="https://catalogue.test/theirs.jpg",
            publisher="Their Publisher",
            source="google_books",
        ),
    )

    assert book.cover_url == "https://example.test/mine.jpg"
    assert book.publisher == "My Publisher"
    assert [g.name for g in book.genres] == ["Fantasy"]


def test_no_match_marks_the_book_not_found(db_session):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    book = _book()
    db_session.add(book)
    db_session.flush()

    assert enrichment.enrich_book(db_session, book, client=client) == "not_found"


@pytest.mark.parametrize(
    ("isbn13", "expected"),
    [("9780439023481", "isbn:9780439023481"), (None, 'intitle:"Test Book"')],
)
def test_google_query_prefers_isbn(isbn13, expected):
    query = enrichment._google_queries(_book(isbn13=isbn13))[0]
    assert query.startswith(expected)


def test_reenrichment_replaces_stale_catalogue_genres(db_session):
    """A second lookup must not leave the first lookup's genres behind."""
    book = _book()
    db_session.add(book)
    db_session.flush()

    enrichment.apply_enrichment(
        db_session,
        book,
        enrichment.Enrichment(genres=["Horror", "Thriller"], source="open_library"),
    )
    assert {g.name for g in book.genres} == {"Horror", "Thriller"}

    enrichment.apply_enrichment(
        db_session,
        book,
        enrichment.Enrichment(genres=["Fantasy"], source="google_books"),
    )
    assert {g.name for g in book.genres} == {"Fantasy"}


def test_reenrichment_keeps_genres_the_user_entered(db_session):
    from app import crud

    book = _book()
    db_session.add(book)
    db_session.flush()
    crud.set_manual_genres(db_session, book, ["Comfort Reads"])

    enrichment.apply_enrichment(
        db_session,
        book,
        enrichment.Enrichment(genres=["Fantasy"], source="google_books"),
    )

    assert {g.name for g in book.genres} == {"Comfort Reads", "Fantasy"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://books.google.com/x.jpg", "https://books.google.com/x.jpg"),
        (
            "https://covers.openlibrary.org/b/id/1-M.jpg",
            "https://covers.openlibrary.org/b/id/1-M.jpg",
        ),
        ("javascript:alert(1)", None),
        ("data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", None),
        ("ftp://example.test/x.jpg", None),
        ("", None),
        (None, None),
    ],
)
def test_only_https_cover_urls_are_stored(raw, expected):
    assert enrichment._https(raw) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("9780441172719", "9780441172719"),
        ("978-0-441-17271-9", "9780441172719"),
        ("0441172717", "0441172717"),
        ("Project Hail Mary", None),
        ("2020", None),
    ],
)
def test_isbn_detection(query, expected):
    assert enrichment.looks_like_isbn(query) == expected


def test_search_returns_candidates_from_the_first_working_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        if "googleapis" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "volumeInfo": {
                                "title": "Piranesi",
                                "authors": ["Susanna Clarke"],
                                "categories": ["Fiction / Fantasy"],
                                "pageCount": 245,
                                "publishedDate": "2020-09-15",
                                "industryIdentifiers": [
                                    {"type": "ISBN_13", "identifier": "9781635575637"}
                                ],
                                "imageLinks": {"thumbnail": "http://example.test/c.jpg"},
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"docs": []})

    with mock.patch.object(enrichment.httpx, "Client", _mock_client_factory(handler)):
        results = enrichment.search_books("piranesi")

    assert len(results) == 1
    assert results[0].title == "Piranesi"
    assert results[0].isbn13 == "9781635575637"
    assert results[0].cover_url.startswith("https://")


def test_no_matches_is_an_empty_list_not_an_error():
    """A rate-limited provider must not turn a mistyped title into an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "googleapis" in request.url.host:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(200, json={"docs": []})

    with mock.patch.object(enrichment.httpx, "Client", _mock_client_factory(handler)):
        assert enrichment.search_books("zzqqxx not a real book") == []


def test_search_raises_only_when_every_provider_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with (
        mock.patch.object(enrichment.httpx, "Client", _mock_client_factory(handler)),
        pytest.raises(httpx.HTTPError),
    ):
        enrichment.search_books("anything")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Believe Me (Shatter Me, #6.5)", "Believe Me"),
        ("King's Cage (Red Queen, #3)", "King's Cage"),
        (
            "With Hearts of Flame: A Novel (Bloodwing Academy Book 4)",
            "With Hearts of Flame: A Novel",
        ),
        ("Half City (Harker Academy, #1)", "Half City"),
        ("1984 (Signet Classics)", "1984 (Signet Classics)"),
        ("Piranesi", "Piranesi"),
        ("(Series, #1)", "(Series, #1)"),
    ],
)
def test_series_suffix_is_stripped_before_searching(title, expected):
    assert enrichment.search_title(title) == expected


def test_isbn_cover_used_when_title_search_finds_nothing(monkeypatch):
    """A series suffix defeats the title search; the ISBN still resolves."""
    book = models.Book(title="Broken Dove (Silver Elite, #2)", isbn13="9780062825681")

    class _Response:
        status_code = 200

    class _Client:
        def head(self, url, **kwargs):
            assert "9780062825681" in url
            assert "default=false" in url
            return _Response()

    assert enrichment.fetch_isbn_cover(_Client(), book) == (
        "https://covers.openlibrary.org/b/isbn/9780062825681-M.jpg"
    )


def test_isbn_cover_skipped_when_open_library_has_none():
    book = models.Book(title="Obscure", isbn13="9780000000000")

    class _Response:
        status_code = 404

    class _Client:
        def head(self, url, **kwargs):
            return _Response()

    assert enrichment.fetch_isbn_cover(_Client(), book) is None


def test_isbn_cover_ignores_malformed_identifiers():
    book = models.Book(title="No ISBN", isbn="n/a", isbn13="")

    class _Client:
        def head(self, url, **kwargs):  # pragma: no cover
            raise AssertionError("should not probe a malformed ISBN")

    assert enrichment.fetch_isbn_cover(_Client(), book) is None


def test_isbn_miss_falls_through_to_title_and_author():
    """A recent book absent by ISBN is still found by name, the Cleopatra case."""
    book = models.Book(title="Cleopatra", author="Saara El-Arifi", isbn13="9780593875643")
    queries = enrichment._google_queries(book)
    assert queries[0] == "isbn:9780593875643"
    assert 'intitle:"Cleopatra"' in queries[1]
    assert 'inauthor:"Saara El-Arifi"' in queries[1]

    seen: list[str] = []

    class _Response:
        def __init__(self, items):
            self._items = items

        def raise_for_status(self):
            pass

        def json(self):
            return {"items": self._items}

    class _Client:
        def get(self, url, params=None, **kwargs):
            seen.append(params["q"])
            if params["q"].startswith("isbn:"):
                return _Response([])
            return _Response([{"volumeInfo": {"title": "Cleopatra"}}])

    result = enrichment.fetch_google_books(_Client(), book)
    assert result is not None
    assert len(seen) == 2, "the ISBN miss should be retried by title and author"


def test_open_library_also_falls_through():
    book = models.Book(title="Cleopatra", author="Saara El-Arifi", isbn13="9780593875643")
    queries = enrichment._open_library_queries(book)
    assert queries[0]["q"] == "isbn:9780593875643"
    assert queries[1]["title"] == "Cleopatra"
    assert queries[1]["author"] == "Saara El-Arifi"


def test_logged_errors_do_not_contain_the_api_key():
    """httpx puts the full URL in its errors, and Google's key is in the URL."""
    request = httpx.Request(
        "GET", "https://www.googleapis.com/books/v1/volumes?q=dune&key=AIzaSecret123"
    )
    try:
        httpx.Response(503, request=request).raise_for_status()
    except httpx.HTTPStatusError as exc:
        text = enrichment._safe_error(exc)

    assert "AIzaSecret123" not in text
    assert "key=[redacted]" in text
    assert "503" in text


def test_httpx_does_not_log_request_urls():
    import logging

    import app.main  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
