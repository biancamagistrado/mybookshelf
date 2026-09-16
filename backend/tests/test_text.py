"""Typographic normalisation of imported titles and authors."""

from app.schemas import BookCreate
from app.services.csv_import import _clean
from app.text import normalise_typography


def test_curly_apostrophe_becomes_straight():
    assert normalise_typography("Ender’s Game (Ender's Saga, #1)") == (
        "Ender's Game (Ender's Saga, #1)"
    )


def test_curly_doubles_dashes_and_ellipsis():
    assert normalise_typography("“Quoted” — wait…") == '"Quoted" - wait...'


def test_plain_text_is_untouched():
    assert normalise_typography("The Hobbit") == "The Hobbit"


def test_csv_clean_normalises_after_unwrapping():
    assert _clean('="Ender’s Game"') == "Ender's Game"


def test_manual_add_normalises_title_and_author():
    book = BookCreate(title="Ender’s Game", author="Orson Scott Card’s Estate")
    assert book.title == "Ender's Game"
    assert book.author == "Orson Scott Card's Estate"
