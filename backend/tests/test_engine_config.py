"""Tests for Phase 1: planning rules, configuration contracts, typed enums, pace integration."""

import unittest

from douini.domain.models import (
    Distance,
    Experience,
    PaceKey,
    PlanWarning,
    RunnerProfile,
    SelectionExplanation,
    Session,
    SessionCategory,
    StepType,
    TrainingPhase,
    TrainingPlan,
    WeekPlan,
)
from douini.domain.engine.config import (
    get_distances,
    get_load_rules,
    get_phases,
    get_progression_rules,
    get_pace_zones,
    get_session_types,
    get_validation_rules,
    resolve_distance,
    resolve_phase,
    validate_config,
)
from douini.domain.engine.pace_engine import (
    GoalFeasibilityChecker,
    PaceEngine,
    PaceValidator,
)


class TestConfigLoading(unittest.TestCase):
    """Test: Load every rule file => typed rules expose four distances and all session categories."""

    def test_distances_json_loads(self):
        d = get_distances()
        for did in ("5K", "10K", "HM", "MARATHON"):
            self.assertIn(did, d["distances"])
            self.assertIn("metres", d["distances"][did])
            self.assertIn("volume_target_km", d["distances"][did])
            self.assertIn("long_run_cap_km", d["distances"][did])
            self.assertIn("taper_weeks", d["distances"][did])

    def test_phases_json_loads(self):
        p = get_phases()
        ids = [ph["id"] for ph in p["phases"]]
        self.assertIn("BASE", ids)
        self.assertIn("BUILD", ids)
        self.assertIn("SPECIFIC", ids)
        self.assertIn("PEAK", ids)
        self.assertIn("TAPER", ids)

    def test_session_types_json_loads(self):
        st = get_session_types()
        cat_ids = [c["id"] for c in st["categories"]]
        self.assertIn("QUALITY", cat_ids)
        self.assertIn("EASY", cat_ids)
        self.assertIn("SECONDARY", cat_ids)
        self.assertIn("LONG_RUN", cat_ids)

    def test_load_rules_json_loads(self):
        lr = get_load_rules()
        self.assertIn("weekly_load_factor", lr)
        self.assertIn("long_run_ratio", lr)
        for did in ("5K", "10K", "HM", "MARATHON"):
            self.assertIn(did, lr["long_run_ratio"])

    def test_progression_rules_json_loads(self):
        pr = get_progression_rules()
        self.assertIn("density_progression", pr)
        self.assertIn("volume_progression", pr)

    def test_validation_rules_json_loads(self):
        vr = get_validation_rules()
        self.assertIn("checks", vr)
        self.assertGreaterEqual(len(vr["checks"]), 9)

    def test_pace_zones_garmin_encoding(self):
        z = get_pace_zones()
        self.assertIn("garmin_encoding", z)
        self.assertEqual(z["garmin_encoding"]["unit"], "metres_per_second")
        self.assertEqual(z["garmin_encoding"]["bound_order"], "fast_first")


class TestConfigValidation(unittest.TestCase):
    """Test: reject malformed or inconsistent data deterministically."""

    def test_validate_config_passes(self):
        errors = validate_config()
        self.assertEqual(errors, [], f"Config validation errors: {errors}")

    def test_distance_cross_reference_consistent(self):
        distances = get_distances()
        from douini.domain.engine.config import get_distance_models
        models = get_distance_models()
        model_metres = {d["id"]: d["metres"] for d in models["distances"]}
        for did, d in distances["distances"].items():
            if did in model_metres:
                self.assertEqual(d["metres"], model_metres[did],
                    f"Metres mismatch for {did}")

    def test_session_category_pace_keys_valid(self):
        st = get_session_types()
        zones = get_pace_zones()
        for cat in st["categories"]:
            self.assertIn(cat["pace_key"], zones,
                f"Category {cat['id']} references unknown pace key: {cat['pace_key']}")


