"""Record when each library was last used, so abandoned ones can be deleted."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seeded_libraries",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_seeded_libraries_last_seen_at", "seeded_libraries", ["last_seen_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_seeded_libraries_last_seen_at", table_name="seeded_libraries")
    op.drop_column("seeded_libraries", "last_seen_at")
