"""plans and sessions

Revision ID: 004
Revises: 003
"""
from __future__ import annotations

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE plans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(200),
            distance VARCHAR(20),
            weeks INTEGER,
            vdot FLOAT,
            start_date DATE,
            goal_time VARCHAR(20),
            sessions_json JSONB DEFAULT '[]',
            settings_json JSONB DEFAULT '{}',
            status VARCHAR(20) DEFAULT 'active',
            race_date DATE,
            mode VARCHAR(20) DEFAULT 'prod',
            auto_pushed_week INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_plans_user ON plans(user_id)")
    op.execute(
        """
        CREATE TABLE plan_sessions (
            id SERIAL PRIMARY KEY,
            plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            week INTEGER NOT NULL,
            day VARCHAR(10) NOT NULL,
            scheduled_date DATE,
            type VARCHAR(30) DEFAULT 'easy',
            workout_name TEXT,
            distance_km FLOAT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            garmin_workout_id VARCHAR(100),
            garmin_activity_id VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(plan_id, week, day)
        )
        """
    )
    op.execute("CREATE INDEX idx_plan_sessions_plan ON plan_sessions(plan_id)")
    op.execute(
        """
        CREATE TABLE session_feedback (
            id SERIAL PRIMARY KEY,
            plan_session_id INTEGER NOT NULL REFERENCES plan_sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pace_rating VARCHAR(20),
            rpe INTEGER,
            fatigue_level VARCHAR(20),
            fatigue_duration VARCHAR(20),
            pain_level VARCHAR(20),
            pain_impact VARCHAR(20),
            pain_location TEXT,
            pain_onset TEXT,
            pain_evolution TEXT,
            temp_cause TEXT,
            difficulty_streak INTEGER DEFAULT 0,
            rules_version VARCHAR(20) DEFAULT '2026.1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX idx_session_feedback_ps ON session_feedback(plan_session_id)")
    op.execute(
        """
        CREATE TABLE plan_adjustments (
            id SERIAL PRIMARY KEY,
            plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            trigger_session_id INTEGER REFERENCES plan_sessions(id),
            status VARCHAR(20) DEFAULT 'pending',
            reason TEXT,
            confidence VARCHAR(20),
            horizon_weeks INTEGER,
            old_vdot FLOAT,
            new_vdot FLOAT,
            diff_json JSONB DEFAULT '[]',
            rules_version VARCHAR(20) DEFAULT '2026.1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX idx_plan_adjustments_plan ON plan_adjustments(plan_id)")
    op.execute(
        """
        CREATE TABLE plan_refresh_state (
            plan_id INTEGER PRIMARY KEY REFERENCES plans(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending',
            proposal_json JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE plan_celebrations (
            plan_id INTEGER PRIMARY KEY REFERENCES plans(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS plan_celebrations")
    op.execute("DROP TABLE IF EXISTS plan_refresh_state")
    op.execute("DROP TABLE IF EXISTS plan_adjustments")
    op.execute("DROP TABLE IF EXISTS session_feedback")
    op.execute("DROP TABLE IF EXISTS plan_sessions")
    op.execute("DROP TABLE IF EXISTS plans")
