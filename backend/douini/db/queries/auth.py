from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def create_user(conn: AsyncConnection, email: str, password_hash: str) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email, password_hash),
        )
        row = await cur.fetchone()
        return row[0]


async def get_user_by_email(conn: AsyncConnection, email: str) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, password_hash, email_verified, created_at, updated_at "
            "FROM users WHERE email = %s",
            (email,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "password_hash": row[2],
            "email_verified": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }


async def get_user_by_id(conn: AsyncConnection, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, password_hash, email_verified, created_at, updated_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "password_hash": row[2],
            "email_verified": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }


async def mark_email_verified(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET email_verified = TRUE, updated_at = NOW() WHERE id = %s",
            (user_id,),
        )


async def store_refresh_token(
    conn: AsyncConnection, user_id: int, jti: str, expires_at: Any
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO refresh_tokens (user_id, jti, expires_at) VALUES (%s, %s, %s)",
            (user_id, jti, expires_at),
        )


async def invalidate_refresh_token(conn: AsyncConnection, jti: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE refresh_tokens SET invalidated_at = NOW() WHERE jti = %s",
            (jti,),
        )


async def invalidate_all_refresh_tokens(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE refresh_tokens SET invalidated_at = NOW() WHERE user_id = %s",
            (user_id,),
        )


async def get_refresh_token(conn: AsyncConnection, jti: str) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, user_id, jti, expires_at, invalidated_at "
            "FROM refresh_tokens WHERE jti = %s",
            (jti,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "jti": row[2],
            "expires_at": row[3],
            "invalidated_at": row[4],
        }


async def store_email_verification_token(
    conn: AsyncConnection, user_id: int, token_hash: str, expires_at: Any
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO email_verifications (user_id, token_hash, expires_at) "
            "VALUES (%s, %s, %s)",
            (user_id, token_hash, expires_at),
        )


async def consume_email_verification_token(
    conn: AsyncConnection, token_hash: str
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, user_id, expires_at, used_at "
            "FROM email_verifications WHERE token_hash = %s",
            (token_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "expires_at": row[2],
            "used_at": row[3],
        }


async def mark_email_verification_used(conn: AsyncConnection, token_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE email_verifications SET used_at = NOW() WHERE id = %s",
            (token_id,),
        )


async def store_reset_token(
    conn: AsyncConnection, user_id: int, token_hash: str, expires_at: Any
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) "
            "VALUES (%s, %s, %s)",
            (user_id, token_hash, expires_at),
        )


async def consume_reset_token(
    conn: AsyncConnection, token_hash: str
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, user_id, expires_at, used_at "
            "FROM password_resets WHERE token_hash = %s",
            (token_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "expires_at": row[2],
            "used_at": row[3],
        }


async def mark_reset_used(conn: AsyncConnection, token_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE password_resets SET used_at = NOW() WHERE id = %s",
            (token_id,),
        )


async def update_password(conn: AsyncConnection, user_id: int, password_hash: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
            (password_hash, user_id),
        )
