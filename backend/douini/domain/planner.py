"""Plan generation engine — Norwegian Singles method.

Pipeline: periodization → progression → week_structure → selection → taper.
"""

from __future__ import annotations

from .models import (
    DEFAULT_DAYS,
    DAY_OFFSET,
    Distance,
    Experience,
    Pace,
    Paces,
    PlanSettings,
    RunnerProfile,
    SelectionExplanation,
    SESSION_DAYS,
    Session,
    TAPER_WEEKS,
    TrainingPhase,
    TrainingPlan,
    WeekPlan,
    WorkoutDef,
    Zone,
)

# ---------------------------------------------------------------------------
# 18 canonical workout definitions (loaded from catalog via library)
# ---------------------------------------------------------------------------

from .engine.library import get_catalog as _get_catalog

def _build_workout_defs() -> dict:
    cat = _get_catalog()
    defs = {}
    for wid in sorted(cat.keys()):
        if not wid.startswith("NS-"):
            continue
        e = cat[wid]
        zone_str = e.get("zone", "SHORT")
        zone = Zone(zone_str.lower()) if zone_str.lower() in ("short", "medium", "long") else Zone.SHORT
        d = dict(
            zone=zone,
            reps=e.get("reps", 0),
            interval_sec=e.get("interval_sec", 0),
            pace_key=e.get("pace_key", "short"),
            rec_sec=e.get("rec_sec", 60),
            desc=e.get("description", ""),
            structure=e.get("structure", "uniform"),
        )
        if e.get("blocks"):
            d["blocks"] = [(b["sec"], b["pace_key"]) for b in e["blocks"]]
        defs[wid] = d
    return defs

WORKOUT_DEFS = _build_workout_defs()
ALL_WORKOUT_NAMES = list(WORKOUT_DEFS.keys())


def build_workout(name: str, paces: Paces, profile=None) -> WorkoutDef:
    from .engine.library import build_workout_def
    return build_workout_def(name, paces, profile=profile)


# ---------------------------------------------------------------------------
# Compat wrappers (delegate to engine modules)
# ---------------------------------------------------------------------------

from .engine import periodization, progression, selection, taper as taper_mod, week_structure
from .engine.config import resolve_distance


def get_plan_structure(distance: Distance, weeks: int, name: str | None = None) -> tuple[int, set[int], set[int]]:
    """Legacy: returns (taper_count, recovery_weeks, taper_weeks)."""
    return periodization.get_plan_structure(distance, weeks, name)


def select_quality_days(training_days: list[str], max_quality: int = 2) -> tuple[str, list[str], list[str]]:
    """Legacy: returns (long_run_day, quality_days, easy_days)."""
    return week_structure.select_quality_days(training_days, max_quality)


# ---------------------------------------------------------------------------
# Session helpers (used by new pipeline)
# ---------------------------------------------------------------------------

def _estimate_quality_distance(wd: WorkoutDef, paces: Paces) -> float:
    warmup_km = (1200 / paces.ef[1].s_per_km) * 1000 / 1000
    cooldown_km = (1200 / paces.ef[1].s_per_km) * 1000 / 1000
    work_km = (wd.work_time_sec / wd.pace_min.s_per_km) * 1000 / 1000
    rec_km = (wd.reps * wd.rec_sec / paces.ef[1].s_per_km) * 1000 / 1000
    strides_km = 0.5
    return round(warmup_km + work_km + rec_km + cooldown_km + strides_km, 1)


def _quality_session(name: str, paces: Paces, day: str, profile=None) -> Session:
    wd = build_workout(name, paces, profile=profile)
    dist = _estimate_quality_distance(wd, paces)
    return Session(day=day, workout=wd, type="quality", structure=wd.description, distance_km=dist)


def _easy_session(day: str, distance_km: float = 12.0) -> Session:
    return Session(day=day, type="easy", structure=f"EF {int(distance_km)}km", distance_km=distance_km)


def _long_session(day: str, km: float) -> Session:
    return Session(day=day, type="long", structure="Sortie longue - EF", distance_km=max(round(km, 1), 5.0))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_DAY_SORT = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _vol_level(km: float) -> str:
    if km < 40:
        return "low"
    if km <= 60:
        return "moderate"
    return "high"


def _freq_level(spw: int) -> str:
    if spw == 3:
        return "low"
    if spw <= 5:
        return "moderate"
    return "high"


