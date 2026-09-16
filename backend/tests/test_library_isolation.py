"""The property a shared deployment depends on: visitors cannot touch each other."""

from __future__ import annotations

import datetime as dt

import pytest

from app import models
from app.config import get_settings

ALICE = {"X-Session-Id": "alice-aaaaaaaaaaaaaaaaaaaa"}
BOB = {"X-Session-Id": "bob-bbbbbbbbbbbbbbbbbbbbbb"}
CAROL = {"X-Session-Id": "carol-cccccccccccccccccccc"}


@pytest.fixture
def visitor_client(client, monkeypatch):
    """A client with per-visitor libraries on, seeding stubbed to one book."""
    from app.services import sample_library

    monkeypatch.setattr(get_settings(), "per_visitor_libraries", True)
    monkeypatch.setattr(
        sample_library,
        "seed_books",
        lambda: [
            {
                "title": "Seeded Book",
                "author": "Seed Author",
                "exclusive_shelf": "read",
                "number_of_pages": 100,
                "my_rating": 4,
                "date_read": "2026-01-15",
                "genres": ["Fantasy"],
            }
        ],
    )
    return client


def test_each_visitor_gets_their_own_seeded_library(visitor_client):
    alice = visitor_client.get("/api/books", headers=ALICE).json()
    bob = visitor_client.get("/api/books", headers=BOB).json()

    assert alice["total"] == 1
    assert bob["total"] == 1
    assert alice["items"][0]["id"] != bob["items"][0]["id"]


def test_one_visitor_cannot_read_anothers_book(visitor_client):
    alice_book = visitor_client.get("/api/books", headers=ALICE).json()["items"][0]

    assert (
        visitor_client.get(f"/api/books/{alice_book['id']}", headers=ALICE).status_code
        == 200
    )
    assert (
        visitor_client.get(f"/api/books/{alice_book['id']}", headers=BOB).status_code
        == 404
    )


def test_one_visitor_cannot_delete_or_edit_anothers_book(visitor_client):
    alice_book = visitor_client.get("/api/books", headers=ALICE).json()["items"][0]

    assert (
        visitor_client.delete(f"/api/books/{alice_book['id']}", headers=BOB).status_code
        == 404
    )
    assert (
        visitor_client.patch(
            f"/api/books/{alice_book['id']}", json={"my_rating": 1}, headers=BOB
        ).status_code
        == 404
    )
    assert (
        visitor_client.get(f"/api/books/{alice_book['id']}", headers=ALICE).status_code
        == 200
    )


def test_adding_a_book_does_not_appear_in_another_library(visitor_client):
    visitor_client.post(
        "/api/books",
        json={"title": "Alice Only", "author": "A", "genres": ["Poetry"]},
        headers=ALICE,
    )

    bob_titles = [
        b["title"] for b in visitor_client.get("/api/books", headers=BOB).json()["items"]
    ]
    assert "Alice Only" not in bob_titles


def test_facets_and_stats_are_per_library(visitor_client):
    visitor_client.post(
        "/api/books",
        json={
            "title": "Alice Only",
            "author": "Alice Author",
            "exclusive_shelf": "read",
            "genres": ["Poetry"],
        },
        headers=ALICE,
    )

    for path in ("/api/books/authors", "/api/books/genres"):
        alice_values = {
            f["value"] for f in visitor_client.get(path, headers=ALICE).json()
        }
        bob_values = {f["value"] for f in visitor_client.get(path, headers=BOB).json()}
        assert alice_values - bob_values, f"{path} leaked nothing unique to Alice"
        assert "Alice Author" not in bob_values
        assert "Poetry" not in bob_values

    assert visitor_client.get("/api/stats", headers=ALICE).json()["total_books"] == 2
    assert visitor_client.get("/api/stats", headers=BOB).json()["total_books"] == 1

    alice_shelves = visitor_client.get("/api/books/shelves", headers=ALICE).json()
    assert sum(row["count"] for row in alice_shelves) == 2


