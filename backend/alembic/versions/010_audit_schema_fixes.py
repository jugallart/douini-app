"""audit schema fixes: auth_attempts, user identity, garmin_email, sync cols

Revision ID: 010
Revises: 009
"""
from __future__ import annotations

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- auth_attempts table (persistent rate limiting)
    op.execute(
        """
        CREATE TABLE auth_attempts (
            key VARCHAR(255) NOT NULL,
            attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_auth_attempts_key ON auth_attempts(key)")
    op.execute("CREATE INDEX idx_auth_attempts_time ON auth_attempts(attempted_at)")

    # -- users: identity columns
    op.execute("ALTER TABLE users ADD COLUMN pseudo VARCHAR(50)")
    op.execute("ALTER TABLE users ADD COLUMN prenom VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN nom VARCHAR(100)")

    # -- profile: garmin email
    op.execute("ALTER TABLE profile ADD COLUMN garmin_email VARCHAR(255)")

    # -- sync_notifications: dedup columns
    op.execute("ALTER TABLE sync_notifications ADD COLUMN session_week INTEGER")
    op.execute("ALTER TABLE sync_notifications ADD COLUMN session_day VARCHAR(10)")
    op.execute("ALTER TABLE sync_notifications ADD COLUMN garmin_activity_id VARCHAR(100)")
    op.execute(
        "CREATE UNIQUE INDEX idx_sync_notifications_garmin_activity "
        "ON sync_notifications(garmin_activity_id) WHERE garmin_activity_id IS NOT NULL"
    )

    # -- sync_leases: cursor tracking
    op.execute("ALTER TABLE sync_leases ADD COLUMN last_sync_at TIMESTAMPTZ")
    op.execute("ALTER TABLE sync_leases ADD COLUMN backoff_until TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE sync_leases DROP COLUMN IF EXISTS backoff_until")
    op.execute("ALTER TABLE sync_leases DROP COLUMN IF EXISTS last_sync_at")
    op.execute("DROP INDEX IF EXISTS idx_sync_notifications_garmin_activity")
    op.execute("ALTER TABLE sync_notifications DROP COLUMN IF EXISTS garmin_activity_id")
    op.execute("ALTER TABLE sync_notifications DROP COLUMN IF EXISTS session_day")
    op.execute("ALTER TABLE sync_notifications DROP COLUMN IF EXISTS session_week")
    op.execute("ALTER TABLE profile DROP COLUMN IF EXISTS garmin_email")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS nom")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS prenom")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS pseudo")
    op.execute("DROP TABLE IF EXISTS auth_attempts")