def generate_plan(
    runner: RunnerProfile,
    distance: Distance,
    weeks: int = 12,
    paces: Paces | None = None,
    sessions_per_week: int = 4,
    training_days: list[str] | None = None,
    interval_adapted: bool = False,
    start_date=None,
    name: str | None = None,
    quality_sessions: int | None = None,
    difficulty_level: str | None = None,
    volume_strategy: str | None = None,
    settings: PlanSettings | None = None,
) -> TrainingPlan:
    """Generate a full training plan using the deterministic pipeline."""
    # 1. Resolve paces via PaceEngine (12-zone PaceProfile)
    from .engine.pace_engine import PaceEngine
    if settings is None:
        settings = PlanSettings(
            target_weekly_km=runner.target_weekly_km,
            sessions_per_week=sessions_per_week,
            training_days=training_days,
            long_run_day=runner.long_run_day,
            quality_sessions=quality_sessions if quality_sessions is not None else runner.quality_sessions,
            difficulty_level=difficulty_level or runner.difficulty_level,
            volume_strategy=volume_strategy or runner.volume_strategy,
            interval_adapted=interval_adapted,
            target_time=runner.target_time,
        )
    plan_vdot = runner.effective_vdot
    pace_profile = PaceEngine(plan_vdot).build_profile()
    if paces is None:
        if runner.paces and plan_vdot == runner.vdot:
            paces = runner.paces
        else:
            paces = pace_profile.to_paces()

    # Resolve new params from runner profile if not passed explicitly
    qs = settings.quality_sessions
    vstrat = settings.volume_strategy.value if hasattr(settings.volume_strategy, "value") else settings.volume_strategy

    # 2. Resolve days and sessions_per_week
    if settings.training_days:
        days = settings.training_days
        spw = len(days)
    elif settings.sessions_per_week:
        days = SESSION_DAYS.get(settings.sessions_per_week, runner.training_days or DEFAULT_DAYS)
        spw = settings.sessions_per_week
    else:
        days = runner.training_days or DEFAULT_DAYS
        spw = len(days)

    # 3. Allocate phases
    perio = periodization.allocate(distance, weeks, name)

    # 4. Build volume plan
    target_vol = float(settings.target_weekly_km or runner.weekly_volume_km)
    current_vol = float(runner.current_weekly_km or target_vol)
    vol_plan = progression.build_volume_plan(
        distance, weeks, current_vol, target_vol,
        perio.recovery_weeks, perio.taper_weeks, perio.taper_count,
        perio.phase_for_week, runner.experience, runner.current_longest_run,
        runner.mileage_tolerance_km,
        difficulty_factor=settings.difficulty_factor,
        volume_strategy=vstrat,
    )

    # 5. Week structure is now computed per-week inside the loop
    # (adaptive engine evaluates templates A/B/C based on phase, load, etc.)

    volume_cap = target_vol + max(0, runner.mileage_tolerance_km)
    vol_level = _vol_level(target_vol)
    freq_level = _freq_level(spw)

    # 6. Generate weeks
    week_plans: list[WeekPlan] = []
    selection_trace: dict[int, list[SelectionExplanation]] = {}
    history: list[str] = []
    prev_template_id = ""
    prev_weekly_load = 0.0

    for week_num in range(1, weeks + 1):
        phase = perio.phase_for_week.get(week_num, "BASE")
        is_recovery = week_num in perio.recovery_weeks
        is_taper = week_num in perio.taper_weeks
        is_race_week = is_taper and week_num == weeks

        bloc = perio.bloc_for_week(week_num)
        weekly_target = vol_plan.weekly_km.get(week_num, target_vol)
        long_target = vol_plan.long_run_km.get(week_num, 10.0)

        # Per-week adaptive structure
        ws = week_structure.choose_week_structure(
            sessions_per_week=spw,
            days=days,
            long_run_day=settings.long_run_day,
            distance=distance,
            phase=phase,
            week_num=week_num,
            weeks_total=weeks,
            weekly_volume=weekly_target,
            interval_adapted=settings.interval_adapted,
            previous_week_load=prev_weekly_load,
            previous_template_id=prev_template_id,
            runner_experience=runner.experience,
            quality_sessions=qs,
        )
        prev_template_id = ws.template_id

        if is_taper:
            t_idx = week_num - (weeks - perio.taper_count + 1)
            sessions = taper_mod.generate_taper_week(
                week_num, weeks, perio.taper_count, t_idx,
                distance, paces, ws.long_run_day,
                ws.quality_days, ws.easy_days,
                long_target, weekly_target, is_race_week,
                profile=pace_profile,
            )
        elif is_recovery:
            sessions = []
            base_easy = max(round(weekly_target / spw * 0.8, 1), 3.0)
            for q_day in ws.quality_days:
                sessions.append(_easy_session(q_day, base_easy))
            for e_day in ws.easy_days:
                sessions.append(_easy_session(e_day, base_easy))
            sessions.append(_long_session(ws.long_run_day, long_target))
        else:
            # Loading week: select workouts
            ctx = selection.SelectionContext(
                distance=resolve_distance(distance.value),
                phase=phase,
                week_num=week_num,
                weeks_total=weeks,
                weeks_to_race=weeks - week_num + 1,
                quality_count=ws.quality_count,
                sessions_per_week=spw,
                volume_level=vol_level,
                frequency_level=freq_level,
                experience=(runner.experience.value if hasattr(runner.experience, "value") else str(runner.experience)),
                history=list(history),
            )
            selected = selection.select_multiple(ctx, ws.quality_count)

            sessions = []
            q_days = ws.quality_days
            for i in range(ws.quality_count):
                if i < len(selected) and i < len(q_days):
                    sw = selected[i]
                    sessions.append(_quality_session(sw.workout_id, paces, q_days[i], profile=pace_profile))
                    selection_trace.setdefault(week_num, []).append(
                        SelectionExplanation(
                            workout_id=sw.workout_id, score=sw.score, reason=sw.reason,
                        )
                    )
                elif i < len(q_days):
                    sessions.append(_easy_session(q_days[i], 10.0))

            for e_day in ws.easy_days:
                sessions.append(_easy_session(e_day, 10.0))

            sessions.append(_long_session(ws.long_run_day, long_target))

        sessions.sort(key=lambda s: _DAY_SORT.get(s.day, 0))

        # Volume adjustment (same logic as legacy)
        quality_km = sum(s.distance_km for s in sessions if s.type == "quality")
        if not is_taper and quality_km > volume_cap:
            raise ValueError(
                f"Weekly volume {volume_cap:g} km is below the plan's quality workload"
            )

        effective_cap = weekly_target
        total = sum(s.distance_km for s in sessions)
        adjustable = [s for s in sessions if s.type not in ("quality", "race")]

        if adjustable and total != effective_cap:
            rem = max(0.0, effective_cap - quality_km)
            adj_sum = sum(s.distance_km for s in adjustable)
            if adj_sum > 0:
                for s in adjustable:
                    s.distance_km = round(s.distance_km * rem / adj_sum, 1)
                cur_total = sum(s.distance_km for s in sessions)
                if cur_total > effective_cap:
                    diff = round(cur_total - effective_cap, 1)
                    for s in sorted(adjustable, key=lambda s: s.distance_km, reverse=True):
                        sub = min(diff, s.distance_km)
                        s.distance_km = round(s.distance_km - sub, 1)
                        diff = round(diff - sub, 1)
                        if diff <= 0:
                            break
                else:
                    diff = round(effective_cap - cur_total, 1)
                    if diff > 0 and adjustable:
                        largest = max(adjustable, key=lambda s: s.distance_km)
                        largest.distance_km = round(largest.distance_km + diff, 1)
            total = sum(s.distance_km for s in sessions)

        phase_enum = TrainingPhase(phase) if phase in ("BASE", "BUILD", "SPECIFIC", "PEAK", "TAPER") else None

        week_plans.append(WeekPlan(
            week_num=week_num,
            bloc=bloc,
            sessions=sessions,
            is_recovery=is_recovery,
            total_km=round(total, 1),
            phase=phase_enum,
        ))

        # Update history for variety penalty
        week_workouts = [s.workout.name for s in sessions if s.workout]
        history = (history + week_workouts)[-6:]

        # Track load for next week's structure decision
        prev_weekly_load = total

    plan = TrainingPlan(
        runner=runner,
        distance=distance,
        weeks=weeks,
        paces=paces,
        name=name,
        week_plans=week_plans,
        sessions_per_week=spw,
        start_date=start_date,
        pace_profile=pace_profile,
        selection_trace=selection_trace,
        settings=settings,
        plan_vdot=plan_vdot,
    )
    return validate_and_annotate(plan)


