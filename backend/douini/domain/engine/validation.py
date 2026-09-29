"""Nine coherence validations + ordered auto-corrections for training plans.

Validation rules loaded from validation_rules.json.
Corrections follow order: lighten session → reduce reps → reduce duration →
replace with easy → reduce long run → adjust volume.
"""

from __future__ import annotations

from ..models import (
    Distance,
    Experience,
    LONG_RUN_CAPS,
    PlanWarning,
    RunnerProfile,
    Session,
    TrainingPhase,
    TrainingPlan,
    WeekPlan,
    VOLUME_CAPS,
)
from .config import get_validation_rules, get_distance_rules, get_load_rules
from .library import get_workout_zone, get_catalog
from .load import compute_session_load, annotate_plan
from .pace_engine import GoalFeasibilityChecker, PaceValidator


# Category load coefficients for auto-correction
_LOAD_BY_TYPE = {"easy": 0.3, "long": 0.5, "quality": 0.7, "race": 0.9, "rest": 0.0}

# Max correction iterations
_MAX_CORRECTIONS = 20


def validate_plan(plan: TrainingPlan) -> list[PlanWarning]:
    """Run all nine coherence checks. Returns list of PlanWarning."""
    rules = get_validation_rules()
    check_ids = {c["id"]: c for c in rules["checks"]}
    warnings: list[PlanWarning] = []

    runner = plan.runner
    volume_cap = runner.volume_cap or VOLUME_CAPS.get(plan.distance, 75)
    catalog = get_catalog()

    for week in plan.week_plans:
        is_taper = week.phase == TrainingPhase.TAPER
        is_recovery = week.is_recovery

        # 1. volume_ceiling
        if not is_taper and week.total_km > volume_cap + 5:
            warnings.append(PlanWarning(
                code="volume_ceiling",
                message=f"W{week.week_num}: {week.total_km}km exceeds cap {volume_cap}km",
                severity=check_ids["volume_ceiling"]["severity"],
            ))

        # 2. long_run_cap
        long_cap = LONG_RUN_CAPS.get(plan.distance, 30)
        for s in week.sessions:
            if s.type == "long" and s.distance_km > long_cap + 1:
                warnings.append(PlanWarning(
                    code="long_run_cap",
                    message=f"W{week.week_num}: long run {s.distance_km}km exceeds cap {long_cap}km",
                    severity=check_ids["long_run_cap"]["severity"],
                ))

        # 3. quality_session_count
        quality_count = sum(1 for s in week.sessions if s.type == "quality")
        spw = plan.sessions_per_week
        expected_max = 3 if spw >= 6 else 2
        if not is_taper and quality_count > expected_max:
            warnings.append(PlanWarning(
                code="quality_session_count",
                message=f"W{week.week_num}: {quality_count} quality sessions (max {expected_max})",
                severity=check_ids["quality_session_count"]["severity"],
            ))

        # 4. recovery_week_volume
        if is_recovery and week.week_num > 1:
            prev = plan.week_plans[week.week_num - 2]
            if week.total_km > prev.total_km * 0.9:
                warnings.append(PlanWarning(
                    code="recovery_week_volume",
                    message=f"W{week.week_num}: recovery week {week.total_km}km >= prev {prev.total_km}km",
                    severity=check_ids["recovery_week_volume"]["severity"],
                ))

        # 5. taper_volume (progressive reduction)
        if is_taper and week.week_num > 1:
            prev = plan.week_plans[week.week_num - 2]
            if prev.phase != TrainingPhase.TAPER:
                # First taper week should be < last loading week
                if week.total_km > prev.total_km * 0.85:
                    warnings.append(PlanWarning(
                        code="taper_volume",
                        message=f"W{week.week_num}: taper {week.total_km}km not reduced from {prev.total_km}km",
                        severity=check_ids["taper_volume"]["severity"],
                    ))
            else:
                # Subsequent taper weeks should continue decreasing
                if week.total_km > prev.total_km:
                    warnings.append(PlanWarning(
                        code="taper_volume",
                        message=f"W{week.week_num}: taper {week.total_km}km increased from {prev.total_km}km",
                        severity=check_ids["taper_volume"]["severity"],
                    ))

        # 6. session_spacing
        quality_days = [s.day for s in week.sessions if s.type == "quality"]
        day_order = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        if len(quality_days) >= 2:
            sorted_qd = sorted(quality_days, key=lambda d: day_order.get(d, 0))
            for i in range(len(sorted_qd) - 1):
                gap = day_order[sorted_qd[i + 1]] - day_order[sorted_qd[i]]
                if gap < 2:
                    warnings.append(PlanWarning(
                        code="session_spacing",
                        message=f"W{week.week_num}: quality sessions {sorted_qd[i]}-{sorted_qd[i+1]} <24h apart",
                        severity=check_ids["session_spacing"]["severity"],
                    ))

        # 7. long_run_day
        long_run_day = runner.long_run_day or "sun"
        has_long = any(s.type == "long" for s in week.sessions)
        long_on_day = any(s.type == "long" and s.day == long_run_day for s in week.sessions)
        if has_long and not long_on_day:
            warnings.append(PlanWarning(
                code="long_run_day",
                message=f"W{week.week_num}: long run not on {long_run_day}",
                severity=check_ids["long_run_day"]["severity"],
            ))

        # 8. norwegian_zone_match (quality workouts should be NS- prefix)
        for s in week.sessions:
            if s.type == "quality" and s.workout:
                name = s.workout.name
                if not name.startswith("NS-") and not name.startswith("5K-") and not name.startswith("10K-") and not name.startswith("HM-") and not name.startswith("MAR-"):
                    warnings.append(PlanWarning(
                        code="norwegian_zone_match",
                        message=f"W{week.week_num}: {name} not in NS/race-specific catalog",
                        severity=check_ids["norwegian_zone_match"]["severity"],
                    ))

    # 10. pace_ordering (run PaceValidator on profile if present)
    if plan.pace_profile:
        try:
            findings = PaceValidator.validate(plan.pace_profile)
            for f in findings:
                warnings.append(PlanWarning(
                    code="pace_ordering",
                    message=f,
                    severity=check_ids.get("pace_ordering", {"severity": "warning"})["severity"],
                ))
        except Exception:
            pass

    # 11. workout_classification (pace_key must match workout method)
    _NS_PACE_KEYS = {"short", "medium", "long"}
    _RACE_PACE_KEYS = {"5K", "10K", "HM", "MARATHON", "threshold", "vo2", "economy"}
    for week in plan.week_plans:
        for s in week.sessions:
            if s.type != "quality" or not s.workout:
                continue
            name = s.workout.name
            cat_entry = catalog.get(name)
            if not cat_entry:
                continue
            pk = cat_entry.get("pace_key", "")
            is_ns = name.startswith("NS-")
            if is_ns and pk not in _NS_PACE_KEYS:
                warnings.append(PlanWarning(
                    code="workout_classification",
                    message=f"W{week.week_num}: {name} is NS but pace_key='{pk}' (expected short/medium/long)",
                    severity=check_ids.get("workout_classification", {"severity": "warning"})["severity"],
                ))
            if not is_ns and pk and pk not in _RACE_PACE_KEYS and pk not in _NS_PACE_KEYS:
                warnings.append(PlanWarning(
                    code="workout_classification",
                    message=f"W{week.week_num}: {name} race-specific but pace_key='{pk}'",
                    severity=check_ids.get("workout_classification", {"severity": "warning"})["severity"],
                ))

    # 12. phase_specificity (workout phases must include current week's phase)
    for week in plan.week_plans:
        phase_str = week.phase.value if week.phase else ""
        if not phase_str or phase_str == "TAPER":
            continue
        for s in week.sessions:
            if s.type != "quality" or not s.workout:
                continue
            cat_entry = catalog.get(s.workout.name)
            if not cat_entry:
                continue
            workout_phases = cat_entry.get("phases", [])
            if workout_phases and phase_str not in workout_phases:
                warnings.append(PlanWarning(
                    code="phase_specificity",
                    message=f"W{week.week_num}: {s.workout.name} tagged {workout_phases} but week is {phase_str}",
                    severity=check_ids.get("phase_specificity", {"severity": "warning"})["severity"],
                ))

    # 13. vdot_gap_warning
    if plan.plan_vdot is not None:
        current = getattr(runner, "effective_vdot", runner.vdot)
        gap = abs(current - plan.plan_vdot)
        if gap > 2.0:
            warnings.append(PlanWarning(
                code="vdot_gap_warning",
                message=f"Plan VDOT {plan.plan_vdot:.1f} vs current {current:.1f} (gap {gap:.1f})",
                severity="info",
            ))

    # 9. vdot_feasibility
    if runner.race_distance and runner.target_time:
        try:
            result = GoalFeasibilityChecker.check(runner.vdot, runner.race_distance, runner.target_time)
            if result.status.value in ("aggressive", "unrealistic"):
                warnings.append(PlanWarning(
                    code="vdot_feasibility",
                    message=f"VDOT gap {result.vdot_gap:+.1f}: {result.warning}",
                    severity=check_ids["vdot_feasibility"]["severity"],
                ))
        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique: list[PlanWarning] = []
    for w in warnings:
        key = (w.code, w.message)
        if key not in seen:
            seen.add(key)
            unique.append(w)

    return unique


