from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.services import release_notes as rn

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("")
async def list_releases():
    return rn.get_all_releases()


@router.get("/unread")
async def unread_releases(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await rn.get_unread_releases(conn, user["id"])


@router.post("/{version}/read")
async def mark_read(
    version: str,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await rn.mark_release_read(conn, user["id"], version)
    await conn.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    count = await rn.mark_all_releases_read(conn, user["id"])
    await conn.commit()
    return {"ok": True, "marked": count}
