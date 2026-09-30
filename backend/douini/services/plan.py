from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from psycopg import AsyncConnection

from douini.db.queries import garmin as garmin_q
from douini.db.queries import plans as plans_q
from douini.db.queries import profile as profile_q
from douini.domain.engine.pace_engine import PaceEngine
from douini.domain.models import (
    DifficultyLevel,
    Distance,
    Experience,
    PlanSettings,
    RunnerProfile,
    Session,
    SessionStatus,
    TrainingPlan,
    VolumeStrategy,
)
from douini.domain.planner import generate_plan, regenerate_plan
from douini.domain.vdot import derive_paces

_EXP_MAP = {
    "debutant": Experience.BEGINNER,
    "intermediaire": Experience.INTERMEDIATE,
    "avance": Experience.ADVANCED,
}

_ZONE_GOALS = {
    "short": "Courir près du seuil aérobie",
    "medium": "Tenir un effort constant",
    "long": "Developper l'endurance",
    "easy": "Récupérer en aisance",
    "long_run": "Developper l'endurance",
    "recovery": "Récupérer",
}

_ZONE_LABELS = {
    "short": "Norwegian · intervalles courts",
    "medium": "Norwegian · intervalles moyens",
    "long": "Norwegian · intervalles longs",
    "easy": "Endurance facile",
    "long_run": "Endurance",
    "recovery": "Récupération",
}


def _session_display(session: Session) -> dict[str, str]:
    t = session.type
    if t == "quality":
        structure = session.structure or ""
        goal = _ZONE_GOALS.get(session.pace_key or "", "")
        pace_label = _ZONE_LABELS.get(session.pace_key or "", "")
        duration = "variable"
    elif t in ("long_run",):
        structure = f"{session.distance_km:.0f} km en endurance"
        goal = _ZONE_GOALS.get("long_run", "")
        pace_label = _ZONE_LABELS.get("long_run", "")
        duration = f"{session.distance_km * 5.5:.0f} min"
    else:
        structure = f"{session.distance_km:.0f} km facile"
        goal = _ZONE_GOALS.get(t, "")
        pace_label = _ZONE_LABELS.get(t, "")
        duration = f"{session.distance_km * 6:.0f} min"
    return {"structure": structure, "goal": goal, "duration": duration, "pace_label": pace_label}


def plan_to_json(plan: TrainingPlan) -> str:
    sessions: list[dict[str, Any]] = []
    for week in plan.week_plans:
        for s in week.sessions:
            disp = _session_display(s)
            sessions.append({
                "week": week.week_num,
                "bloc": week.bloc,
                "is_recovery": week.is_recovery,
                "phase": week.phase or "",
                "day": s.day,
                "type": s.type,
                "workout": (s.workout.name if hasattr(s.workout, "name") else s.workout) or "",
                "structure": disp["structure"],
                "distance_km": s.distance_km,
                "category": s.category or "",
                "pace_key": s.pace_key or "",
                "goal": disp["goal"],
                "duration": disp["duration"],
                "pace_label": disp["pace_label"],
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "id": s.id,
            })
    return json.dumps(sessions)


def settings_to_json(plan: TrainingPlan) -> str:
    return json.dumps(asdict(plan.settings))


def _build_settings(row: dict[str, Any]) -> PlanSettings:
    sj = row.get("settings_json", {})
    if isinstance(sj, str):
        sj = json.loads(sj or "{}")
    if sj:
        return PlanSettings(
            target_weekly_km=sj.get("target_weekly_km"),
            sessions_per_week=sj.get("sessions_per_week", 4),
            training_days=sj.get("training_days"),
            long_run_day=sj.get("long_run_day"),
            quality_sessions=sj.get("quality_sessions"),
            difficulty_level=DifficultyLevel(sj.get("difficulty_level", "balanced")),
            volume_strategy=VolumeStrategy(sj.get("volume_strategy", "progressive")),
            interval_adapted=sj.get("interval_adapted", False),
            target_time=sj.get("target_time"),
        )
    return PlanSettings(
        sessions_per_week=row.get("sessions_per_week", 4),
        target_time=row.get("goal_time"),
    )


