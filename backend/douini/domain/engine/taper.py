"""Taper and race week generation."""

from __future__ import annotations

from ..models import Distance, Paces, Session, Zone
from .config import get_distance_rules, resolve_distance
from .library import get_workout, build_workout_def
from .progression import _taper_factor

_RACE_WORKOUT = {
    Distance.K5: "RACE-5K",
    Distance.K10: "RACE-10K",
    Distance.SEMI: "RACE-HM",
    Distance.MARATHON: "RACE-MARATHON",
}

_TAPER_QUALITY = {
    Distance.K5: "NS-S01",
    Distance.K10: "NS-M01",
    Distance.SEMI: "NS-M01",
    Distance.MARATHON: "NS-L01",
}


def _easy_session(day: str, distance_km: float = 10.0) -> Session:
    return Session(
        day=day,
        type="easy",
        structure=f"EF {int(distance_km)}km",
        distance_km=distance_km,
    )


def _long_session(day: str, km: float) -> Session:
    return Session(
        day=day,
        type="long",
        structure="Sortie longue - EF",
        distance_km=max(round(km, 1), 5.0),
    )


def _quality_session(name: str, paces: Paces, day: str, profile=None) -> Session:
    wd = build_workout_def(name, paces, profile=profile)
    return Session(
        day=day,
        workout=wd,
        type="quality",
        structure=wd.description,
        distance_km=12.0,  # estimated; volume adjustment scales this
    )


def generate_taper_week(
    week_num: int,
    weeks_total: int,
    taper_count: int,
    t_idx: int,
    distance: Distance,
    paces: Paces,
    long_run_day: str,
    quality_days: list[str],
    easy_days: list[str],
    long_run_km: float,
    weekly_km: float,
    is_race_week: bool = False,
    profile=None,
) -> list[Session]:
    """Generate sessions for a taper week."""
    t_factor = _taper_factor(taper_count, t_idx)
    sessions: list[Session] = []

    if is_race_week:
        return _generate_race_week(
            distance, paces, long_run_day, quality_days, easy_days, long_run_km, weekly_km,
            profile=profile,
        )

    # Non-race taper week: 1 quality (light) + easy + long (reduced)
    q_day = quality_days[0] if quality_days else "mon"
    taper_name = _TAPER_QUALITY.get(distance, "NS-S01")
    sessions.append(_quality_session(taper_name, paces, q_day, profile=profile))

    for e_day in easy_days:
        base = max(round(10.0 * t_factor, 1), 3.0)
        sessions.append(_easy_session(e_day, base))

    # Additional easy days for extra quality slots
    for q_day_extra in quality_days[1:]:
        sessions.append(_easy_session(q_day_extra, max(round(8.0 * t_factor, 1), 3.0)))

    long_km = max(round(long_run_km * t_factor, 1), 5.0)
    sessions.append(_long_session(long_run_day, long_km))

    sessions.sort(key=lambda s: {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}.get(s.day, 0))
    return sessions


def _generate_race_week(
    distance: Distance,
    paces: Paces,
    long_run_day: str,
    quality_days: list[str],
    easy_days: list[str],
    long_run_km: float,
    weekly_km: float,
    profile=None,
) -> list[Session]:
    """Generate race week: easy days + light quality + race on long-run day."""
    sessions: list[Session] = []

    # Light quality session early in the week
    q_day = quality_days[0] if quality_days else "mon"
    taper_name = _TAPER_QUALITY.get(distance, "NS-S01")
    sessions.append(_quality_session(taper_name, paces, q_day, profile=profile))

    # Easy days
    for e_day in easy_days:
        sessions.append(_easy_session(e_day, 8.0))

    # Extra quality days become easy
    for q_day_extra in quality_days[1:]:
        sessions.append(_easy_session(q_day_extra, 8.0))

    # Race session on long-run day
    race_id = _RACE_WORKOUT.get(distance, "RACE-HM")
    race_entry = get_workout(race_id)
    race_dist_km = 0.0
    if race_entry:
        # Estimate race distance in km from metres
        try:
            did = resolve_distance(distance.value)
            rules = get_distance_rules(did)
            race_dist_km = rules["metres"] / 1000.0
        except (ValueError, KeyError):
            pass

    sessions.append(Session(
        day=long_run_day,
        type="race",
        structure=f"COURSE - {distance.value.upper()}",
        distance_km=max(race_dist_km, 5.0),
        workout=build_workout_def(race_id, paces, profile=profile) if get_workout(race_id) else None,
    ))

    sessions.sort(key=lambda s: {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}.get(s.day, 0))
    return sessions