def test_importing_a_csv_only_affects_that_visitor(visitor_client):
    from tests.conftest import GOODREADS_CSV

    visitor_client.post(
        "/api/import/goodreads?enrich=false",
        files={"file": ("library.csv", GOODREADS_CSV, "text/csv")},
        headers=ALICE,
    )

    assert visitor_client.get("/api/books", headers=ALICE).json()["total"] == 4
    assert visitor_client.get("/api/books", headers=BOB).json()["total"] == 1


def test_deleting_every_book_leaves_the_shelf_empty(visitor_client):
    """The sample books are given once."""
    for book in visitor_client.get("/api/books", headers=ALICE).json()["items"]:
        visitor_client.delete(f"/api/books/{book['id']}", headers=ALICE)

    assert visitor_client.get("/api/books", headers=ALICE).json()["total"] == 0


def test_clearing_a_shelf_only_affects_that_visitor(visitor_client):
    visitor_client.get("/api/books", headers=BOB)

    response = visitor_client.delete("/api/books", headers=ALICE)

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    assert visitor_client.get("/api/books", headers=ALICE).json()["total"] == 0
    assert visitor_client.get("/api/books", headers=BOB).json()["total"] == 1


def test_a_cleared_shelf_stays_empty_and_takes_new_books(visitor_client):
    visitor_client.delete("/api/books", headers=ALICE)
    visitor_client.post("/api/books", json={"title": "My Own Book"}, headers=ALICE)

    books = visitor_client.get("/api/books", headers=ALICE).json()
    assert [book["title"] for book in books["items"]] == ["My Own Book"]


def test_reset_brings_the_sample_books_back_after_a_clear(visitor_client):
    visitor_client.delete("/api/books", headers=ALICE)

    assert (
        visitor_client.post("/api/sample-library/reset", headers=ALICE).status_code == 202
    )
    assert visitor_client.get("/api/books", headers=ALICE).json()["total"] == 1


def test_a_malformed_session_id_is_rejected(visitor_client):
    assert (
        visitor_client.get("/api/books", headers={"X-Session-Id": "short"}).status_code
        == 400
    )
    assert (
        visitor_client.get("/api/books", headers={"X-Session-Id": "bad id!"}).status_code
        == 400
    )


def _library(db_session, visitor):
    return db_session.get(models.SeededLibrary, visitor["X-Session-Id"])


def test_libraries_idle_too_long_are_deleted(visitor_client, db_session):
    visitor_client.get("/api/books", headers=ALICE)
    visitor_client.get("/api/books", headers=BOB)
    _library(db_session, ALICE).last_seen_at = dt.datetime.now(dt.UTC) - dt.timedelta(
        days=31
    )
    db_session.commit()

    visitor_client.get("/api/books", headers=CAROL)

    assert _library(db_session, ALICE) is None
    assert _library(db_session, BOB) is not None
    assert not db_session.scalars(
        models.Book.__table__.select().where(
            models.Book.session_id == ALICE["X-Session-Id"]
        )
    ).first()


def test_past_the_cap_the_least_recently_used_library_goes(
    visitor_client, db_session, monkeypatch
):
    monkeypatch.setattr(get_settings(), "max_libraries", 2)
    visitor_client.get("/api/books", headers=ALICE)
    visitor_client.get("/api/books", headers=BOB)
    _library(db_session, ALICE).last_seen_at = dt.datetime.now(dt.UTC) - dt.timedelta(
        hours=2
    )
    db_session.commit()

    visitor_client.get("/api/books", headers=CAROL)

    assert _library(db_session, ALICE) is None
    assert _library(db_session, BOB) is not None
    assert _library(db_session, CAROL) is not None


def test_a_visit_refreshes_when_the_library_was_last_used(visitor_client, db_session):
    visitor_client.get("/api/books", headers=ALICE)
    stale = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    _library(db_session, ALICE).last_seen_at = stale
    db_session.commit()

    visitor_client.get("/api/books", headers=ALICE)

    assert _library(db_session, ALICE).last_seen_at > stale + dt.timedelta(hours=1)
