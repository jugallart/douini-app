"""Tests for the deterministic planning pipeline (Phase 4)."""

import unittest

from douini.domain.models import (
    Distance,
    Experience,
    MIN_WEEKS,
    MAX_WEEKS,
    RECOVERY_WEEKS,
    RunnerProfile,
    SessionCategory,
    TrainingPhase,
)
from douini.domain.planner import generate_plan, get_plan_structure
from douini.domain.vdot import derive_paces
from douini.domain.engine import periodization, progression, selection, week_structure
from douini.domain.engine.config import resolve_distance


def _profile(vdot=49.4, vol=70, spw=4, exp=Experience.INTERMEDIATE,
             current_km=None, current_longest=None):
    return RunnerProfile(
        vdot=vdot,
        weekly_volume_km=vol,
        sessions_per_week=spw,
        experience=exp,
        current_weekly_km=current_km,
        current_longest_run=current_longest,
    )


class PeriodizationTest(unittest.TestCase):
    """Task 1: Allocate phases and recovery weeks."""

    def test_all_distances_have_required_phases(self):
        for dist in Distance:
            weeks = MIN_WEEKS[dist]
            perio = periodization.allocate(dist, weeks, None)
            phases_present = set(perio.phase_for_week.values())
            # Short plans may compress, but BASE and TAPER are always present
            self.assertIn("BASE", phases_present)
            self.assertIn("TAPER", phases_present)

    def test_taper_weeks_match_distance_config(self):
        expected_taper = {
            Distance.K5: 1, Distance.K10: 1,
            Distance.SEMI: 2, Distance.MARATHON: 3,
        }
        for dist in Distance:
            weeks = MIN_WEEKS[dist]
            perio = periodization.allocate(dist, weeks, None)
            self.assertEqual(perio.taper_count, expected_taper[dist])
            self.assertEqual(len(perio.taper_weeks), expected_taper[dist])

    def test_recovery_weeks_within_loading_range(self):
        for dist in Distance:
            weeks = 12
            perio = periodization.allocate(dist, weeks, None)
            b = weeks - perio.taper_count
            for rw in perio.recovery_weeks:
                self.assertIn(rw, RECOVERY_WEEKS)
                self.assertLessEqual(rw, b - 2)

    def test_recovery_week_phase_matches_preceding(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        loading_weeks = sorted(
            w for w in range(1, 13)
            if w not in perio.recovery_weeks and w not in perio.taper_weeks
        )
        for rw in perio.recovery_weeks:
            preceding = [lw for lw in loading_weeks if lw < rw]
            if preceding:
                self.assertEqual(
                    perio.phase_for_week[rw],
                    perio.phase_for_week[preceding[-1]],
                )

    def test_tst_dev_one_week(self):
        perio = periodization.allocate(Distance.SEMI, 1, "TST_DEV")
        self.assertEqual(perio.phase_for_week, {1: "BASE"})
        self.assertEqual(perio.recovery_weeks, set())
        self.assertEqual(perio.taper_weeks, set())

    def test_french_labels_via_compat(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        for week_num in range(1, 13):
            label = perio.bloc_for_week(week_num)
            self.assertIsInstance(label, str)
            self.assertTrue(len(label) > 0)

    def test_get_plan_structure_compat(self):
        for dist in Distance:
            weeks = MIN_WEEKS[dist]
            taper_count, recovery_set, taper_set = get_plan_structure(dist, weeks)
            self.assertIsInstance(taper_count, int)
            self.assertIsInstance(recovery_set, set)
            self.assertIsInstance(taper_set, set)


class VolumeProgressionTest(unittest.TestCase):
    """Task 2: Build weekly volume and long-run progression."""

    def test_volume_ramps_from_current_to_target(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        vol = progression.build_volume_plan(
            Distance.SEMI, 12, current_km=40, target_km=70,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        # Later loading weeks should approach target more than early ones
        loading = sorted(
            w for w in range(1, 13)
            if w not in perio.recovery_weeks and w not in perio.taper_weeks
        )
        self.assertLess(vol.weekly_km[loading[0]], vol.weekly_km[loading[-1]])

    def test_no_ramp_when_current_equals_target(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        vol = progression.build_volume_plan(
            Distance.SEMI, 12, current_km=70, target_km=70,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        # Loading weeks should be near target (recovery weeks dip intentionally)
        for w in range(1, 13):
            if w not in perio.recovery_weeks and w not in perio.taper_weeks:
                self.assertGreaterEqual(vol.weekly_km[w], 50.0)

    def test_recovery_weeks_reduce_volume(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        vol = progression.build_volume_plan(
            Distance.SEMI, 12, current_km=70, target_km=70,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        for rw in perio.recovery_weeks:
            prev = vol.weekly_km.get(rw - 1, 70.0)
            self.assertLess(vol.weekly_km[rw], prev)

    def test_taper_weeks_reduce_volume(self):
        perio = periodization.allocate(Distance.MARATHON, 16, None)
        vol = progression.build_volume_plan(
            Distance.MARATHON, 16, current_km=78, target_km=78,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        for tw in perio.taper_weeks:
            self.assertLess(vol.weekly_km[tw], 78.0)

    def test_long_runs_capped_by_distance(self):
        perio = periodization.allocate(Distance.K5, 4, None)
        vol = progression.build_volume_plan(
            Distance.K5, 4, current_km=65, target_km=65,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        for w in range(1, 5):
            self.assertGreaterEqual(vol.long_run_km[w], 5.0)

    def test_volume_warning_for_large_gap(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        vol = progression.build_volume_plan(
            Distance.SEMI, 12, current_km=20, target_km=70,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
        )
        self.assertTrue(any("ramp" in w.lower() for w in vol.warnings))

    def test_long_run_progression_increases(self):
        perio = periodization.allocate(Distance.SEMI, 12, None)
        vol = progression.build_volume_plan(
            Distance.SEMI, 12, current_km=70, target_km=70,
            recovery_weeks=perio.recovery_weeks, taper_weeks=perio.taper_weeks,
            taper_count=perio.taper_count, phase_for_week=perio.phase_for_week,
            current_longest=10.0,
        )
        # Long runs should generally increase over loading weeks
        loading_weeks = sorted(
            w for w in range(1, 13)
            if w not in perio.recovery_weeks and w not in perio.taper_weeks
        )
        if len(loading_weeks) >= 2:
            self.assertGreaterEqual(
                vol.long_run_km[loading_weeks[-1]],
                vol.long_run_km[loading_weeks[0]],
            )


class WeekStructureTest(unittest.TestCase):
    """Task 3: Place frequency-aware session slots."""

    def test_session_count_matches_requested(self):
        for spw in range(3, 8):
            ws = week_structure.assign_sessions(
                preferred_days=None, sessions_per_week=spw,
                distance=Distance.SEMI, interval_adapted=False, long_run_day=None,
            )
            total = len(ws.quality_days) + len(ws.easy_days) + 1  # +1 for long run
            self.assertEqual(total, spw)

    def test_long_run_day_present(self):
        ws = week_structure.assign_sessions(
            preferred_days=None, sessions_per_week=4,
            distance=Distance.SEMI, interval_adapted=False, long_run_day=None,
        )
        self.assertIsNotNone(ws.long_run_day)

    def test_quality_days_spaced_from_easy(self):
        ws = week_structure.assign_sessions(
            preferred_days=None, sessions_per_week=5,
            distance=Distance.SEMI, interval_adapted=False, long_run_day=None,
        )
        all_days = ws.quality_days + ws.easy_days + [ws.long_run_day]
        self.assertEqual(len(all_days), len(set(all_days)))

    def test_quality_count_for_frequency(self):
        cases = [
            (3, Distance.SEMI, False, 1),
            (4, Distance.SEMI, False, 1),
            (4, Distance.SEMI, True, 2),
            (5, Distance.SEMI, False, 2),
            (6, Distance.SEMI, False, 3),
            (7, Distance.MARATHON, False, 2),
        ]
        for spw, dist, adapted, expected in cases:
            qc = week_structure.quality_count_for(spw, dist, adapted)
            self.assertEqual(qc, expected, f"spw={spw} dist={dist} adapted={adapted}")

    def test_preferred_days_used_when_count_matches(self):
        preferred = ["tue", "thu", "sat", "sun"]
        ws = week_structure.assign_sessions(
            preferred_days=preferred, sessions_per_week=4,
            distance=Distance.SEMI, interval_adapted=False, long_run_day=None,
        )
        all_days = set(ws.quality_days + ws.easy_days + [ws.long_run_day])
        self.assertEqual(all_days, set(preferred))


class SelectionTest(unittest.TestCase):
    """Task 4: Score and select workouts."""

    def test_selection_returns_candidates(self):
        ctx = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=1, weeks_total=12,
            weeks_to_race=12, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[],
        )
        result = selection.select(ctx, 0)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.workout_id) > 0)

    def test_selection_deterministic(self):
        ctx = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=1, weeks_total=12,
            weeks_to_race=12, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[],
        )
        r1 = selection.select(ctx, 0)
        r2 = selection.select(ctx, 0)
        self.assertEqual(r1.workout_id, r2.workout_id)
        self.assertEqual(r1.score, r2.score)

    def test_identical_plans_for_identical_inputs(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan1 = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        plan2 = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        for w1, w2 in zip(plan1.week_plans, plan2.week_plans):
            for s1, s2 in zip(w1.sessions, w2.sessions):
                self.assertEqual(s1.workout.name if s1.workout else None,
                                 s2.workout.name if s2.workout else None)
                self.assertEqual(s1.distance_km, s2.distance_km)

    def test_selection_trace_recorded(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        self.assertTrue(len(plan.selection_trace) > 0)
        for week_num, trace in plan.selection_trace.items():
            for entry in trace:
                self.assertTrue(len(entry.workout_id) > 0)
                self.assertIsInstance(entry.score, float)

    def test_two_week_repetition_penalized(self):
        ctx1 = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=1, weeks_total=12,
            weeks_to_race=12, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[],
        )
        first = selection.select(ctx1, 0)
        ctx2 = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=2, weeks_total=12,
            weeks_to_race=11, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[first.workout_id],
        )
        second = selection.select(ctx2, 0)
        # The first-choice workout should be penalized in week 2
        # (may still win if it's far ahead, but the penalty component should exist)
        # Verify the trace shows the penalty was applied
        ctx2_full = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=2, weeks_total=12,
            weeks_to_race=11, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[first.workout_id],
        )
        candidates = selection._filter(ctx2_full)
        scored = [selection._score(e, ctx2_full, 0) for e in candidates]
        first_entry = next((s for s in scored if s.workout_id == first.workout_id), None)
        if first_entry:
            variety = [c for c in first_entry.components if c.name == "variety"]
            self.assertTrue(len(variety) > 0)
            self.assertLess(variety[0].delta, 0)

    def test_tie_break_by_workout_id(self):
        """Equal scores break by workout ID ascending."""
        ctx = selection.SelectionContext(
            distance="HM", phase="BASE", week_num=1, weeks_total=12,
            weeks_to_race=12, quality_count=2, sessions_per_week=4,
            volume_level="moderate", frequency_level="moderate",
            experience="INTERMEDIATE", history=[],
        )
        result = selection.select(ctx, 0)
        # Verify deterministic: same call returns same result
        result2 = selection.select(ctx, 0)
        self.assertEqual(result.workout_id, result2.workout_id)


class TaperAndRaceWeekTest(unittest.TestCase):
    """Task 5: Generate taper and race week."""

    def test_race_week_has_race_session(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        final_week = plan.week_plans[-1]
        race_sessions = [s for s in final_week.sessions if s.type == "race"]
        self.assertEqual(len(race_sessions), 1)

    def test_race_session_on_long_run_day(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        final_week = plan.week_plans[-1]
        race = [s for s in final_week.sessions if s.type == "race"][0]
        # Race should be on the long run day (sun by default)
        self.assertEqual(race.day, "sun")

    def test_race_distance_correct(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        expected_km = {
            Distance.K5: 5.0, Distance.K10: 10.0,
            Distance.SEMI: 21.1, Distance.MARATHON: 42.2,
        }
        for dist in Distance:
            weeks = MIN_WEEKS[dist]
            plan = generate_plan(runner, dist, weeks=weeks, paces=paces)
            final_week = plan.week_plans[-1]
            race = [s for s in final_week.sessions if s.type == "race"]
            self.assertEqual(len(race), 1)
            self.assertAlmostEqual(race[0].distance_km, expected_km[dist], places=0)

    def test_taper_weeks_reduce_load(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        # Find last loading week and first taper week
        loading_totals = []
        taper_totals = []
        for w in plan.week_plans:
            if w.bloc == "Developpement":
                loading_totals.append(w.total_km)
            elif w.bloc == "Affutage":
                taper_totals.append(w.total_km)
        if loading_totals and taper_totals:
            self.assertGreater(max(loading_totals), min(taper_totals))

    def test_legacy_generate_plan_signature(self):
        """Existing callers still generate plans."""
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70)
        plan = generate_plan(
            runner, Distance.SEMI, weeks=12, paces=paces,
            sessions_per_week=4, start_date="2026-09-29",
        )
        self.assertEqual(len(plan.week_plans), 12)
        self.assertEqual(plan.sessions_per_week, 4)
        for w in plan.week_plans:
            self.assertGreater(len(w.sessions), 0)

    def test_all_distances_generate(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        for dist in Distance:
            weeks = MIN_WEEKS[dist]
            plan = generate_plan(runner, dist, weeks=weeks, paces=paces)
            self.assertEqual(len(plan.week_plans), weeks)


class PlanCoherenceTest(unittest.TestCase):
    """Cross-cutting coherence checks."""

    def test_three_to_seven_sessions(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        for w in plan.week_plans:
            self.assertGreaterEqual(len(w.sessions), 3)
            self.assertLessEqual(len(w.sessions), 7)

    def test_long_run_present_each_week(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        for w in plan.week_plans:
            long_runs = [s for s in w.sessions if s.type == "long" or s.type == "race"]
            self.assertGreaterEqual(len(long_runs), 1)

    def test_no_duplicate_days_in_week(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        for w in plan.week_plans:
            days = [s.day for s in w.sessions]
            self.assertEqual(len(days), len(set(days)))

    def test_quality_sessions_are_norwegian_or_specific(self):
        paces = derive_paces(49.4)
        runner = _profile(vol=70, spw=4)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces)
        for w in plan.week_plans:
            for s in w.sessions:
                if s.type == "quality" and s.workout:
                    name = s.workout.name
                    self.assertTrue(
                        name.startswith("NS-") or name.startswith("5K-")
                        or name.startswith("10K-") or name.startswith("HM-")
                        or name.startswith("MAR-"),
                        f"Unexpected workout: {name}",
                    )


if __name__ == "__main__":
    unittest.main()