def check_feasibility(runner: RunnerProfile, distance: Distance, weeks: int) -> list[PlanWarning]:
    """Pre-generation feasibility checks for profile + plan parameters."""
    from ..models import MIN_WEEKS
    warnings: list[PlanWarning] = []

    # Duration minimum
    if weeks < MIN_WEEKS.get(distance, 4):
        warnings.append(PlanWarning(
            code="duration_minimum",
            message=f"{weeks} weeks below minimum {MIN_WEEKS[distance]} for {distance.value}",
            severity="error",
        ))

    # Current volume feasibility
    target_vol = runner.target_weekly_km or runner.weekly_volume_km
    current_vol = runner.current_weekly_km or target_vol

    if current_vol < target_vol * 0.5 and weeks <= MIN_WEEKS.get(distance, 4) + 2:
        warnings.append(PlanWarning(
            code="volume_gap",
            message=f"Current {current_vol}km << target {target_vol}km, ramp too short for {weeks}w",
            severity="error",
        ))

    # Long run feasibility
    long_cap = LONG_RUN_CAPS.get(distance, 30)
    current_long = runner.current_longest_run or 0
    if current_long > 0 and current_long < long_cap * 0.4 and weeks <= 8:
        warnings.append(PlanWarning(
            code="long_run_gap",
            message=f"Current longest {current_long}km << cap {long_cap}km, too aggressive for {weeks}w",
            severity="warning",
        ))

    # VDOT feasibility (only if goal time provided)
    if runner.race_distance and runner.target_time:
        try:
            result = GoalFeasibilityChecker.check(runner.vdot, runner.race_distance, runner.target_time)
            if result.status.value == "unrealistic":
                warnings.append(PlanWarning(
                    code="vdot_feasibility",
                    message=f"VDOT gap {result.vdot_gap:+.1f} unrealistic. {result.warning}",
                    severity="error",
                ))
            elif result.status.value == "aggressive":
                warnings.append(PlanWarning(
                    code="vdot_feasibility",
                    message=f"VDOT gap {result.vdot_gap:+.1f} aggressive. {result.warning}",
                    severity="warning",
                ))
        except Exception:
            pass

    return warnings


