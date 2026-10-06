from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q
from douini.db.queries import profile as profile_q
from douini.db.queries import sessions as sessions_q
from douini.domain.models import SessionFeedback
from douini.settings import settings
from douini.domain.vdot import evaluate_feedback, get_workout_zone, recalibrate_vdot

_PACE_ACTIONS = {"recalibrate_vdot", "local_progression_trial", "monitor_difficulty"}

_DIFF_ACTIONS = (
    "suspend_running", "suspend_next_quality", "lighten_next_quality",
    "monitor_difficulty", "local_progression_trial",
)


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
    if session["status"] in ("pending", "skipped") and settings.ENVIRONMENT != "dev":
        raise ValueError("Feedback only after Garmin sync")

    is_quality = session.get("type") == "quality"

    # P13: streak from DB, not caller
    previous_streak = (
        await sessions_q.get_previous_quality_streak(conn, session["plan_id"], session_id)
        if is_quality
        else 0
    )

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
        difficulty_streak=previous_streak,
        user_id=user_id,
    )

    eval_result = evaluate_feedback(
        feedback,
        session.get("workout_name", ""),
        previous_streak,
    )

    action = eval_result.get("action", "maintain")
    proposal = eval_result.get("proposal") or {}

    # P14: suppress pace/difficulty actions on non-quality sessions
    if not is_quality and action in _PACE_ACTIONS:
        action = "maintain"
        eval_result["action"] = action
        eval_result["reason"] = (
            "Session non-quality : aucune proposition de recalibration ou progression."
        )
        proposal = {}

    new_streak = eval_result.get("difficulty_streak", previous_streak)

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
        difficulty_streak=new_streak,
    )

    adjustment = None

    # P12: VDOT recalibration (quality only, no session diff)
    if action == "recalibrate_vdot":
        adjustment = await _handle_recalibrate_vdot(
            conn, session, user_id, proposal, eval_result
        )

    # P15: recovery auto-restore on clean feedback
    elif _is_clean_feedback(feedback_data) and action == "maintain":
        adjustment = await _try_restore_adjustments(conn, session, user_id)

    # Pain/fatigue + quality pace actions that modify sessions
    elif action in _DIFF_ACTIONS:
        adjustment = await _apply_session_diff(
            conn, session, user_id, action, proposal, eval_result
        )

    return {
        "feedback_id": feedback_id,
        "action": action,
        "reason": eval_result.get("reason"),
        "adjustment": adjustment,
    }


def _is_clean_feedback(data: dict[str, Any]) -> bool:
    return data.get("pain_level", "none") in ("none", "") and data.get(
        "fatigue_level", "none"
    ) in ("none", "light")


async def _handle_recalibrate_vdot(
    conn: AsyncConnection,
    session: dict[str, Any],
    user_id: int,
    proposal: dict[str, Any],
    eval_result: dict[str, Any],
) -> dict[str, Any] | None:
    zone = get_workout_zone(session.get("workout_name", ""))
    if not zone:
        return None

    plan_row = await plans_q.get_plan(conn, session["plan_id"], user_id)
    if not plan_row:
        return None

    old_vdot = plan_row.get("vdot", 50.0)
    pace_factor = proposal.get("pace_factor", 1.0)
    new_vdot = round(recalibrate_vdot(old_vdot, zone, pace_factor), 1)

    await plans_q.update_plan_vdot(conn, session["plan_id"], new_vdot)
    await profile_q.upsert_profile(conn, user_id, vdot=new_vdot)

    diff = [{"type": "vdot_recalibration", "old_vdot": old_vdot, "new_vdot": new_vdot}]
    adj_id = await plans_q.save_plan_adjustment(
        conn,
        plan_id=session["plan_id"],
        trigger_session_id=session["id"],
        status="applied",
        reason=eval_result.get("reason", "recalibrate_vdot"),
        confidence=proposal.get("confidence", "medium"),
        horizon_weeks=proposal.get("horizon_weeks"),
        old_vdot=old_vdot,
        new_vdot=new_vdot,
        diff_json=json.dumps(diff),
    )
    return {"id": adj_id, "old_vdot": old_vdot, "new_vdot": new_vdot}


async def _try_restore_adjustments(
    conn: AsyncConnection, session: dict[str, Any], user_id: int
) -> dict[str, Any] | None:
    adjustments = await plans_q.get_applied_adjustments(conn, session["plan_id"])
    if not adjustments:
        return None

    plan_row = await plans_q.get_plan(conn, session["plan_id"], user_id)
    if not plan_row:
        return None

    sessions = plan_row.get("sessions_json", [])
    if isinstance(sessions, str):
        sessions = json.loads(sessions or "[]")

    restored_ids = []
    for adj in adjustments:
        diff = adj.get("diff_json")
        if isinstance(diff, str):
            diff = json.loads(diff)
        if not diff:
            continue

        # Skip VDOT-only adjustments (no session changes to reverse)
        if len(diff) == 1 and diff[0].get("type") == "vdot_recalibration":
            await plans_q.update_adjustment_status(conn, adj["id"], "restored")
            restored_ids.append(adj["id"])
            continue

        reverse = _reverse_diff(diff)
        if reverse:
            sessions = _apply_diff(sessions, reverse)
            await plans_q.update_adjustment_status(conn, adj["id"], "restored")
            restored_ids.append(adj["id"])

    if not restored_ids:
        return None

    await plans_q.update_plan_sessions_json(
        conn, session["plan_id"], json.dumps(sessions)
    )
    return {"restored_adjustments": restored_ids}


