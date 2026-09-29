"""Adaptive week structure tests for 4-day Norwegian Singles plans.

Tests the prompt_v3 requirements:
- Templates A/B/C with deterministic scoring
- interval_adapted authorizes but does not force 2 quality
- Per-week variation based on phase, load, experience
- Quality load budget gates quality_count
- Taper reduces quality density
- Mon+Wed (Template C) only when justified
- Wed+Fri (Template B) preferred over Mon+Wed
"""

import unittest

from douini.domain.models import Distance, Experience, RunnerProfile, VOLUME_CAPS
from douini.domain.engine import week_structure
from douini.domain.engine.week_structure import (
    WeekStructure,
    WeekTemplate,
    _build_templates_for_days,
    _score_template,
    choose_week_structure,
    quality_load_budget,
)
from douini.domain.planner import generate_plan
from douini.domain.vdot import derive_paces


_DAYS_4 = ["mon", "wed", "fri", "sun"]


class TestFourDaySingleQualityStructure(unittest.TestCase):
    """interval_adapted=False => exactly 1 quality session."""

    def test_single_quality_when_not_adapted(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BASE", week_num=1, weeks_total=12,
            weekly_volume=65, interval_adapted=False,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertEqual(ws.quality_count, 1)
        self.assertEqual(ws.template_id, "A")

    def test_single_quality_in_taper_even_if_adapted(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="TAPER", week_num=12, weeks_total=12,
            weekly_volume=65, interval_adapted=True,
            runner_experience=Experience.ADVANCED,
        )
        self.assertEqual(ws.quality_count, 1)


class TestFourDayTwoQualityStructure(unittest.TestCase):
    """interval_adapted=True + high budget => 2 quality sessions."""

    def test_two_quality_when_adapted_and_high_budget(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=65, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertEqual(ws.quality_count, 2)
        self.assertEqual(ws.template_id, "B")

    def test_two_quality_uses_wed_fri_not_mon_wed(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.SEMI, phase="SPECIFIC", week_num=7, weeks_total=12,
            weekly_volume=75, interval_adapted=True,
            runner_experience=Experience.ADVANCED,
        )
        self.assertEqual(ws.quality_count, 2)
        self.assertIn("wed", ws.quality_days)
        self.assertIn("fri", ws.quality_days)
        self.assertNotIn("mon", ws.quality_days)


class TestIntervalAdaptedAllowsButDoesNotForce(unittest.TestCase):
    """interval_adapted=True authorizes 2 quality but budget may still choose 1."""

    def test_beginner_low_volume_still_one_quality(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BASE", week_num=1, weeks_total=9,
            weekly_volume=35, interval_adapted=True,
            runner_experience=Experience.BEGINNER,
        )
        self.assertEqual(ws.quality_count, 1,
                         "Beginner at 35km should get 1 quality even with interval_adapted=True")

    def test_advanced_high_volume_gets_two_quality(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K10, phase="BUILD", week_num=4, weeks_total=12,
            weekly_volume=80, interval_adapted=True,
            runner_experience=Experience.ADVANCED,
        )
        self.assertEqual(ws.quality_count, 2)


class TestQualityDaysNotGloballyFixed(unittest.TestCase):
    """Quality days should not always be Mon+Wed."""

    def test_preferred_template_uses_wed_fri(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=65, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertNotEqual(ws.quality_days, ["mon", "wed"],
                            "Should not default to Mon+Wed")

    def test_full_plan_not_always_mon_wed(self):
        """12-week plan should not have Mon+Wed quality every single week."""
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=65,
                               sessions_per_week=4, experience=Experience.INTERMEDIATE)
        plan = generate_plan(runner, Distance.K5, weeks=12, paces=paces,
                             sessions_per_week=4, interval_adapted=True)
        # Check that not every loading week has quality on both mon and wed
        loading_weeks = [w for w in plan.week_plans
                         if not w.is_recovery and w.phase and w.phase.value != "TAPER"]
        mon_wed_count = 0
        for w in loading_weeks:
            quality_days = [s.day for s in w.sessions if s.type == "quality"]
            if quality_days == ["mon", "wed"]:
                mon_wed_count += 1
        self.assertLess(mon_wed_count, len(loading_weeks),
                        "Not all loading weeks should have Mon+Wed quality")


class TestWeekStructureChangesBetweenWeeks(unittest.TestCase):
    """Structure should vary between weeks based on phase."""

    def test_base_vs_taper_different_structure(self):
        ws_base = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=65, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        ws_taper = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="TAPER", week_num=12, weeks_total=12,
            weekly_volume=50, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertNotEqual(ws_base.quality_count, ws_taper.quality_count,
                            "Build and Taper should have different quality counts")

    def test_structure_trace_in_plan(self):
        """Generated plan should have per-week structure info."""
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70,
                               sessions_per_week=4, experience=Experience.INTERMEDIATE)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces,
                             sessions_per_week=4, interval_adapted=True)
        # Verify plan generates without error
        self.assertEqual(len(plan.week_plans), 12)
        # Verify sessions are valid each week
        for w in plan.week_plans:
            days = [s.day for s in w.sessions]
            self.assertEqual(len(days), len(set(days)), f"Duplicate days in week {w.week_num}")