def auto_correct(plan: TrainingPlan) -> tuple[TrainingPlan, list[str]]:
    """Apply ordered corrections to a plan. Returns (plan, corrections_log).

    Order: lighten session → reduce reps → reduce duration →
           replace with easy → reduce long run → adjust volume.
    """
    corrections: list[str] = []
    warnings = validate_plan(plan)

    for _ in range(_MAX_CORRECTIONS):
        if not warnings:
            break

        # Find first actionable warning (errors + correctable warnings)
        actionable = [w for w in warnings if w.severity == "error" or w.code in ("volume_ceiling", "vdot_feasibility")]
        if not actionable:
            # Only warnings/info remain — not correctable
            break

        w = actionable[0]
        corrected = False

        if w.code == "volume_ceiling":
            # Reduce easy/long session distances
            for week in plan.week_plans:
                if week.total_km > (plan.runner.volume_cap or 75) + 5:
                    adjustable = [s for s in week.sessions if s.type in ("easy", "long")]
                    for s in sorted(adjustable, key=lambda s: s.distance_km, reverse=True):
                        if week.total_km <= (plan.runner.volume_cap or 75) + 5:
                            break
                        reduce = min(2.0, s.distance_km * 0.2)
                        s.distance_km = round(s.distance_km - reduce, 1)
                        corrected = True
                    week.total_km = round(sum(s.distance_km for s in week.sessions), 1)
            if corrected:
                corrections.append(f"volume_ceiling: reduced session distances")

        elif w.code == "recovery_week_volume":
            for week in plan.week_plans:
                if week.is_recovery and week.week_num > 1:
                    prev = plan.week_plans[week.week_num - 2]
                    if week.total_km > prev.total_km * 0.9:
                        scale = prev.total_km * 0.8 / max(week.total_km, 1.0)
                        for s in week.sessions:
                            if s.type not in ("quality", "race"):
                                s.distance_km = round(s.distance_km * scale, 1)
                        week.total_km = round(sum(s.distance_km for s in week.sessions), 1)
                        corrected = True
            if corrected:
                corrections.append(f"recovery_week_volume: scaled down recovery week")

        elif w.code == "taper_volume":
            for week in plan.week_plans:
                if week.phase == TrainingPhase.TAPER and week.week_num > 1:
                    prev = plan.week_plans[week.week_num - 2]
                    if week.total_km > prev.total_km * 0.85:
                        scale = prev.total_km * 0.75 / max(week.total_km, 1.0)
                        for s in week.sessions:
                            if s.type not in ("quality", "race"):
                                s.distance_km = round(s.distance_km * scale, 1)
                        week.total_km = round(sum(s.distance_km for s in week.sessions), 1)
                        corrected = True
            if corrected:
                corrections.append(f"taper_volume: reduced taper week volume")

        elif w.code == "duration_minimum":
            # Cannot correct — structural constraint
            corrections.append(f"duration_minimum: cannot auto-correct, needs more weeks")
            break

        elif w.code == "volume_gap":
            corrections.append(f"volume_gap: cannot auto-correct, reduce target volume or extend plan")
            break

        elif w.code == "vdot_feasibility":
            corrections.append(f"vdot_feasibility: cannot auto-correct, adjust goal time")
            break

        if not corrected:
            break

        warnings = validate_plan(plan)

    # Re-annotate loads after corrections
    exp = plan.runner.experience if hasattr(plan.runner, "experience") else Experience.INTERMEDIATE
    annotate_plan(plan.week_plans, exp)

    # Append unresolved warnings to plan
    plan.warnings.extend(warnings)

    return plan, corrections
