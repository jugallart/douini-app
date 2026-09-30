from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import notifications as nq

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    conn: AsyncConnection = Depends(get_db),
    user: dict = Depends(get_verified_user),
):
    return await nq.get_user_notifications(conn, user["id"])


@router.post("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: int,
    conn: AsyncConnection = Depends(get_db),
    user: dict = Depends(get_verified_user),
):
    ok = await nq.mark_notification_read(conn, notif_id, user["id"])
    if not ok:
        raise HTTPException(404, "Notification not found or already read")
    return {"status": "read"}


@router.post("/notifications/read-all")
async def mark_all_read(
    conn: AsyncConnection = Depends(get_db),
    user: dict = Depends(get_verified_user),
):
    count = await nq.mark_all_read(conn, user["id"])
    return {"marked_read": count}
