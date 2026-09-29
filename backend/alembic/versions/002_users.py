"""users and auth tables

Revision ID: 002
Revises: 001
Create Date: 2026-09-29
"""
from __future__ import annotations

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE email_verifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE password_resets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            jti VARCHAR(36) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            invalidated_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX idx_email_verifications_token ON email_verifications(token_hash)")
    op.execute("CREATE INDEX idx_password_resets_token ON password_resets(token_hash)")
    op.execute("CREATE INDEX idx_refresh_tokens_jti ON refresh_tokens(jti)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS password_resets")
    op.execute("DROP TABLE IF EXISTS email_verifications")
    op.execute("DROP TABLE IF EXISTS users")