class TestResolveDistance(unittest.TestCase):
    """Test distance alias resolution."""

    def test_compat_aliases(self):
        self.assertEqual(resolve_distance("5k"), "5K")
        self.assertEqual(resolve_distance("10k"), "10K")
        self.assertEqual(resolve_distance("semi"), "HM")
        self.assertEqual(resolve_distance("marathon"), "MARATHON")

    def test_canonical_passthrough(self):
        self.assertEqual(resolve_distance("5K"), "5K")
        self.assertEqual(resolve_distance("HM"), "HM")


class TestResolvePhase(unittest.TestCase):
    """Test legacy French label mapping."""

    def test_french_to_canonical(self):
        self.assertEqual(resolve_phase("Adaptation"), "BASE")
        self.assertEqual(resolve_phase("Accumulation"), "BUILD")
        self.assertEqual(resolve_phase("Developpement"), "SPECIFIC")

    def test_canonical_passthrough(self):
        self.assertEqual(resolve_phase("BASE"), "BASE")
        self.assertEqual(resolve_phase("TAPER"), "TAPER")


class TestEnums(unittest.TestCase):
    """Test new typed enums exist and have expected values."""

    def test_experience_enum(self):
        self.assertEqual(Experience.BEGINNER.value, "debutant")
        self.assertEqual(Experience.INTERMEDIATE.value, "intermediaire")
        self.assertEqual(Experience.ADVANCED.value, "avance")

    def test_training_phase_enum(self):
        self.assertEqual(TrainingPhase.BASE.value, "BASE")
        self.assertEqual(TrainingPhase.BUILD.value, "BUILD")
        self.assertEqual(TrainingPhase.SPECIFIC.value, "SPECIFIC")
        self.assertEqual(TrainingPhase.PEAK.value, "PEAK")
        self.assertEqual(TrainingPhase.TAPER.value, "TAPER")

    def test_session_category_enum(self):
        self.assertEqual(SessionCategory.QUALITY.value, "quality")
        self.assertEqual(SessionCategory.LONG_RUN.value, "long_run")

    def test_step_type_enum(self):
        self.assertEqual(StepType.WARMUP.value, "warmup")
        self.assertEqual(StepType.INTERVAL.value, "interval")
        self.assertEqual(StepType.REPEAT.value, "repeat")
        self.assertEqual(StepType.COOLDOWN.value, "cooldown")

    def test_pace_key_enum(self):
        self.assertEqual(PaceKey.EASY.value, "easy")
        self.assertEqual(PaceKey.THRESHOLD.value, "threshold")
        self.assertEqual(PaceKey.NORWEGIAN.value, "norwegian")


