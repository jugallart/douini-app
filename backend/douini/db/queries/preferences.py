from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

DEFAULTS: dict[str, Any] = {
    "metric_units": True,
    "notifications": True,
    "long_run_reminder": False,
}


async def get_preferences(conn: AsyncConnection, user_id: int) -> dict[str, Any]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT preferences FROM user_preferences WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
    stored = row[0] if row else {}
    if isinstance(stored, str):
        stored = json.loads(stored)
    return {**DEFAULTS, **(stored or {})}


async def save_all_preferences(
    conn: AsyncConnection, user_id: int, prefs: dict[str, Any]
) -> dict[str, Any]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO user_preferences (user_id, preferences, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET preferences =
                user_preferences.preferences || EXCLUDED.preferences,
                updated_at = NOW()
            """,
            (user_id, json.dumps(prefs)),
        )
    return await get_preferences(conn, user_id)