def _reverse_diff(diff_entries: list[dict]) -> list[dict]:
    reverse = []
    for d in diff_entries:
        if "week" not in d:
            continue
        reverse.append({
            "week": d["week"],
            "day": d["day"],
            "new_type": d.get("old_type"),
            "new_workout": d.get("old_workout"),
            "new_structure": d.get("old_structure"),
            "new_distance_km": d.get("old_distance_km"),
        })
    return reverse


async def _apply_session_diff(
    conn: AsyncConnection,
    session: dict[str, Any],
    user_id: int,
    action: str,
    proposal: dict[str, Any],
    eval_result: dict[str, Any],
) -> dict[str, Any] | None:
    plan_row = await plans_q.get_plan(conn, session["plan_id"], user_id)
    if not plan_row:
        return None

    old_sessions = plan_row.get("sessions_json", [])
    if isinstance(old_sessions, str):
        old_sessions = json.loads(old_sessions or "[]")

    locked = await plans_q.locked_plan_session_keys(conn, session["plan_id"])
    diff_entries = _build_diff(old_sessions, locked, action, proposal)

    if not diff_entries:
        return None

    new_sessions = json.dumps(_apply_diff(old_sessions, diff_entries))
    adj_id = await plans_q.save_plan_adjustment(
        conn,
        plan_id=session["plan_id"],
        trigger_session_id=session["id"],
        status="applied",
        reason=eval_result.get("reason", action),
        confidence=proposal.get("confidence", "medium"),
        horizon_weeks=proposal.get("horizon_weeks"),
        old_vdot=plan_row.get("vdot"),
        new_vdot=plan_row.get("vdot"),
        diff_json=json.dumps(diff_entries),
    )
    await plans_q.update_plan_sessions_json(conn, session["plan_id"], new_sessions)
    return {"id": adj_id, "diff": diff_entries}


def _build_diff(
    sessions: list[dict],
    locked: set[tuple[int, str]],
    action: str,
    proposal: dict[str, Any],
) -> list[dict]:
    diff_entries = []
    for s in sessions:
        key = (s["week"], s["day"])
        if key in locked:
            continue
        if s.get("status") not in ("pending", None):
            continue
        if s.get("type") != "quality":
            continue

        if action in ("suspend_running", "suspend_next_quality"):
            diff_entries.append({
                "week": s["week"], "day": s["day"],
                "old_type": s.get("type"), "new_type": "easy",
                "old_workout": s.get("workout"), "new_workout": "Endurance facile",
                "old_structure": s.get("structure"), "new_structure": "Récupération active",
                "old_distance_km": s.get("distance_km"), "new_distance_km": min(s.get("distance_km", 8), 8),
            })
        elif action in ("lighten_next_quality", "monitor_difficulty"):
            diff_entries.append({
                "week": s["week"], "day": s["day"],
                "old_type": s.get("type"), "new_type": s.get("type"),
                "old_workout": s.get("workout"), "new_workout": s.get("workout"),
                "old_structure": s.get("structure"), "new_structure": "Allégé",
                "old_distance_km": s.get("distance_km"),
                "new_distance_km": round(s.get("distance_km", 6) * 0.8, 1),
            })
        elif action == "local_progression_trial":
            diff_entries.append({
                "week": s["week"], "day": s["day"],
                "old_type": s.get("type"), "new_type": s.get("type"),
                "old_workout": s.get("workout"),
                "new_workout": proposal.get("workout_target", s.get("workout")),
                "old_structure": s.get("structure"), "new_structure": s.get("structure"),
                "old_distance_km": s.get("distance_km"), "new_distance_km": s.get("distance_km"),
            })
    return diff_entries


def _apply_diff(sessions: list[dict], diff_entries: list[dict]) -> list[dict]:
    by_key = {(s["week"], s["day"]): s for s in sessions}
    for d in diff_entries:
        s = by_key.get((d["week"], d["day"]))
        if s:
            if d.get("new_type") is not None:
                s["type"] = d["new_type"]
            if d.get("new_workout") is not None:
                s["workout"] = d["new_workout"]
            if d.get("new_structure") is not None:
                s["structure"] = d["new_structure"]
            if d.get("new_distance_km") is not None:
                s["distance_km"] = d["new_distance_km"]
    return sessions
