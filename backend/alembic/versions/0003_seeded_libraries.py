"""Remember which libraries have been given the sample books."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seeded_libraries",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "seeded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO seeded_libraries (session_id) SELECT DISTINCT session_id FROM books"
    )


def downgrade() -> None:
    op.drop_table("seeded_libraries")
