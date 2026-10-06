from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import plans as plans_q
from douini.db.queries import sessions as sessions_q
from douini.services import feedback as feedback_svc

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    session = await sessions_q.get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    plan_row = await conn.execute(
        "SELECT user_id FROM plans WHERE id = %s", (session["plan_id"],)
    )
    row = await plan_row.fetchone()
    if not row or row[0] != user["id"]:
        raise HTTPException(404, "Session not found")
    return session


@router.patch("/{session_id}")
async def patch_session(
    session_id: int,
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    session = await sessions_q.get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT p.user_id FROM plans p JOIN plan_sessions ps ON ps.plan_id = p.id "
            "WHERE ps.id = %s",
            (session_id,),
        )
        row = await cur.fetchone()
        if not row or row[0] != user["id"]:
            raise HTTPException(404, "Session not found")

    status = data.get("status")
    if status:
        updated = await sessions_q.update_session_status(conn, session_id, status)

        plan_row = await plans_q.get_plan(conn, updated["plan_id"], user["id"])
        if plan_row:
            sessions_json = plan_row.get("sessions_json", [])
            for s in sessions_json:
                if s["week"] == updated["week"] and s["day"] == updated["day"]:
                    s["status"] = status
                    break
            await plans_q.update_plan_sessions_json(
                conn, updated["plan_id"], json.dumps(sessions_json)
            )

        await conn.commit()
        return updated
    return session


@router.post("/{session_id}/feedback")
async def add_feedback(
    session_id: int,
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await feedback_svc.process_feedback(conn, session_id, data, user["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    await conn.commit()
    return result


@router.post("/{session_id}/adjust")
async def adjust_session(
    session_id: int,
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await feedback_svc.process_feedback(conn, session_id, data, user["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    await conn.commit()
    return result
