from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from psycopg import AsyncConnection

from douini.domain.models import DAY_OFFSET


async def save_plan(
    conn: AsyncConnection,
    *,
    user_id: int,
    name: str,
    distance: str,
    weeks: int,
    vdot: float,
    start_date: date | None,
    goal_time: str | None,
    sessions_json: str,
    settings_json: str,
    race_date: date | None = None,
    mode: str = "prod",
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO plans (user_id, name, distance, weeks, vdot, start_date, "
            "goal_time, sessions_json, settings_json, race_date, mode) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, name, distance, weeks, vdot, start_date, goal_time,
             sessions_json, settings_json, race_date, mode),
        )
        row = await cur.fetchone()
        plan_id = row[0]

    await _materialize_plan_sessions(conn, plan_id, sessions_json, start_date)
    return plan_id


async def _materialize_plan_sessions(
    conn: AsyncConnection, plan_id: int, sessions_json: str, start_date: date | None
) -> None:
    sessions = json.loads(sessions_json)
    async with conn.cursor() as cur:
        for s in sessions:
            week = s["week"]
            day = s["day"]
            if start_date:
                sd = start_date + timedelta(weeks=week - 1, days=DAY_OFFSET.get(day, 0))
            else:
                sd = None
            await cur.execute(
                "INSERT INTO plan_sessions (plan_id, week, day, scheduled_date, type, "
                "workout_name, distance_km, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (plan_id, week, day) DO UPDATE SET "
                "type = EXCLUDED.type, workout_name = EXCLUDED.workout_name, "
                "distance_km = EXCLUDED.distance_km, updated_at = NOW()",
                (plan_id, week, day, sd, s.get("type", "easy"),
                 s.get("workout", ""), s.get("distance_km", 0),
                 s.get("status", "pending")),
            )


async def list_plans(conn: AsyncConnection, user_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, name, distance, weeks, vdot, start_date, goal_time, "
            "status, created_at FROM plans WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def get_plan(conn: AsyncConnection, plan_id: int, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plans WHERE id = %s AND user_id = %s",
            (plan_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        d = dict(zip(cols, row))
        sj = d.get("sessions_json", [])
        d["sessions_json"] = json.loads(sj) if isinstance(sj, str) else (sj or [])
        st = d.get("settings_json", {})
        d["settings_json"] = json.loads(st) if isinstance(st, str) else (st or {})
        return d


async def delete_plan(conn: AsyncConnection, plan_id: int, user_id: int) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM plans WHERE id = %s AND user_id = %s",
            (plan_id, user_id),
        )
        return cur.rowcount > 0


async def update_plan_sessions_json(
    conn: AsyncConnection, plan_id: int, sessions_json: str
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plans SET sessions_json = %s WHERE id = %s",
            (sessions_json, plan_id),
        )


async def update_plan_vdot(conn: AsyncConnection, plan_id: int, vdot: float) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plans SET vdot = %s WHERE id = %s", (vdot, plan_id)
        )


async def is_plan_complete(conn: AsyncConnection, plan_id: int) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM plan_sessions WHERE plan_id = %s AND status = 'pending'",
            (plan_id,),
        )
        row = await cur.fetchone()
        return row[0] == 0


async def get_completed_sessions(conn: AsyncConnection, plan_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_sessions WHERE plan_id = %s AND status = 'completed' "
            "ORDER BY week, day",
            (plan_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def get_plan_sessions(conn: AsyncConnection, plan_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_sessions WHERE plan_id = %s ORDER BY week, day",
            (plan_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def get_plan_session_by_id(
    conn: AsyncConnection, session_id: int
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_sessions WHERE id = %s", (session_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))


async def get_user_plans(conn: AsyncConnection, user_id: int) -> list[dict[str, Any]]:
    return await list_plans(conn, user_id)


async def locked_plan_session_keys(conn: AsyncConnection, plan_id: int) -> set[tuple[int, str]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT week, day FROM plan_sessions WHERE plan_id = %s AND status IN ('completed', 'skipped')",
            (plan_id,),
        )
        rows = await cur.fetchall()
        return {(r[0], r[1]) for r in rows}


async def save_plan_adjustment(
    conn: AsyncConnection,
    *,
    plan_id: int,
    trigger_session_id: int,
    status: str,
    reason: str,
    confidence: str,
    horizon_weeks: int | None,
    old_vdot: float | None,
    new_vdot: float | None,
    diff_json: str,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO plan_adjustments (plan_id, trigger_session_id, status, reason, "
            "confidence, horizon_weeks, old_vdot, new_vdot, diff_json) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (plan_id, trigger_session_id, status, reason, confidence,
             horizon_weeks, old_vdot, new_vdot, diff_json),
        )
        row = await cur.fetchone()
        return row[0]


async def get_plan_adjustment(conn: AsyncConnection, adj_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_adjustments WHERE id = %s", (adj_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        d = dict(zip(cols, row))
        dj = d.get("diff_json", [])
        d["diff_json"] = json.loads(dj) if isinstance(dj, str) else (dj or [])
        return d


async def update_adjustment_status(conn: AsyncConnection, adj_id: int, status: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plan_adjustments SET status = %s, reviewed_at = NOW() WHERE id = %s",
            (status, adj_id),
        )


async def get_applied_adjustments(conn: AsyncConnection, plan_id: int) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_adjustments WHERE plan_id = %s AND status = 'applied' "
            "ORDER BY created_at DESC",
            (plan_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def save_refresh_state(
    conn: AsyncConnection, plan_id: int, user_id: int, proposal_json: str
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO plan_refresh_state (plan_id, user_id, status, proposal_json) "
            "VALUES (%s, %s, 'pending', %s) "
            "ON CONFLICT (plan_id) DO UPDATE SET status = 'pending', "
            "proposal_json = EXCLUDED.proposal_json, created_at = NOW()",
            (plan_id, user_id, proposal_json),
        )


async def update_refresh_state(
    conn: AsyncConnection, plan_id: int, status: str
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plan_refresh_state SET status = %s, reviewed_at = NOW() WHERE plan_id = %s",
            (status, plan_id),
        )


async def get_refresh_state(conn: AsyncConnection, plan_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM plan_refresh_state WHERE plan_id = %s", (plan_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        d = dict(zip(cols, row))
        pj = d.get("proposal_json", {})
        d["proposal_json"] = json.loads(pj) if isinstance(pj, str) else (pj or {})
        return d


async def get_auto_pushed_week(conn: AsyncConnection, plan_id: int) -> int | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT auto_pushed_week FROM plans WHERE id = %s", (plan_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def set_auto_pushed_week(conn: AsyncConnection, plan_id: int, week: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plans SET auto_pushed_week = %s WHERE id = %s", (week, plan_id)
        )


async def clear_plan_garmin_workouts(
    conn: AsyncConnection, plan_id: int, keep_ids: list[int]
) -> None:
    async with conn.cursor() as cur:
        if keep_ids:
            await cur.execute(
                "UPDATE plan_sessions SET garmin_workout_id = NULL, garmin_activity_id = NULL "
                "WHERE plan_id = %s AND id NOT IN %s",
                (plan_id, tuple(keep_ids)),
            )
        else:
            await cur.execute(
                "UPDATE plan_sessions SET garmin_workout_id = NULL, garmin_activity_id = NULL "
                "WHERE plan_id = %s",
                (plan_id,),
            )
