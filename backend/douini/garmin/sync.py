from __future__ import annotations

import asyncio
import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q
from douini.domain.models import french_session_name
from douini.domain.planner import get_all_sessions
from douini.garmin.builders import (
    build_session_workout,
    create_workout,
    fetch_running_activities,
    reconcile_plan_sessions,
    schedule_workout,
    update_workout,
)
from douini.services.plan import plan_from_row


async def push_plan_sessions_to_garmin(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any]:
    row = await plans_q.get_plan(conn, plan_id, user_id)
    if not row:
        raise ValueError("Plan not found")

    from douini.garmin.client import get_client
    client = await get_client(user_id, conn)

    plan = await plan_from_row(conn, row)
    sessions = list(get_all_sessions(plan))

    ok = fail = scheduled = 0
    results: list[dict] = []

    for week, day, session in sessions:
        name = french_session_name(week, day, session, plan_name=plan.name)
        wj = build_session_workout(session, plan.paces, name, profile=plan.pace_profile)

        success, result = await asyncio.to_thread(create_workout, client, wj)

        if success:
            if plan.start_date:
                d = plan.session_date(week, day)
                if d:
                    sched_ok, _ = await asyncio.to_thread(schedule_workout, client, result, d.isoformat())
                    if sched_ok:
                        scheduled += 1
            ok += 1
            results.append({"week": week, "day": day, "status": "ok", "workout_id": result})
        else:
            fail += 1
            results.append({"week": week, "day": day, "status": "fail", "error": result})

    return {"ok": ok, "fail": fail, "scheduled": scheduled, "results": results}


async def sync_plan_from_garmin(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any]:
    row = await plans_q.get_plan(conn, plan_id, user_id)
    if not row:
        raise ValueError("Plan not found")

    from douini.garmin.client import get_client
    client = await get_client(user_id, conn)

    sessions = await plans_q.get_plan_sessions(conn, plan_id)
    pending = [s for s in sessions if s["status"] == "pending" and s.get("scheduled_date")]
    if not pending:
        return {"matches": 0, "reviews": 0, "unmatched": 0}

    dates = [s["scheduled_date"] for s in pending if s.get("scheduled_date")]
    start = min(dates).isoformat()
    end = max(dates).isoformat()

    activities = await asyncio.to_thread(fetch_running_activities, client, start, end)

    session_dicts = [
        {
            "week": s["week"],
            "day": s["day"],
            "scheduled_date": s["scheduled_date"].isoformat() if s.get("scheduled_date") else None,
            "garmin_workout_id": s.get("garmin_workout_id"),
            "garmin_activity_id": s.get("garmin_activity_id"),
            "distance_km": s.get("distance_km", 0),
            "workout_name": s.get("workout_name", ""),
            "status": s.get("status", "pending"),
        }
        for s in pending
    ]

    matches, reviews, unmatched = reconcile_plan_sessions(session_dicts, activities)

    for session, activity in matches:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE plan_sessions SET status = 'review', garmin_activity_id = %s, "
                "updated_at = NOW() WHERE plan_id = %s AND week = %s AND day = %s",
                (activity["id"], plan_id, session["week"], session["day"]),
            )

    return {
        "matches": len(matches),
        "reviews": len(reviews),
        "unmatched": len(unmatched),
    }
