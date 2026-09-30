from __future__ import annotations

import json
from pathlib import Path

from psycopg import AsyncConnection

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "release_notes.json"


def get_all_releases() -> list[dict]:
    return json.loads(_DATA_FILE.read_text())


async def get_unread_releases(conn: AsyncConnection, user_id: int) -> list[dict]:
    all_releases = get_all_releases()
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT release_version FROM release_reads WHERE user_id = %s",
            (user_id,),
        )
        rows = await cur.fetchall()
    read_versions = {r[0] for r in rows}
    return [r for r in all_releases if r["version"] not in read_versions]


async def mark_release_read(conn: AsyncConnection, user_id: int, version: str) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO release_reads (user_id, release_version)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, version),
        )


async def mark_all_releases_read(conn: AsyncConnection, user_id: int) -> int:
    all_releases = get_all_releases()
    versions = [r["version"] for r in all_releases]
    if not versions:
        return 0
    async with conn.cursor() as cur:
        for version in versions:
            await cur.execute(
                "INSERT INTO release_reads (user_id, release_version) "
                "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, version),
            )
    return len(versions)
