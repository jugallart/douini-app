from __future__ import annotations

import asyncio
import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q
from douini.domain.models import Pace, french_session_name
from douini.domain.planner import get_all_sessions
from douini.domain.vdot import derive_paces
from douini.garmin.builders import build_session_workout, create_workout, update_workout
from douini.services.feedback import _apply_diff, _reverse_diff
from douini.services.plan import plan_from_row

_ZONES = ("ef", "short", "medium", "long")


async def reject_adjustment(
    conn: AsyncConnection, plan_id: int, adj_id: int, user_id: int
) -> dict[str, Any]:
    adj = await plans_q.get_plan_adjustment(conn, adj_id)
    if not adj or adj["plan_id"] != plan_id:
        raise ValueError("Adjustment not found")

    diff = adj.get("diff_json", [])
    if isinstance(diff, str):
        diff = json.loads(diff)

    if not diff:
        await plans_q.update_adjustment_status(conn, adj_id, "rejected")
        return {"id": adj_id, "status": "rejected", "restored": False}

    if len(diff) == 1 and diff[0].get("type") == "vdot_recalibration":
        old_vdot = diff[0].get("old_vdot")
        if old_vdot is not None:
            await plans_q.update_plan_vdot(conn, plan_id, old_vdot)
        await plans_q.update_adjustment_status(conn, adj_id, "rejected")
        return {"id": adj_id, "status": "rejected", "restored": True, "vdot_reverted": old_vdot}

    reverse = _reverse_diff(diff)
    if not reverse:
        await plans_q.update_adjustment_status(conn, adj_id, "rejected")
        return {"id": adj_id, "status": "rejected", "restored": False}

    plan_row = await plans_q.get_plan(conn, plan_id, user_id)
    if not plan_row:
        raise ValueError("Plan not found")
    sessions = plan_row.get("sessions_json", [])
    if isinstance(sessions, str):
        sessions = json.loads(sessions or "[]")

    sessions = _apply_diff(sessions, reverse)
    await plans_q.update_plan_sessions_json(conn, plan_id, json.dumps(sessions))
    await plans_q.update_adjustment_status(conn, adj_id, "rejected")

    return {"id": adj_id, "status": "rejected", "restored": True}


async def restore_plan(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any]:
    adjustments = await plans_q.get_applied_adjustments(conn, plan_id)
    if not adjustments:
        return {"restored_adjustments": []}

    plan_row = await plans_q.get_plan(conn, plan_id, user_id)
    if not plan_row:
        raise ValueError("Plan not found")
    sessions = plan_row.get("sessions_json", [])
    if isinstance(sessions, str):
        sessions = json.loads(sessions or "[]")

    restored_ids = []
    for adj in adjustments:
        diff = adj.get("diff_json")
        if isinstance(diff, str):
            diff = json.loads(diff)
        if not diff:
            continue

        if len(diff) == 1 and diff[0].get("type") == "vdot_recalibration":
            old_vdot = diff[0].get("old_vdot")
            if old_vdot is not None:
                await plans_q.update_plan_vdot(conn, plan_id, old_vdot)
            await plans_q.update_adjustment_status(conn, adj["id"], "restored")
            restored_ids.append(adj["id"])
            continue

        reverse = _reverse_diff(diff)
        if reverse:
            sessions = _apply_diff(sessions, reverse)
            await plans_q.update_adjustment_status(conn, adj["id"], "restored")
            restored_ids.append(adj["id"])

    if restored_ids:
        await plans_q.update_plan_sessions_json(conn, plan_id, json.dumps(sessions))

    return {"restored_adjustments": restored_ids}


async def sync_adjustment_to_garmin(
    conn: AsyncConnection, plan_id: int, adj_id: int, user_id: int
) -> dict[str, Any]:
    adj = await plans_q.get_plan_adjustment(conn, adj_id)
    if not adj or adj["plan_id"] != plan_id:
        raise ValueError("Adjustment not found")

    diff = adj.get("diff_json", [])
    if isinstance(diff, str):
        diff = json.loads(diff)

    diff_keys = {(d["week"], d["day"]) for d in diff if "week" in d}
    if not diff_keys:
        return {"synced": 0, "reason": "No session changes in diff"}

    plan_row = await plans_q.get_plan(conn, plan_id, user_id)
    if not plan_row:
        raise ValueError("Plan not found")

    from douini.garmin.client import get_client
    client = await get_client(user_id, conn)

    plan = await plan_from_row(conn, plan_row)
    all_sessions = list(get_all_sessions(plan))

    db_sessions = await plans_q.get_plan_sessions(conn, plan_id)
    by_key = {(s["week"], s["day"]): s for s in db_sessions}

    ok = fail = 0
    results = []
    for week, day, session in all_sessions:
        if (week, day) not in diff_keys:
            continue
        name = french_session_name(week, day, session, plan_name=plan.name)
        wj = build_session_workout(session, plan.paces, name, profile=plan.pace_profile)
        db_s = by_key.get((week, day), {})
        wid = db_s.get("garmin_workout_id")

        if wid:
            success, result = await asyncio.to_thread(update_workout, client, wid, wj)
        else:
            success, result = await asyncio.to_thread(create_workout, client, wj)
            if success:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE plan_sessions SET garmin_workout_id = %s "
                        "WHERE plan_id = %s AND week = %s AND day = %s",
                        (result, plan_id, week, day),
                    )

        if success:
            ok += 1
            results.append({"week": week, "day": day, "status": "ok", "workout_id": result})
        else:
            fail += 1
            results.append({"week": week, "day": day, "status": "fail", "error": result})

    return {"synced": ok, "failed": fail, "results": results}


def get_pace_changes(
    old_vdot: float, new_vdot: float
) -> list[dict[str, str]]:
    old_paces = derive_paces(old_vdot)
    new_paces = derive_paces(new_vdot)

    changes = []
    for zone in _ZONES:
        old_t = getattr(old_paces, zone)
        new_t = getattr(new_paces, zone)
        old_mid = (old_t[0].s_per_km + old_t[1].s_per_km) / 2
        new_mid = (new_t[0].s_per_km + new_t[1].s_per_km) / 2
        delta = round(old_mid - new_mid)
        changes.append({
            "zone": zone,
            "old_pace": str(Pace(int(round(old_mid)))),
            "new_pace": str(Pace(int(round(new_mid)))),
            "delta": f"{'+' if delta >= 0 else ''}{delta}s/km",
            "direction": "faster" if delta > 0 else "slower" if delta < 0 else "same",
        })
    return changes


if __name__ == "__main__":
    changes = get_pace_changes(50.0, 49.5)
    for c in changes:
        print(c)
    assert all(c["direction"] == "slower" for c in changes), "lower VDOT = slower"
    changes2 = get_pace_changes(50.0, 50.5)
    assert all(c["direction"] == "faster" for c in changes2), "higher VDOT = faster"
    print("OK")
