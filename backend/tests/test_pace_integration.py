"""Phase 1 integration tests: PaceEngine → Planner → WorkoutDef → Session → pace.

Verifies that pace_key resolution uses PaceProfile (12 zones) throughout the
pipeline, not the legacy 4-zone derive_paces().

Critical test: VDOT=53, pace_key="vo2" must produce 3'37–3'51/km,
not 4'03–4'10 (threshold/short) or 5'28–5'52 (easy/ef).
"""

import pytest

from douini.domain.models import Distance, RunnerProfile, Pace
from douini.domain.engine.pace_engine import PaceEngine
from douini.domain.engine.library import build_workout_def, resolve_pace
from douini.domain.planner import generate_plan, build_workout
from douini.garmin.builders import build_garmin_workout, build_session_workout


VDOT = 53


@pytest.fixture
def profile():
    return PaceEngine(VDOT).build_profile()


@pytest.fixture
def paces(profile):
    return profile.to_paces()


# ── PaceProfile construction ──────────────────────────────────────────────────

class TestPaceProfileBuilt:
    """Verify PaceProfile has all 12 zones for VDOT=53."""

    def test_vdot_stored(self, profile):
        assert profile.vdot == VDOT

    def test_vo2_zone(self, profile):
        assert profile.vo2 is not None
        assert profile.vo2.fast > 0
        assert profile.vo2.slow > profile.vo2.fast

    def test_threshold_zone(self, profile):
        assert profile.threshold is not None
        assert profile.threshold.fast > 0

    def test_economy_zone(self, profile):
        assert profile.economy is not None

    def test_easy_zone(self, profile):
        assert profile.easy is not None

    def test_recovery_zone(self, profile):
        assert profile.recovery is not None

    def test_long_run_zone(self, profile):
        assert profile.long_run is not None

    def test_race_paces(self, profile):
        for key in ("5K", "10K", "HM", "MARATHON"):
            assert key in profile.race_paces, f"Missing race pace: {key}"

    def test_norwegian_zones(self, profile):
        for key in ("short", "medium", "long"):
            assert key in profile.norwegian, f"Missing Norwegian zone: {key}"

    def test_to_paces_adapter(self, profile, paces):
        """PaceProfile.to_paces() produces compatible legacy 4-zone Paces."""
        assert paces.ef is not None
        assert paces.short is not None
        assert paces.medium is not None
        assert paces.long is not None


# ── resolve_pace with PaceProfile ─────────────────────────────────────────────

class TestResolvePace:
    """resolve_pace() must resolve all pace_keys from PaceProfile."""

    def test_vo2(self, profile):
        pmin, pmax = resolve_pace("vo2", profile=profile)
        # VO2 = 3'37–3'51 for VDOT=53
        assert 215 <= pmin.s_per_km <= 220, f"vo2 fast={pmin.s_per_km}"
        assert 228 <= pmax.s_per_km <= 235, f"vo2 slow={pmax.s_per_km}"

    def test_5k(self, profile):
        pmin, pmax = resolve_pace("5K", profile=profile)
        # 5K race pace ~3'47 = 227 s/km for VDOT=53 (Daniels canonical formula)
        assert 224 <= pmin.s_per_km <= 230

    def test_10k(self, profile):
        pmin, pmax = resolve_pace("10K", profile=profile)
        assert 230 <= pmin.s_per_km <= 240

    def test_hm(self, profile):
        pmin, pmax = resolve_pace("HM", profile=profile)
        assert 243 <= pmin.s_per_km <= 252

    def test_marathon(self, profile):
        pmin, pmax = resolve_pace("MARATHON", profile=profile)
        assert 253 <= pmin.s_per_km <= 263

    def test_threshold(self, profile):
        pmin, pmax = resolve_pace("threshold", profile=profile)
        # Threshold = 3'56–4'11
        assert 233 <= pmin.s_per_km <= 240
        assert 248 <= pmax.s_per_km <= 255

    def test_economy(self, profile):
        pmin, pmax = resolve_pace("economy", profile=profile)
        assert pmin.s_per_km < profile.threshold.fast

    def test_easy(self, profile):
        pmin, pmax = resolve_pace("easy", profile=profile)
        assert pmin.s_per_km > profile.threshold.slow

    def test_recovery(self, profile):
        pmin, pmax = resolve_pace("recovery", profile=profile)
        assert pmin.s_per_km > profile.easy.slow

    def test_long_run(self, profile):
        pmin, pmax = resolve_pace("long_run", profile=profile)
        assert pmin.s_per_km > profile.threshold.slow
        assert pmin.s_per_km < profile.easy.fast

    def test_norwegian_short(self, profile):
        pmin, pmax = resolve_pace("short", profile=profile)
        assert 238 <= pmin.s_per_km <= 245

    def test_norwegian_medium(self, profile):
        pmin, pmax = resolve_pace("medium", profile=profile)
        assert 245 <= pmin.s_per_km <= 253

    def test_norwegian_long(self, profile):
        pmin, pmax = resolve_pace("long", profile=profile)
        assert 250 <= pmin.s_per_km <= 258


