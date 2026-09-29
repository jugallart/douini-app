from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import plans as plans_q
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
