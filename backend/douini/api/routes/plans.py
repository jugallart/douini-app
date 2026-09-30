from __future__ import annotations

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
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
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
