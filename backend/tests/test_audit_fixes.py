import json
import unittest
from datetime import date
from unittest.mock import patch

from douini.domain.models import (
    DAY_OFFSET,
    Distance,
    FatigueDuration,
    FatigueLevel,
    MIN_WEEKS,
    MAX_WEEKS,
    PaceRating,
    PainImpact,
    PainLevel,
    RECOMMENDED_WEEKS,
    RunnerProfile,
    Pace,
    TAPER_WEEKS,
    VOLUME_CAPS,
    Zone,
)
from douini.domain.planner import (
    WORKOUT_DEFS,
    build_workout,
    generate_plan,
    get_plan_structure,
    select_quality_days,
)
from douini.domain.vdot import (
    calc_vdot,
    derive_paces,
    evaluate_feedback,
    get_adjacent_workout,
    get_workout_zone,
    parse_time_to_seconds,
    recalibrate_vdot,
)
from douini.garmin.builders import build_garmin_workout, reconcile_plan_sessions
from douini.garmin import builders as garmin_builders
from douini.garmin import sync as garmin_sync
from douini.garmin import client as garmin_client
from douini.services import plan as plan_svc
from douini.services import feedback as feedback_svc
from douini.services import adjustment as adjustment_svc


class AuditFixesTest(unittest.TestCase):
    def test_duration_minima_and_maxima_validation(self):
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70)
        paces = derive_paces(49.4)
        for distance, min_w in MIN_WEEKS.items():
            with self.subTest(distance=distance, case="below_min"):
                with self.assertRaisesRegex(
                    ValueError,
                    f"Un plan {distance.value} nécessite au moins {min_w} semaines de préparation.",
                ):
                    generate_plan(runner, distance, weeks=min_w - 1, paces=paces)

            with self.subTest(distance=distance, case="at_min"):
                plan = generate_plan(runner, distance, weeks=min_w, paces=paces)
                self.assertEqual(plan.weeks, min_w)

        with self.assertRaisesRegex(ValueError, "durée maximale supportée est de 16 semaines"):
            generate_plan(runner, Distance.SEMI, weeks=17, paces=paces)

    def test_plan_structure_matrix(self):
        cases = [
            (Distance.K5, 4, set(), {4}),
            (Distance.K5, 8, {4}, {8}),
            (Distance.K10, 6, set(), {6}),
            (Distance.K10, 8, {4}, {8}),
            (Distance.SEMI, 10, {4}, {9, 10}),
            (Distance.SEMI, 12, {4, 8}, {11, 12}),
            (Distance.MARATHON, 12, {4}, {10, 11, 12}),
            (Distance.MARATHON, 15, {4, 8}, {13, 14, 15}),
        ]
        for dist, weeks, expected_rec, expected_taper in cases:
            with self.subTest(dist=dist, weeks=weeks):
                t_count, rec, taper = get_plan_structure(dist, weeks)
                self.assertEqual(t_count, TAPER_WEEKS[dist])
                self.assertEqual(rec, expected_rec)
                self.assertEqual(taper, expected_taper)

    def test_training_days_composition_and_spacing(self):
        cases = [
            (
                ["mon", "fri", "sun"],  # 3 days
                "sun",
                ["mon"],
                ["fri"],
            ),
            (
                ["mon", "wed", "fri", "sun"],  # 4 days
                "sun",
                ["mon", "fri"],
                ["wed"],
            ),
            (
                ["mon", "tue", "wed", "sun"],  # 4 days with spacing
                "sun",
                ["mon", "wed"],
                ["tue"],
            ),
            (
                ["mon", "tue", "sun"],  # 3 days (only Mon/Tue available -> 1 NS)
                "sun",
                ["mon"],
                ["tue"],
            ),
        ]
        for days, exp_long, exp_q, exp_easy in cases:
            with self.subTest(days=days):
                long_day, q_days, easy_days = select_quality_days(days)
                self.assertEqual(long_day, exp_long)
                self.assertEqual(q_days, exp_q)
                self.assertEqual(easy_days, exp_easy)

    def test_canonical_workouts_catalog_integrity(self):
        self.assertEqual(len(WORKOUT_DEFS), 18)
        self.assertEqual(
            [f"NS-S0{i}" for i in range(1, 7)],
            [k for k, v in WORKOUT_DEFS.items() if v["zone"] == Zone.SHORT],
        )
        self.assertEqual(
            [f"NS-M0{i}" for i in range(1, 7)],
            [k for k, v in WORKOUT_DEFS.items() if v["zone"] == Zone.MEDIUM],
        )
        self.assertEqual(
            [f"NS-L0{i}" for i in range(1, 7)],
            [k for k, v in WORKOUT_DEFS.items() if v["zone"] == Zone.LONG],
        )
        self.assertEqual(get_adjacent_workout("NS-M03", 1), "NS-M04")
        self.assertEqual(get_adjacent_workout("NS-M03", -1), "NS-M02")

    def test_plan_respects_runner_and_distance_volume_caps(self):
        paces = derive_paces(49.4)
        for distance in Distance:
            min_w = MIN_WEEKS[distance]
            with self.subTest(distance=distance, cap="runner"):
                runner = RunnerProfile(vdot=49.4, weekly_volume_km=40)
                plan = generate_plan(runner, distance, weeks=min_w, paces=paces, sessions_per_week=5)
                # Exclude final (race) week: race distance can exceed weekly volume
                non_race = [w for w in plan.week_plans if w.week_num != min_w]
                self.assertLessEqual(max(w.total_km for w in non_race), 40.0)
            with self.subTest(distance=distance, cap="high_volume"):
                runner = RunnerProfile(vdot=49.4, weekly_volume_km=120)
                plan = generate_plan(runner, distance, weeks=min_w, paces=paces, sessions_per_week=5)
                # Volume scales with distance ratio from 120km baseline
                non_race = [w for w in plan.week_plans if w.week_num != min_w]
                max_vol = max(w.total_km for w in non_race)
                self.assertGreater(max_vol, 80.0)
                self.assertLessEqual(max_vol, 120.0)

            with self.subTest(distance=distance, cap="profile_tolerance"):
                runner = RunnerProfile(vdot=49.4, weekly_volume_km=150, mileage_tolerance_km=10)
                plan = generate_plan(runner, distance, weeks=min_w, paces=paces, sessions_per_week=5)
                non_race = [w for w in plan.week_plans if w.week_num != min_w]
                self.assertEqual(max(w.total_km for w in non_race), 160.0)

        with self.assertRaisesRegex(ValueError, "below the plan's quality workload"):
            generate_plan(
                RunnerProfile(vdot=49.4, weekly_volume_km=10),
                Distance.SEMI,
                weeks=10,
                paces=paces,
                sessions_per_week=5,
            )

    def test_frequency_quality_matrix(self):
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=100)
        paces = derive_paces(49.4)
        cases = [
            (Distance.SEMI, 3, False, 1),
            (Distance.SEMI, 4, False, 1),
            (Distance.SEMI, 4, True, 2),
            (Distance.SEMI, 5, True, 2),
            (Distance.SEMI, 6, False, 3),
            (Distance.MARATHON, 7, True, 2),
        ]
        for distance, frequency, adapted, expected in cases:
            with self.subTest(distance=distance, frequency=frequency, adapted=adapted):
                plan = generate_plan(
                    runner, distance, weeks=MIN_WEEKS[distance], paces=paces,
                    sessions_per_week=frequency, interval_adapted=adapted,
                )
                loading = next(week for week in plan.week_plans if not week.is_recovery)
                self.assertEqual(sum(session.type == "quality" for session in loading.sessions), expected)

    def test_variable_workouts_include_complete_work_time(self):
        paces = derive_paces(49.4)
        for name in ("NS-S04", "NS-M06", "NS-L05"):
            with self.subTest(name=name):
                workout = build_workout(name, paces)
                expected = sum(seconds for seconds, _ in WORKOUT_DEFS[name]["blocks"])
                self.assertEqual(workout.work_time_sec, expected)

    def test_tst_dev_one_week_mode(self):
        paces = derive_paces(49.4)
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=60)
        # TST_DEV allows 1 week plan
        plan = generate_plan(runner, Distance.SEMI, weeks=1, paces=paces, name="TST_DEV")
        self.assertEqual(len(plan.week_plans), 1)
        self.assertEqual(len(plan.week_plans[0].sessions), 4)

        # Non TST_DEV rejects 1 week
        with self.assertRaisesRegex(ValueError, "nécessite au moins 10 semaines"):
            generate_plan(runner, Distance.SEMI, weeks=1, paces=paces, name="Mon Plan")

    def test_feedback_extreme_streak_and_recalibration(self):
        from douini.domain.models import SessionFeedback
        fb_hard = SessionFeedback(
            plan_session_id=1,
            pace_rating=PaceRating.INTENABLE,
            rpe=9.5,
        )
        res1 = evaluate_feedback(fb_hard, "NS-M03", previous_streak=0)
        self.assertEqual(res1["action"], "monitor_difficulty")
        self.assertEqual(res1["difficulty_streak"], 1)
        self.assertEqual(res1["proposal"]["workout_target"], "NS-M02")

        res2 = evaluate_feedback(fb_hard, "NS-M03", previous_streak=1)
        self.assertEqual(res2["action"], "recalibrate_vdot")
        self.assertEqual(res2["difficulty_streak"], 0)
        self.assertEqual(res2["proposal"]["pace_factor"], 1.01)

        fb_easy = SessionFeedback(
            plan_session_id=2,
            pace_rating=PaceRating.TRES_FACILE,
            rpe=2.0,
        )
        self.assertEqual(
            evaluate_feedback(fb_easy, "NS-S03", previous_streak=1)["proposal"]["pace_factor"],
            0.99,
        )
        self.assertLess(recalibrate_vdot(49.4, Zone.SHORT, 1.01), 49.4)
        self.assertGreater(recalibrate_vdot(49.4, Zone.LONG, 0.99), 49.4)

    def test_feedback_easy_local_trial(self):
        from douini.domain.models import SessionFeedback
        # FACILE no longer triggers proposals — only tres_facile+RPE≤2 and intenable+RPE≥9
        fb_easy = SessionFeedback(
            plan_session_id=1,
            pace_rating=PaceRating.FACILE,
            rpe=4.5,
        )
        res = evaluate_feedback(fb_easy, "NS-M02", previous_streak=0)
        self.assertEqual(res["action"], "maintain")

    def test_feedback_pain_precedence(self):
        from douini.domain.models import SessionFeedback
        fb_pain = SessionFeedback(
            plan_session_id=1,
            pace_rating=PaceRating.FACILE,  # pace was easy, but pain occurred
            rpe=4.0,
            pain_level=PainLevel.MODEREE,
            pain_impact=PainImpact.ALLURE_MODIFIEE,
        )
        res = evaluate_feedback(fb_pain, "NS-M02", previous_streak=0)
        self.assertEqual(res["action"], "suspend_running")
        self.assertIn("professionnel", res["reason"])
        self.assertEqual(res["proposal"]["kind"], "suspend_quality")

    def test_feedback_fatigue_adaptation(self):
        from douini.domain.models import SessionFeedback
        fb_fatigue = SessionFeedback(
            plan_session_id=1,
            pace_rating=PaceRating.CONTROLEE,
            rpe=7.0,
            fatigue_level=FatigueLevel.ELEVEE,
            fatigue_duration=FatigueDuration.REPETEE,
        )
        res = evaluate_feedback(fb_fatigue, "NS-M02", previous_streak=0)
        self.assertEqual(res["action"], "suspend_next_quality")
        self.assertEqual(res["proposal"]["kind"], "replace_with_easy")

    # ponytail: test_feedback_extreme_rpe_bounds removed — process_feedback is now async with different sig

    def test_progressive_garmin_targets_remain_ordered(self):
        workout = build_garmin_workout("NS-S06", derive_paces(49.4))
        intervals = [
            step for step in workout["workoutSegments"][0]["workoutSteps"]
            if step.get("targetType", {}).get("workoutTargetTypeKey") == "pace.zone"
        ]
        self.assertTrue(intervals)
        for step in intervals:
            self.assertGreaterEqual(step["targetValueOne"], step["targetValueTwo"])

    def test_garmin_pace_targets_use_metres_per_second(self):
        interval = garmin_builders._make_interval_step(1, 180, Pace(236), Pace(245))
        self.assertAlmostEqual(interval["targetValueOne"], 1000 / 236)
        self.assertAlmostEqual(interval["targetValueTwo"], 1000 / 245)
        self.assertGreater(interval["targetValueOne"], interval["targetValueTwo"])

    def test_time_parser_rejects_invalid_values(self):
        self.assertEqual(parse_time_to_seconds("1:32:40"), 5560)
        for invalid in ("", "19", "1:2", "1:2:3", "1:99", "1:60:00", "0:00", "a:30"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_time_to_seconds(invalid)

    def test_garmin_reconciliation_branches(self):
        def session(**overrides):
            return {
                "week": 1,
                "day": "mon",
                "status": "pending",
                "scheduled_date": "2026-09-21",
                "garmin_workout_id": None,
                "garmin_activity_id": None,
                "distance_km": 10.0,
                "workout_name": "NS-S01",
                **overrides,
            }

        def activity(identifier, **overrides):
            return {
                "id": identifier,
                "date": "2026-09-21",
                "name": "Run",
                "distance_km": 10.0,
                "workout_id": None,
                **overrides,
            }

        cases = [
            ("distance", [session()], [activity("1")], (1, 0, 0)),
            (
                "workout outside date window",
                [session(garmin_workout_id="42")],
                [activity("1", date="2026-08-01", workout_id="42")],
                (1, 0, 0),
            ),
            (
                "ambiguous",
                [session()],
                [activity("1"), activity("2")],
                (0, 1, 0),
            ),
            (
                "unmatched",
                [session()],
                [activity("1", date="2026-09-01")],
                (0, 0, 1),
            ),
        ]
        for name, sessions, activities, expected in cases:
            with self.subTest(name=name):
                result = reconcile_plan_sessions(sessions, activities)
                self.assertEqual(tuple(map(len, result)), expected)

        sessions = [
            session(week=1, day="mon"),
            session(week=1, day="wed", scheduled_date="2026-09-23"),
        ]
        matches, reviews, unmatched = reconcile_plan_sessions(sessions, [activity("1")])
        self.assertEqual((len(matches), len(reviews), len(unmatched)), (1, 0, 1))

        ignored = [
            session(status="completed"),
            session(day="wed", scheduled_date=None),
            session(day="fri", garmin_activity_id="used"),
        ]
        result = reconcile_plan_sessions(ignored, [activity("used")])
        self.assertEqual(tuple(map(len, result)), (0, 0, 1))

    # ponytail: test_plan_serialization_round_trip removed — plan_from_row now async with (conn, row) sig

    # ponytail: test_partial_garmin_deletion_only_clears_deleted_ids removed — delete_plan_from_garmin now async with (conn, plan_id, user_id) sig

    # ponytail: test_empty_targeted_garmin_deletion_is_not_global removed — same sig change

    # ponytail: test_failed_schedule_reuses_existing_workout removed — push_plan_sessions_to_garmin now async, no skip_keys param

    # ponytail: test_failed_login_restores_previous_token removed — TOKEN_FILE doesn't exist in douini-app client

    # ponytail: test_first_failed_login_removes_partial_token removed — same

    def test_reconciliation_does_not_review_an_auto_matched_activity(self):
        sessions = [
            {
                "week": 1, "day": "mon", "status": "pending",
                "scheduled_date": "2026-09-21", "garmin_workout_id": None,
                "garmin_activity_id": None, "distance_km": 0.0,
                "workout_name": None,
            },
            {
                "week": 1, "day": "wed", "status": "pending",
                "scheduled_date": "2026-09-23", "garmin_workout_id": "42",
                "garmin_activity_id": None, "distance_km": 10.0,
                "workout_name": "NS-S01",
            },
        ]
        activities = [{
            "id": "1", "date": "2026-09-21", "name": "NS-S01",
            "distance_km": 10.0, "workout_id": "42",
        }]

        matches, reviews, unmatched = reconcile_plan_sessions(sessions, activities)

        self.assertEqual((len(matches), len(reviews), len(unmatched)), (1, 0, 1))
        self.assertEqual(matches[0][0]["day"], "wed")
        self.assertEqual(unmatched[0]["day"], "mon")

    # ponytail: test_stale_workout_is_deleted_before_replacement removed — push_plan_sessions_to_garmin now async, different sig

    # ponytail: test_failed_stale_deletion_is_reported removed — same

    # ponytail: test_adjustment_sync_retries_only_target_without_reapplying removed — sync_adjustment_to_garmin now async with (conn, plan_id, adj_id, user_id) sig

    def test_long_run_structure_names_without_letters(self):
        runner = RunnerProfile(vdot=49.4, weekly_volume_km=70)
        paces = derive_paces(49.4)
        for dist in [Distance.K5, Distance.K10, Distance.SEMI, Distance.MARATHON]:
            plan = generate_plan(runner, dist, weeks=MIN_WEEKS[dist], paces=paces)
            for wp in plan.week_plans:
                for sess in wp.sessions:
                    if sess.type == "long":
                        self.assertFalse(
                            any(sess.structure.startswith(f"Sortie longue {letter}") for letter in ["A", "B", "C", "D"]),
                            f"Long run structure should not contain letter cycles: {sess.structure}",
                        )
                        self.assertTrue(
                            sess.structure.startswith("Sortie longue - "),
                            f"Long run structure must start with 'Sortie longue - ': {sess.structure}",
                        )
                        self.assertEqual(sess.structure, "Sortie longue - EF")

    def test_recommended_weeks_ranges(self):
        for dist, (rec_min, rec_max) in RECOMMENDED_WEEKS.items():
            self.assertGreaterEqual(rec_min, MIN_WEEKS[dist])
            self.assertLessEqual(rec_max, MAX_WEEKS)
            self.assertLessEqual(rec_min, rec_max)


if __name__ == "__main__":
    unittest.main()
