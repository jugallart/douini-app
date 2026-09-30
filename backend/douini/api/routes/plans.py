from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import plans as plans_q
from douini.services import adjustment as adjustment_svc
from douini.services import celebration as celebration_svc
from douini.services import plan as plan_svc
from douini.services import refresh as refresh_svc

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/generate")
async def generate_plan(
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    plan_id = await plan_svc.generate_plan_service(conn, user["id"], **data)
    await conn.commit()
    return {"plan_id": plan_id}


@router.get("")
async def list_plans(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await plans_q.list_plans(conn, user["id"])


@router.get("/{plan_id}")
async def get_plan(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    detail = await plan_svc.get_plan_detail(conn, plan_id, user["id"])
    if not detail:
        raise HTTPException(404, "Plan not found")
    return detail


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: int,
    garmin_cleanup: bool = False,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    if garmin_cleanup:
        try:
            from douini.garmin.sync import delete_plan_from_garmin
            await delete_plan_from_garmin(conn, plan_id, user["id"])
        except (ValueError, Exception):
            pass
    deleted = await plans_q.delete_plan(conn, plan_id, user["id"])
    if not deleted:
        raise HTTPException(404, "Plan not found")
    await conn.commit()
    return {"status": "deleted"}


@router.get("/{plan_id}/refresh-proposal")
async def get_refresh_proposal(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    proposal = await refresh_svc.get_refresh_proposal(conn, plan_id, user["id"])
    if proposal is None:
        raise HTTPException(400, "Plan not complete or not found")
    await conn.commit()
    return proposal


@router.post("/{plan_id}/refresh-proposal/accept")
async def accept_refresh(
    plan_id: int,
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await refresh_svc.accept_refresh(conn, plan_id, user["id"], data.get("next_goal"))
    await conn.commit()
    return {"status": "accepted"}


@router.post("/{plan_id}/refresh-proposal/decline")
async def decline_refresh(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await refresh_svc.decline_refresh(conn, plan_id)
    await conn.commit()
    return {"status": "declined"}


@router.get("/{plan_id}/review-queue")
async def get_review_queue(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    plan = await plans_q.get_plan(conn, plan_id, user["id"])
    if not plan:
        raise HTTPException(404, "Plan not found")
    return await plans_q.get_review_queue(conn, plan_id)


@router.post("/{plan_id}/adjustments/{adjustment_id}/reject")
async def reject_adjustment(
    plan_id: int,
    adjustment_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await adjustment_svc.reject_adjustment(conn, plan_id, adjustment_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    await conn.commit()
    return result


@router.post("/{plan_id}/adjustments/restore")
async def restore_plan(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await adjustment_svc.restore_plan(conn, plan_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    await conn.commit()
    return result


@router.post("/{plan_id}/adjustments/{adjustment_id}/sync-garmin")
async def sync_adjustment_garmin(
    plan_id: int,
    adjustment_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await adjustment_svc.sync_adjustment_to_garmin(
            conn, plan_id, adjustment_id, user["id"]
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    await conn.commit()
    return result


@router.get("/{plan_id}/adjustments/{adjustment_id}/pace-changes")
async def get_pace_changes(
    plan_id: int,
    adjustment_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    adj = await plans_q.get_plan_adjustment(conn, adjustment_id)
    if not adj or adj["plan_id"] != plan_id:
        raise HTTPException(404, "Adjustment not found")
    plan = await plans_q.get_plan(conn, plan_id, user["id"])
    if not plan:
        raise HTTPException(404, "Plan not found")
    old_vdot = adj.get("old_vdot") or plan["vdot"]
    new_vdot = adj.get("new_vdot") or plan["vdot"]
    return adjustment_svc.get_pace_changes(old_vdot, new_vdot)


@router.get("/{plan_id}/celebration")
async def get_celebration(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    cel = await celebration_svc.get_or_create_celebration(conn, plan_id, user["id"])
    if cel is None:
        raise HTTPException(400, "Plan not complete or not found")
    await conn.commit()
    return cel


@router.post("/{plan_id}/celebration/seen")
async def mark_celebration_seen_route(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    ok = await celebration_svc.mark_celebration_seen(conn, plan_id)
    if not ok:
        raise HTTPException(404, "Celebration not found")
    await conn.commit()
    return {"status": "seen"}


@router.post("/{plan_id}/regenerate")
async def regenerate_plan(
    plan_id: int,
    data: dict | None = None,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    from_week = (data or {}).get("from_week")
    try:
        result = await plan_svc.regenerate_plan_service(conn, plan_id, user["id"], from_week)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await conn.commit()
    return result


@router.put("/{plan_id}/weeks/{week}")
async def edit_week(
    plan_id: int,
    week: int,
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    plan = await plans_q.get_plan(conn, plan_id, user["id"])
    if not plan:
        raise HTTPException(404, "Plan not found")

    locked = await plans_q.locked_plan_session_keys(conn, plan_id)
    new_days = {s["day"] for s in data.get("sessions", [])}
    locked_in_week = {d for w, d in locked if w == week}
    if locked_in_week & new_days:
        raise HTTPException(409, f"Cannot edit locked sessions: {locked_in_week & new_days}")

    sessions_json = plan.get("sessions_json", [])
    sessions_json = [s for s in sessions_json if s["week"] != week]
    for s in data.get("sessions", []):
        s["week"] = week
        sessions_json.append(s)
    sessions_json.sort(key=lambda s: (s["week"], s.get("day", "")))

    await plans_q.update_plan_sessions_json(conn, plan_id, json.dumps(sessions_json))
    from douini.domain.models import DAY_OFFSET
    from datetime import timedelta
    start_date = plan.get("start_date")
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM plan_sessions WHERE plan_id = %s AND week = %s",
            (plan_id, week),
        )
        for s in data.get("sessions", []):
            if start_date:
                sd = start_date + timedelta(weeks=week - 1, days=DAY_OFFSET.get(s["day"], 0))
            else:
                sd = None
            await cur.execute(
                "INSERT INTO plan_sessions (plan_id, week, day, scheduled_date, type, "
                "workout_name, distance_km, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (plan_id, week, day) DO UPDATE SET "
                "type = EXCLUDED.type, workout_name = EXCLUDED.workout_name, "
                "distance_km = EXCLUDED.distance_km, updated_at = NOW()",
                (plan_id, week, s["day"], sd, s.get("type", "easy"),
                 s.get("workout", ""), s.get("distance_km", 0),
                 s.get("status", "pending")),
            )
    await conn.commit()
    return {"status": "updated", "week": week}


@router.delete("/{plan_id}/weeks/{week}")
async def delete_week(
    plan_id: int,
    week: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    plan = await plans_q.get_plan(conn, plan_id, user["id"])
    if not plan:
        raise HTTPException(404, "Plan not found")

    locked = await plans_q.locked_plan_session_keys(conn, plan_id)
    locked_in_week = {d for w, d in locked if w == week}
    if locked_in_week:
        raise HTTPException(409, f"Cannot delete week with locked sessions: {locked_in_week}")

    deleted = await plans_q.delete_week(conn, plan_id, week)
    if not deleted:
        raise HTTPException(404, "Week not found")

    sessions_json = plan.get("sessions_json", [])
    sessions_json = [s for s in sessions_json if s["week"] != week]
    await plans_q.update_plan_sessions_json(conn, plan_id, json.dumps(sessions_json))

    await conn.commit()
    return {"status": "deleted", "week": week}
