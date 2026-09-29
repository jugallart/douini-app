from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from psycopg import AsyncConnection

from douini.auth.jwt import decode_token
from douini.db.connection import get_conn
from douini.db.queries import auth as q
from douini.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


async def get_db() -> AsyncIterator[AsyncConnection]:
    async with get_conn() as conn:
        yield conn


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: AsyncConnection = Depends(get_db),
) -> dict:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(401, "Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")

    user_id = int(payload["sub"])
    user = await q.get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def get_verified_user(
    user: dict = Depends(get_current_user),
) -> dict:
    if not user["email_verified"]:
        raise HTTPException(403, "Email not verified")
    return user
