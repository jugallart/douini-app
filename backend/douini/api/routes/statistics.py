from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from douini.api.dependencies import get_db, get_verified_user
from douini.db.queries import plans as plans_q
from douini.db.queries import sessions as sessions_q
from douini.domain.engine.statistics import compute_statistics

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("")
async def get_statistics(
    user: dict = Depends(get_verified_user),
    conn: AsyncConnection = Depends(get_db),
):
    completed = await sessions_q.get_user_completed_sessions(conn, user["id"])
    plans = await plans_q.get_user_plans(conn, user["id"])
    counts = await sessions_q.get_user_session_counts(conn, user["id"])
    global_stats = await sessions_q.get_global_training_statistics(conn, user["id"])

    sessions_data = [
        {
            "distance_km": s.get("distance_km", 0),
            "status": s.get("status"),
            "type": s.get("type"),
            "week": s.get("week"),
            "day": s.get("day"),
            "scheduled_date": str(s.get("scheduled_date")) if s.get("scheduled_date") else None,
        }
        for s in completed
    ]
    plans_data = [
        {"id": p.get("id"), "distance": p.get("distance"), "weeks": p.get("weeks")}
        for p in plans
    ]

    stats = compute_statistics(sessions_data, plans_data, counts)
    stats.update(global_stats)
    return stats
