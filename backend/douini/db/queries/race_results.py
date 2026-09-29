from __future__ import annotations

from datetime import date
from typing import Any

from psycopg import AsyncConnection


async def save_race_result(
    conn: AsyncConnection,
    *,
    user_id: int,
    distance: str,
    actual_time: str,
    race_date: date | None = None,
    derived_vdot: float | None = None,
    notes: str = "",
    location: str = "",
    plan_id: int | None = None,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO race_results (user_id, plan_id, distance, actual_time, "
            "race_date, derived_vdot, notes, location) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, plan_id, distance, actual_time, race_date,
             derived_vdot, notes, location),
        )
        row = await cur.fetchone()
        return row[0]


async def list_race_results(conn: AsyncConnection, user_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM race_results WHERE user_id = %s ORDER BY race_date DESC NULLS LAST, created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def delete_race_result(conn: AsyncConnection, result_id: int, user_id: int) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM race_results WHERE id = %s AND user_id = %s",
            (result_id, user_id),
        )
        return cur.rowcount > 0


async def get_latest_race_result(conn: AsyncConnection, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM race_results WHERE user_id = %s "
            "ORDER BY race_date DESC NULLS LAST LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))


async def record_vdot_entry(
    conn: AsyncConnection,
    *,
    user_id: int,
    vdot: float,
    source: str = "manual",
    plan_id: int | None = None,
    is_provisional: bool = False,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO profile_vdot_history (user_id, vdot, source, plan_id, is_provisional) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, vdot, source, plan_id, is_provisional),
        )


async def get_vdot_history(conn: AsyncConnection, user_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM profile_vdot_history WHERE user_id = %s ORDER BY recorded_at",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]
