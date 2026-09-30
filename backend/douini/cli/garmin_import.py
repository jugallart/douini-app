"""douini-cli garmin-import — pushes 18 NS workouts to Garmin Connect.

Usage:
    douini-cli garmin-import --email <email> --password <pwd> [--dry-run]
"""
from __future__ import annotations

import asyncio
import sys

from douini.domain.planner import WORKOUT_DEFS, build_workout
from douini.domain.vdot import derive_paces
from douini.garmin.builders import build_session_workout, create_workout


async def _run(email: str, password: str, dry_run: bool) -> None:
    from garminconnect import Garmin

    client = Garmin(email, password)
    await asyncio.to_thread(client.login)

    paces = derive_paces(40.0)
    for name in sorted(WORKOUT_DEFS):
        wd = build_workout(name, paces)
        session = type("S", (), {"workout_name": name, "workout_target": wd.description, "type": "quality"})()
        wj = build_session_workout(session, paces, display_name=name)
        if dry_run:
            print(f"[dry-run] {name}: {wd.description}")
            continue
        wid = await asyncio.to_thread(create_workout, client, wj)
        print(f"Created {name} -> workout_id={wid}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    email = ""
    password = ""
    dry_run = False
    i = 0
    while i < len(args):
        if args[i] == "--email":
            email = args[i + 1]
            i += 2
        elif args[i] == "--password":
            password = args[i + 1]
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            i += 1
    if not email or not password:
        print("--email and --password required")
        return
    asyncio.run(_run(email, password, dry_run))
