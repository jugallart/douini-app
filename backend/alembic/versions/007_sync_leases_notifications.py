"""sync leases and notifications

Revision ID: 007
Revises: 006
"""
from __future__ import annotations

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sync_leases (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sync_notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id INTEGER REFERENCES plans(id) ON DELETE CASCADE,
            session_id INTEGER REFERENCES plan_sessions(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            type VARCHAR(50) NOT NULL DEFAULT 'sync_match',
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_sync_notifications_user_unread "
        "ON sync_notifications(user_id) WHERE read_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sync_notifications")
    op.execute("DROP TABLE IF EXISTS sync_leases")