def validate_and_annotate(plan: TrainingPlan) -> TrainingPlan:
    """Annotate loads and run coherence validations on a generated plan."""
    from .engine.load import annotate_plan
    from .engine.validation import validate_plan
    from .models import Experience

    exp = runner_exp(plan)
    annotate_plan(plan.week_plans, exp)
    plan.warnings = validate_plan(plan)
    return plan


def runner_exp(plan: TrainingPlan) -> Experience:
    """Extract Experience from plan.runner, handling string values."""
    exp = plan.runner.experience
    if hasattr(exp, "value"):
        return exp
    try:
        return Experience(exp)
    except Exception:
        return Experience.INTERMEDIATE


def get_workout_names_for_plan(plan: TrainingPlan) -> list[str]:
    names = set()
    for week in plan.week_plans:
        for s in week.sessions:
            if s.workout:
                names.add(s.workout.name)
    return sorted(names)


def get_all_sessions(plan: TrainingPlan) -> list[tuple[int, str, Session]]:
    result = []
    for week in plan.week_plans:
        for s in week.sessions:
            result.append((week.week_num, s.day, s))
    return result


def regenerate_plan(
    plan: TrainingPlan,
    from_week: int = 1,
    settings: PlanSettings | None = None,
) -> TrainingPlan:
    """Regenerate pending sessions while preserving completed and skipped work."""
    from .models import SessionStatus

    if not 1 <= from_week <= plan.weeks:
        raise ValueError("from_week must be within the plan")
    settings = settings or plan.settings
    if plan.plan_vdot is None and settings.sessions_per_week == 4:
        settings.sessions_per_week = plan.sessions_per_week
    fresh = generate_plan(
        runner=plan.runner,
        distance=plan.distance,
        weeks=plan.weeks,
        paces=plan.paces if (plan.plan_vdot or plan.runner.vdot) == plan.runner.effective_vdot else None,
        start_date=plan.start_date,
        name=plan.name,
        settings=settings,
    )

    merged: list[WeekPlan] = []
    originals = {w.week_num: w for w in plan.week_plans}
    for fresh_wp in fresh.week_plans:
        orig = originals.get(fresh_wp.week_num)
        if fresh_wp.week_num < from_week:
            merged.append(orig or fresh_wp)
        else:
            if orig:
                frozen = {s.day: s for s in orig.sessions if s.status in (SessionStatus.COMPLETED, SessionStatus.SKIPPED)}
                fresh_wp.sessions = [frozen.pop(s.day, s) for s in fresh_wp.sessions]
                fresh_wp.sessions.extend(frozen.values())
                fresh_wp.sessions.sort(key=lambda s: DAY_OFFSET.get(s.day, 0))
                fresh_wp.total_km = round(sum(s.distance_km for s in fresh_wp.sessions), 1)
            merged.append(fresh_wp)

    fresh.week_plans = merged
    fresh.selection_trace = {**{k: v for k, v in plan.selection_trace.items() if k < from_week},
                             **{k: v for k, v in fresh.selection_trace.items() if k >= from_week}}
    return validate_and_annotate(fresh)


