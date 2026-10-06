from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.api.schemas import UserIdentityIn
from douini.db.queries import auth as auth_q

router = APIRouter(prefix="/account", tags=["account"])


@router.delete("")
async def delete_account(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await auth_q.delete_user(conn, user["id"])
    await conn.commit()
    return {"status": "deleted"}


@router.post("/reset-data")
async def reset_data(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await auth_q.reset_all_data(conn, user["id"])
    await conn.commit()
    return {"status": "reset"}


@router.put("/identity")
async def update_identity(
    data: UserIdentityIn,
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    await auth_q.update_user_identity(
        conn, user["id"], data.pseudo, data.prenom, data.nom
    )
    await conn.commit()
    return {"status": "updated"}