async def plan_from_row(conn: AsyncConnection, row: dict[str, Any]) -> TrainingPlan:
    vdot = row.get("vdot", 50.0)
    paces = PaceEngine(vdot).build_profile().to_paces()
    profile_row = await profile_q.get_profile(conn, row["user_id"])

    runner = RunnerProfile(
        vdot=vdot,
        paces=paces,
    )
    if profile_row:
        runner.experience = Experience(profile_row.get("experience", "intermediaire"))
        runner.sessions_per_week = profile_row.get("sessions_per_week", 4)
        runner.target_weekly_km = profile_row.get("target_weekly_km")
        runner.current_weekly_km = profile_row.get("current_weekly_km")
        runner.current_longest_run = profile_row.get("current_longest_run")
        runner.long_run_day = profile_row.get("long_run_day")
        runner.training_days = profile_row.get("training_days", [])

    sessions_json = row.get("sessions_json", [])
    if isinstance(sessions_json, str):
        sessions_json = json.loads(sessions_json or "[]")

    week_plans: list[Any] = []
    by_week: dict[int, list[Session]] = {}
    for s in sessions_json:
        sess = Session(
            day=s["day"],
            workout=s.get("workout"),
            type=s.get("type", "easy"),
            structure=s.get("structure", ""),
            distance_km=s.get("distance_km", 0),
            category=s.get("category"),
            pace_key=s.get("pace_key"),
            status=SessionStatus(s.get("status", "pending")),
            id=s.get("id"),
        )
        by_week.setdefault(s["week"], []).append(sess)

    from douini.domain.models import WeekPlan

    for wk, sess_list in sorted(by_week.items()):
        first = sess_list[0]
        week_plans.append(
            WeekPlan(
                week_num=wk,
                bloc="",
                sessions=sess_list,
            )
        )

    return TrainingPlan(
        runner=runner,
        distance=Distance(row.get("distance", "10k")),
        weeks=row.get("weeks", 12),
        paces=paces,
        name=row.get("name"),
        week_plans=week_plans,
        sessions_per_week=row.get("sessions_per_week", 4),
        start_date=row.get("start_date"),
        settings=_build_settings(row),
        plan_vdot=vdot,
        mode=row.get("mode", "prod"),
    )


async def generate_plan_service(
    conn: AsyncConnection, user_id: int, **params: Any
) -> int:
    vdot = params.get("vdot", 50.0)
    paces = derive_paces(vdot)
    experience = _EXP_MAP.get(params.get("experience", "intermediaire"), Experience.INTERMEDIATE)

    runner = RunnerProfile(
        vdot=vdot,
        paces=paces,
        experience=experience,
        sessions_per_week=params.get("sessions_per_week", 4),
        target_weekly_km=params.get("target_weekly_km"),
        current_weekly_km=params.get("current_weekly_km"),
        current_longest_run=params.get("current_longest_run"),
        long_run_day=params.get("long_run_day"),
        training_days=params.get("training_days", []),
        race_distance=params.get("distance"),
        weeks=params.get("weeks", 12),
        target_time=params.get("target_time"),
        quality_sessions=params.get("quality_sessions"),
        difficulty_level=DifficultyLevel(params.get("difficulty_level", "balanced")),
        volume_strategy=VolumeStrategy(params.get("volume_strategy", "progressive")),
    )

    settings = PlanSettings(
        target_weekly_km=params.get("target_weekly_km"),
        sessions_per_week=params.get("sessions_per_week", 4),
        training_days=params.get("training_days"),
        long_run_day=params.get("long_run_day"),
        quality_sessions=params.get("quality_sessions"),
        difficulty_level=DifficultyLevel(params.get("difficulty_level", "balanced")),
        volume_strategy=VolumeStrategy(params.get("volume_strategy", "progressive")),
        interval_adapted=params.get("interval_adapted", False),
        target_time=params.get("target_time"),
    )

    start_date = None
    if params.get("start_date"):
        start_date = date.fromisoformat(params["start_date"])
    race_date = None
    if params.get("race_date"):
        race_date = date.fromisoformat(params["race_date"])

    plan = generate_plan(
        runner,
        Distance(params.get("distance", "10k")),
        weeks=params.get("weeks", 12),
        training_days=params.get("training_days"),
        interval_adapted=params.get("interval_adapted", False),
        start_date=start_date,
        name=params.get("plan_name"),
        quality_sessions=params.get("quality_sessions"),
        difficulty_level=DifficultyLevel(params.get("difficulty_level", "balanced")),
        volume_strategy=VolumeStrategy(params.get("volume_strategy", "progressive")),
        settings=settings,
    )

    sessions_json = plan_to_json(plan)
    settings_json = settings_to_json(plan)

    plan_id = await plans_q.save_plan(
        conn,
        user_id=user_id,
        name=plan.name or params.get("plan_name") or "Plan",
        distance=params.get("distance", "10k"),
        weeks=params.get("weeks", 12),
        vdot=vdot,
        start_date=start_date,
        goal_time=params.get("target_time"),
        sessions_json=sessions_json,
        settings_json=settings_json,
        race_date=race_date,
        mode="prod",
    )

    await profile_q.upsert_profile(
        conn,
        user_id=user_id,
        vdot=vdot,
        sessions_per_week=params.get("sessions_per_week", 4),
        target_weekly_km=params.get("target_weekly_km"),
        current_weekly_km=params.get("current_weekly_km"),
        current_longest_run=params.get("current_longest_run"),
        long_run_day=params.get("long_run_day"),
        training_days=params.get("training_days", []),
        race_distance=params.get("distance"),
        weeks=params.get("weeks", 12),
        target_time=params.get("target_time"),
        experience=params.get("experience", "intermediaire"),
        quality_sessions=params.get("quality_sessions"),
        difficulty_level=params.get("difficulty_level", "balanced"),
        volume_strategy=params.get("volume_strategy", "progressive"),
    )

    return plan_id


