from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection


async def update_session_status(
    conn: AsyncConnection, session_id: int, status: str
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE plan_sessions SET status = %s, updated_at = NOW() "
            "WHERE id = %s RETURNING *",
            (status, session_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))


async def save_session_feedback(
    conn: AsyncConnection,
    *,
    plan_session_id: int,
    user_id: int,
    pace_rating: str,
    rpe: int,
    fatigue_level: str,
    fatigue_duration: str,
    pain_level: str,
    pain_impact: str,
    pain_location: str,
    pain_onset: str,
    pain_evolution: str,
    temp_cause: str,
    difficulty_streak: int,
    rules_version: str = "2026.1",
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO session_feedback (plan_session_id, user_id, pace_rating, rpe, "
            "fatigue_level, fatigue_duration, pain_level, pain_impact, pain_location, "
            "pain_onset, pain_evolution, temp_cause, difficulty_streak, rules_version) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (plan_session_id) DO UPDATE SET "
            "pace_rating = EXCLUDED.pace_rating, rpe = EXCLUDED.rpe, "
            "fatigue_level = EXCLUDED.fatigue_level, fatigue_duration = EXCLUDED.fatigue_duration, "
            "pain_level = EXCLUDED.pain_level, pain_impact = EXCLUDED.pain_impact, "
            "pain_location = EXCLUDED.pain_location, pain_onset = EXCLUDED.pain_onset, "
            "pain_evolution = EXCLUDED.pain_evolution, temp_cause = EXCLUDED.temp_cause, "
            "difficulty_streak = EXCLUDED.difficulty_streak "
            "RETURNING id",
            (plan_session_id, user_id, pace_rating, rpe, fatigue_level, fatigue_duration,
             pain_level, pain_impact, pain_location, pain_onset, pain_evolution,
             temp_cause, difficulty_streak, rules_version),
        )
        row = await cur.fetchone()
        return row[0]


async def list_session_feedbacks(
    conn: AsyncConnection, plan_id: int
) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT sf.* FROM session_feedback sf "
            "JOIN plan_sessions ps ON sf.plan_session_id = ps.id "
            "WHERE ps.plan_id = %s ORDER BY sf.created_at",
            (plan_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def get_user_completed_sessions(
    conn: AsyncConnection, user_id: int
) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT ps.* FROM plan_sessions ps "
            "JOIN plans p ON ps.plan_id = p.id "
            "WHERE p.user_id = %s AND ps.status = 'completed' "
            "ORDER BY ps.scheduled_date DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]


async def get_user_session_counts(conn: AsyncConnection, user_id: int) -> dict[str, int]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT ps.status, COUNT(*) FROM plan_sessions ps "
            "JOIN plans p ON ps.plan_id = p.id "
            "WHERE p.user_id = %s GROUP BY ps.status",
            (user_id,),
        )
        rows = await cur.fetchall()
        return {r[0]: r[1] for r in rows}


async def get_global_training_statistics(
    conn: AsyncConnection, user_id: int
) -> dict[str, Any]:
    sessions = await get_user_completed_sessions(conn, user_id)
    return {
        "total_sessions": len(sessions),
        "total_distance": sum(s.get("distance_km", 0) or 0 for s in sessions),
    }
