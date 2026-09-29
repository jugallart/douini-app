"""profile table

Revision ID: 003
Revises: 002
"""
from __future__ import annotations

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE profile (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            vdot FLOAT,
            weekly_volume_km FLOAT DEFAULT 0,
            mileage_tolerance_km FLOAT DEFAULT 0,
            training_days_json JSONB DEFAULT '[]',
            target_weekly_km FLOAT,
            sessions_per_week INTEGER DEFAULT 4,
            race_distance VARCHAR(20),
            weeks INTEGER DEFAULT 12,
            target_time VARCHAR(20),
            experience VARCHAR(20) DEFAULT 'intermediaire',
            current_weekly_km FLOAT,
            current_longest_run FLOAT,
            long_run_day VARCHAR(10),
            preferred_days_json JSONB DEFAULT '[]',
            quality_sessions INTEGER,
            difficulty_level VARCHAR(20) DEFAULT 'balanced',
            volume_strategy VARCHAR(20) DEFAULT 'progressive',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile")
