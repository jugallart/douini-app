from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from psycopg import AsyncConnection

from douini.db.connection import get_conn
from douini.db.queries import garmin as garmin_q
from douini.db.queries import plans as plans_q
from douini.garmin.sync import auto_sync_plan

logger = logging.getLogger(__name__)

LEASE_TTL = 300
MAX_BACKOFF = 1800
BASE_BACKOFF = 30
SCAN_INTERVAL = 60


async def acquire_lease(
    conn: AsyncConnection, user_id: int, ttl: int = LEASE_TTL
) -> bool:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO sync_leases (user_id, expires_at) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO NOTHING",
            (user_id, expires_at),
        )
        if cur.rowcount > 0:
            return True
        await cur.execute(
            "UPDATE sync_leases SET acquired_at = NOW(), expires_at = %s, "
            "attempt_count = sync_leases.attempt_count + 1 "
            "WHERE user_id = %s AND expires_at < NOW()",
            (expires_at, user_id),
        )
        return cur.rowcount > 0


async def release_lease(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM sync_leases WHERE user_id = %s", (user_id,))


async def _get_attempt_count(conn: AsyncConnection, user_id: int) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT attempt_count FROM sync_leases WHERE user_id = %s", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def sync_user_plans(conn: AsyncConnection, user_id: int) -> dict:
    plans = await plans_q.get_user_plans(conn, user_id)
    active = [p for p in plans if p.get("status") == "active"]
    results = []
    for p in active:
        try:
            r = await auto_sync_plan(conn, p["id"], user_id)
            results.append({"plan_id": p["id"], **r})
        except Exception as exc:
            logger.warning("sync plan %s failed: %s", p["id"], exc)
            results.append({"plan_id": p["id"], "error": str(exc)})
    return {"plans_synced": len(active), "results": results}


async def run_sync_loop() -> None:
    logger.info("sync loop started")
    while True:
        try:
            async with get_conn() as conn:
                user_ids = await garmin_q.list_garmin_connected_users(conn)
            for uid in user_ids:
                async with get_conn() as conn:
                    got = await acquire_lease(conn, uid)
                    if not got:
                        continue
                    try:
                        await sync_user_plans(conn, uid)
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "UPDATE sync_leases SET attempt_count = 0 WHERE user_id = %s",
                                (uid,),
                            )
                    except Exception:
                        attempts = await _get_attempt_count(conn, uid)
                        delay = min(BASE_BACKOFF * 2**attempts, MAX_BACKOFF)
                        logger.warning("sync uid=%s failed, attempt=%s backoff=%ss", uid, attempts, delay)
                    finally:
                        await release_lease(conn, uid)
        except Exception:
            logger.exception("sync loop iteration failed")
        await asyncio.sleep(SCAN_INTERVAL)
