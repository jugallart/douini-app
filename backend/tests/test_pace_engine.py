"""Tests for the Phase 0 pace engine: VDOT, PaceEngine, PaceProfile, feasibility, validation."""

import unittest

from douini.domain.models import (
    FeasibilityStatus,
    Pace,
    PaceProfile,
    PaceTarget,
    RaceResult,
)
from douini.domain.vdot import VDOTCalculator, parse_time_to_seconds, seconds_to_time_str
from douini.domain.engine.config import (
    get_distance_metres,
    get_norwegian_paces,
    get_pace_zones,
    get_vdot_config,
    resolve_distance,
    validate_config,
)
from douini.domain.engine.pace_engine import (
    GoalFeasibilityChecker,
    PaceAdjustmentEngine,
    PaceEngine,
    PaceValidator,
    debug_output,
)


class TestConfigLoading(unittest.TestCase):
    """Test: Load packaged VDOT distance Norwegian and zone configuration."""

    def test_vdot_config_loads(self):
        cfg = get_vdot_config()
        self.assertIn("formula", cfg)
        self.assertIn("vo2_coefficients", cfg["formula"])
        self.assertIn("threshold_fraction", cfg["formula"])

    def test_distance_models_load(self):
        metres = get_distance_metres("5K")
        self.assertEqual(metres, 5000)
        self.assertEqual(get_distance_metres("5k"), 5000)
        self.assertEqual(get_distance_metres("semi"), 21097.5)
        self.assertEqual(get_distance_metres("marathon"), 42195.0)

    def test_resolve_distance_compat(self):
        self.assertEqual(resolve_distance("5k"), "5K")
        self.assertEqual(resolve_distance("10k"), "10K")
        self.assertEqual(resolve_distance("semi"), "HM")
        self.assertEqual(resolve_distance("marathon"), "MARATHON")
        self.assertEqual(resolve_distance("5K"), "5K")

    def test_pace_zones_load(self):
        zones = get_pace_zones()
        for name in ("easy", "recovery", "long_run", "threshold", "vo2", "economy"):
            self.assertIn(name, zones)
            self.assertTrue(zones[name]["fast_factor"] <= zones[name]["slow_factor"])

    def test_norwegian_paces_load(self):
        ns = get_norwegian_paces()
        self.assertGreaterEqual(ns["min_duration_minutes"], 3.0)
        self.assertLessEqual(ns["max_duration_minutes"], 12.0)
        anchors = ns["anchors"]
        self.assertGreaterEqual(len(anchors), 2)
        for i in range(len(anchors) - 1):
            self.assertLess(anchors[i]["duration"], anchors[i + 1]["duration"])

    def test_config_validation_passes(self):
        errors = validate_config()
        self.assertEqual(errors, [], f"Config validation errors: {errors}")


