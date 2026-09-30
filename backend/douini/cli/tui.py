"""douini-cli — dev CLI for VDOT, race prediction, plan export.

Usage:
    douini-cli vdot <distance> <time>          e.g. douini-cli vdot 10k 45:30
    douini-cli predict <vdot> <distance>        e.g. douini-cli predict 42.5 10k
    douini-cli export <plan_id> [json|csv|md]   exports plan from DB
"""
from __future__ import annotations

import asyncio
import json
import sys

from douini.domain.vdot import VDOTCalculator, derive_paces
from douini.domain.planner import get_all_sessions
from douini.garmin.builders import build_session_workout


def _cmd_vdot(distance: str, time: str) -> None:
    calc = VDOTCalculator()
    vdot = calc.from_race(distance, time)
    print(f"VDOT: {vdot:.1f}")
    paces = derive_paces(vdot)
    for zone_name, zone in [("ef", paces.ef), ("short", paces.short), ("medium", paces.medium), ("long", paces.long)]:
        print(f"  {zone_name}: {zone[0]}'–{zone[1]}'/km")


def _cmd_predict(vdot: float, distance: str) -> None:
    calc = VDOTCalculator()
    time = calc.race_time(vdot, distance)
    print(f"Predicted {distance} time at VDOT {vdot}: {time}")


async def _cmd_export(plan_id: int, fmt: str) -> None:
    from douini.db.connection import close_pool, open_pool, get_conn
    from douini.db.queries import plans as plans_q
    from douini.services.plan import plan_from_row

    await open_pool()
    try:
        async with get_conn() as conn:
            row = await plans_q.get_plan(conn, plan_id)
            if not row:
                print(f"Plan {plan_id} not found")
                return
            plan = plan_from_row(conn, row)
    finally:
        await close_pool()

    sessions = list(get_all_sessions(plan))
    if fmt == "json":
        out = []
        for week, day, s in sessions:
            out.append({"week": week, "day": day, "name": s.workout_name, "type": s.type, "distance_km": s.distance_km})
        print(json.dumps(out, indent=2, default=str))
    elif fmt == "csv":
        print("week,day,name,type,distance_km")
        for week, day, s in sessions:
            print(f"{week},{day},{s.workout_name},{s.type},{s.distance_km}")
    else:
        print(f"# {plan.name}\n")
        for week, day, s in sessions:
            print(f"- S{week}D{day}: {s.workout_name} ({s.type}) {s.distance_km}km")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "vdot" and len(sys.argv) >= 4:
        _cmd_vdot(sys.argv[2], sys.argv[3])
    elif cmd == "predict" and len(sys.argv) >= 4:
        _cmd_predict(float(sys.argv[2]), sys.argv[3])
    elif cmd == "export" and len(sys.argv) >= 3:
        fmt = sys.argv[3] if len(sys.argv) > 3 else "md"
        asyncio.run(_cmd_export(int(sys.argv[2]), fmt))
    else:
        print(__doc__)
