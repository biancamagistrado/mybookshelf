"""Pydantic request/response models."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.text import normalise_typography


class GenreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=500)
    additional_authors: str | None = None
    isbn: str | None = Field(default=None, max_length=13)
    isbn13: str | None = Field(default=None, max_length=13)
    publisher: str | None = None
    binding: str | None = Field(default=None, max_length=80)
    number_of_pages: int | None = Field(default=None, ge=0, le=100_000)
    year_published: int | None = None
    original_publication_year: int | None = None
    exclusive_shelf: str = Field(default="to-read", max_length=80)
    bookshelves: str | None = None
    my_rating: int | None = Field(default=None, ge=0, le=5)
    average_rating: float | None = Field(default=None, ge=0, le=5)
    date_read: dt.date | None = None
    date_added: dt.date | None = None
    read_count: int | None = Field(default=None, ge=0)
    owned_copies: int | None = Field(default=None, ge=0)
    my_review: str | None = None
    cover_url: str | None = None
    description: str | None = None

    @field_validator("exclusive_shelf")
    @classmethod
    def normalise_shelf(cls, v: str) -> str:
        v = (v or "").strip().lower().replace(" ", "-")
        return v or "to-read"

    @field_validator("title", "author", "publisher")
    @classmethod
    def normalise_text(cls, v: str | None) -> str | None:
        return normalise_typography(v) if v else v


class BookCreate(BookBase):
    """Payload for the manual "add a book" form."""

    genres: list[str] = Field(default_factory=list, max_length=20)


class BookUpdate(BaseModel):
    """Partial update, every field optional."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    isbn: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    number_of_pages: int | None = Field(default=None, ge=0, le=100_000)
    exclusive_shelf: str | None = Field(default=None, max_length=80)
    my_rating: int | None = Field(default=None, ge=0, le=5)
    date_read: dt.date | None = None
    my_review: str | None = None
    cover_url: str | None = None
    description: str | None = None
    genres: list[str] | None = Field(default=None, max_length=20)

    @field_validator("exclusive_shelf")
    @classmethod
    def normalise_shelf(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower().replace(" ", "-") or None

    @field_validator("title", "author", "publisher")
    @classmethod
    def normalise_text(cls, v: str | None) -> str | None:
        return normalise_typography(v) if v else v


class BookOut(BookBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goodreads_id: int | None = None
    source: str
    enrichment_status: str
    enrichment_source: str | None = None
    enriched_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    genres: list[GenreOut] = Field(default_factory=list)


class BookSuggestion(BaseModel):
    """A catalogue search result offered in the add-a-book form."""

    title: str
    author: str = ""
    isbn13: str | None = None
    cover_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    number_of_pages: int | None = None
    year_published: int | None = None
    publisher: str | None = None
    source: str = ""


class BookPage(BaseModel):
    """A page of books plus the total matching the current filters."""

    items: list[BookOut]
    total: int
    limit: int
    offset: int


class ShelfCount(BaseModel):
    shelf: str
    count: int


class FacetCount(BaseModel):
    """A filter facet value and how many books carry it."""

    value: str
    count: int


class ImportResult(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    enrichment_queued: bool = False


class ListImportRequest(BaseModel):
    """Import from typed-in titles or ISBNs, one per line."""

    lines: list[str] = Field(min_length=1, max_length=25)
    exclusive_shelf: str = Field(default="to-read", max_length=80)

    @field_validator("exclusive_shelf")
    @classmethod
    def normalise_shelf(cls, v: str) -> str:
        return (v or "").strip().lower().replace(" ", "-") or "to-read"


class ListImportResult(BaseModel):
    created: int
    already_on_shelf: list[str] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)


class EnrichmentRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    only_pending: bool = True


class EnrichmentStatus(BaseModel):
    pending: int
    enriched: int
    not_found: int
    failed: int
    running: bool


class TopItem(BaseModel):
    name: str
    count: int


class RatingBucket(BaseModel):
    rating: int
    count: int


class YearCount(BaseModel):
    year: int
    count: int


class StatsOut(BaseModel):
    total_books: int
    books_read: int
    books_read_this_year: int
    currently_reading: int
    to_read: int
    pages_read: int
    average_rating_given: float | None
    top_genres: list[TopItem]
    top_authors: list[TopItem]
    books_per_year: list[YearCount]
    rating_distribution: list[RatingBucket]


SortField = Literal[
    "title", "author", "date_read", "date_added", "my_rating", "average_rating"
]