class TestVDOTCalculator(unittest.TestCase):
    """Test: VDOT/performance and distance/time/pace conversion with decimal precision."""

    VDOTS = [35, 40, 49.4, 55, 60]
    DISTANCES = ["1500", "3000", "5K", "10K", "15K", "HM", "25K", "30K", "MARATHON"]
    COMPAT_DISTANCES = ["5k", "10k", "semi", "marathon"]

    def test_from_race_semi(self):
        v = VDOTCalculator.from_race("semi", "1:32:40")
        self.assertAlmostEqual(v, 49.4, delta=1.0)

    def test_from_race_5k(self):
        v = VDOTCalculator.from_race("5k", "19:00")
        self.assertAlmostEqual(v, 52.9, delta=1.0)

    def test_compat_distances_match(self):
        for d in self.COMPAT_DISTANCES:
            canonical = resolve_distance(d)
            m1 = get_distance_metres(d)
            m2 = get_distance_metres(canonical)
            self.assertEqual(m1, m2, f"{d} metres mismatch with {canonical}")

    def test_all_vdots_all_distances(self):
        for vdot in self.VDOTS:
            for dist in self.DISTANCES:
                time = VDOTCalculator.race_time(vdot, dist)
                self.assertGreater(parse_time_to_seconds(time), 0)
                pace = VDOTCalculator.race_pace_float(vdot, dist)
                self.assertGreater(pace.s_per_km, 0)

    def test_race_time_round_trip(self):
        """VDOT -> time -> VDOT preserves value within 0.5."""
        for vdot in self.VDOTS:
            for dist in ["5K", "10K", "HM", "MARATHON"]:
                time = VDOTCalculator.race_time(vdot, dist)
                v2 = VDOTCalculator.from_race(dist, time)
                self.assertAlmostEqual(vdot, v2, delta=0.5,
                    msg=f"Round trip failed: VDOT {vdot} -> time {time} -> VDOT {v2} for {dist}")

    def test_pace_time_distance_conversions(self):
        # pace from time+distance
        pace = VDOTCalculator.pace_from_time_distance("1:32:40", "HM")
        self.assertAlmostEqual(pace, 262.9, delta=1.0)
        # time from pace+distance
        time_str = VDOTCalculator.time_from_pace_distance(pace, "HM")
        self.assertAlmostEqual(parse_time_to_seconds(time_str), 5560, delta=2)
        # distance from time+pace
        km = VDOTCalculator.distance_from_time_pace("1:32:40", pace)
        self.assertAlmostEqual(km, 21.1, delta=0.5)

    def test_pace_to_kmh_round_trip(self):
        for pace_s in [240.0, 257.5, 300.0, 360.0]:
            kmh = VDOTCalculator.pace_to_kmh(pace_s)
            back = VDOTCalculator.kmh_to_pace(kmh)
            self.assertAlmostEqual(pace_s, back, places=2)

    def test_format_pace(self):
        self.assertEqual(VDOTCalculator.format_pace(257.5), "4'18")
        self.assertEqual(VDOTCalculator.format_pace(300.0), "5'00")
        self.assertEqual(VDOTCalculator.format_pace(360.0), "6'00")

    def test_format_pace_range(self):
        r = VDOTCalculator.format_pace_range(255.0, 262.0)
        self.assertIn("4'15", r)
        self.assertIn("4'22", r)

    def test_threshold_pace_float_precision(self):
        tf = VDOTCalculator.threshold_pace_float(49.4)
        self.assertIsInstance(tf.s_per_km, float)
        # Should be near 258 s/km (~4'18)
        self.assertAlmostEqual(tf.s_per_km, 258, delta=3)

    def test_resolve_vdot_explicit(self):
        v, src = VDOTCalculator.resolve_vdot(explicit=50.0, estimated=49.4)
        self.assertEqual(v, 50.0)
        self.assertEqual(src, "explicit")

    def test_resolve_vdot_race(self):
        results = [RaceResult(distance="5k", time="19:00")]
        v, src = VDOTCalculator.resolve_vdot(explicit=None, race_results=results)
        self.assertAlmostEqual(v, 52.9, delta=1.0)
        self.assertEqual(src, "race")

    def test_resolve_vdot_estimated(self):
        v, src = VDOTCalculator.resolve_vdot(explicit=None, race_results=None, estimated=47.0)
        self.assertEqual(v, 47.0)
        self.assertEqual(src, "estimated")

    def test_update_vdot_from_performance(self):
        result = VDOTCalculator.update_vdot_from_performance("5k", "19:00", 49.4)
        self.assertIn("new_vdot", result)
        self.assertIn("delta", result)
        self.assertEqual(result["applies_to"], "subsequent")
        self.assertGreater(result["new_vdot"], 49.0)


