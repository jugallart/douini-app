"""Tests for plan modes (DEV/PROD), week validation, Garmin upsert/sync, and feedback flow."""

import unittest
from unittest.mock import MagicMock

from douini.domain.models import (
    PaceRating,
    FatigueLevel,
    FatigueDuration,
    PainLevel,
    PainImpact,
    SessionFeedback,
)
from douini.domain.vdot import evaluate_feedback
from douini.garmin.builders import update_workout
from douini.garmin.sync import reconcile_plan_sessions


# ─── 3. RPE trigger conjunctions ───

class TestRPETriggerConjunctions(unittest.TestCase):
    def test_intenable_rpe9_triggers_lighten(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.INTENABLE, rpe=9.0)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["action"], "monitor_difficulty")
        self.assertEqual(res["proposal"]["kind"], "lighten_workout")

    def test_intenable_rpe10_triggers_lighten(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.INTENABLE, rpe=10.0)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["proposal"]["kind"], "lighten_workout")

    def test_intenable_rpe8_no_proposal(self):
        """RPE 8 with intenable should NOT trigger (requires RPE≥9)."""
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.INTENABLE, rpe=8.0)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertIsNone(res["proposal"])
        self.assertEqual(res["action"], "maintain")

    def test_tres_facile_rpe1_triggers_progression(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=1.0)
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["action"], "local_progression_trial")
        self.assertEqual(res["proposal"]["kind"], "progression_trial")

    def test_tres_facile_rpe2_triggers_progression(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=2.0)
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["proposal"]["kind"], "progression_trial")

    def test_tres_facile_rpe3_no_proposal(self):
        """RPE 3 with tres_facile should NOT trigger (requires RPE≤2)."""
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=3.0)
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertIsNone(res["proposal"])

    def test_difficile_no_proposal(self):
        """DIFFICILE no longer triggers proposals."""
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.DIFFICILE, rpe=7.0)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertIsNone(res["proposal"])

    def test_facile_no_proposal(self):
        """FACILE no longer triggers proposals."""
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.FACILE, rpe=4.0)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertIsNone(res["proposal"])

    def test_intenable_second_streak_recalibrates(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.INTENABLE, rpe=9.5)
        res = evaluate_feedback(fb, "NS-M03", previous_streak=1)
        self.assertEqual(res["action"], "recalibrate_vdot")
        self.assertEqual(res["proposal"]["kind"], "recalibrate_vdot")
        self.assertEqual(res["proposal"]["pace_factor"], 1.01)

    def test_tres_facile_second_streak_recalibrates(self):
        fb = SessionFeedback(plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=1.5)
        res = evaluate_feedback(fb, "NS-S03", previous_streak=1)
        self.assertEqual(res["action"], "recalibrate_vdot")
        self.assertEqual(res["proposal"]["pace_factor"], 0.99)

    def test_pain_overrides_everything(self):
        """Pain takes priority over pace rating conjunctions."""
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=1.0,
            pain_level=PainLevel.SEVERE,
        )
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_running")
        self.assertEqual(res["proposal"]["kind"], "suspend_quality")

    def test_fatigue_overrides_pace(self):
        """Fatigue takes priority over pace rating."""
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.INTENABLE, rpe=9.5,
            fatigue_level=FatigueLevel.ELEVEE,
        )
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_next_quality")
        self.assertEqual(res["proposal"]["kind"], "replace_with_easy")


# ─── 5. Garmin upsert ───

class TestGarminUpsert(unittest.TestCase):
    def test_update_workout_calls_client(self):
        client = MagicMock()
        client.update_workout.return_value = {"workoutId": "42"}
        ok, msg = update_workout(client, "42", {"workoutName": "test"})
        self.assertTrue(ok)
        self.assertEqual(msg, "42")
        client.update_workout.assert_called_once_with("42", {"workoutName": "test"})

    def test_update_workout_failure_returns_false(self):
        client = MagicMock()
        client.update_workout.side_effect = Exception("Network error")
        ok, msg = update_workout(client, "42", {"workoutName": "test"})
        self.assertFalse(ok)
        self.assertIn("Network error", msg)


# ─── 6. Garmin reconcile idempotency ───

