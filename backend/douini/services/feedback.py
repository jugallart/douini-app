from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q
from douini.db.queries import sessions as sessions_q
from douini.domain.models import SessionFeedback, SessionStatus
from douini.domain.vdot import evaluate_feedback, get_workout_zone, recalibrate_vdot


async def process_feedback(
    conn: AsyncConnection,
    session_id: int,
    feedback_data: dict[str, Any],
    user_id: int,
) -> dict[str, Any]:
    session = await sessions_q.get_session_by_id(conn, session_id)
    if not session:
        raise ValueError("Session not found")

    if session["status"] not in ("completed", "pending", "skipped"):
        raise ValueError("Invalid session status")

    feedback = SessionFeedback(
        plan_session_id=session_id,
        pace_rating=feedback_data.get("pace_rating", "controlee"),
        rpe=feedback_data.get("rpe", 3),
        fatigue_level=feedback_data.get("fatigue_level", "none"),
        fatigue_duration=feedback_data.get("fatigue_duration", "aucune"),
        pain_level=feedback_data.get("pain_level", "none"),
        pain_impact=feedback_data.get("pain_impact", "aucun"),
        pain_location=feedback_data.get("pain_location", ""),
        pain_onset=feedback_data.get("pain_onset", ""),
        pain_evolution=feedback_data.get("pain_evolution", ""),
        temp_cause=feedback_data.get("temp_cause", ""),
        difficulty_streak=feedback_data.get("difficulty_streak", 0),
        user_id=user_id,
    )

    eval_result = evaluate_feedback(
        feedback,
        session.get("workout_name", ""),
        feedback_data.get("previous_streak", 0),
    )

    feedback_id = await sessions_q.save_session_feedback(
        conn,
        plan_session_id=session_id,
        user_id=user_id,
        pace_rating=feedback.pace_rating.value if hasattr(feedback.pace_rating, "value") else str(feedback.pace_rating),
        rpe=feedback.rpe,
        fatigue_level=feedback.fatigue_level.value if hasattr(feedback.fatigue_level, "value") else str(feedback.fatigue_level),
        fatigue_duration=feedback.fatigue_duration.value if hasattr(feedback.fatigue_duration, "value") else str(feedback.fatigue_duration),
        pain_level=feedback.pain_level.value if hasattr(feedback.pain_level, "value") else str(feedback.pain_level),
        pain_impact=feedback.pain_impact.value if hasattr(feedback.pain_impact, "value") else str(feedback.pain_impact),
        pain_location=feedback.pain_location,
        pain_onset=feedback.pain_onset,
        pain_evolution=feedback.pain_evolution,
        temp_cause=feedback.temp_cause,
        difficulty_streak=feedback.difficulty_streak,
    )

    action = eval_result.get("action", "maintain")
    proposal = eval_result.get("proposal", {})

    adjustment = None
    if session.get("type") == "quality" and action in (
        "suspend_running", "suspend_next_quality", "lighten_next_quality",
        "recalibrate_vdot", "progression_trial", "lighten_workout",
        "replace_with_easy", "suspend_quality",
    ):
        plan_row = await plans_q.get_plan(conn, session["plan_id"], user_id)
        if plan_row:
            old_sessions = plan_row.get("sessions_json", [])
            if isinstance(old_sessions, str):
                old_sessions = json.loads(old_sessions or "[]")

            locked = await plans_q.locked_plan_session_keys(conn, session["plan_id"])

            diff_entries = []
            for s in old_sessions:
                key = (s["week"], s["day"])
                if key in locked:
                    continue
                if s.get("status") not in ("pending", None):
                    continue
                if action in ("suspend_quality", "suspend_next_quality"):
                    if s.get("type") == "quality":
                        diff_entries.append({
                            "week": s["week"], "day": s["day"],
                            "old_type": s.get("type"), "new_type": "easy",
                            "old_workout": s.get("workout"), "new_workout": "Endurance facile",
                            "old_structure": s.get("structure"), "new_structure": "Récupération active",
                            "old_distance_km": s.get("distance_km"), "new_distance_km": min(s.get("distance_km", 8), 8),
                        })
                elif action in ("lighten_workout", "lighten_next_quality"):
                    if s.get("type") == "quality":
                        diff_entries.append({
                            "week": s["week"], "day": s["day"],
                            "old_type": s.get("type"), "new_type": s.get("type"),
                            "old_workout": s.get("workout"), "new_workout": s.get("workout"),
                            "old_structure": s.get("structure"), "new_structure": "Allégé",
                            "old_distance_km": s.get("distance_km"),
                            "new_distance_km": s.get("distance_km", 6) * 0.8,
                        })

            if diff_entries:
                new_sessions = json.dumps(_apply_diff(old_sessions, diff_entries))
                adj_id = await plans_q.save_plan_adjustment(
                    conn,
                    plan_id=session["plan_id"],
                    trigger_session_id=session_id,
                    status="applied",
                    reason=eval_result.get("reason", action),
                    confidence=proposal.get("confidence", "medium"),
                    horizon_weeks=proposal.get("horizon_weeks"),
                    old_vdot=plan_row.get("vdot"),
                    new_vdot=plan_row.get("vdot"),
                    diff_json=json.dumps(diff_entries),
                )
                await plans_q.update_plan_sessions_json(conn, session["plan_id"], new_sessions)
                adjustment = {"id": adj_id, "diff": diff_entries}

    return {
        "feedback_id": feedback_id,
        "action": action,
        "reason": eval_result.get("reason"),
        "adjustment": adjustment,
    }


def _apply_diff(sessions: list[dict], diff_entries: list[dict]) -> list[dict]:
    by_key = {(s["week"], s["day"]): s for s in sessions}
    for d in diff_entries:
        s = by_key.get((d["week"], d["day"]))
        if s:
            s["type"] = d.get("new_type", s["type"])
            s["workout"] = d.get("new_workout", s["workout"])
            s["structure"] = d.get("new_structure", s["structure"])
            s["distance_km"] = d.get("new_distance_km", s["distance_km"])
    return sessions