# ── build_workout_def with profile ────────────────────────────────────────────

class TestBuildWorkoutDefProfile:
    """build_workout_def must use PaceProfile when provided."""

    def test_5k_8x400_vo2(self, profile, paces):
        """Critical: pace_key='vo2' must NOT resolve to threshold (short) or easy."""
        wd = build_workout_def("5K-8x400", paces, profile=profile)
        # VO2 fast ~217 s/km (3'37), slow ~231 s/km (3'51)
        assert wd.pace_min.s_per_km <= 220, f"Expected ~217, got {wd.pace_min.s_per_km}"
        assert wd.pace_max.s_per_km <= 235, f"Expected ~231, got {wd.pace_max.s_per_km}"

    def test_5k_6x800_race(self, profile, paces):
        wd = build_workout_def("5K-6x800", paces, profile=profile)
        assert 224 <= wd.pace_min.s_per_km <= 230

    def test_5k_5x1000_race(self, profile, paces):
        wd = build_workout_def("5K-5x1000", paces, profile=profile)
        assert 224 <= wd.pace_min.s_per_km <= 230

    def test_5k_4x1200_race(self, profile, paces):
        wd = build_workout_def("5K-4x1200", paces, profile=profile)
        assert 224 <= wd.pace_min.s_per_km <= 230

    def test_10k_5x1000_race(self, profile, paces):
        wd = build_workout_def("10K-5x1000", paces, profile=profile)
        assert 230 <= wd.pace_min.s_per_km <= 240

    def test_10k_4x1500_race(self, profile, paces):
        wd = build_workout_def("10K-4x1500", paces, profile=profile)
        assert 230 <= wd.pace_min.s_per_km <= 240

    def test_10k_3x2000_threshold(self, profile, paces):
        """threshold must NOT resolve to easy."""
        wd = build_workout_def("10K-3x2000", paces, profile=profile)
        assert 233 <= wd.pace_min.s_per_km <= 240, f"Expected ~236, got {wd.pace_min.s_per_km}"
        assert 248 <= wd.pace_max.s_per_km <= 255

    def test_10k_4x2000_threshold(self, profile, paces):
        wd = build_workout_def("10K-4x2000", paces, profile=profile)
        assert 233 <= wd.pace_min.s_per_km <= 240

    def test_10k_3x3000_threshold(self, profile, paces):
        wd = build_workout_def("10K-3x3000", paces, profile=profile)
        assert 233 <= wd.pace_min.s_per_km <= 240

    def test_ns_s01_short(self, profile, paces):
        wd = build_workout_def("NS-S01", paces, profile=profile)
        assert 238 <= wd.pace_min.s_per_km <= 245

    def test_ns_m01_medium(self, profile, paces):
        wd = build_workout_def("NS-M01", paces, profile=profile)
        assert 245 <= wd.pace_min.s_per_km <= 253

    def test_ns_l01_long(self, profile, paces):
        wd = build_workout_def("NS-L01", paces, profile=profile)
        assert 250 <= wd.pace_min.s_per_km <= 258