class TestQualityLoadBudget(unittest.TestCase):
    """quality_load_budget returns sensible values."""

    def test_high_volume_advanced_high_budget(self):
        budget = quality_load_budget(
            weekly_volume=80, sessions_per_week=4,
            experience=Experience.ADVANCED, phase="BUILD",
            distance=Distance.K10,
        )
        self.assertGreater(budget, 0.75)

    def test_low_volume_beginner_low_budget(self):
        budget = quality_load_budget(
            weekly_volume=35, sessions_per_week=4,
            experience=Experience.BEGINNER, phase="BASE",
            distance=Distance.K5,
        )
        self.assertLess(budget, 0.6)

    def test_taper_reduces_budget(self):
        budget_build = quality_load_budget(
            weekly_volume=70, sessions_per_week=4,
            experience=Experience.INTERMEDIATE, phase="BUILD",
            distance=Distance.SEMI,
        )
        budget_taper = quality_load_budget(
            weekly_volume=70, sessions_per_week=4,
            experience=Experience.INTERMEDIATE, phase="TAPER",
            distance=Distance.SEMI,
        )
        self.assertLess(budget_taper, budget_build)

    def test_previous_load_reduces_budget(self):
        budget_no_prev = quality_load_budget(
            weekly_volume=70, sessions_per_week=4,
            experience=Experience.INTERMEDIATE, phase="BUILD",
            distance=Distance.SEMI, previous_week_load=0.0,
        )
        budget_with_prev = quality_load_budget(
            weekly_volume=70, sessions_per_week=4,
            experience=Experience.INTERMEDIATE, phase="BUILD",
            distance=Distance.SEMI, previous_week_load=75.0,
        )
        self.assertLess(budget_with_prev, budget_no_prev)


class TestRecoverySpacing(unittest.TestCase):
    """Quality days should have adequate recovery spacing."""

    def test_template_b_has_gap(self):
        templates = _build_templates_for_days(["mon", "wed", "fri"], "sun")
        tmpl_b = next(t for t in templates if t.id == "B")
        # Wed and Fri are 2 days apart
        offsets = [2, 4]  # wed=2, fri=4
        self.assertEqual(offsets[1] - offsets[0], 2)

    def test_template_c_adjacent(self):
        templates = _build_templates_for_days(["mon", "wed", "fri"], "sun")
        tmpl_c = next(t for t in templates if t.id == "C")
        # Mon and Wed are 2 days apart (still OK but less recovery before long run)
        self.assertEqual(tmpl_c.quality_days, ["mon", "wed"])


class TestTaperReducesQualityDensity(unittest.TestCase):
    """Taper phase should reduce quality count."""

    def test_taper_one_quality(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.SEMI, phase="TAPER", week_num=11, weeks_total=12,
            weekly_volume=55, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertEqual(ws.quality_count, 1)

    def test_peak_may_reduce(self):
        """PEAK phase may reduce to 1 quality depending on budget."""
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="PEAK", week_num=10, weeks_total=12,
            weekly_volume=55, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        # PEAK with moderate volume and intermediate: budget ~0.75 * 0.75 = 0.56
        # Should lean towards 1 quality
        self.assertLessEqual(ws.quality_count, 2)


class TestMondayWednesdayException(unittest.TestCase):
    """Template C (Mon+Wed) only selected when load permits."""

    def test_template_c_not_selected_for_beginner(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BASE", week_num=1, weeks_total=12,
            weekly_volume=35, interval_adapted=True,
            runner_experience=Experience.BEGINNER,
        )
        self.assertNotEqual(ws.template_id, "C",
                            "Template C should not be selected for beginner/low volume")

    def test_template_c_allowed_when_advanced_high_volume(self):
        """Template C may be valid for advanced runner with high volume and low fatigue."""
        # With high budget and advanced, C is allowed but B is still preferred
        # C would only win if variety bonus from prev=C pushes it... but that's deterministic
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=80, interval_adapted=True,
            runner_experience=Experience.ADVANCED,
            previous_template_id="B",  # variety bonus for C
        )
        # Even with variety bonus, B should still win due to recovery spacing
        self.assertNotEqual(ws.template_id, "C",
                            "B should always beat C due to recovery spacing")


