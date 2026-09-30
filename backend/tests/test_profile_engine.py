"""Tests for the profile engine: validation, defaults, derivation."""

import unittest

from douini.domain.engine.profile import ProfileEngine
from douini.domain.models import (
    Distance,
    Experience,
    MAX_WEEKS,
    MIN_WEEKS,
    RunnerProfile,
    ProfileValidationResult,
    DerivedVars,
)


def _complete_profile(**kw) -> RunnerProfile:
    """Return a profile with all mandatory + recommended fields filled."""
    defaults = dict(
        vdot=49.4,
        weekly_volume_km=70,
        training_days=["mon", "wed", "fri", "sun"],
        target_weekly_km=75,
        sessions_per_week=4,
        race_distance="semi",
        weeks=12,
        target_time="1:30:00",
        experience=Experience.INTERMEDIATE,
        current_weekly_km=65,
        current_longest_run=18,
        long_run_day="sun",
        preferred_days=["mon", "wed", "fri", "sun"],
    )
    defaults.update(kw)
    return RunnerProfile(**defaults)


class ProfileValidationTest(unittest.TestCase):
    """Task 1+2: mandatory fields, validation, derived variables."""

    def test_complete_profile_valid(self):
        p = _complete_profile()
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        self.assertEqual(r.missing_fields, [])
        self.assertEqual(r.errors, [])

    def test_missing_target_time(self):
        p = _complete_profile(target_time=None)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertIn("target_time", r.missing_fields)

    def test_missing_target_weekly_km(self):
        p = _complete_profile(target_weekly_km=None)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertIn("target_weekly_km", r.missing_fields)

    def test_missing_race_distance(self):
        p = _complete_profile(race_distance=None)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertIn("race_distance", r.missing_fields)

    def test_missing_fields_deterministic_order(self):
        p = _complete_profile(
            target_weekly_km=None,
            race_distance=None,
            target_time=None,
        )
        r = ProfileEngine().validate(p)
        self.assertEqual(
            r.missing_fields,
            ["target_weekly_km", "race_distance", "target_time"],
        )

    def test_invalid_vdot(self):
        p = _complete_profile(vdot=0)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("VDOT" in e for e in r.errors))

    def test_invalid_vdot_too_high(self):
        p = _complete_profile(vdot=150)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("VDOT" in e for e in r.errors))

    def test_unsupported_distance(self):
        p = _complete_profile(race_distance="ultra")
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("Distance" in e for e in r.errors))

    def test_sessions_per_week_below_range(self):
        p = _complete_profile(sessions_per_week=2)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)

    def test_sessions_per_week_above_range(self):
        p = _complete_profile(sessions_per_week=8)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)

    def test_weeks_too_few(self):
        p = _complete_profile(weeks=3, race_distance="marathon")
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("semaines" in e.lower() for e in r.errors))

    def test_weeks_too_many(self):
        p = _complete_profile(weeks=20)
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)

    def test_duplicate_training_days(self):
        p = _complete_profile(training_days=["mon", "mon", "fri", "sun"])
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("doublon" in e for e in r.errors))

    def test_long_run_day_not_in_preferred(self):
        p = _complete_profile(long_run_day="sat", preferred_days=["mon", "wed", "fri", "sun"])
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("sortie longue" in e.lower() for e in r.errors))

    def test_duplicate_preferred_days(self):
        p = _complete_profile(preferred_days=["mon", "mon", "fri", "sun"])
        r = ProfileEngine().validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any("preferes" in e.lower() for e in r.errors))

    def test_no_errors_when_only_warnings(self):
        p = _complete_profile(current_weekly_km=20, current_longest_run=5)
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        self.assertTrue(len(r.warnings) > 0)

    def test_no_feasibility_warning_when_volume_ok(self):
        p = _complete_profile(current_weekly_km=72, current_longest_run=16)
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        # Should have no volume-gap warning (72 >= 75*0.70 = 52.5)
        # long run 16 >= 28*0.5 = 14, so no long-run warning either
        self.assertEqual(r.warnings, [])


