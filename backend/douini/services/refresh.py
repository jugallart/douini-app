from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import plans as plans_q
from douini.db.queries import profile as profile_q
from douini.db.queries import race_results as race_q
from douini.domain.engine.config import get_distance_rules
from douini.domain.models import RefreshProposal


async def get_refresh_proposal(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any] | None:
    if not await plans_q.is_plan_complete(conn, plan_id):
        return None

    plan_row = await plans_q.get_plan(conn, plan_id, user_id)
    if not plan_row:
        return None

    profile = await profile_q.get_profile(conn, user_id)
    if not profile:
        return None

    old_vdot = plan_row.get("vdot", profile.get("vdot", 50.0))
    old_weekly = profile.get("current_weekly_km")
    old_longest = profile.get("current_longest_run")

    sessions = plan_row.get("sessions_json", [])
    if isinstance(sessions, str):
        sessions = json.loads(sessions or "[]")

    distance = plan_row.get("distance", "10k")
    rules = get_distance_rules(distance)
    taper_weeks = rules.get("taper_weeks", 3)

    completed = [s for s in sessions if s.get("status") == "completed"]
    loading_weeks = [
        s for s in completed
        if s.get("week", 0) <= (plan_row.get("weeks", 12) - taper_weeks)
    ]
    if loading_weeks:
        proposed_weekly = sum(s.get("distance_km", 0) for s in loading_weeks) / len(
            set(s["week"] for s in loading_weeks)
        ) if loading_weeks else old_weekly
    else:
        proposed_weekly = old_weekly

    long_sessions = [
        s for s in completed
        if s.get("type") in ("long_run",) or s.get("distance_km", 0) >= 15
    ]
    proposed_longest = max(
        (s.get("distance_km", 0) for s in long_sessions), default=old_longest or 0
    )

    latest_race = await race_q.get_latest_race_result(conn, user_id)
    if latest_race and latest_race.get("derived_vdot"):
        proposed_vdot = latest_race["derived_vdot"]
        confidence = "high"
    else:
        proposed_vdot = old_vdot
        confidence = "low"

    proposal = RefreshProposal(
        old_vdot=old_vdot,
        proposed_vdot=proposed_vdot,
        old_current_weekly_km=old_weekly,
        proposed_current_weekly_km=proposed_weekly,
        old_current_longest_run=old_longest,
        proposed_current_longest_run=proposed_longest,
        evidence={"completed_sessions": len(completed)},
        confidence=confidence,
    )

    proposal_json = json.dumps({
        "old_vdot": proposal.old_vdot,
        "proposed_vdot": proposal.proposed_vdot,
        "old_current_weekly_km": proposal.old_current_weekly_km,
        "proposed_current_weekly_km": proposal.proposed_current_weekly_km,
        "old_current_longest_run": proposal.old_current_longest_run,
        "proposed_current_longest_run": proposal.proposed_current_longest_run,
        "evidence": proposal.evidence,
        "confidence": proposal.confidence,
        "assumptions": proposal.assumptions,
    })

    await plans_q.save_refresh_state(conn, plan_id, user_id, proposal_json)
    return json.loads(proposal_json)


async def accept_refresh(
    conn: AsyncConnection,
    plan_id: int,
    user_id: int,
    next_goal: dict[str, Any] | None = None,
) -> None:
    state = await plans_q.get_refresh_state(conn, plan_id)
    if not state:
        raise ValueError("No refresh proposal found")

    proposal = state.get("proposal_json", {})
    profile = await profile_q.get_profile(conn, user_id)
    if not profile:
        raise ValueError("Profile not found")

    fields: dict[str, Any] = {
        "vdot": proposal.get("proposed_vdot", profile.get("vdot")),
        "current_weekly_km": proposal.get("proposed_current_weekly_km"),
        "current_longest_run": proposal.get("proposed_current_longest_run"),
    }
    if next_goal:
        if next_goal.get("distance"):
            fields["race_distance"] = next_goal["distance"]
        if next_goal.get("target_time"):
            fields["target_time"] = next_goal["target_time"]
        if next_goal.get("weeks"):
            fields["weeks"] = next_goal["weeks"]
        if next_goal.get("sessions_per_week"):
            fields["sessions_per_week"] = next_goal["sessions_per_week"]

    await profile_q.upsert_profile(conn, user_id=user_id, **fields)
    await plans_q.update_refresh_state(conn, plan_id, "accepted")


async def decline_refresh(conn: AsyncConnection, plan_id: int) -> None:
    await plans_q.update_refresh_state(conn, plan_id, "declined")
