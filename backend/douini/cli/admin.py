"""douini-admin — admin CLI for user/plan management.

Usage:
    douini-admin users
    douini-admin user <user_id>
    douini-admin verify <user_id>
    douini-admin delete-user <user_id>
    douini-admin plans
    douini-admin stats
"""
from __future__ import annotations

import asyncio
import sys

from psycopg import AsyncConnection

from douini.db.connection import close_pool, open_pool, get_conn
from douini.settings import settings


async def _list_users(conn: AsyncConnection) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, email_verified, created_at "
            "FROM users ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
    print(f"{'ID':<6} {'EMAIL':<35} {'VERIFIED':<10} {'CREATED'}")
    for r in rows:
        print(f"{r[0]:<6} {r[1]:<35} {'yes' if r[2] else 'no':<10} {r[3]}")


async def _user_detail(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, email_verified, created_at, updated_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        u = await cur.fetchone()
        if not u:
            print(f"User {user_id} not found")
            return
        await cur.execute(
            "SELECT id, name, vdot, created_at FROM plans WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        plans = await cur.fetchall()
    print(f"User #{u[0]}: {u[1]}")
    print(f"  Verified: {'yes' if u[2] else 'no'}")
    print(f"  Created: {u[3]}  Updated: {u[4]}")
    print(f"  Plans ({len(plans)}):")
    for p in plans:
        print(f"    #{p[0]} {p[1]} vdot={p[2]} ({p[3]})")


async def _verify_user(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET email_verified = TRUE, updated_at = NOW() WHERE id = %s",
            (user_id,),
        )
    await conn.commit()
    print(f"User {user_id} verified")


async def _delete_user(conn: AsyncConnection, user_id: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    await conn.commit()
    print(f"User {user_id} deleted (cascade)")


async def _list_plans(conn: AsyncConnection) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT p.id, p.user_id, u.email, p.name, p.vdot, p.created_at "
            "FROM plans p JOIN users u ON u.id = p.user_id "
            "ORDER BY p.created_at DESC"
        )
        rows = await cur.fetchall()
    print(f"{'ID':<6} {'USER':<6} {'EMAIL':<30} {'NAME':<25} {'VDOT':<8} {'CREATED'}")
    for r in rows:
        print(f"{r[0]:<6} {r[1]:<6} {r[2]:<30} {r[3]:<25} {r[4]!s:<8} {r[5]}")


async def _stats(conn: AsyncConnection) -> None:
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM plans")
        plans = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM plans WHERE is_complete = FALSE")
        active = (await cur.fetchone())[0]
    print(f"Users: {users}")
    print(f"Plans: {plans}")
    print(f"Active plans: {active}")


async def _run(cmd: str, arg: str | None) -> None:
    await open_pool()
    try:
        async with get_conn() as conn:
            if cmd == "users":
                await _list_users(conn)
            elif cmd == "user" and arg:
                await _user_detail(conn, int(arg))
            elif cmd == "verify" and arg:
                await _verify_user(conn, int(arg))
            elif cmd == "delete-user" and arg:
                await _delete_user(conn, int(arg))
            elif cmd == "plans":
                await _list_plans(conn)
            elif cmd == "stats":
                await _stats(conn)
            else:
                print(__doc__)
    finally:
        await close_pool()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(_run(cmd, arg))
