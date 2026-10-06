from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.api.schemas import RunnerProfileIn
from douini.db.queries import profile as profile_q

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    profile = await profile_q.get_profile(conn, user["id"])
    if not profile:
        return {}
    return profile


@router.put("")
async def update_profile(
    data: RunnerProfileIn,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await profile_q.upsert_profile(conn, user["id"], **data.model_dump(exclude_unset=True))
    await conn.commit()
    profile = await profile_q.get_profile(conn, user["id"])
    return profile or {}


@router.get("/completeness")
async def profile_completeness(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await profile_q.get_profile_completeness(conn, user["id"])