def _carry_statuses(orig: WeekPlan, fresh: WeekPlan) -> None:
    """Carry a status only when the session's identity is unchanged."""
    from .models import SessionStatus
    def key(s: Session) -> tuple[str, str, str]:
        return s.day, s.type, s.workout.name if s.workout else ""
    statuses = {key(s): s for s in orig.sessions if s.status != SessionStatus.PENDING}
    for s in fresh.sessions:
        if key(s) in statuses:
            s.status = statuses[key(s)].status
            s.id = statuses[key(s)].id


# --- Self-check ---
if __name__ == "__main__":
    from .vdot import derive_paces

    runner = RunnerProfile(vdot=49.4, weekly_volume_km=70)
    paces = derive_paces(49.4)

    for dist in Distance:
        plan = generate_plan(runner, dist, 12, paces)
        workout_names = get_workout_names_for_plan(plan)
        print(f"{dist.value:10s}: {plan.total_workouts} quality sessions, "
              f"{len(workout_names)} unique workouts, "
              f"{plan.week_plans[-1].total_km}km final week")
        assert plan.total_workouts > 0, f"No workouts generated for {dist}"

    for spw in [3, 4, 5, 6, 7]:
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=spw)
        sessions_w1 = len(plan.week_plans[0].sessions)
        print(f"  {spw} sessions/wk -> {sessions_w1} sessions in week 1, {plan.week_plans[0].total_km}km")
        assert sessions_w1 == spw, f"Expected {spw} sessions, got {sessions_w1}"

    from datetime import date
    plan = generate_plan(runner, Distance.SEMI, 12, paces, start_date=date(2026, 9, 21))
    d1 = plan.session_date(1, "mon")
    d6 = plan.session_date(6, "mon")
    print(f"  start_date -> W1 Mon: {d1}, W6 Mon: {d6}")
    assert d1 == date(2026, 9, 21), f"Expected 2026-09-21, got {d1}"
    assert d6 == date(2026, 10, 26), f"Expected 2026-10-26, got {d6}"

    for vol in [40, 55, 70, 100]:
        r = RunnerProfile(vdot=49.4, weekly_volume_km=vol)
        p = generate_plan(r, Distance.SEMI, 12, paces, sessions_per_week=4)
        w1_total = p.week_plans[0].total_km
        cap = min(vol, 75)
        print(f"  volume={vol}km -> W1 total={w1_total}km (cap={cap})")
        assert w1_total <= cap + 5, f"Week total {w1_total} exceeds cap {cap} by >5km"

    from .models import french_session_name
    s = plan.week_plans[0].sessions[0]
    fname = french_session_name(1, "mon", s)
    print(f"  French name: {fname}")
    assert fname.startswith("S01"), f"Expected S01 prefix, got {fname}"

    print("\nAll checks passed.")
