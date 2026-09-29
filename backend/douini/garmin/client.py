from __future__ import annotations

from garminconnect import Garmin

from douini.db.queries.garmin import get_garmin_token
from douini.garmin.crypto import decrypt_token


async def get_client(user_id: int, conn) -> Garmin:
    row = await get_garmin_token(conn, user_id)
    if not row:
        from fastapi import HTTPException
        raise HTTPException(400, "Garmin not connected")

    plaintext = decrypt_token(row["encrypted_token"])
    client = Garmin()
    client.login(tokenstore=plaintext)
    return client


def connect_garmin(email: str, password: str) -> str:
    client = Garmin(email, password)
    client.client.skip_strategies = {"mobile+requests", "portal+requests"}
    client.login()
    return client.client.dumps()