class DerivedVarsTest(unittest.TestCase):
    """Task 2: all 8 derived variables present and correct."""

    def test_all_eight_derived_vars_present(self):
        p = _complete_profile()
        r = ProfileEngine().validate(p)
        self.assertIsNotNone(r.derived)
        d = r.derived
        self.assertIn(d.volume_level, {"low", "moderate", "high"})
        self.assertIn(d.frequency_level, {"low", "moderate", "high"})
        self.assertIn(d.specificity_need, {"low", "moderate", "high"})
        self.assertIn(d.aerobic_strength, {"developing", "adequate", "strong"})
        self.assertIn(d.speed_requirement, {"low", "moderate", "high"})
        self.assertGreater(d.long_run_requirement, 0)
        self.assertIn(d.recovery_requirement, {"low", "moderate", "high"})
        self.assertGreater(d.training_load_tolerance, 0)
        self.assertLessEqual(d.training_load_tolerance, 1.0)

    def test_volume_level_high(self):
        p = _complete_profile(target_weekly_km=80)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.volume_level, "high")

    def test_volume_level_low(self):
        p = _complete_profile(target_weekly_km=30)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.volume_level, "low")

    def test_volume_level_moderate(self):
        p = _complete_profile(target_weekly_km=50)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.volume_level, "moderate")

    def test_frequency_level_low(self):
        p = _complete_profile(sessions_per_week=3)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.frequency_level, "low")

    def test_frequency_level_high(self):
        p = _complete_profile(sessions_per_week=6)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.frequency_level, "high")

    def test_specificity_5k(self):
        p = _complete_profile(race_distance="5k", weeks=6)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.specificity_need, "high")
        self.assertEqual(r.derived.speed_requirement, "high")

    def test_specificity_marathon(self):
        p = _complete_profile(race_distance="marathon", weeks=14)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.specificity_need, "low")
        self.assertEqual(r.derived.speed_requirement, "low")

    def test_aerobic_strength_developing(self):
        p = _complete_profile(target_weekly_km=80, current_weekly_km=40)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.aerobic_strength, "developing")

    def test_aerobic_strength_strong(self):
        p = _complete_profile(target_weekly_km=70, current_weekly_km=68)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.aerobic_strength, "strong")

    def test_long_run_requirement_marathon(self):
        p = _complete_profile(race_distance="marathon", weeks=14)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.long_run_requirement, 32)

    def test_long_run_requirement_5k(self):
        p = _complete_profile(race_distance="5k", weeks=6)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.long_run_requirement, 18)

    def test_recovery_requirement_high(self):
        p = _complete_profile(target_weekly_km=80, sessions_per_week=7)
        r = ProfileEngine().validate(p)
        self.assertEqual(r.derived.recovery_requirement, "high")

    def test_training_load_tolerance_beginner(self):
        p = _complete_profile(experience=Experience.BEGINNER, target_weekly_km=50)
        r = ProfileEngine().validate(p)
        self.assertLess(r.derived.training_load_tolerance, 0.85)

    def test_training_load_tolerance_advanced(self):
        p = _complete_profile(experience=Experience.ADVANCED, target_weekly_km=50)
        r = ProfileEngine().validate(p)
        self.assertAlmostEqual(r.derived.training_load_tolerance, 1.0)


class ApplyDefaultsTest(unittest.TestCase):
    """Task 1: recommended defaults applied correctly."""

    def test_defaults_applied_when_missing(self):
        p = RunnerProfile(
            vdot=49.4,
            weekly_volume_km=70,
            training_days=["mon", "wed", "fri", "sun"],
            target_weekly_km=75,
            sessions_per_week=4,
            race_distance="semi",
            weeks=12,
            target_time="1:30:00",
        )
        pe = ProfileEngine()
        pe.apply_defaults(p)
        self.assertIsNotNone(p.current_weekly_km)
        self.assertEqual(p.current_weekly_km, 75)  # defaults to target
        self.assertIsNotNone(p.preferred_days)
        self.assertEqual(p.long_run_day, p.preferred_days[-1])
        self.assertIsNotNone(p.current_longest_run)
        self.assertEqual(p.experience, Experience.INTERMEDIATE)

    def test_defaults_dont_override_explicit(self):
        p = _complete_profile(current_weekly_km=50, long_run_day="sat")
        ProfileEngine().apply_defaults(p)
        self.assertEqual(p.current_weekly_km, 50)
        self.assertEqual(p.long_run_day, "sat")

    def test_derived_not_in_persistence(self):
        """Derived fields are computed, not stored on the profile."""
        p = _complete_profile()
        r = ProfileEngine().validate(p)
        # The profile should not have a 'derived' attribute
        self.assertFalse(hasattr(p, "derived"))
        self.assertTrue(hasattr(r, "derived"))


class FeasibilityWarningsTest(unittest.TestCase):
    """Task 2: feasibility warnings without mutating user data."""

    def test_volume_gap_warning(self):
        p = _complete_profile(target_weekly_km=80, current_weekly_km=30)
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        self.assertTrue(any("Volume" in w for w in r.warnings))

    def test_long_run_gap_warning(self):
        p = _complete_profile(race_distance="marathon", weeks=14,
                              current_longest_run=5)
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        self.assertTrue(any("sortie longue" in w.lower() for w in r.warnings))

    def test_no_warning_when_fit(self):
        p = _complete_profile(
            target_weekly_km=70, current_weekly_km=68,
            current_longest_run=20, race_distance="semi",
        )
        r = ProfileEngine().validate(p)
        self.assertTrue(r.valid)
        self.assertEqual(r.warnings, [])


class ProfileConstructCompatTest(unittest.TestCase):
    """Task 1: existing callers can still construct RunnerProfile."""

    def test_legacy_constructor(self):
        p = RunnerProfile(vdot=49.4, weekly_volume_km=70)
        self.assertEqual(p.vdot, 49.4)
        self.assertEqual(p.weekly_volume_km, 70)
        self.assertIsNone(p.target_weekly_km)
        self.assertEqual(p.sessions_per_week, 4)

    def test_volume_cap_still_works(self):
        p = RunnerProfile(vdot=49.4, weekly_volume_km=70, mileage_tolerance_km=5)
        self.assertEqual(p.volume_cap, 75)

    def test_phase1_fields_still_present(self):
        p = RunnerProfile(vdot=49.4)
        self.assertEqual(p.experience, Experience.INTERMEDIATE)
        self.assertEqual(p.weeks, 12)
        self.assertIsNone(p.race_distance)

    def test_new_fields_default_none(self):
        p = RunnerProfile(vdot=49.4)
        self.assertIsNone(p.current_weekly_km)
        self.assertIsNone(p.current_longest_run)
        self.assertIsNone(p.long_run_day)
        self.assertIsNone(p.preferred_days)


if __name__ == "__main__":
    unittest.main()
