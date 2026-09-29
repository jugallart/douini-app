from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def upsert_garmin_token(conn: AsyncConnection, user_id: int, encrypted_token: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO garmin_tokens (user_id, encrypted_token) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET encrypted_token = EXCLUDED.encrypted_token, "
            "updated_at = NOW()",
            (user_id, encrypted_token),
        )


async def get_garmin_token(conn: AsyncConnection, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT user_id, encrypted_token, updated_at FROM garmin_tokens WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {"user_id": row[0], "encrypted_token": row[1], "updated_at": row[2]}


async def delete_garmin_token(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM garmin_tokens WHERE user_id = %s", (user_id,))


async def get_garmin_status(conn: AsyncConnection, user_id: int) -> dict[str, Any]:
    row = await get_garmin_token(conn, user_id)
    return {"connected": row is not None}
