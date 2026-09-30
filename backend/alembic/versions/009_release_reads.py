"""release reads tracking

Revision ID: 009
Revises: 008
"""
from __future__ import annotations

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE release_reads (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            release_version VARCHAR(20) NOT NULL,
            read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, release_version)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS release_reads")
