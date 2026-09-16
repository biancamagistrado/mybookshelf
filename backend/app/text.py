"""Typographic normalisation for imported text."""

from __future__ import annotations

_TYPOGRAPHIC = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "″": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
    }
)


def normalise_typography(value: str) -> str:
    """Replace curly punctuation with the ASCII equivalent."""
    return value.translate(_TYPOGRAPHIC).replace("…", "...")