# ── build_workout_def without profile (legacy fallback) ────────────────────────

class TestBuildWorkoutDefLegacy:
    """build_workout_def without profile still works (legacy 4-zone)."""

    def test_ns_s01_legacy(self, paces):
        wd = build_workout_def("NS-S01", paces)
        assert wd.pace_min is not None

    def test_5k_8x400_legacy_falls_back(self, paces):
        """Without profile, vo2 falls back to ef (easy). Known limitation."""
        wd = build_workout_def("5K-8x400", paces)
        # Falls back to ef (easy pace) — this is the legacy bug we're fixing
        assert wd.pace_min.s_per_km >= 300  # easy pace


# ── Full plan generation ──────────────────────────────────────────────────────

class TestPlanGeneration:
    """generate_plan must produce a plan with pace_profile set."""

    def test_plan_has_pace_profile(self):
        runner = RunnerProfile(vdot=VDOT, sessions_per_week=4, target_weekly_km=65)
        plan = generate_plan(runner, Distance.K5, 12)
        assert plan.pace_profile is not None
        assert plan.pace_profile.vdot == VDOT

    def test_plan_paces_derived_from_profile(self):
        runner = RunnerProfile(vdot=VDOT, sessions_per_week=4, target_weekly_km=65)
        plan = generate_plan(runner, Distance.K5, 12)
        # Paces should be derived from PaceProfile (not legacy derive_paces)
        # Norwegian short fast should match profile.norwegian["short"].pace_min
        ns_fast = plan.pace_profile.norwegian["short"].pace_min
        assert ns_fast.s_per_km == plan.paces.short[0].s_per_km

    def test_5k_plan_has_vo2_sessions(self):
        """5K plan in SPECIFIC phase should have race-specific workouts with correct paces."""
        runner = RunnerProfile(vdot=VDOT, sessions_per_week=4, target_weekly_km=65)
        plan = generate_plan(runner, Distance.K5, 12)
        # Check that at least one quality session has VO2-like pace (not easy)
        vo2_sessions = []
        for wp in plan.week_plans:
            for s in wp.sessions:
                if s.workout and s.workout.pace_min.s_per_km < 230:
                    vo2_sessions.append(s)
        # In a 12-week 5K plan, SPECIFIC phase should produce some fast sessions
        assert len(vo2_sessions) > 0, "No VO2-paced sessions found in 5K plan"

    def test_10k_plan_threshold_sessions(self):
        """10K plan should have threshold-paced sessions with correct pace (not easy)."""
        runner = RunnerProfile(vdot=VDOT, sessions_per_week=4, target_weekly_km=70)
        plan = generate_plan(runner, Distance.K10, 12)
        threshold_sessions = []
        for wp in plan.week_plans:
            for s in wp.sessions:
                if s.workout and 230 <= s.workout.pace_min.s_per_km <= 240:
                    threshold_sessions.append(s)
        assert len(threshold_sessions) > 0, "No threshold-paced sessions in 10K plan"

    def test_all_distances_generate(self):
        """All 4 distances must generate plans without errors."""
        for dist in [Distance.K5, Distance.K10, Distance.SEMI, Distance.MARATHON]:
            runner = RunnerProfile(vdot=VDOT, sessions_per_week=4, target_weekly_km=65)
            plan = generate_plan(runner, dist, 12)
            assert plan.pace_profile is not None
            assert len(plan.week_plans) == 12


# ── Garmin export ─────────────────────────────────────────────────────────────

