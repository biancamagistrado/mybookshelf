"""Initial schema: books, genres, book_genres."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
    )

    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goodreads_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="manual"
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False, server_default=""),
        sa.Column("additional_authors", sa.Text(), nullable=True),
        sa.Column("isbn", sa.String(length=13), nullable=True),
        sa.Column("isbn13", sa.String(length=13), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("binding", sa.String(length=80), nullable=True),
        sa.Column("number_of_pages", sa.Integer(), nullable=True),
        sa.Column("year_published", sa.Integer(), nullable=True),
        sa.Column("original_publication_year", sa.Integer(), nullable=True),
        sa.Column(
            "exclusive_shelf",
            sa.String(length=80),
            nullable=False,
            server_default="to-read",
        ),
        sa.Column("bookshelves", sa.Text(), nullable=True),
        sa.Column("my_rating", sa.SmallInteger(), nullable=True),
        sa.Column("average_rating", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("date_read", sa.Date(), nullable=True),
        sa.Column("date_added", sa.Date(), nullable=True),
        sa.Column("read_count", sa.Integer(), nullable=True),
        sa.Column("owned_copies", sa.Integer(), nullable=True),
        sa.Column("my_review", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enrichment_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("enrichment_source", sa.String(length=40), nullable=True),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "my_rating IS NULL OR (my_rating BETWEEN 0 AND 5)", name="ck_books_my_rating"
        ),
        sa.CheckConstraint(
            "average_rating IS NULL OR (average_rating BETWEEN 0 AND 5)",
            name="ck_books_average_rating",
        ),
        sa.CheckConstraint(
            "enrichment_status IN ('pending','enriched','not_found','failed')",
            name="ck_books_enrichment_status",
        ),
    )

    op.create_table(
        "book_genres",
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "genre_id",
            sa.Integer(),
            sa.ForeignKey("genres.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="catalogue"
        ),
        sa.CheckConstraint(
            "source IN ('catalogue','manual')", name="ck_book_genres_source"
        ),
    )

    op.create_index("ix_books_exclusive_shelf", "books", ["exclusive_shelf"])
    op.create_index("ix_books_author", "books", ["author"])
    op.create_index("ix_books_date_read", "books", ["date_read"])
    op.create_index("ix_books_enrichment_status", "books", ["enrichment_status"])
    op.create_index("ix_books_isbn13", "books", ["isbn13"])
    op.create_index(
        "ix_books_title_author",
        "books",
        [sa.text("lower(title)"), sa.text("lower(author)")],
    )
    op.create_index("ix_book_genres_genre_id", "book_genres", ["genre_id"])


def downgrade() -> None:
    op.drop_table("book_genres")
    op.drop_table("books")
    op.drop_table("genres")
