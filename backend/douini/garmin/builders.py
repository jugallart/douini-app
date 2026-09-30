"""Garmin Connect workout JSON builders — copied from douini-run, imports updated."""
from __future__ import annotations

import json
from datetime import date, timedelta

from douini.domain.models import Paces, Pace, WorkoutDef, Session, TrainingPlan, PaceProfile
from douini.domain.planner import WORKOUT_DEFS, build_workout, get_all_sessions
from douini.domain.engine.library import get_workout as _get_catalog_workout, resolve_pace

WARMUP_SEC = 1200
COOLDOWN_SEC = 1200
STRIDE_FAST = 20
STRIDE_SLOW = 40


def _seconds_to_distance_m(seconds: int, paces: Paces) -> float:
    ef_mid = (paces.ef[0].s_per_km + paces.ef[1].s_per_km) / 2
    return seconds / ef_mid * 1000


def _step_executable(order, seconds, step_type_id, step_type_key, target_type="open", value_one=None, value_two=None):
    target_info = (
        {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
        if target_type == "open"
        else {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
    )
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": order,
        "stepType": {"stepTypeId": step_type_id, "stepTypeKey": step_type_key},
        "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
        "endConditionValue": float(seconds),
        "targetType": target_info,
        "targetValueOne": value_one,
        "targetValueTwo": value_two,
    }


def _step_distance(order, meters, step_type_id=3, step_type_key="interval"):
    step = _step_executable(order, 0, step_type_id, step_type_key, "open")
    step["endCondition"] = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
    step["endConditionValue"] = float(meters)
    return step


def _step_repeat(order, repeat_count, child_steps):
    return {
        "type": "RepeatGroupDTO",
        "stepOrder": order,
        "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
        "numberOfIterations": repeat_count,
        "workoutSteps": child_steps,
    }


def _build_workout_json(name, description, steps, distance_km=None):
    workout = {
        "workoutName": name,
        "description": description,
        "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": steps,
        }],
    }
    if distance_km is not None:
        workout["estimatedDistanceInMeters"] = round(distance_km * 1000)
        workout["workoutSegments"][0]["estimatedDistanceInMeters"] = round(distance_km * 1000)
    return workout


def _pace_to_garmin(p: Pace) -> float:
    return 1000 / p.s_per_km


def _make_warmup_steps(paces: Paces, interval_unit: str = "time"):
    steps = []
    order = 1
    if interval_unit == "distance":
        steps.append(_step_distance(order, _seconds_to_distance_m(WARMUP_SEC, paces), 1, "warmup"))
    else:
        steps.append(_step_executable(order, WARMUP_SEC, 1, "warmup", "open"))
    order += 1
    stride_fast = _step_executable(1, STRIDE_FAST, 3, "interval", "open")
    stride_slow = _step_executable(2, STRIDE_SLOW, 4, "recovery", "open")
    steps.append(_step_repeat(order, 4, [stride_fast, stride_slow]))
    order += 1
    return steps, order


def _make_interval_step(order, seconds, pace_min: Pace, pace_max: Pace, interval_unit: str = "time"):
    fast = _pace_to_garmin(pace_min)
    slow = _pace_to_garmin(pace_max)
    step = _step_executable(order, seconds, 3, "interval", "pace", fast, slow)
    if interval_unit == "distance":
        midpoint = (pace_min.s_per_km + pace_max.s_per_km) / 2
        step["endCondition"] = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
        step["endConditionValue"] = float(seconds / midpoint * 1000)
    return step


def _make_recovery_step(order, seconds, paces: Paces, interval_unit: str = "time"):
    # Recovery between intervals stays time-based — walkers/joggers need duration, not distance.
    return _step_executable(order, seconds, 4, "recovery", "open")


def _add_cooldown(steps, order, paces: Paces, interval_unit: str = "time"):
    if interval_unit == "distance":
        steps.append(_step_distance(order, _seconds_to_distance_m(COOLDOWN_SEC, paces), 2, "cooldown"))
    else:
        steps.append(_step_executable(order, COOLDOWN_SEC, 2, "cooldown", "open"))


