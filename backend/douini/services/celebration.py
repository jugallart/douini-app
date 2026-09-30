from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q


async def get_or_create_celebration(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT plan_id, seen_at FROM plan_celebrations WHERE plan_id = %s",
            (plan_id,),
        )
        existing = await cur.fetchone()

    plan = await plans_q.get_plan(conn, plan_id, user_id)
    if not plan:
        return None

    if existing:
        return {"plan_id": existing[0], "seen_at": existing[1], "stats": await _compute_stats(conn, plan)}

    if not await plans_q.is_plan_complete(conn, plan_id):
        return None

    stats = await _compute_stats(conn, plan)

    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO plan_celebrations (plan_id, user_id) VALUES (%s, %s) "
            "ON CONFLICT (plan_id) DO NOTHING",
            (plan_id, user_id),
        )

    return {"plan_id": plan_id, "seen_at": None, "stats": stats}


async def mark_celebration_seen(
    conn: AsyncConnection, plan_id: int
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plan_celebrations SET seen_at = NOW() WHERE plan_id = %s",
            (plan_id,),
        )
        return cur.rowcount > 0


async def _compute_stats(conn: AsyncConnection, plan: dict[str, Any]) -> dict[str, Any]:
    sessions = await plans_q.get_plan_sessions(conn, plan["id"])
    completed = [s for s in sessions if s["status"] == "completed"]
    skipped = [s for s in sessions if s["status"] == "skipped"]
    total_km = sum(s.get("distance_km", 0) or 0 for s in completed)
    longest = max((s.get("distance_km", 0) or 0 for s in completed), default=0)

    sessions_json = plan.get("sessions_json", [])
    if isinstance(sessions_json, str):
        sessions_json = json.loads(sessions_json or "[]")
    start_vdot = sessions_json[0].get("vdot", plan.get("vdot")) if sessions_json else plan.get("vdot")
    end_vdot = plan.get("vdot")

    return {
        "total_km": round(total_km, 1),
        "sessions_completed": len(completed),
        "sessions_skipped": len(skipped),
        "longest_run_km": round(longest, 1),
        "vdot_start": start_vdot,
        "vdot_end": end_vdot,
        "vdot_delta": round((end_vdot or 0) - (start_vdot or 0), 2) if start_vdot and end_vdot else None,
    }
