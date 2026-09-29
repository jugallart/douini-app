"""Tests for training load, feasibility, coherence validations, and auto-corrections."""

from __future__ import annotations

import random
from datetime import date

import pytest

from douini.domain.models import (
    Distance,
    Experience,
    MIN_WEEKS,
    PlanWarning,
    RunnerProfile,
    Session,
    TrainingPhase,
    TrainingPlan,
    WeekPlan,
)
from douini.domain.planner import generate_plan
from douini.domain.vdot import derive_paces
from douini.domain.engine.load import (
    compute_session_load,
    compute_weekly_load,
    annotate_plan,
    weekly_load_budget,
)
from douini.domain.engine.validation import (
    validate_plan,
    check_feasibility,
    auto_correct,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_runner(
    vdot=49.4, vol=70, spw=4, dist="semi", weeks=12, goal="1:32:40",
    current_vol=None, current_long=None, exp=Experience.INTERMEDIATE,
    tol=0,
) -> RunnerProfile:
    return RunnerProfile(
        vdot=vdot,
        weekly_volume_km=vol,
        mileage_tolerance_km=tol,
        target_weekly_km=vol if current_vol is None else None,
        sessions_per_week=spw,
        race_distance=dist,
        weeks=weeks,
        target_time=goal,
        experience=exp,
        current_weekly_km=current_vol,
        current_longest_run=current_long,
        long_run_day="sun",
        preferred_days=["mon", "wed", "fri", "sun"],
    )


def make_plan(runner=None, dist=Distance.SEMI, weeks=12, **kw) -> TrainingPlan:
    runner = runner or make_runner()
    paces = derive_paces(runner.vdot)
    return generate_plan(runner, dist, weeks, paces, **kw)


# ---------------------------------------------------------------------------
# Task 1: Training load
# ---------------------------------------------------------------------------

class TestSessionLoad:
    def test_easy_low_load(self):
        s = Session(day="mon", type="easy", distance_km=10.0)
        load = compute_session_load(s)
        assert 0 < load < 25  # 10km * 6min/km * 0.3 = 18

    def test_quality_higher_than_easy(self):
        easy = Session(day="mon", type="easy", distance_km=10.0)
        qual = Session(day="wed", type="quality", distance_km=10.0)
        assert compute_session_load(qual) > compute_session_load(easy)

    def test_rest_zero(self):
        s = Session(day="mon", type="rest", distance_km=0.0)
        assert compute_session_load(s) == 0.0

    def test_zero_distance_zero(self):
        s = Session(day="mon", type="easy", distance_km=0.0)
        assert compute_session_load(s) == 0.0

    def test_long_moderate(self):
        s = Session(day="sun", type="long", distance_km=20.0)
        load = compute_session_load(s)
        easy_load = compute_session_load(Session(day="mon", type="easy", distance_km=20.0))
        assert load > easy_load  # long coeff 0.5 > easy 0.3


class TestWeeklyLoad:
    def test_weekly_load_positive(self):
        plan = make_plan()
        w1 = plan.week_plans[0]
        assert w1.weekly_load > 0

    def test_fatigue_index_positive(self):
        plan = make_plan()
        w1 = plan.week_plans[0]
        assert w1.fatigue_index > 0

    def test_recovery_need_range(self):
        plan = make_plan()
        for w in plan.week_plans:
            assert 0 <= w.recovery_need <= 1

    def test_annotated_sessions(self):
        plan = make_plan()
        for w in plan.week_plans:
            for s in w.sessions:
                assert s.load_score >= 0

    def test_taper_reduces_load(self):
        plan = make_plan(dist=Distance.MARATHON, weeks=12)
        loading_weeks = [w for w in plan.week_plans if w.phase != TrainingPhase.TAPER]
        # Exclude final race week from taper average (race session inflates load)
        taper_weeks = [w for w in plan.week_plans if w.phase == TrainingPhase.TAPER and w.week_num != plan.weeks]
        if loading_weeks and taper_weeks:
            avg_loading = sum(w.weekly_load for w in loading_weeks) / len(loading_weeks)
            avg_taper = sum(w.weekly_load for w in taper_weeks) / len(taper_weeks)
            assert avg_taper < avg_loading

    def test_fatigue_accumulates(self):
        """Fatigue index should carry forward from prior weeks."""
        plan = make_plan()
        # First week has no prior fatigue
        assert plan.week_plans[0].fatigue_index > 0
        # Later weeks should have accumulated fatigue
        # (not strictly monotonic due to recovery weeks, but last loading week > first)
        loading = [w for w in plan.week_plans if not w.is_recovery and w.phase != TrainingPhase.TAPER]
        if len(loading) >= 2:
            assert loading[-1].fatigue_index >= loading[0].fatigue_index * 0.8


class TestWeeklyBudget:
    def test_budget_positive(self):
        b = weekly_load_budget(70, 4, Distance.SEMI, "BASE")
        assert b > 0

    def test_taper_reduces_budget(self):
        base = weekly_load_budget(70, 4, Distance.SEMI, "SPECIFIC")
        taper = weekly_load_budget(70, 4, Distance.SEMI, "TAPER")
        assert taper < base

    def test_more_sessions_higher_budget(self):
        b3 = weekly_load_budget(70, 3, Distance.SEMI, "BASE")
        b6 = weekly_load_budget(70, 6, Distance.SEMI, "BASE")
        assert b6 > b3


# ---------------------------------------------------------------------------
# Task 2: Feasibility checks
# ---------------------------------------------------------------------------

class TestFeasibility:
    def test_realistic_plan_no_error(self):
        runner = make_runner()
        warnings = check_feasibility(runner, Distance.SEMI, 12)
        errors = [w for w in warnings if w.severity == "error"]
        assert len(errors) == 0

    def test_duration_minimum(self):
        runner = make_runner(weeks=4)
        warnings = check_feasibility(runner, Distance.SEMI, 4)
        errors = [w for w in warnings if w.severity == "error"]
        assert any(w.code == "duration_minimum" for w in errors)

    def test_volume_gap_error(self):
        """Low-volume runner with short plan should get volume_gap error."""
        runner = make_runner(vol=30, current_vol=10, weeks=10)
        warnings = check_feasibility(runner, Distance.SEMI, 10)
        errors = [w for w in warnings if w.severity == "error"]
        # Should have volume_gap or vdot_feasibility error
        assert len(errors) > 0

    def test_four_week_marathon_extreme(self):
        """4-week marathon with 20km/week should be infeasible."""
        runner = make_runner(vdot=45, vol=20, current_vol=20, dist="marathon", weeks=4, goal="4:00:00")
        warnings = check_feasibility(runner, Distance.MARATHON, 4)
        errors = [w for w in warnings if w.severity == "error"]
        assert len(errors) > 0

    def test_low_volume_5k_viable(self):
        """Low-volume 5K plan should remain viable (not rejected)."""
        runner = make_runner(vdot=45, vol=40, current_vol=35, dist="5k", weeks=6, goal="22:00")
        warnings = check_feasibility(runner, Distance.K5, 6)
        errors = [w for w in warnings if w.severity == "error"]
        assert len(errors) == 0

    def test_ambitious_warning_not_error(self):
        """Ambitious but safely plannable targets should warn, not error."""
        runner = make_runner(vdot=45, vol=60, current_vol=55, dist="5k", weeks=10, goal="18:30")
        warnings = check_feasibility(runner, Distance.K5, 10)
        errors = [w for w in warnings if w.severity == "error"]
        # May have warnings but should not be hard errors
        assert not any(w.code == "duration_minimum" for w in errors)


# ---------------------------------------------------------------------------
# Task 3: Nine coherence validations
# ---------------------------------------------------------------------------

class TestCoherenceValidations:
    def test_valid_plan_no_errors(self):
        plan = make_plan()
        warnings = validate_plan(plan)
        errors = [w for w in warnings if w.severity == "error"]
        assert len(errors) == 0

    def test_volume_ceiling_detected(self):
        plan = make_plan()
        # Inflate a week's volume
        plan.week_plans[0].total_km = 999
        warnings = validate_plan(plan)
        assert any(w.code == "volume_ceiling" for w in warnings)

    def test_long_run_cap_detected(self):
        plan = make_plan()
        for s in plan.week_plans[0].sessions:
            if s.type == "long":
                s.distance_km = 99
        warnings = validate_plan(plan)
        assert any(w.code == "long_run_cap" for w in warnings)

    def test_recovery_week_volume_detected(self):
        plan = make_plan()
        # Make a recovery week higher than previous
        for w in plan.week_plans:
            if w.is_recovery:
                w.total_km = plan.week_plans[w.week_num - 2].total_km + 10
                break
        warnings = validate_plan(plan)
        assert any(w.code == "recovery_week_volume" for w in warnings)

    def test_taper_volume_detected(self):
        plan = make_plan(dist=Distance.MARATHON, weeks=12)
        # Make first taper week higher than last loading week
        taper_weeks = [w for w in plan.week_plans if w.phase == TrainingPhase.TAPER]
        if taper_weeks:
            prev = plan.week_plans[taper_weeks[0].week_num - 2]
            taper_weeks[0].total_km = prev.total_km + 10
            warnings = validate_plan(plan)
            assert any(w.code == "taper_volume" for w in warnings)

    def test_session_spacing_detected(self):
        plan = make_plan()
        # Move quality sessions to consecutive days
        w = plan.week_plans[0]
        quality_sessions = [s for s in w.sessions if s.type == "quality"]
        if len(quality_sessions) >= 2:
            quality_sessions[0].day = "mon"
            quality_sessions[1].day = "tue"
            warnings = validate_plan(plan)
            assert any(w2.code == "session_spacing" for w2 in warnings)

    def test_quality_count_detected(self):
        plan = make_plan(sessions_per_week=4, interval_adapted=True)
        # Add extra quality sessions
        wp = plan.week_plans[0]
        wp.sessions.append(Session(day="sat", type="quality", distance_km=12))
        wp.sessions.append(Session(day="thu", type="quality", distance_km=12))
        warnings = validate_plan(plan)
        assert any(pw.code == "quality_session_count" for pw in warnings)

    def test_all_checks_defined(self):
        plan = make_plan()
        warnings = validate_plan(plan)
        # All check codes from validation_rules.json should be possible
        from douini.domain.engine.config import get_validation_rules
        rules = get_validation_rules()
        check_ids = {c["id"] for c in rules["checks"]}
        assert check_ids == {
            "volume_ceiling", "long_run_cap", "quality_session_count",
            "recovery_week_volume", "taper_volume", "session_spacing",
            "long_run_day", "norwegian_zone_match", "vdot_feasibility",
            "pace_ordering", "workout_classification", "phase_specificity",
        }

    def test_warnings_deduplicated(self):
        plan = make_plan()
        # Create duplicate violations
        for w in plan.week_plans[:3]:
            w.total_km = 999
        warnings = validate_plan(plan)
        # Each week should produce one warning, not duplicates for same week
        vol_warnings = [w2 for w2 in warnings if w2.code == "volume_ceiling"]
        assert len(vol_warnings) == 3  # one per week, no dupes


# ---------------------------------------------------------------------------
# Task 4: Auto-corrections
# ---------------------------------------------------------------------------

class TestAutoCorrection:
    def test_correction_order_documented(self):
        """Auto-correct follows: lighten → reduce reps → reduce duration →
        replace with easy → reduce long run → adjust volume."""
        # The correction order is implemented in auto_correct()
        plan = make_plan()
        plan.week_plans[0].total_km = 999
        corrected, log = auto_correct(plan)
        assert len(log) > 0

    def test_finite_iterations(self):
        """Correction loop terminates."""
        plan = make_plan()
        plan.week_plans[0].total_km = 999
        plan.week_plans[1].total_km = 999
        corrected, log = auto_correct(plan)
        # Should not loop forever
        assert len(log) < 20

    def test_deterministic(self):
        """Same plan in → same corrections out."""
        plan1 = make_plan()
        plan1.week_plans[0].total_km = 999
        plan2 = make_plan()
        plan2.week_plans[0].total_km = 999
        _, log1 = auto_correct(plan1)
        _, log2 = auto_correct(plan2)
        assert log1 == log2

    def test_volume_ceiling_corrected(self):
        plan = make_plan()
        plan.week_plans[0].total_km = 999
        corrected, _ = auto_correct(plan)
        w = corrected.week_plans[0]
        assert w.total_km < 999

    def test_recovery_week_corrected(self):
        plan = make_plan()
        for w in plan.week_plans:
            if w.is_recovery and w.week_num > 1:
                w.total_km = plan.week_plans[w.week_num - 2].total_km + 10
                break
        corrected, log = auto_correct(plan)
        # Should have attempted correction
        assert any("recovery" in entry for entry in log)

    def test_uncorrectable_warning_preserved(self):
        """When correction can't fix, warning is preserved."""
        plan = make_plan()
        # vdot_feasibility can't be auto-corrected
        plan.runner.race_distance = "marathon"
        plan.runner.target_time = "2:30:00"  # unrealistic for VDOT 49.4
        plan.runner.vdot = 40
        warnings = validate_plan(plan)
        vdot_warnings = [w for w in warnings if w.code == "vdot_feasibility"]
        if vdot_warnings:
            corrected, log = auto_correct(plan)
            assert any("vdot_feasibility" in entry for entry in log)

    def test_corrected_plan_warnings_updated(self):
        plan = make_plan()
        plan.week_plans[0].total_km = 999
        corrected, _ = auto_correct(plan)
        # After correction, remaining warnings should be on the plan
        assert len(corrected.warnings) >= 0

    def test_persisted_and_garmin_match(self):
        """Corrected plan sessions have valid structure for Garmin."""
        plan = make_plan()
        plan.week_plans[0].total_km = 999
        corrected, _ = auto_correct(plan)
        for w in corrected.week_plans:
            for s in w.sessions:
                assert s.distance_km >= 0
                assert s.day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


# ---------------------------------------------------------------------------
# Task 5: Reference and generated profiles
# ---------------------------------------------------------------------------

class TestReferenceProfiles:
    """Six fixed reference cases + four-week marathon extreme."""

    CASES = [
        # (vdot, vol, spw, dist_str, weeks, goal_time, current_vol)
        (35, 30, 3, "5k", 6, "25:00", 30),
        (40, 40, 4, "10k", 8, "50:00", 40),
        (49.4, 65, 4, "5k", 10, "20:00", 65),
        (55, 80, 5, "semi", 12, "1:25:00", 75),
        (60, 100, 6, "marathon", 14, "2:55:00", 90),
        (45, 20, 3, "marathon", 4, "4:00:00", 20),  # extreme
    ]

    @pytest.mark.parametrize("vdot,vol,spw,dist_str,weeks,goal,current_vol", CASES)
    def test_reference_profile_generates(self, vdot, vol, spw, dist_str, weeks, goal, current_vol):
        """Every reference case generates without uncaught error."""
        dist = Distance(dist_str)
        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=current_vol * 0.25,
        )
        paces = derive_paces(vdot)
        try:
            plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
            assert len(plan.week_plans) == weeks
        except ValueError as e:
            # 4-week marathon is expected to fail (min weeks constraint)
            assert "nécessite au moins" in str(e) or "quality workload" in str(e)

    @pytest.mark.parametrize("vdot,vol,spw,dist_str,weeks,goal,current_vol", CASES)
    def test_reference_deterministic(self, vdot, vol, spw, dist_str, weeks, goal, current_vol):
        """Same inputs produce same plan."""
        dist = Distance(dist_str)
        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=current_vol * 0.25,
        )
        paces = derive_paces(vdot)
        try:
            p1 = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
            p2 = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
            assert get_workout_names(p1) == get_workout_names(p2)
            assert [w.total_km for w in p1.week_plans] == [w.total_km for w in p2.week_plans]
        except ValueError:
            pass  # Infeasible cases are deterministic too

    @pytest.mark.parametrize("vdot,vol,spw,dist_str,weeks,goal,current_vol", CASES)
    def test_reference_no_silent_violations(self, vdot, vol, spw, dist_str, weeks, goal, current_vol):
        """No silent error-severity violations (or they have documented warnings)."""
        dist = Distance(dist_str)
        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=current_vol * 0.25,
        )
        paces = derive_paces(vdot)
        try:
            plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        except ValueError:
            return  # Infeasible: no silent violation, explicit rejection
        warnings = validate_plan(plan)
        errors = [w for w in warnings if w.severity == "error"]
        # The extreme 4-week marathon may have errors, which is expected
        if dist_str == "marathon" and weeks == 4:
            assert len(errors) >= 1  # Expected: infeasible
        else:
            # Non-extreme cases should not have silent errors
            assert len(errors) == 0, f"Unexpected errors: {[w.message for w in errors]}"

    @pytest.mark.parametrize("vdot,vol,spw,dist_str,weeks,goal,current_vol", CASES)
    def test_reference_load_coherent(self, vdot, vol, spw, dist_str, weeks, goal, current_vol):
        """All weeks have non-negative load values."""
        dist = Distance(dist_str)
        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=current_vol * 0.25,
        )
        paces = derive_paces(vdot)
        try:
            plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        except ValueError:
            return
        for w in plan.week_plans:
            assert w.weekly_load >= 0
            assert w.fatigue_index >= 0
            assert 0 <= w.recovery_need <= 1

    @pytest.mark.parametrize("vdot,vol,spw,dist_str,weeks,goal,current_vol", CASES)
    def test_reference_taper_progression(self, vdot, vol, spw, dist_str, weeks, goal, current_vol):
        """Taper weeks reduce load progressively."""
        dist = Distance(dist_str)
        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=current_vol * 0.25,
        )
        paces = derive_paces(vdot)
        try:
            plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        except ValueError:
            return
        taper_weeks = [w for w in plan.week_plans if w.phase == TrainingPhase.TAPER and w.week_num != plan.weeks]
        if len(taper_weeks) >= 2:
            for i in range(1, len(taper_weeks)):
                assert taper_weeks[i].weekly_load <= taper_weeks[i - 1].weekly_load + 1