def _build_uniform(wd, paces, display_name=None, profile=None, interval_unit="time"):
    steps, order = _make_warmup_steps(paces, interval_unit=interval_unit)
    rep_step = _make_interval_step(1, wd.interval_sec, wd.pace_min, wd.pace_max, interval_unit=interval_unit)
    rec_step = _make_recovery_step(2, wd.rec_sec, paces)
    steps.append(_step_repeat(order, wd.reps, [rep_step, rec_step]))
    order += 1
    _add_cooldown(steps, order, paces, interval_unit=interval_unit)
    return _build_workout_json(display_name or wd.name, wd.description, steps)


def _build_variable(wd, paces, display_name=None, profile=None, interval_unit="time"):
    steps, order = _make_warmup_steps(paces, interval_unit=interval_unit)
    entry = _get_catalog_workout(wd.name) or {}
    raw_blocks = entry.get("blocks", [])
    if raw_blocks and isinstance(raw_blocks[0], dict):
        blocks = [(b.get("sec", 0), b.get("pace_key", "")) for b in raw_blocks]
    else:
        blocks = WORKOUT_DEFS.get(wd.name, {}).get("blocks", [])
    for sec, pace_key in blocks:
        pace_range = _resolve_pace_range(pace_key, paces, profile=profile)
        if pace_range is None:
            pace_range = (paces.ef[0], paces.ef[1])
        steps.append(_make_interval_step(order, sec, pace_range[0], pace_range[1], interval_unit=interval_unit))
        order += 1
        steps.append(_make_recovery_step(order, wd.rec_sec, paces))
        order += 1
    _add_cooldown(steps, order, paces, interval_unit=interval_unit)
    return _build_workout_json(display_name or wd.name, wd.description, steps)


def _build_progressive(wd, paces, display_name=None, profile=None, interval_unit="time"):
    steps, order = _make_warmup_steps(paces, interval_unit=interval_unit)
    pace_range = _resolve_pace_range(wd.zone.value, paces, profile=profile)
    if pace_range is None:
        pace_range = (paces.ef[0], paces.ef[1])
    n = wd.reps
    for i in range(n):
        t = i / max(n - 1, 1)
        p_min = pace_range[0].scaled(1 - t * 0.02)
        p_max = pace_range[1].scaled(1 - t * 0.02)
        steps.append(_make_interval_step(order, wd.interval_sec, p_min, p_max, interval_unit=interval_unit))
        order += 1
        steps.append(_make_recovery_step(order, wd.rec_sec, paces))
        order += 1
    _add_cooldown(steps, order, paces, interval_unit=interval_unit)
    return _build_workout_json(display_name or wd.name, wd.description, steps)


def _build_distance(wd, paces, display_name=None, profile=None, interval_unit="time"):
    entry = _get_catalog_workout(wd.name) or {}
    distance_m = entry.get("interval_m", 0) or entry.get("distance_m", 0)
    pace_key = entry.get("pace_key", "threshold")
    reps = entry.get("reps", 1)
    rec_sec = entry.get("rec_sec", 90)
    warmup_sec = entry.get("warmup_sec", WARMUP_SEC)
    cooldown_sec = entry.get("cooldown_sec", COOLDOWN_SEC)

    steps = []
    order = 1
    if warmup_sec > 0:
        if interval_unit == "distance":
            steps.append(_step_distance(order, _seconds_to_distance_m(warmup_sec, paces), 1, "warmup"))
        else:
            steps.append(_step_executable(order, warmup_sec, 1, "warmup", "open"))
        order += 1

    pace_range = _resolve_pace_range(pace_key, paces, profile=profile)
    if reps > 1:
        interval_step = _step_distance(1, distance_m, 3, "interval")
        if pace_range:
            interval_step = _step_executable(1, 0, 3, "interval", "pace",
                                              _pace_to_garmin(pace_range[0]),
                                              _pace_to_garmin(pace_range[1]))
            interval_step["endCondition"] = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
            interval_step["endConditionValue"] = float(distance_m)
        rec_step = _make_recovery_step(2, rec_sec, paces)
        steps.append(_step_repeat(order, reps, [interval_step, rec_step]))
        order += 1
    else:
        if pace_range:
            step = _step_executable(order, 0, 3, "interval", "pace",
                                     _pace_to_garmin(pace_range[0]),
                                     _pace_to_garmin(pace_range[1]))
            step["endCondition"] = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
            step["endConditionValue"] = float(distance_m)
            steps.append(step)
        else:
            steps.append(_step_distance(order, distance_m))
        order += 1

    if cooldown_sec > 0:
        if interval_unit == "distance":
            steps.append(_step_distance(order, _seconds_to_distance_m(cooldown_sec, paces), 2, "cooldown"))
        else:
            steps.append(_step_executable(order, cooldown_sec, 2, "cooldown", "open"))
        order += 1

    return _build_workout_json(display_name or wd.name, wd.description, steps)


