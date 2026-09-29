from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection


async def get_profile(conn: AsyncConnection, user_id: int) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM profile WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        d = dict(zip(cols, row))
        td = d.pop("training_days_json", [])
        d["training_days"] = json.loads(td) if isinstance(td, str) else (td or [])
        pd = d.pop("preferred_days_json", [])
        d["preferred_days"] = json.loads(pd) if isinstance(pd, str) else (pd or [])
        return d


async def upsert_profile(conn: AsyncConnection, user_id: int, **fields: Any) -> None:
    training_days = json.dumps(fields.pop("training_days", []))
    preferred_days = json.dumps(fields.pop("preferred_days", []))

    cols = ["user_id", "training_days_json", "preferred_days_json"]
    vals: list[Any] = [user_id, training_days, preferred_days]
    for k, v in fields.items():
        cols.append(k)
        vals.append(v)

    set_cols = [c for c in cols if c != "user_id"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in set_cols)
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(vals))

    async with conn.cursor() as cur:
        await cur.execute(
            f"INSERT INTO profile ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT (user_id) DO UPDATE SET {set_clause}, updated_at = NOW()",
            vals,
        )


async def get_profile_completeness(conn: AsyncConnection, user_id: int) -> dict[str, Any]:
    profile = await get_profile(conn, user_id)
    if not profile:
        return {"complete": False, "missing": ["profile"]}
    missing = []
    if not profile.get("vdot"):
        missing.append("vdot")
    if not profile.get("race_distance"):
        missing.append("race_distance")
    if not profile.get("target_time"):
        missing.append("target_time")
    if not profile.get("training_days"):
        missing.append("training_days")
    return {"complete": len(missing) == 0, "missing": missing}