async def get_plan_detail(
    conn: AsyncConnection, plan_id: int, user_id: int
) -> dict[str, Any] | None:
    row = await plans_q.get_plan(conn, plan_id, user_id)
    if not row:
        return None

    sessions = row.get("sessions_json", [])
    db_sessions = await plans_q.get_plan_sessions(conn, plan_id)
    id_map = {(s["week"], s["day"]): s["id"] for s in db_sessions}
    for s in sessions:
        db_id = id_map.get((s.get("week"), s.get("day")))
        if db_id is not None:
            s["id"] = db_id

    return {
        "id": row["id"],
        "name": row.get("name"),
        "distance": row.get("distance"),
        "weeks": row.get("weeks"),
        "vdot": row.get("vdot"),
        "start_date": str(row["start_date"]) if row.get("start_date") else None,
        "goal_time": row.get("goal_time"),
        "status": row.get("status", "active"),
        "sessions": sessions,
        "settings": row.get("settings_json", {}),
        "created_at": str(row.get("created_at")) if row.get("created_at") else None,
    }


async def regenerate_plan_service(
    conn: AsyncConnection, plan_id: int, user_id: int, from_week: int | None = None
) -> dict[str, Any]:
    row = await plans_q.get_plan(conn, plan_id, user_id)
    if not row:
        raise ValueError("Plan not found")

    plan = await plan_from_row(conn, row)

    if from_week is None:
        sessions = row.get("sessions_json", [])
        pending_weeks = [s["week"] for s in sessions if s.get("status") == "pending"]
        if not pending_weeks:
            raise ValueError("No pending sessions to regenerate")
        from_week = min(pending_weeks)

    regenerated = regenerate_plan(plan, from_week=from_week)
    new_sessions_json = plan_to_json(regenerated)

    await plans_q.update_plan_sessions_json(conn, plan_id, new_sessions_json)
    await plans_q._materialize_plan_sessions(
        conn, plan_id, new_sessions_json, row.get("start_date")
    )

    return {"plan_id": plan_id, "from_week": from_week}


def compute_current_week(plan_start: date, weeks: int) -> int:
    delta = (date.today() - plan_start).days
    return max(1, min(weeks, delta // 7 + 1))


async def apply_interval_unit_change(conn: AsyncConnection, user_id: int, use_distance: bool) -> None:
    interval_unit = "distance" if use_distance else "time"
    row = await plans_q.get_active_plan(conn, user_id)
    if not row:
        return
    plan_id = row["id"]
    garmin_status = await garmin_q.get_garmin_status(conn, user_id)
    if not garmin_status["connected"]:
        return
    plan = await plan_from_row(conn, row)
    today = date.today()
    plan_start = plan.start_date
    if not plan_start or plan_start > today + timedelta(days=6):
        return
    current_week = compute_current_week(plan_start, plan.weeks)
    from douini.garmin.sync import push_plan_sessions_to_garmin
    await push_plan_sessions_to_garmin(
        conn, plan_id, user_id, force=True, week=current_week, interval_unit=interval_unit,
    )
