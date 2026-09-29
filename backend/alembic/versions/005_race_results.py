"""race results and vdot history

Revision ID: 005
Revises: 004
"""
from __future__ import annotations

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE race_results (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
            distance VARCHAR(20),
            actual_time VARCHAR(20),
            race_date DATE,
            derived_vdot FLOAT,
            notes TEXT,
            location VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_race_results_user ON race_results(user_id)")
    op.execute(
        """
        CREATE TABLE profile_vdot_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            vdot FLOAT NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source VARCHAR(50),
            plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
            is_provisional BOOLEAN DEFAULT FALSE
        )
        """
    )
    op.execute("CREATE INDEX idx_profile_vdot_history_user ON profile_vdot_history(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile_vdot_history")
    op.execute("DROP TABLE IF EXISTS race_results")
