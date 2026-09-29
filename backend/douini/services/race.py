from __future__ import annotations

from datetime import date
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import profile as profile_q
from douini.db.queries import race_results as race_q
from douini.domain.vdot import calc_vdot


async def add_race_result(
    conn: AsyncConnection,
    *,
    user_id: int,
    distance: str,
    actual_time: str,
    race_date: str | None = None,
    notes: str = "",
    location: str = "",
    plan_id: int | None = None,
) -> dict[str, Any]:
    vdot = calc_vdot(distance, actual_time)

    rd = date.fromisoformat(race_date) if race_date else None

    result_id = await race_q.save_race_result(
        conn,
        user_id=user_id,
        distance=distance,
        actual_time=actual_time,
        race_date=rd,
        derived_vdot=vdot,
        notes=notes,
        location=location,
        plan_id=plan_id,
    )

    await race_q.record_vdot_entry(
        conn, user_id=user_id, vdot=vdot, source="race", plan_id=plan_id
    )

    profile = await profile_q.get_profile(conn, user_id)
    if profile:
        await profile_q.upsert_profile(
            conn,
            user_id=user_id,
            vdot=vdot,
            race_distance=profile.get("race_distance"),
            target_time=profile.get("target_time"),
            sessions_per_week=profile.get("sessions_per_week", 4),
        )

    return {
        "id": result_id,
        "distance": distance,
        "actual_time": actual_time,
        "race_date": race_date,
        "derived_vdot": vdot,
        "notes": notes,
        "location": location,
    }


async def update_vdot_from_race(
    conn: AsyncConnection, user_id: int, race_distance: str, race_time: str
) -> float:
    vdot = calc_vdot(race_distance, race_time)
    profile = await profile_q.get_profile(conn, user_id)
    if profile:
        await profile_q.upsert_profile(
            conn,
            user_id=user_id,
            vdot=vdot,
            race_distance=profile.get("race_distance"),
            target_time=profile.get("target_time"),
            sessions_per_week=profile.get("sessions_per_week", 4),
        )
    await race_q.record_vdot_entry(
        conn, user_id=user_id, vdot=vdot, source="race"
    )
    return vdot
