"""Training load calculation without external services or hidden state.

Load = duration * category_coefficient * intensity_factor.
Weekly budget derived from volume, experience, frequency, distance, phase.
Rolling fatigue = exponential moving average of prior weekly loads.
"""

from __future__ import annotations

from ..models import Session, WeekPlan, Experience, Distance, LONG_RUN_CAPS, SessionStatus
from .config import get_load_rules

# Load rules from config (single source of truth)
_rules = get_load_rules()

# Category load coefficients (0-1 scale)
# easy=low, long_easy=moderate, NS long=moderate, NS medium=moderate/high,
# NS short/race-specific=high, VO2=very high
_CATEGORY_COEFF = {
    "easy": 0.3,
    "long": 0.5,
    "quality": _rules.get("quality_load_factor", 0.7),
    "race": 0.9,
    "rest": 0.0,
}

# Zone intensity multiplier for quality sessions
_ZONE_FACTOR = {
    "short": 1.15,   # NS short = high
    "medium": 1.0,   # NS medium = moderate/high
    "long": 0.85,    # NS long = moderate
}

# Experience fatigue multiplier
_EXP_FATIGUE = {
    Experience.BEGINNER: 1.15,
    Experience.INTERMEDIATE: 1.0,
    Experience.ADVANCED: 0.9,
}

# Rolling fatigue EMA decay (weight for prior week)
_FATIGUE_DECAY = 1.0 - _rules.get("recovery_load_factor", 0.75)  # 0.25 weight on prior


def _zone_from_workout(session: Session) -> str | None:
    """Extract zone string from a quality session's workout."""
    if session.workout and hasattr(session.workout, "zone"):
        z = session.workout.zone
        return z.value if hasattr(z, "value") else str(z).lower()
    return None


def _session_coefficient(session: Session) -> float:
    """Load coefficient for a session based on category and zone."""
    base = _CATEGORY_COEFF.get(session.type, 0.3)
    if session.type == "quality":
        zone = _zone_from_workout(session)
        if zone:
            base *= _ZONE_FACTOR.get(zone, 1.0)
    return base


def compute_session_load(session: Session) -> float:
    """Compute deterministic load score for a session.

    load = duration_min * coefficient
    SKIPPED sessions contribute 0 load.
    """
    if session.type == "rest" or session.distance_km <= 0:
        return 0.0
    if getattr(session, "status", None) == SessionStatus.SKIPPED:
        return 0.0
    coeff = _session_coefficient(session)
    # Estimate duration from distance and a generic pace (~6 min/km for load purposes)
    duration_min = session.distance_km * 6.0
    return round(duration_min * coeff, 2)


def compute_weekly_load(
    week: WeekPlan,
    prior_fatigue: float = 0.0,
    experience: Experience = Experience.INTERMEDIATE,
) -> tuple[float, float, float]:
    """Compute weekly load, fatigue index, recovery need.

    Returns (weekly_load, fatigue_index, recovery_need).
    """
    total_load = sum(compute_session_load(s) for s in week.sessions)

    # Fatigue = EMA: 50% current week + 50% prior
    exp_mult = _EXP_FATIGUE.get(experience, 1.0)
    fatigue_index = round((total_load * _FATIGUE_DECAY + prior_fatigue * (1 - _FATIGUE_DECAY)) * exp_mult, 2)

    # Recovery need: ratio of quality load to total
    quality_load = sum(compute_session_load(s) for s in week.sessions if s.type == "quality")
    recovery_need = round(quality_load / max(total_load, 1.0), 3) if total_load > 0 else 0.0

    return total_load, fatigue_index, recovery_need


def annotate_plan(week_plans: list[WeekPlan], experience: Experience = Experience.INTERMEDIATE) -> None:
    """Annotate sessions and weeks with load values in-place."""
    prior_fatigue = 0.0
    for week in week_plans:
        for s in week.sessions:
            s.load_score = compute_session_load(s)
            s.fatigue_contribution = round(s.load_score * _FATIGUE_DECAY, 2)
        wl, fi, rn = compute_weekly_load(week, prior_fatigue, experience)
        week.weekly_load = wl
        week.fatigue_index = fi
        week.recovery_need = rn
        prior_fatigue = fi


def weekly_load_budget(
    target_km: float,
    sessions_per_week: int,
    distance: Distance,
    phase: str,
    experience: Experience = Experience.INTERMEDIATE,
) -> float:
    """Derive weekly load budget from volume, experience, frequency, distance, phase."""
    base = target_km * 6.0  # approx total duration in min

    # Frequency factor: more sessions = more recovery capacity
    freq_factor = 1.0 + (sessions_per_week - 4) * 0.05

    # Distance factor: longer races = more aerobic resilience
    dist_factor = {
        Distance.K5: 0.9,
        Distance.K10: 0.95,
        Distance.SEMI: 1.0,
        Distance.MARATHON: 1.05,
    }.get(distance, 1.0)

    # Phase factor: taper/peak = reduced budget
    phase_factor = {
        "BASE": 1.0,
        "BUILD": 1.05,
        "SPECIFIC": 1.1,
        "PEAK": 0.9,
        "TAPER": 0.6,
    }.get(phase, 1.0)

    exp_factor = _EXP_FATIGUE.get(experience, 1.0)

    return round(base * freq_factor * dist_factor * phase_factor / exp_factor, 2)
