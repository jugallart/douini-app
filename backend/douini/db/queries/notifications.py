from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def create_sync_notification(
    conn: AsyncConnection,
    user_id: int,
    plan_id: int,
    session_id: int | None,
    message: str,
    type: str = "sync_match",
    session_week: int | None = None,
    session_day: str | None = None,
    garmin_activity_id: str | None = None,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO sync_notifications "
            "(user_id, plan_id, session_id, message, type, session_week, session_day, garmin_activity_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, plan_id, session_id, message, type, session_week, session_day, garmin_activity_id),
        )
        return await cur.fetchone()  # type: ignore[return-value]


async def get_user_notifications(
    conn: AsyncConnection, user_id: int, limit: int = 50
) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, plan_id, session_id, message, type, read_at, created_at, "
            "session_week, session_day, garmin_activity_id "
            "FROM sync_notifications WHERE user_id = %s "
            "ORDER BY read_at IS NULL DESC, created_at DESC LIMIT %s",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": r[0],
                "plan_id": r[1],
                "session_id": r[2],
                "message": r[3],
                "type": r[4],
                "read_at": r[5],
                "created_at": r[6],
                "session_week": r[7],
                "session_day": r[8],
                "garmin_activity_id": r[9],
            }
            for r in rows
        ]


async def mark_notification_read(conn: AsyncConnection, notif_id: int, user_id: int) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE sync_notifications SET read_at = NOW() "
            "WHERE id = %s AND user_id = %s AND read_at IS NULL",
            (notif_id, user_id),
        )
        return cur.rowcount > 0


async def mark_all_read(conn: AsyncConnection, user_id: int) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE sync_notifications SET read_at = NOW() "
            "WHERE user_id = %s AND read_at IS NULL",
            (user_id,),
        )
        return cur.rowcount
