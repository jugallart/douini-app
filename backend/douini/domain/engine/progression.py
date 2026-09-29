"""Weekly volume and long-run progression."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Distance, Experience, LONG_RUN_CAPS
from .config import get_distance_rules, get_load_rules, get_progression_rules, resolve_distance

_TAPER_FACTORS = {
    1: [0.50],
    2: [0.70, 0.50],
    3: [0.80, 0.65, 0.50],
}


def _taper_factor(taper_count: int, t_idx: int) -> float:
    if taper_count <= 0:
        return 1.0
    factors = _TAPER_FACTORS.get(taper_count, [0.50])
    return factors[min(t_idx, len(factors) - 1)]


@dataclass
class VolumePlan:
    weekly_km: dict[int, float] = field(default_factory=dict)
    long_run_km: dict[int, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _exp_long_factor(experience: Experience) -> float:
    if experience == Experience.BEGINNER:
        return 0.85
    if experience == Experience.ADVANCED:
        return 1.05
    return 1.0


def _vol_to_load(level: str) -> int:
    return {"low": 2, "moderate": 3, "high": 4}.get(level, 3)


def build_volume_plan(
    distance: Distance,
    weeks: int,
    current_km: float,
    target_km: float,
    recovery_weeks: set[int],
    taper_weeks: set[int],
    taper_count: int,
    phase_for_week: dict[int, str],
    experience: Experience = Experience.INTERMEDIATE,
    current_longest: float | None = None,
    mileage_tolerance_km: int = 0,
    difficulty_factor: float = 1.0,
    volume_strategy: str = "progressive",
) -> VolumePlan:
    """Build weekly volume + long-run progression from current to target."""
    rules = get_load_rules()
    prog = get_progression_rules()

    # Strategy overrides ramp parameters from plan_settings.json
    from .config import get_plan_settings
    settings = get_plan_settings()
    strategies = settings.get("volume_strategies", {})
    strat = strategies.get(volume_strategy, {})
    strat_increase_pct = strat.get("weekly_increase_pct")
    strat_max_consec = strat.get("max_consecutive_increase_weeks")

    max_increase_pct = (strat_increase_pct if strat_increase_pct is not None
                         else prog["volume_progression"]["weekly_increase_pct"]) / 100
    max_consecutive = (strat_max_consec if strat_max_consec is not None
                       else prog["volume_progression"]["max_consecutive_increase_weeks"])
    recovery_reduction = prog["volume_progression"]["recovery_week_reduction_pct"] / 100
    long_increase_km = prog["long_run_progression"]["weekly_increase_km"]
    max_consec_long = prog["long_run_progression"]["max_consecutive_increase_weeks"]

    long_run_ratio = rules["long_run_ratio"].get(resolve_distance(distance.value), 0.30)

    try:
        dist_rules = get_distance_rules(resolve_distance(distance.value))
        long_cap = dist_rules["long_run_cap_km"]
    except (ValueError, KeyError):
        long_cap = LONG_RUN_CAPS[distance]

    # difficulty_factor scales target volume and long-run cap (NOT pace)
    target_km = target_km * difficulty_factor
    volume_cap = target_km + max(0, mileage_tolerance_km)
    exp_factor = _exp_long_factor(experience)

    # --- Weekly volume ramp ---
    weekly_km: dict[int, float] = {}
    consecutive_inc = 0

    for week in range(1, weeks + 1):
        if week in taper_weeks:
            t_idx = week - (weeks - taper_count + 1)
            weekly_km[week] = round(target_km * _taper_factor(taper_count, t_idx), 1)
            consecutive_inc = 0
        elif week in recovery_weeks:
            prev = weekly_km.get(week - 1, target_km)
            weekly_km[week] = round(prev * (1 - recovery_reduction), 1)
            consecutive_inc = 0
        else:
            if week == 1:
                vol = current_km if current_km > 0 else target_km * 0.9
            else:
                prev = weekly_km.get(week - 1, target_km)
                if prev < target_km and consecutive_inc < max_consecutive:
                    increase = min(prev * max_increase_pct, target_km - prev)
                    if increase > 0:
                        vol = round(prev + increase, 1)
                        consecutive_inc += 1
                    else:
                        vol = target_km
                        consecutive_inc = 0
                else:
                    vol = target_km
                    consecutive_inc = 0

            phase = phase_for_week.get(week, "BASE")
            if phase == "BASE":
                vol = min(vol, target_km * 0.9)
            elif phase == "BUILD":
                vol = min(vol, target_km)
            elif phase == "SPECIFIC":
                vol = volume_cap
            weekly_km[week] = round(vol, 1)

    # --- Long run progression ---
    long_run_km: dict[int, float] = {}
    start_long = current_longest if current_longest and current_longest > 0 else min(long_cap * 0.6, 10.0)
    consecutive_long = 0

    for week in range(1, weeks + 1):
        if week in taper_weeks:
            t_idx = week - (weeks - taper_count + 1)
            long_run_km[week] = round(max(long_cap * 0.6 * _taper_factor(taper_count, t_idx), 5.0), 1)
            consecutive_long = 0
        elif week in recovery_weeks:
            prev = long_run_km.get(week - 1, start_long)
            long_run_km[week] = round(max(prev * 0.8, 5.0), 1)
            consecutive_long = 0
        else:
            if week == 1:
                lr = start_long
            else:
                prev = long_run_km.get(week - 1, start_long)
                target_long = min(long_cap * exp_factor, weekly_km.get(week, target_km) * long_run_ratio)
                if prev < target_long and consecutive_long < max_consec_long:
                    lr = min(prev + long_increase_km, target_long)
                    consecutive_long += 1
                else:
                    lr = prev
                    consecutive_long = 0
            lr = min(lr, long_cap * exp_factor)
            long_run_km[week] = round(max(lr, 5.0), 1)

    # --- Warnings ---
    warnings: list[str] = []
    if current_km > 0 and current_km < target_km * 0.5:
        ramp_weeks_needed = 0
        v = current_km
        while v < target_km * 0.9 and ramp_weeks_needed < weeks:
            v += v * max_increase_pct
            ramp_weeks_needed += 1
        if ramp_weeks_needed > weeks * 0.5:
            warnings.append(
                f"Volume ramp from {current_km:.0f}km to {target_km:.0f}km requires "
                f"~{ramp_weeks_needed} weeks (>50% of plan)."
            )

    return VolumePlan(weekly_km=weekly_km, long_run_km=long_run_km, warnings=warnings)
