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
            "SELECT id, email, password_hash, email_verified, pseudo, prenom, nom, created_at, updated_at "
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
            "pseudo": row[4],
            "prenom": row[5],
            "nom": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }


async def get_user_by_id(conn: AsyncConnection, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, password_hash, email_verified, pseudo, prenom, nom, created_at, updated_at "
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
            "pseudo": row[4],
            "prenom": row[5],
            "nom": row[6],
            "created_at": row[7],
            "updated_at": row[8],
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


async def delete_user(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM plans WHERE user_id = %s", (user_id,)
        )
        plan_ids = [r[0] for r in await cur.fetchall()]
        if plan_ids:
            await cur.execute(
                "DELETE FROM session_feedback WHERE plan_session_id IN "
                "(SELECT id FROM plan_sessions WHERE plan_id = ANY(%s))",
                (plan_ids,),
            )
            await cur.execute(
                "DELETE FROM plan_adjustments WHERE plan_id = ANY(%s)", (plan_ids,)
            )
            await cur.execute(
                "DELETE FROM plan_refresh_state WHERE plan_id = ANY(%s)", (plan_ids,)
            )
            await cur.execute(
                "DELETE FROM plan_sessions WHERE plan_id = ANY(%s)", (plan_ids,)
            )
        await cur.execute("DELETE FROM race_results WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM profile_vdot_history WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM plans WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM profile WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM email_verifications WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM release_reads WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM plan_celebrations WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM sync_notifications WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM garmin_tokens WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM user_preferences WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM auth_attempts WHERE key = %s", (str(user_id),))
        await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


async def reset_all_data(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM race_results WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM plan_celebrations WHERE user_id = %s", (user_id,))
        await cur.execute(
            "SELECT id FROM plans WHERE user_id = %s", (user_id,)
        )
        plan_ids = [r[0] for r in await cur.fetchall()]
        if plan_ids:
            await cur.execute(
                "DELETE FROM session_feedback WHERE plan_session_id IN "
                "(SELECT id FROM plan_sessions WHERE plan_id = ANY(%s))",
                (plan_ids,),
            )
            await cur.execute(
                "DELETE FROM plan_adjustments WHERE plan_id = ANY(%s)", (plan_ids,)
            )
            await cur.execute(
                "DELETE FROM plan_refresh_state WHERE plan_id = ANY(%s)", (plan_ids,)
            )
            await cur.execute(
                "DELETE FROM plan_sessions WHERE plan_id = ANY(%s)", (plan_ids,)
            )
        await cur.execute("DELETE FROM plans WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM profile_vdot_history WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM profile WHERE user_id = %s", (user_id,))
        await cur.execute("DELETE FROM sync_notifications WHERE user_id = %s", (user_id,))


async def record_auth_attempt(conn: AsyncConnection, key: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO auth_attempts (key) VALUES (%s)", (key,)
        )
        await cur.execute("DELETE FROM auth_attempts WHERE attempted_at < NOW() - INTERVAL '1 hour'")


async def count_auth_attempts(conn: AsyncConnection, key: str, window_seconds: int) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM auth_attempts WHERE key = %s AND attempted_at >= NOW() - (%s || ' seconds')::INTERVAL",
            (key, str(window_seconds)),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def update_user_identity(
    conn: AsyncConnection, user_id: int, pseudo: str | None, prenom: str | None, nom: str | None
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET pseudo = %s, prenom = %s, nom = %s, updated_at = NOW() WHERE id = %s",
            (pseudo, prenom, nom, user_id),
        )