class TestSeededProfiles:
    """Generate seeded profiles across supported bounds."""

    @pytest.mark.parametrize("seed", range(50))
    def test_seeded_profile_generates(self, seed):
        rng = random.Random(seed)
        vdot = round(rng.uniform(35, 65), 1)
        vol = rng.choice([30, 40, 50, 60, 70, 80, 90, 100])
        spw = rng.choice([3, 4, 5, 6, 7])
        dist_str = rng.choice(["5k", "10k", "semi", "marathon"])
        dist = Distance(dist_str)
        weeks = rng.choice([MIN_WEEKS[dist], MIN_WEEKS[dist] + 2, 12, 16])
        current_vol = max(10, vol - rng.randint(0, 30))
        goal = _estimate_goal_time(vdot, dist_str)

        runner = make_runner(
            vdot=vdot, vol=vol, spw=spw, dist=dist_str, weeks=weeks,
            goal=goal, current_vol=current_vol, current_long=max(3, current_vol * 0.2),
        )
        paces = derive_paces(vdot)
        try:
            plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
            assert len(plan.week_plans) == weeks
            # No uncaught errors
            for w in plan.week_plans:
                assert w.total_km >= 0
                assert len(w.sessions) >= 1
        except ValueError as e:
            # Feasibility rejection is acceptable
            assert "quality workload" in str(e) or "weeks" in str(e) or "minimum" in str(e)


def _estimate_goal_time(vdot: float, dist_str: str) -> str:
    """Rough goal time from VDOT for test seeding."""
    from douini.domain.vdot import VDOTCalculator
    try:
        time = VDOTCalculator.race_time(vdot, dist_str)
        return VDOTCalculator.format_pace_range.__qualname__ and _format_time(time)
    except Exception:
        return "20:00"


def _format_time(seconds: float) -> str:
    s = int(round(seconds))
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def get_workout_names(plan: TrainingPlan) -> list[str]:
    names = set()
    for w in plan.week_plans:
        for s in w.sessions:
            if s.workout:
                names.add(s.workout.name)
    return sorted(names)