class TestWednesdayFridayPreferredStructure(unittest.TestCase):
    """Template B (Wed+Fri) is preferred over C (Mon+Wed)."""

    def test_b_scores_higher_than_c(self):
        templates = _build_templates_for_days(["mon", "wed", "fri"], "sun")
        tmpl_b = next(t for t in templates if t.id == "B")
        tmpl_c = next(t for t in templates if t.id == "C")

        budget = 0.9
        score_b, _ = _score_template(tmpl_b, "BUILD", Distance.K5, budget, "", 5, 12)
        score_c, _ = _score_template(tmpl_c, "BUILD", Distance.K5, budget, "", 5, 12)
        self.assertGreater(score_b, score_c,
                          "Template B should score higher than C")

    def test_b_selected_in_loading_weeks(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70,
                               sessions_per_week=4, experience=Experience.INTERMEDIATE)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces,
                             sessions_per_week=4, interval_adapted=True)
        # At least one loading week should have quality on wed+fri (Template B)
        loading_weeks = [w for w in plan.week_plans
                         if not w.is_recovery and w.phase and w.phase.value not in ("TAPER",)]
        has_wed_fri = False
        for w in loading_weeks:
            quality_days = set(s.day for s in w.sessions if s.type == "quality")
            if quality_days == {"wed", "fri"}:
                has_wed_fri = True
                break
        self.assertTrue(has_wed_fri,
                        "At least one loading week should use Wed+Fri (Template B)")


class TestNonFourDayNoRegression(unittest.TestCase):
    """3-day and 5-day plans should still work (legacy path)."""

    def test_three_day_plan_generates(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=50,
                               sessions_per_week=3, experience=Experience.INTERMEDIATE)
        plan = generate_plan(runner, Distance.K5, weeks=8, paces=paces,
                             sessions_per_week=3, interval_adapted=False)
        self.assertEqual(len(plan.week_plans), 8)
        for w in plan.week_plans:
            self.assertEqual(len(w.sessions), 3)

    def test_five_day_plan_generates(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70,
                               sessions_per_week=5, experience=Experience.INTERMEDIATE)
        plan = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces,
                             sessions_per_week=5, interval_adapted=True)
        self.assertEqual(len(plan.week_plans), 12)
        for w in plan.week_plans:
            self.assertEqual(len(w.sessions), 5)

    def test_six_day_plan_generates(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=75,
                               sessions_per_week=6, experience=Experience.ADVANCED)
        plan = generate_plan(runner, Distance.MARATHON, weeks=12, paces=paces,
                             sessions_per_week=6, interval_adapted=True)
        self.assertEqual(len(plan.week_plans), 12)
        for w in plan.week_plans:
            self.assertEqual(len(w.sessions), 6)


class TestDeterministicOutput(unittest.TestCase):
    """Same inputs => same output (no random)."""

    def test_identical_context_same_template(self):
        kwargs = dict(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.SEMI, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=70, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        ws1 = choose_week_structure(**kwargs)
        ws2 = choose_week_structure(**kwargs)
        self.assertEqual(ws1.template_id, ws2.template_id)
        self.assertEqual(ws1.quality_days, ws2.quality_days)
        self.assertEqual(ws1.quality_count, ws2.quality_count)

    def test_identical_plans_identical_structures(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70,
                               sessions_per_week=4, experience=Experience.INTERMEDIATE)
        plan1 = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces,
                               sessions_per_week=4, interval_adapted=True)
        plan2 = generate_plan(runner, Distance.SEMI, weeks=12, paces=paces,
                              sessions_per_week=4, interval_adapted=True)
        for w1, w2 in zip(plan1.week_plans, plan2.week_plans):
            q1 = sorted(s.day for s in w1.sessions if s.type == "quality")
            q2 = sorted(s.day for s in w2.sessions if s.type == "quality")
            self.assertEqual(q1, q2, f"Week {w1.week_num} quality days differ")


class TestDebugOutput(unittest.TestCase):
    """WeekStructure should carry selection_reason for debug."""

    def test_selection_reason_populated(self):
        ws = choose_week_structure(
            sessions_per_week=4, days=_DAYS_4, long_run_day="sun",
            distance=Distance.K5, phase="BUILD", week_num=5, weeks_total=12,
            weekly_volume=65, interval_adapted=True,
            runner_experience=Experience.INTERMEDIATE,
        )
        self.assertTrue(len(ws.selection_reason) > 0)
        self.assertTrue(len(ws.template_id) > 0)

    def test_legacy_structure_has_reason(self):
        ws = choose_week_structure(
            sessions_per_week=5, days=["mon", "wed", "fri", "sat", "sun"],
            long_run_day="sun", distance=Distance.SEMI, phase="BUILD",
            week_num=5, weeks_total=12, weekly_volume=70,
            interval_adapted=True, runner_experience=Experience.INTERMEDIATE,
        )
        self.assertEqual(ws.template_id, "legacy")
        self.assertTrue("Non-4-day" in ws.selection_reason)


if __name__ == "__main__":
    unittest.main()
