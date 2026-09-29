from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import race_results as race_q
from douini.services import race as race_svc

router = APIRouter(prefix="/race-results", tags=["race-results"])


@router.post("")
async def add_race_result(
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    result = await race_svc.add_race_result(
        conn,
        user_id=user["id"],
        distance=data.get("distance", ""),
        actual_time=data.get("actual_time", ""),
        race_date=data.get("race_date"),
        notes=data.get("notes", ""),
        location=data.get("location", ""),
        plan_id=data.get("plan_id"),
    )
    await conn.commit()
    return result


@router.get("")
async def list_race_results(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await race_q.list_race_results(conn, user["id"])


@router.get("/{result_id}")
async def get_race_result(
    result_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    results = await race_q.list_race_results(conn, user["id"])
    for r in results:
        if r["id"] == result_id:
            return r
    raise HTTPException(404, "Race result not found")


@router.delete("/{result_id}")
async def delete_race_result(
    result_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    deleted = await race_q.delete_race_result(conn, result_id, user["id"])
    if not deleted:
        raise HTTPException(404, "Race result not found")
    await conn.commit()
    return {"status": "deleted"}