class TestGarminExport:
    """Garmin workout builder must use PaceProfile for pace resolution."""

    def test_5k_8x400_garmin_has_vo2_target(self, profile, paces):
        wj = build_garmin_workout("5K-8x400", paces, profile=profile)
        steps = wj["workoutSegments"][0]["workoutSteps"]
        # Find interval steps and check they have pace targets
        for step in steps:
            if step.get("type") == "RepeatGroupDTO":
                for inner in step.get("workoutSteps", []):
                    if inner.get("stepType", {}).get("stepTypeKey") == "interval":
                        target = inner.get("targetValueOne")
                        assert target is not None, "Interval has no pace target"
                        # VO2 pace ~217 s/km => 1000/217 = 4.608 m/s
                        assert 4.0 <= target <= 5.0, f"Expected ~4.6 m/s, got {target}"

    def test_hm_race_blocks_no_crash(self, profile, paces):
        """HM-RACE-BLOCKS has block pace_key='threshold' — must not crash."""
        wj = build_garmin_workout("HM-RACE-BLOCKS", paces, profile=profile)
        assert "workoutSegments" in wj

    def test_mar_long_mp_no_crash(self, profile, paces):
        """MAR-LONG-MP has block pace_key='MARATHON' — must not crash."""
        wj = build_garmin_workout("MAR-LONG-MP", paces, profile=profile)
        assert "workoutSegments" in wj

    def test_all_pace_keys_garmin(self, profile, paces):
        """Test that all pace_keys found in catalogs can be resolved for Garmin export."""
        from douini.domain.engine.library import get_catalog
        catalog = get_catalog()
        tested = set()
        for wid, entry in catalog.items():
            pk = entry.get("pace_key", "short")
            if pk in tested:
                continue
            tested.add(pk)
            # Build a dummy workout to test pace resolution
            wd = build_workout(wid, paces, profile=profile)
            assert wd.pace_min is not None, f"pace_key={pk} failed for {wid}"
            assert wd.pace_max is not None

    def test_session_workout_uses_profile(self, profile, paces):
        """build_session_workout must accept and use profile."""
        from douini.domain.models import Session
        wd = build_workout("5K-8x400", paces, profile=profile)
        session = Session(day="mon", workout=wd, type="quality", structure="8x400", distance_km=8.0)
        wj = build_session_workout(session, paces, "Test", profile=profile)
        assert "workoutSegments" in wj


# ── Pace ordering ─────────────────────────────────────────────────────────────

class TestPaceOrdering:
    """Verify pace ordering: VO2 < 5K < threshold (faster = lower s/km)."""

    def test_vo2_faster_than_5k(self, profile):
        assert profile.vo2.fast < profile.race_paces["5K"].target

    def test_5k_faster_than_threshold(self, profile):
        assert profile.race_paces["5K"].target < profile.threshold.fast

    def test_threshold_faster_than_easy(self, profile):
        assert profile.threshold.slow < profile.easy.fast

    def test_norwegian_short_faster_than_medium(self, profile):
        assert profile.norwegian["short"].fast < profile.norwegian["medium"].fast

    def test_norwegian_medium_faster_than_long(self, profile):
        assert profile.norwegian["medium"].fast < profile.norwegian["long"].fast

    def test_race_pace_ordering(self, profile):
        assert profile.race_paces["5K"].target < profile.race_paces["10K"].target
        assert profile.race_paces["10K"].target < profile.race_paces["HM"].target
        assert profile.race_paces["HM"].target < profile.race_paces["MARATHON"].target


# ── Rounding fix ──────────────────────────────────────────────────────────────

class TestPaceRounding:
    """Pace must use round() not int() truncation."""

    def test_scaled_uses_round(self):
        p = Pace(243)
        scaled = p.scaled(1.03)
        # 243 * 1.03 = 250.29 -> round = 250, int = 250 (same here)
        assert scaled.s_per_km == 250

    def test_scaled_round_not_truncate(self):
        p = Pace(200)
        scaled = p.scaled(1.005)
        # 200 * 1.005 = 201.0 -> round = 201
        assert scaled.s_per_km == 201

    def test_from_float_uses_round(self):
        from douini.domain.models import Pace
        p = Pace.from_float(243.6)
        assert p.s_per_km == 244  # round, not truncate to 243