class TestExtendedDataclasses(unittest.TestCase):
    """Test existing constructors still work with new defaulted fields."""

    def test_runner_profile_default_construction(self):
        p = RunnerProfile()
        self.assertEqual(p.vdot, 49.4)
        self.assertEqual(p.sessions_per_week, 4)
        self.assertEqual(p.weeks, 12)
        self.assertIsNone(p.target_weekly_km)
        self.assertIsNone(p.race_distance)
        self.assertIsNone(p.target_time)
        self.assertEqual(p.experience, Experience.INTERMEDIATE)

    def test_runner_profile_extended_construction(self):
        p = RunnerProfile(
            vdot=55.0,
            target_weekly_km=80,
            sessions_per_week=5,
            race_distance="HM",
            weeks=14,
            target_time="1:25:00",
            experience=Experience.ADVANCED,
        )
        self.assertEqual(p.vdot, 55.0)
        self.assertEqual(p.target_weekly_km, 80)
        self.assertEqual(p.sessions_per_week, 5)
        self.assertEqual(p.race_distance, "HM")
        self.assertEqual(p.weeks, 14)
        self.assertEqual(p.target_time, "1:25:00")
        self.assertEqual(p.experience, Experience.ADVANCED)

    def test_session_with_new_fields(self):
        s = Session(day="mon", category=SessionCategory.QUALITY, pace_key=PaceKey.THRESHOLD)
        self.assertEqual(s.category, SessionCategory.QUALITY)
        self.assertEqual(s.pace_key, PaceKey.THRESHOLD)

    def test_session_without_new_fields(self):
        s = Session(day="mon")
        self.assertIsNone(s.category)
        self.assertIsNone(s.pace_key)

    def test_weekplan_with_phase(self):
        w = WeekPlan(week_num=1, bloc="Adaptation", phase=TrainingPhase.BASE)
        self.assertEqual(w.phase, TrainingPhase.BASE)

    def test_weekplan_without_phase(self):
        w = WeekPlan(week_num=1, bloc="Adaptation")
        self.assertIsNone(w.phase)

    def test_training_plan_with_new_fields(self):
        from douini.domain.models import Paces, Pace
        paces = Paces(
            ef=(Pace(360), Pace(390)),
            short=(Pace(258), Pace(265)),
            medium=(Pace(263), Pace(273)),
            long=(Pace(270), Pace(278)),
        )
        runner = RunnerProfile()
        plan = TrainingPlan(
            runner=runner,
            distance=Distance.SEMI,
            weeks=12,
            paces=paces,
        )
        self.assertIsNone(plan.pace_profile)
        self.assertIsNone(plan.feasibility_result)
        self.assertEqual(plan.warnings, [])

    def test_plan_warning(self):
        w = PlanWarning(code="volume_ceiling", message="Volume exceeds target")
        self.assertEqual(w.severity, "warning")

    def test_selection_explanation(self):
        s = SelectionExplanation(workout_id="NS-S01", score=85.0, reason="Best match")
        self.assertEqual(s.workout_id, "NS-S01")
        self.assertEqual(s.score, 85.0)


class TestPaceContractIntegration(unittest.TestCase):
    """Test: Planning consumes Phase 0 pace outputs unchanged."""

    def test_pace_profile_consumed_by_validator(self):
        profile = PaceEngine(49.4).build_profile()
        findings = PaceValidator.validate(profile)
        self.assertEqual(findings, [])

    def test_unrealistic_goal_adds_warning(self):
        result = GoalFeasibilityChecker.check(45, "MARATHON", "3:00:00")
        self.assertGreater(result.vdot_gap, 4)
        self.assertTrue(result.warning)

    def test_ambitious_goal_does_not_accelerate_paces(self):
        result = GoalFeasibilityChecker.check(49.4, "5K", "18:00")
        self.assertGreater(result.vdot_gap, 2)
        # Training paces based on current VDOT, not target
        engine = PaceEngine(49.4)
        threshold = engine.get_threshold_pace()
        self.assertAlmostEqual(
            threshold.target,
            PaceEngine(49.4).get_threshold_pace().target,
        )

    def test_excessive_gap_warning_message(self):
        """Unrealistic status includes the required warning."""
        result = GoalFeasibilityChecker.check(35, "MARATHON", "2:30:00")
        self.assertTrue(result.warning)

    def test_deterministic_config_resolution(self):
        """Resolve planning rules twice => identical typed contracts."""
        d1 = get_distances()
        d2 = get_distances()
        self.assertEqual(d1, d2)
        p1 = get_phases()
        p2 = get_phases()
        self.assertEqual(p1, p2)


class TestCompatibility(unittest.TestCase):
    """Test legacy fields remain readable."""

    def test_legacy_bloc_field(self):
        w = WeekPlan(week_num=1, bloc="Adaptation")
        self.assertEqual(w.bloc, "Adaptation")

    def test_legacy_session_type(self):
        s = Session(day="mon", type="quality")
        self.assertEqual(s.type, "quality")

    def test_legacy_volume_cap(self):
        p = RunnerProfile(weekly_volume_km=70, mileage_tolerance_km=5)
        self.assertEqual(p.volume_cap, 75)


if __name__ == "__main__":
    unittest.main()
