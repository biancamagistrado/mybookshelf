"""ORM models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

book_genres = Table(
    "book_genres",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    Column("source", String(20), nullable=False, server_default="catalogue"),
)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    books: Mapped[list[Book]] = relationship(
        secondary=book_genres, back_populates="genres", viewonly=True
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", server_default="default"
    )
    goodreads_id: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False, default="")
    additional_authors: Mapped[str | None] = mapped_column(Text)
    isbn: Mapped[str | None] = mapped_column(String(13))
    isbn13: Mapped[str | None] = mapped_column(String(13))
    publisher: Mapped[str | None] = mapped_column(Text)
    binding: Mapped[str | None] = mapped_column(String(80))
    number_of_pages: Mapped[int | None] = mapped_column(Integer)
    year_published: Mapped[int | None] = mapped_column(Integer)
    original_publication_year: Mapped[int | None] = mapped_column(Integer)

    exclusive_shelf: Mapped[str] = mapped_column(
        String(80), nullable=False, default="to-read"
    )
    bookshelves: Mapped[str | None] = mapped_column(Text)
    my_rating: Mapped[int | None] = mapped_column(SmallInteger)
    average_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    date_read: Mapped[dt.date | None] = mapped_column(Date)
    date_added: Mapped[dt.date | None] = mapped_column(Date)
    read_count: Mapped[int | None] = mapped_column(Integer)
    owned_copies: Mapped[int | None] = mapped_column(Integer)
    my_review: Mapped[str | None] = mapped_column(Text)

    cover_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    enrichment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    enrichment_source: Mapped[str | None] = mapped_column(String(40))
    enriched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    genres: Mapped[list[Genre]] = relationship(
        secondary=book_genres,
        back_populates="books",
        lazy="selectin",
        viewonly=True,
        order_by="Genre.name",
    )


Index("ix_books_session_shelf", Book.session_id, Book.exclusive_shelf)
Index("ix_books_session_author", Book.session_id, Book.author)
Index("ix_books_session_date_read", Book.session_id, Book.date_read)
Index("ix_books_session_enrichment", Book.session_id, Book.enrichment_status)
Index(
    "ix_books_session_title_author",
    Book.session_id,
    func.lower(Book.title),
    func.lower(Book.author),
)
Index("ix_books_isbn13", Book.isbn13)
Book.__table__.append_constraint(
    UniqueConstraint("session_id", "goodreads_id", name="uq_books_session_goodreads")
)


class SeededLibrary(Base):
    """A library that has already received the sample books."""

    __tablename__ = "seeded_libraries"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seeded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