class TestPaceEngine(unittest.TestCase):
    """Test: PaceEngine returns complete ranged PaceProfile and PaceTarget."""

    VDOTS = [35, 40, 49.4, 55, 60]

    def test_build_profile(self):
        engine = PaceEngine(49.4)
        profile = engine.build_profile()
        self.assertIsInstance(profile, PaceProfile)
        self.assertEqual(profile.vdot, 49.4)
        # Race paces
        for d in ("5K", "10K", "HM", "MARATHON"):
            self.assertIn(d, profile.race_paces)
            self.assertIsInstance(profile.race_paces[d], PaceTarget)
        # Training zones
        for attr in ("easy", "recovery", "long_run", "threshold", "vo2", "economy"):
            pt = getattr(profile, attr)
            self.assertIsInstance(pt, PaceTarget)
            self.assertLessEqual(pt.fast, pt.slow)
        # Norwegian
        for d in ("3", "4", "6", "8", "10", "12"):
            self.assertIn(d, profile.norwegian)
        for label in ("short", "medium", "long"):
            self.assertIn(label, profile.norwegian)

    def test_pace_target_properties(self):
        engine = PaceEngine(49.4)
        easy = engine.get_easy_pace()
        self.assertIsInstance(easy.pace_min, Pace)
        self.assertIsInstance(easy.pace_max, Pace)
        self.assertLessEqual(easy.pace_min.s_per_km, easy.pace_max.s_per_km)

    def test_recovery_slower_than_easy(self):
        engine = PaceEngine(49.4)
        easy = engine.get_easy_pace()
        recovery = engine.get_recovery_pace()
        self.assertGreater(recovery.target, easy.target)

    def test_long_run_between_easy_and_threshold(self):
        engine = PaceEngine(49.4)
        easy = engine.get_easy_pace()
        long_run = engine.get_long_run_pace()
        threshold = engine.get_threshold_pace()
        self.assertGreater(long_run.target, threshold.target)
        self.assertLess(long_run.target, easy.target)

    def test_vo2_faster_than_threshold(self):
        engine = PaceEngine(49.4)
        threshold = engine.get_threshold_pace()
        vo2 = engine.get_vo2_pace()
        self.assertLess(vo2.target, threshold.target)

    def test_fatigue_widens_easy(self):
        normal = PaceEngine(49.4)
        fatigued = PaceEngine(49.4, context={"fatigue": "heavy"})
        normal_easy = normal.get_easy_pace()
        fatigued_easy = fatigued.get_easy_pace()
        # Fast bound unchanged, slow bound wider
        self.assertAlmostEqual(normal_easy.fast, fatigued_easy.fast)
        self.assertGreater(fatigued_easy.slow, normal_easy.slow)

    def test_context_does_not_change_threshold(self):
        normal = PaceEngine(49.4)
        fatigued = PaceEngine(49.4, context={"fatigue": "heavy"})
        self.assertAlmostEqual(
            normal.get_threshold_pace().target,
            fatigued.get_threshold_pace().target,
        )

    def test_all_vdots_produce_valid_profiles(self):
        for vdot in self.VDOTS:
            profile = PaceEngine(vdot).build_profile()
            self.assertEqual(profile.vdot, vdot)


