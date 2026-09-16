"""Scope books to a library so visitors do not share one shelf."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column(
            "session_id",
            sa.String(length=64),
            nullable=False,
            server_default="default",
        ),
    )

    op.drop_constraint("books_goodreads_id_key", "books", type_="unique")
    op.create_unique_constraint(
        "uq_books_session_goodreads", "books", ["session_id", "goodreads_id"]
    )

    op.drop_index("ix_books_exclusive_shelf", table_name="books")
    op.drop_index("ix_books_author", table_name="books")
    op.drop_index("ix_books_date_read", table_name="books")
    op.drop_index("ix_books_enrichment_status", table_name="books")
    op.drop_index("ix_books_title_author", table_name="books")

    op.create_index("ix_books_session_shelf", "books", ["session_id", "exclusive_shelf"])
    op.create_index("ix_books_session_author", "books", ["session_id", "author"])
    op.create_index("ix_books_session_date_read", "books", ["session_id", "date_read"])
    op.create_index(
        "ix_books_session_enrichment", "books", ["session_id", "enrichment_status"]
    )
    op.create_index(
        "ix_books_session_title_author",
        "books",
        ["session_id", sa.text("lower(title)"), sa.text("lower(author)")],
    )


def downgrade() -> None:
    op.drop_index("ix_books_session_title_author", table_name="books")
    op.drop_index("ix_books_session_enrichment", table_name="books")
    op.drop_index("ix_books_session_date_read", table_name="books")
    op.drop_index("ix_books_session_author", table_name="books")
    op.drop_index("ix_books_session_shelf", table_name="books")

    op.create_index("ix_books_exclusive_shelf", "books", ["exclusive_shelf"])
    op.create_index("ix_books_author", "books", ["author"])
    op.create_index("ix_books_date_read", "books", ["date_read"])
    op.create_index("ix_books_enrichment_status", "books", ["enrichment_status"])
    op.create_index(
        "ix_books_title_author",
        "books",
        [sa.text("lower(title)"), sa.text("lower(author)")],
    )

    op.drop_constraint("uq_books_session_goodreads", "books", type_="unique")
    op.create_unique_constraint("books_goodreads_id_key", "books", ["goodreads_id"])
    op.drop_column("books", "session_id")
