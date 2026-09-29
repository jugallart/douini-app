from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import garmin as garmin_q
from douini.garmin.client import connect_garmin
from douini.garmin.crypto import encrypt_token
from douini.garmin.sync import push_plan_sessions_to_garmin, sync_plan_from_garmin

router = APIRouter(prefix="/garmin", tags=["garmin"])


@router.post("/connect")
async def connect(
    data: dict,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    email = data.get("email", "")
    password = data.get("password", "")
    if not email or not password:
        raise HTTPException(400, "Email and password required")

    try:
        token_json = connect_garmin(email, password)
    except Exception as e:
        raise HTTPException(400, f"Garmin login failed: {e}")

    await garmin_q.upsert_garmin_token(conn, user["id"], encrypt_token(token_json))
    await conn.commit()
    return {"status": "connected"}


@router.get("/status")
async def status(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await garmin_q.get_garmin_status(conn, user["id"])


@router.post("/push/{plan_id}")
async def push_plan(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await push_plan_sessions_to_garmin(conn, plan_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, str(e))
    await conn.commit()
    return result


@router.post("/sync/{plan_id}")
async def sync_plan(
    plan_id: int,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    try:
        result = await sync_plan_from_garmin(conn, plan_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, str(e))
    await conn.commit()
    return result


@router.delete("/disconnect")
async def disconnect(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await garmin_q.delete_garmin_token(conn, user["id"])
    await conn.commit()
    return {"status": "disconnected"}