def _build_time(wd, paces, display_name=None, profile=None, interval_unit="time"):
    entry = _get_catalog_workout(wd.name) or {}
    duration = entry.get("duration_sec", 2700)
    step = _step_executable(1, duration, 3, "interval", "open")
    return _build_workout_json(display_name or wd.name, wd.description, [step])


def _resolve_pace_range(pace_key, paces, profile=None):
    if profile is not None:
        try:
            return resolve_pace(pace_key, profile=profile)
        except ValueError:
            pass
    compat = {"easy": "ef", "ef": "ef", "recovery": "ef",
              "short": "short", "medium": "medium", "long": "long"}
    attr = compat.get(pace_key, pace_key)
    if hasattr(paces, attr):
        return getattr(paces, attr)
    return None


_BUILDERS = {
    "uniform": _build_uniform,
    "variable": _build_variable,
    "progressive": _build_progressive,
    "distance": _build_distance,
    "time": _build_time,
}


def build_garmin_workout(name, paces, display_name=None, profile=None, interval_unit="time"):
    entry = _get_catalog_workout(name)
    if entry:
        structure = entry.get("structure", "uniform")
    else:
        structure = WORKOUT_DEFS.get(name, {}).get("structure", "uniform")
    wd = build_workout(name, paces, profile=profile)
    builder = _BUILDERS.get(structure, _build_uniform)
    return builder(wd, paces, display_name=display_name, profile=profile, interval_unit=interval_unit)


def _build_continuous_workout(display_name, description, distance_km):
    from math import isfinite
    if distance_km is None or not isfinite(distance_km) or distance_km <= 0:
        raise ValueError(f"Distance positive requise pour exporter '{display_name}' vers Garmin sans timer.")
    step = _step_distance(1, distance_km * 1000)
    return _build_workout_json(display_name, description, [step], distance_km=distance_km)


def build_easy_workout(display_name, duration_sec=2700, distance_km=None):
    return _build_continuous_workout(display_name, "Endurance Facile", distance_km)


def build_long_workout(display_name, duration_sec=5400, distance_km=None):
    return _build_continuous_workout(display_name, "Sortie Longue EF", distance_km)


def build_session_workout(session, paces, display_name, profile=None, interval_unit="time"):
    if session.workout:
        entry = _get_catalog_workout(session.workout.name)
        if not entry:
            entry = WORKOUT_DEFS.get(session.workout.name, {})
        structure = entry.get("structure", "uniform")
        if structure == "time":
            return _build_continuous_workout(
                display_name=display_name,
                description=session.workout.description,
                distance_km=session.distance_km,
            )
        workout = build_garmin_workout(
            session.workout.name, paces, display_name=display_name, profile=profile,
            interval_unit=interval_unit,
        )
        distance_m = round(session.distance_km * 1000)
        workout["estimatedDistanceInMeters"] = distance_m
        workout["workoutSegments"][0]["estimatedDistanceInMeters"] = distance_m
        return workout

    if session.type == "long":
        return build_long_workout(display_name, distance_km=session.distance_km)
    return build_easy_workout(display_name, distance_km=session.distance_km)


def create_workout(client, workout_json):
    try:
        result = client.upload_workout(workout_json)
        return True, str(result.get("workoutId", "?"))
    except Exception as e:
        return False, str(e)[:200]


