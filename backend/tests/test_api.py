"""End-to-end tests over the HTTP API."""

from __future__ import annotations

from app.config import get_settings
from app.services import csv_import
from tests.conftest import GOODREADS_CSV


def seed(db_session):
    csv_import.import_csv(db_session, GOODREADS_CSV)


def test_upload_endpoint_reports_a_summary(client):
    response = client.post(
        "/api/import/goodreads?enrich=false",
        files={"file": ("library.csv", GOODREADS_CSV, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 3
    assert body["enrichment_queued"] is False


def test_non_csv_upload_is_rejected(client):
    response = client.post(
        "/api/import/goodreads",
        files={"file": ("library.txt", b"nope", "text/plain")},
    )
    assert response.status_code == 400


def test_list_books_filters_by_shelf(client, db_session):
    seed(db_session)
    response = client.get("/api/books", params={"shelf": "read"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "The Hunger Games"


def test_list_books_search_matches_author(client, db_session):
    seed(db_session)
    response = client.get("/api/books", params={"search": "tolkien"})
    assert response.json()["total"] == 1


def test_shelves_endpoint_counts_each_shelf(client, db_session):
    seed(db_session)
    shelves = {
        row["shelf"]: row["count"] for row in client.get("/api/books/shelves").json()
    }
    assert shelves == {"read": 1, "to-read": 1, "currently-reading": 1}


def test_manual_add_and_genre_filter(client):
    created = client.post(
        "/api/books",
        json={
            "title": "Piranesi",
            "author": "Susanna Clarke",
            "exclusive_shelf": "read",
            "my_rating": 5,
            "genres": ["Fantasy", "fantasy", "Literary Fiction"],
        },
    )
    assert created.status_code == 201, created.text
    book = created.json()
    assert len(book["genres"]) == 2

    filtered = client.get("/api/books", params={"genre": "fantasy"})
    assert filtered.json()["total"] == 1


def test_manual_add_rejects_duplicates(client):
    payload = {"title": "Piranesi", "author": "Susanna Clarke"}
    assert client.post("/api/books", json=payload).status_code == 201
    assert client.post("/api/books", json=payload).status_code == 409


def test_update_and_delete_book(client):
    book_id = client.post(
        "/api/books", json={"title": "Dune", "author": "Frank Herbert"}
    ).json()["id"]

    patched = client.patch(
        f"/api/books/{book_id}", json={"exclusive_shelf": "Read", "my_rating": 4}
    )
    assert patched.status_code == 200
    assert patched.json()["exclusive_shelf"] == "read"

    assert client.delete(f"/api/books/{book_id}").status_code == 204
    assert client.get(f"/api/books/{book_id}").status_code == 404


def test_stats_endpoint(client, db_session):
    seed(db_session)
    stats = client.get("/api/stats").json()
    assert stats["total_books"] == 3
    assert stats["books_read"] == 1
    assert stats["currently_reading"] == 1
    assert stats["to_read"] == 1
    assert stats["pages_read"] == 374
    assert {y["year"] for y in stats["books_per_year"]} == {2024, 2025}


def test_enrichment_status_endpoint(client, db_session):
    seed(db_session)
    body = client.get("/api/enrichment/status").json()
    assert body["pending"] == 3
    assert body["running"] is False


def test_editing_genres_replaces_the_whole_list(client):
    book_id = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "genres": ["Sci-Fi", "Epic"]},
    ).json()["id"]

    patched = client.patch(f"/api/books/{book_id}", json={"genres": ["Science Fiction"]})

    assert [g["name"] for g in patched.json()["genres"]] == ["Science Fiction"]


def test_genres_can_be_cleared(client):
    book_id = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "genres": ["Sci-Fi"]},
    ).json()["id"]

    patched = client.patch(f"/api/books/{book_id}", json={"genres": []})

    assert patched.json()["genres"] == []


def test_reset_is_hidden_unless_per_visitor_libraries_is_on(client):
    assert client.post("/api/sample-library/reset").status_code == 404


def test_personal_install_ignores_the_session_header(client):
    """With per-visitor libraries off there is one library, whatever header is sent."""
    client.post("/api/books", json={"title": "Dune", "author": "Frank Herbert"})

    for headers in ({}, {"X-Session-Id": "some-other-visitor-id"}):
        assert client.get("/api/books", headers=headers).json()["total"] == 1


def test_list_import_adds_books_from_typed_titles(client, monkeypatch):
    from app.routers import imports
    from app.services.enrichment import Candidate

    lookups: list[str] = []

    def fake_search(query: str, limit: int = 8):
        lookups.append(query)
        if "nonsense" in query:
            return []
        return [
            Candidate(
                title=query.title(),
                author="A. Writer",
                cover_url="https://covers.test/x.jpg",
                genres=["Fantasy"],
                source="google_books",
            )
        ]

    monkeypatch.setattr(imports.enrichment, "search_books", fake_search)

    response = client.post(
        "/api/import/list",
        json={
            "lines": ["piranesi", "dune", "nonsense book", ""],
            "exclusive_shelf": "read",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert body["not_found"] == ["nonsense book"]
    assert "" not in lookups

    books = client.get("/api/books", params={"shelf": "read"}).json()
    assert books["total"] == 2
    assert all(b["cover_url"] for b in books["items"])
    assert all(b["enrichment_status"] == "enriched" for b in books["items"])


def test_list_import_reports_books_already_on_the_shelf(client, monkeypatch):
    from app.routers import imports
    from app.services.enrichment import Candidate

    monkeypatch.setattr(
        imports.enrichment,
        "search_books",
        lambda query, limit=8: [Candidate(title="Dune", author="Frank Herbert")],
    )

    first = client.post("/api/import/list", json={"lines": ["dune"]})
    second = client.post("/api/import/list", json={"lines": ["dune"]})

    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert second.json()["already_on_shelf"] == ["Dune"]


def test_list_import_is_capped(client):
    response = client.post(
        "/api/import/list", json={"lines": [f"book {n}" for n in range(30)]}
    )
    assert response.status_code == 422


def test_search_matches_title_author_or_genre(client):
    client.post(
        "/api/books",
        json={
            "title": "Piranesi",
            "author": "Susanna Clarke",
            "genres": ["Fantasy", "Literary Fiction"],
        },
    )
    client.post(
        "/api/books",
        json={"title": "Atomic Habits", "author": "James Clear", "genres": ["Self-Help"]},
    )

    def titles(term: str) -> list[str]:
        page = client.get("/api/books", params={"search": term}).json()
        return [b["title"] for b in page["items"]]

    assert titles("piranesi") == ["Piranesi"]
    assert titles("clarke") == ["Piranesi"]
    assert titles("fantasy") == ["Piranesi"]
    assert titles("self-help") == ["Atomic Habits"]
    assert titles("zzz") == []


def test_clearing_the_library_deletes_every_book(client, db_session):
    seed(db_session)

    response = client.delete("/api/books")

    assert response.status_code == 200
    assert response.json() == {"deleted": 3}
    assert client.get("/api/books").json()["total"] == 0


def test_adding_a_book_to_a_full_library_is_refused(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_books_per_library", 1)

    assert client.post("/api/books", json={"title": "One"}).status_code == 201
    response = client.post("/api/books", json={"title": "Two"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Your library is full."


def test_csv_import_stops_at_the_book_cap(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_books_per_library", 2)

    body = client.post(
        "/api/import/goodreads?enrich=false",
        files={"file": ("library.csv", GOODREADS_CSV, "text/csv")},
    ).json()

    assert body["created"] == 2
    assert any("library is full" in warning for warning in body["warnings"])
    assert client.get("/api/books").json()["total"] == 2


def test_a_pasted_list_past_the_book_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_books_per_library", 1)

    response = client.post("/api/import/list", json={"lines": ["Dune", "Piranesi"]})

    assert response.status_code == 400
