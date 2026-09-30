from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import preferences as prefs_q
from douini.services import plan as plan_svc

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("")
async def get_preferences(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await prefs_q.get_preferences(conn, user["id"])


@router.put("")
async def update_preferences(
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    result = await prefs_q.save_all_preferences(conn, user["id"], data)
    await conn.commit()
    return result


@router.post("/interval-unit")
async def change_interval_unit(
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    use_distance = data.get("use_distance", False)
    await prefs_q.save_all_preferences(conn, user["id"], {"metric_units": not use_distance})
    await plan_svc.apply_interval_unit_change(conn, user["id"], use_distance)
    await conn.commit()
    return {"ok": True}
