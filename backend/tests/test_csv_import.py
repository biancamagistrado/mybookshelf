"""Tests for the Goodreads CSV parser, the format's quirks are the point."""

from __future__ import annotations

import datetime as dt

from app import models
from app.services import csv_import
from tests.conftest import GOODREADS_CSV


def test_strips_spreadsheet_isbn_wrapper():
    assert csv_import._clean('="0439023483"') == "0439023483"
    assert csv_import._clean('=""') is None
    assert csv_import._clean("  ") is None


def test_parses_goodreads_date_formats():
    assert csv_import._to_date("2024/03/14") == dt.date(2024, 3, 14)
    assert csv_import._to_date("2024-03-14") == dt.date(2024, 3, 14)
    assert csv_import._to_date("2024") == dt.date(2024, 1, 1)
    assert csv_import._to_date("") is None
    assert csv_import._to_date("not a date") is None


def test_shelf_is_normalised():
    assert csv_import._to_shelf("Currently Reading") == "currently-reading"
    assert csv_import._to_shelf(None) == "to-read"


def test_import_creates_books_and_skips_blank_rows(db_session):
    summary = csv_import.import_csv(db_session, GOODREADS_CSV)

    assert summary.created == 3
    assert summary.updated == 0
    assert summary.skipped == 1
    assert summary.total_rows == 4

    hunger_games = db_session.query(models.Book).filter_by(goodreads_id=2767052).one()
    assert hunger_games.isbn == "0439023483"
    assert hunger_games.isbn13 == "9780439023481"
    assert hunger_games.my_rating == 5
    assert hunger_games.date_read == dt.date(2024, 3, 14)
    assert hunger_games.exclusive_shelf == "read"
    assert hunger_games.enrichment_status == "pending"


def test_zero_rating_is_stored_as_null_not_zero_stars(db_session):
    csv_import.import_csv(db_session, GOODREADS_CSV)
    hobbit = db_session.query(models.Book).filter_by(goodreads_id=5907).one()
    assert hobbit.my_rating is None


def test_empty_isbn_sentinel_becomes_null(db_session):
    csv_import.import_csv(db_session, GOODREADS_CSV)
    enders = db_session.query(models.Book).filter_by(goodreads_id=375802).one()
    assert enders.isbn is None
    assert enders.isbn13 is None


def test_reimport_updates_instead_of_duplicating(db_session):
    csv_import.import_csv(db_session, GOODREADS_CSV)
    summary = csv_import.import_csv(db_session, GOODREADS_CSV)

    assert summary.created == 0
    assert summary.updated == 3
    assert db_session.query(models.Book).count() == 3


def test_reimport_preserves_enrichment(db_session):
    csv_import.import_csv(db_session, GOODREADS_CSV)
    book = db_session.query(models.Book).filter_by(goodreads_id=5907).one()
    book.cover_url = "https://example.test/cover.jpg"
    book.enrichment_status = "enriched"
    db_session.commit()

    csv_import.import_csv(db_session, GOODREADS_CSV)

    db_session.refresh(book)
    assert book.cover_url == "https://example.test/cover.jpg"
    assert book.enrichment_status == "enriched"


def test_csv_without_title_column_is_rejected(db_session):
    try:
        csv_import.import_csv(db_session, b"Foo,Bar\n1,2\n")
    except ValueError as exc:
        assert "Title" in str(exc)
    else:
        raise AssertionError("expected a ValueError")


def test_storygraph_export_is_read_in_full(db_session):
    """A non-Goodreads export must not import as titles with nothing else."""
    storygraph = (
        b"Title,Authors,ISBN/UID,Format,Read Status,Date Added,Last Date Read,Star Rating\n"
        b"Piranesi,Susanna Clarke,9781635575637,Hardcover,read,2026/01/02,2026/03/14,5\n"
    )
    summary = csv_import.import_csv(db_session, storygraph)
    book = db_session.query(models.Book).one()

    assert summary.created == 1
    assert summary.warnings == []
    assert book.author == "Susanna Clarke"
    assert book.isbn13 == "9781635575637"
    assert book.exclusive_shelf == "read"
    assert book.date_read == dt.date(2026, 3, 14)


def test_semicolon_separated_file_is_parsed(db_session):
    """European Excel writes semicolons; assuming commas makes one long column."""
    content = b"Title;Author;Exclusive Shelf\nDune;Frank Herbert;read\n"
    summary = csv_import.import_csv(db_session, content)

    assert summary.created == 1
    assert db_session.query(models.Book).one().author == "Frank Herbert"


def test_unrecognised_columns_are_reported_not_silently_dropped(db_session):
    summary = csv_import.import_csv(db_session, b"Title,Pages\nSome Book,300\n")

    assert summary.created == 1
    assert len(summary.warnings) == 1
    assert "author" in summary.warnings[0]