class TestReconcileIdempotency(unittest.TestCase):
    def test_review_sessions_not_re_matched(self):
        """Sessions in 'review' status should be excluded from reconcile pending list."""
        sessions = [
            {"week": 1, "day": "mon", "scheduled_date": "2027-01-04",
             "garmin_workout_id": "w1", "garmin_activity_id": None,
             "status": "review"},
        ]
        activities = [{
            "id": "act-1", "date": "2027-01-04", "time": "08:00",
            "name": "NS-S01", "distance_km": 10.0, "duration_sec": 1800,
            "workout_id": "w1",
        }]
        matches, reviews, unmatched = reconcile_plan_sessions(sessions, activities)
        # review sessions excluded from pending → no matches, no reviews
        self.assertEqual(len(matches), 0)
        self.assertEqual(len(reviews), 0)

    def test_completed_not_re_matched(self):
        sessions = [
            {"week": 1, "day": "mon", "scheduled_date": "2027-01-04",
             "garmin_workout_id": "w1", "garmin_activity_id": "act-old",
             "status": "completed"},
        ]
        activities = [{
            "id": "act-new", "date": "2027-01-04", "time": "08:00",
            "name": "NS-S01", "distance_km": 10.0, "duration_sec": 1800,
            "workout_id": "w1",
        }]
        matches, reviews, unmatched = reconcile_plan_sessions(sessions, activities)
        self.assertEqual(len(matches), 0)

    def test_exact_match_auto_completes(self):
        sessions = [
            {"week": 1, "day": "mon", "scheduled_date": "2027-01-04",
             "garmin_workout_id": "w1", "garmin_activity_id": None,
             "status": "pending"},
        ]
        activities = [{
            "id": "act-1", "date": "2027-01-04", "time": "08:00",
            "name": "NS-S01", "distance_km": 10.0, "duration_sec": 1800,
            "workout_id": "w1",
        }]
        matches, reviews, unmatched = reconcile_plan_sessions(sessions, activities)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(reviews), 0)


# ─── 9. Fatigue/pain priority ───

class TestFatiguePainPriority(unittest.TestCase):
    def test_pain_light_suspends_progression_no_proposal(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=1.0,
            pain_level=PainLevel.LEGERE,
        )
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_progression")
        self.assertIsNone(res["proposal"])

    def test_pain_moderate_suspends_quality(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.CONTROLEE, rpe=5.0,
            pain_level=PainLevel.MODEREE,
        )
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_running")
        self.assertEqual(res["proposal"]["kind"], "suspend_quality")

    def test_pain_impact_vie_quotidienne_suspends(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.CONTROLEE, rpe=5.0,
            pain_level=PainLevel.LEGERE,
            pain_impact=PainImpact.VIE_QUOTIDIENNE,
        )
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_running")

    def test_fatigue_elevee_lightens(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.CONTROLEE, rpe=5.0,
            fatigue_level=FatigueLevel.MODEREE,
            fatigue_duration=FatigueDuration.ISOLEE,
        )
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["action"], "lighten_next_quality")
        self.assertEqual(res["proposal"]["kind"], "lighten_workout")

    def test_fatigue_tres_elevee_replaces_with_easy(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.CONTROLEE, rpe=5.0,
            fatigue_level=FatigueLevel.ELEVEE,
        )
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_next_quality")
        self.assertEqual(res["proposal"]["kind"], "replace_with_easy")

    def test_fatigue_persistante_replaces_with_easy(self):
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.CONTROLEE, rpe=5.0,
            fatigue_level=FatigueLevel.ELEVEE,
            fatigue_duration=FatigueDuration.PERSISTANTE,
        )
        res = evaluate_feedback(fb, "NS-M03", previous_streak=0)
        self.assertEqual(res["action"], "suspend_next_quality")
        self.assertEqual(res["proposal"]["kind"], "replace_with_easy")

    def test_tres_facile_does_not_neutralize_severe_pain(self):
        """High fatigue or concerning pain must NOT be neutralized by Tres_facile."""
        fb = SessionFeedback(
            plan_session_id=1, pace_rating=PaceRating.TRES_FACILE, rpe=1.0,
            pain_level=PainLevel.SEVERE,
        )
        res = evaluate_feedback(fb, "NS-S03", previous_streak=0)
        # Pain should win, not tres_facile progression
        self.assertEqual(res["action"], "suspend_running")
        self.assertNotEqual(res["proposal"]["kind"], "progression_trial")


if __name__ == "__main__":
    unittest.main()