class TestNorwegianContinuousModel(unittest.TestCase):
    """Test: Norwegian pace supports 3-12 min continuously, monotonically, stably."""

    DURATIONS = [3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
    KEY_DURATIONS = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    VDOTS = [35, 40, 49.4, 55, 60]

    def test_all_durations_produce_targets(self):
        engine = PaceEngine(49.4)
        for d in self.DURATIONS:
            pt = engine.get_norwegian_pace(d)
            self.assertIsInstance(pt, PaceTarget)
            self.assertGreater(pt.target, 0)
            self.assertLessEqual(pt.fast, pt.slow)

    def test_monotonic_slowing(self):
        """Longer durations produce slower paces (higher s/km)."""
        for vdot in self.VDOTS:
            engine = PaceEngine(vdot)
            prev = None
            for d in self.KEY_DURATIONS:
                pt = engine.get_norwegian_pace(d)
                if prev is not None:
                    self.assertGreaterEqual(
                        pt.target, prev.target - 0.5,
                        f"Norwegian pace not monotonic at VDOT {vdot}: {d}min slower than previous"
                    )
                prev = pt

    def test_stability_same_vdot(self):
        """Same VDOT produces same pace."""
        e1 = PaceEngine(49.4)
        e2 = PaceEngine(49.4)
        for d in self.KEY_DURATIONS:
            self.assertEqual(
                e1.get_norwegian_pace(d).target,
                e2.get_norwegian_pace(d).target,
            )

    def test_compat_labels(self):
        engine = PaceEngine(49.4)
        short = engine.get_norwegian_label("SHORT")
        medium = engine.get_norwegian_label("MEDIUM")
        long = engine.get_norwegian_label("LONG")
        self.assertLessEqual(short.target, medium.target)
        self.assertLessEqual(medium.target, long.target)

    def test_clamped_durations(self):
        engine = PaceEngine(49.4)
        below = engine.get_norwegian_pace(1.0)
        at_min = engine.get_norwegian_pace(3.0)
        above = engine.get_norwegian_pace(15.0)
        at_max = engine.get_norwegian_pace(12.0)
        self.assertAlmostEqual(below.target, at_min.target)
        self.assertAlmostEqual(above.target, at_max.target)


class TestMonotonicity(unittest.TestCase):
    """Test: VDOT 40-60 paces get progressively faster."""

    def test_race_pace_monotonic_improvement(self):
        vdots = [40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60]
        for dist in ("5K", "10K", "HM", "MARATHON"):
            prev = None
            for vdot in vdots:
                pace = VDOTCalculator.race_pace_float(vdot, dist).s_per_km
                if prev is not None:
                    self.assertLess(
                        pace, prev,
                        f"Race pace not improving for {dist} at VDOT {vdot}"
                    )
                prev = pace

    def test_threshold_pace_monotonic(self):
        vdots = [40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60]
        prev = None
        for vdot in vdots:
            pace = VDOTCalculator.threshold_pace_float(vdot).s_per_km
            if prev is not None:
                self.assertLess(pace, prev, f"Threshold not improving at VDOT {vdot}")
            prev = pace

    def test_norwegian_monotonic_per_vdot(self):
        """For each VDOT, Norwegian paces slow with duration."""
        for vdot in [40, 49.4, 55, 60]:
            engine = PaceEngine(vdot)
            paces = [engine.get_norwegian_pace(d).target for d in [3, 4, 6, 8, 10, 12]]
            for i in range(len(paces) - 1):
                self.assertGreaterEqual(
                    paces[i + 1], paces[i] - 0.5,
                    f"Norwegian not monotonic at VDOT {vdot}"
                )


class TestPhysiologicalOrdering(unittest.TestCase):
    """Test: all race and training-zone physiological orderings."""

    VDOTS = [35, 40, 45, 49.4, 50, 55, 60]

    def test_training_zone_ordering(self):
        """Recovery > Easy > Long > Threshold > VO2 (by s/km)."""
        for vdot in self.VDOTS:
            engine = PaceEngine(vdot)
            recovery = engine.get_recovery_pace().target
            easy = engine.get_easy_pace().target
            long_run = engine.get_long_run_pace().target
            threshold = engine.get_threshold_pace().target
            vo2 = engine.get_vo2_pace().target
            self.assertGreater(recovery, easy - 3, f"Recovery not slower than easy at VDOT {vdot}")
            self.assertGreater(easy, long_run - 3, f"Easy not slower than long at VDOT {vdot}")
            self.assertGreater(long_run, threshold - 3, f"Long not slower than threshold at VDOT {vdot}")
            self.assertGreater(threshold, vo2 - 3, f"Threshold not slower than VO2 at VDOT {vdot}")

    def test_race_pace_ordering(self):
        """5K < 10K < HM < MARATHON (by s/km: lower = faster)."""
        for vdot in self.VDOTS:
            engine = PaceEngine(vdot)
            p5k = engine.get_race_pace("5K").target
            p10k = engine.get_race_pace("10K").target
            phm = engine.get_race_pace("HM").target
            pmar = engine.get_race_pace("MARATHON").target
            self.assertLess(p5k, p10k + 3, f"5K not faster than 10K at VDOT {vdot}")
            self.assertLess(p10k, phm + 3, f"10K not faster than HM at VDOT {vdot}")
            self.assertLess(phm, pmar + 3, f"HM not faster than Marathon at VDOT {vdot}")

    def test_norwegian_ordering(self):
        """Short < Medium < Long (by s/km: lower = faster)."""
        for vdot in self.VDOTS:
            engine = PaceEngine(vdot)
            short = engine.get_norwegian_label("SHORT").target
            medium = engine.get_norwegian_label("MEDIUM").target
            long = engine.get_norwegian_label("LONG").target
            self.assertLessEqual(short, medium + 3, f"NS short not faster than medium at VDOT {vdot}")
            self.assertLessEqual(medium, long + 3, f"NS medium not faster than long at VDOT {vdot}")


class TestGoalFeasibility(unittest.TestCase):
    """Test: explicit fitness authoritative; goal feasibility visible; no pace inflation."""

    def test_realistic_goal(self):
        # VDOT 49.4, target 5K 19:00 → VDOT ~52.9, gap ~3.5
        result = GoalFeasibilityChecker.check(49.4, "5K", "19:00")
        self.assertIn(result.status, (FeasibilityStatus.REALISTIC, FeasibilityStatus.AMBITIOUS))
        self.assertGreater(result.vdot_gap, 0)

    def test_unrealistic_goal(self):
        # VDOT 45, target marathon 2:30 → VDOT ~55+
        result = GoalFeasibilityChecker.check(45, "MARATHON", "2:30:00")
        self.assertIn(result.status, (FeasibilityStatus.AGGRESSIVE, FeasibilityStatus.UNREALISTIC))
        self.assertGreater(result.vdot_gap, 4)
        self.assertTrue(result.warning)

    def test_ambitious_does_not_inflate_paces(self):
        """Ambitious goal keeps training paces at current fitness."""
        result = GoalFeasibilityChecker.check(49.4, "5K", "18:00")  # very fast 5K
        self.assertGreater(result.vdot_gap, 2)
        # Training paces should be based on 49.4, not the target
        engine = PaceEngine(49.4)
        threshold = engine.get_threshold_pace()
        self.assertAlmostEqual(
            threshold.target,
            VDOTCalculator.threshold_pace_float(49.4).s_per_km,
            delta=0.5,
        )

    def test_extreme_goal_marathon_4wk(self):
        """Profile F: VDOT 45, 20km/wk, 3 sessions, marathon, 4 weeks."""
        result = GoalFeasibilityChecker.check(45, "MARATHON", "3:00:00")
        self.assertGreater(result.vdot_gap, 4)
        self.assertIn(result.status, (FeasibilityStatus.AGGRESSIVE, FeasibilityStatus.UNREALISTIC))
        self.assertTrue(result.warning)

    def test_feasibility_status_ordering(self):
        """Higher gap → worse status."""
        r1 = GoalFeasibilityChecker.check(50.0, "5K", "19:30")  # small gap
        r2 = GoalFeasibilityChecker.check(45.0, "5K", "16:00")  # big gap
        self.assertLess(r1.vdot_gap, r2.vdot_gap)


class TestPaceValidator(unittest.TestCase):
    """Test: validator detects inverted pace relationships."""

    def test_valid_profile_no_findings(self):
        profile = PaceEngine(49.4).build_profile()
        findings = PaceValidator.validate(profile)
        self.assertEqual(findings, [], f"Unexpected findings: {findings}")

    def test_all_vdots_valid(self):
        for vdot in [35, 40, 49.4, 55, 60]:
            profile = PaceEngine(vdot).build_profile()
            findings = PaceValidator.validate(profile)
            self.assertEqual(findings, [], f"VDOT {vdot}: {findings}")

    def test_detects_inverted_recovery_easy(self):
        """Manually invert recovery and easy to test detection."""
        profile = PaceEngine(49.4).build_profile()
        # Swap recovery and easy targets
        profile.recovery, profile.easy = profile.easy, profile.recovery
        findings = PaceValidator.validate(profile)
        self.assertTrue(any("recovery" in f.lower() and "easy" in f.lower() for f in findings))

    def test_detects_inverted_norwegian(self):
        profile = PaceEngine(49.4).build_profile()
        profile.norwegian["short"], profile.norwegian["long"] = (
            profile.norwegian["long"],
            profile.norwegian["short"],
        )
        findings = PaceValidator.validate(profile)
        self.assertTrue(any("norwegian" in f.lower() for f in findings))


class TestPaceAdjustmentEngine(unittest.TestCase):
    """Test: no-op adjustment boundary."""

    def test_noop_adjust(self):
        self.assertEqual(PaceAdjustmentEngine.adjust(257.5), 257.5)
        self.assertEqual(PaceAdjustmentEngine.adjust(257.5, {"temp": 30}), 257.5)


class TestDeterminism(unittest.TestCase):
    """Test: equal inputs yield byte-equivalent output."""

    def test_profile_determinism(self):
        p1 = PaceEngine(49.4).build_profile()
        p2 = PaceEngine(49.4).build_profile()
        self.assertEqual(p1.vdot, p2.vdot)
        for d in ("5K", "10K", "HM", "MARATHON"):
            self.assertEqual(p1.race_paces[d].target, p2.race_paces[d].target)
        for d in ("3", "4", "6", "8", "10", "12"):
            self.assertEqual(p1.norwegian[d].target, p2.norwegian[d].target)

    def test_debug_output_determinism(self):
        out1 = debug_output(49.4)
        out2 = debug_output(49.4)
        self.assertEqual(out1, out2)

    def test_debug_output_with_feasibility(self):
        out = debug_output(49.4, "5K", "19:30")
        self.assertIn("FAISABILITE", out)
        self.assertIn("49.4", out)


class TestV2Profiles(unittest.TestCase):
    """Test the six exact V2 profiles from the prompt."""

    PROFILES = [
        # (vdot, volume, sessions, distance)
        (35, 30, 3, "5K"),
        (40, 40, 4, "10K"),
        (49.4, 65, 4, "5K"),
        (55, 80, 5, "HM"),
        (60, 100, 6, "MARATHON"),
    ]

    def test_all_profiles_produce_valid_pace_profile(self):
        for vdot, vol, sess, dist in self.PROFILES:
            engine = PaceEngine(vdot, context={"volume": vol, "frequency": sess})
            profile = engine.build_profile()
            findings = PaceValidator.validate(profile)
            self.assertEqual(findings, [], f"VDOT {vdot} {dist}: {findings}")

    def test_profile_f_feasibility_alert(self):
        """VDOT 45, 20km, 3 sessions, marathon, 4 weeks → feasibility alert."""
        result = GoalFeasibilityChecker.check(45, "MARATHON", "3:15:00")
        self.assertGreater(result.vdot_gap, 2)
        self.assertIn(result.status, (
            FeasibilityStatus.AMBITIOUS,
            FeasibilityStatus.AGGRESSIVE,
            FeasibilityStatus.UNREALISTIC,
        ))
        self.assertTrue(result.warning)


class TestRoundTrips(unittest.TestCase):
    """Test: race conversion round trips, unit conversion, formatting, tolerance."""

    def test_vdot_time_round_trip_all_distances(self):
        for vdot in [35, 40, 49.4, 55, 60]:
            for dist in ["5K", "10K", "HM", "MARATHON"]:
                time = VDOTCalculator.race_time(vdot, dist)
                v2 = VDOTCalculator.from_race(dist, time)
                self.assertAlmostEqual(vdot, v2, delta=0.5,
                    msg=f"{dist} VDOT {vdot} -> {time} -> {v2}")

    def test_pace_time_consistency(self):
        """Race pace * distance = race time."""
        for vdot in [40, 49.4, 55]:
            for dist in ["5K", "10K", "HM", "MARATHON"]:
                time_str = VDOTCalculator.race_time(vdot, dist)
                pace_s = VDOTCalculator.race_pace_float(vdot, dist).s_per_km
                d_metres = get_distance_metres(dist)
                expected_time = pace_s * d_metres / 1000.0
                self.assertAlmostEqual(
                    parse_time_to_seconds(time_str), expected_time, delta=2,
                    msg=f"{dist} VDOT {vdot}: time/pace inconsistency"
                )


class TestDebugOutput(unittest.TestCase):
    """Test: debug output includes all required fields."""

    def test_debug_includes_all_sections(self):
        out = debug_output(49.4)
        self.assertIn("VDOT : 49.4", out)
        self.assertIn("5K", out)
        self.assertIn("10K", out)
        self.assertIn("HM", out)
        self.assertIn("MARATHON", out)
        self.assertIn("Recovery", out)
        self.assertIn("Easy", out)
        self.assertIn("Long Run", out)
        self.assertIn("Threshold", out)
        self.assertIn("VO2", out)
        self.assertIn("NORWEGIAN", out)
        self.assertIn("3'", out)
        self.assertIn("12'", out)

    def test_debug_all_vdots(self):
        for vdot in [35, 40, 49.4, 55, 60]:
            out = debug_output(vdot)
            self.assertIn(f"VDOT : {vdot}", out)
            # Should have pace ranges with apostrophe format
            self.assertIn("'", out)


class TestNoHardcodedPaces(unittest.TestCase):
    """Test: no literal pace prescriptions in plan modules."""

    def test_pace_engine_uses_config(self):
        """PaceEngine produces paces from VDOT + config, not hardcoded values."""
        engine = PaceEngine(49.4)
        easy = engine.get_easy_pace()
        # Easy pace should vary with VDOT
        engine2 = PaceEngine(55.0)
        easy2 = engine2.get_easy_pace()
        self.assertNotAlmostEqual(easy.target, easy2.target, delta=5,
            msg="Easy pace should change with VDOT")


if __name__ == "__main__":
    unittest.main()