def update_workout(client, workout_id, workout_json):
    try:
        client.update_workout(workout_id, workout_json)
        return True, str(workout_id)
    except Exception as e:
        return False, str(e)[:200]


def schedule_workout(client, workout_id, date_str):
    try:
        client.schedule_workout(workout_id, date_str)
        return True, date_str
    except Exception as e:
        return False, str(e)[:200]


def delete_workout(client, workout_id):
    try:
        if hasattr(client, "delete_workout"):
            client.delete_workout(workout_id)
        else:
            url = f"https://connect.garmin.com/proxy/workout-service/workout/{workout_id}"
            session = getattr(getattr(client, "garth", None), "session", getattr(client, "session", None))
            if session:
                session.delete(url)
            else:
                client.req.delete(url)
        return True, "deleted"
    except Exception as e:
        return False, str(e)[:200]


def fetch_running_activities(client, start_date, end_date):
    activities = client.get_activities_by_date(start_date, end_date, activitytype="running")
    if not activities:
        try:
            recent = client.get_activities(0, 20)
            activities = [
                a for a in recent
                if (a.get("activityType", {}).get("typeKey") == "running"
                    or a.get("activityType") == "running")
            ]
        except Exception:
            pass
    return [
        {
            "id": str(activity["activityId"]),
            "date": activity["startTimeLocal"][:10],
            "time": activity["startTimeLocal"][11:19],
            "name": activity.get("activityName", "Run"),
            "distance_km": round((activity.get("distance") or 0) / 1000, 2),
            "duration_sec": round(activity.get("duration") or 0),
            "workout_id": str(activity["workoutId"]) if activity.get("workoutId") else None,
        }
        for activity in activities
        if activity.get("activityId") and activity.get("startTimeLocal")
    ]


def reconcile_plan_sessions(sessions, activities):
    matches = []
    reviews = []
    unmatched = []
    used_activity_ids = {s["garmin_activity_id"] for s in sessions if s.get("garmin_activity_id")}
    pending = [s for s in sessions if s["status"] not in ("completed", "review", "skipped", "removed") and s["scheduled_date"]]
    exact_session_keys = set()
    for session in pending:
        if not session["garmin_workout_id"]:
            continue
        exact = [a for a in activities if a["id"] not in used_activity_ids and a["workout_id"] == session["garmin_workout_id"]]
        if len(exact) == 1:
            matches.append((session, exact[0]))
            used_activity_ids.add(exact[0]["id"])
            exact_session_keys.add((session["week"], session["day"]))

    for session in pending:
        if (session["week"], session["day"]) in exact_session_keys:
            continue
        scheduled_date = date.fromisoformat(session["scheduled_date"])
        candidates = [
            a for a in activities
            if a["id"] not in used_activity_ids
            and ((bool(session["garmin_workout_id"]) and a["workout_id"] == session["garmin_workout_id"])
                 or scheduled_date - timedelta(days=7) <= date.fromisoformat(a["date"]) <= scheduled_date)
        ]
        if candidates:
            scored = [
                (int(bool(session["garmin_workout_id"]) and a["workout_id"] == session["garmin_workout_id"]) * 3
                 + int(bool(session["distance_km"]) and abs(a["distance_km"] - session["distance_km"]) <= max(1.5, session["distance_km"] * 0.15)) * 2
                 + int(bool(session["workout_name"]) and session["workout_name"].lower() in a["name"].lower()),
                 a)
                for a in candidates
            ]
            best_score = max(score for score, _ in scored)
            best = [a for score, a in scored if score == best_score]
            if best_score >= 2 and len(best) == 1:
                matches.append((session, best[0]))
                used_activity_ids.add(best[0]["id"])
            else:
                reviews.append((session, candidates))
        else:
            unmatched.append(session)

    filtered_reviews = []
    for session, candidates in reviews:
        available = [a for a in candidates if a["id"] not in used_activity_ids]
        if available:
            filtered_reviews.append((session, available))
        else:
            unmatched.append(session)
    return matches, filtered_reviews, unmatched
