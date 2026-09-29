"""Tests for plan evolution: PlanSettings, regeneration, skip, VDOT, statistics."""

import tempfile
import os

from douini.domain.models import (
    DifficultyLevel,
    Distance,
    Experience,
    Pace,
    Paces,
    PlanSettings,
    RunnerProfile,
    Session,
    SessionStatus,
    TrainingPlan,
    WeekPlan,
    VolumeStrategy,
)
from douini.domain.planner import generate_plan, regenerate_plan
from douini.domain.engine.load import compute_session_load
from douini.domain.engine.validation import validate_plan
from douini.domain.engine.statistics import compute_statistics
from douini.domain.exporters import save_plan_json, load_plan_json


def _runner(vdot=53.0, spw=4):
    return RunnerProfile(vdot=vdot, weekly_volume_km=70, sessions_per_week=spw, experience=Experience.INTERMEDIATE)


# T1 — PlanSettings separation
def test_t1_plan_settings_stored():
    runner = _runner()
    settings = PlanSettings(quality_sessions=2, difficulty_level=DifficultyLevel.DEMANDING)
    plan = generate_plan(runner, Distance.K5, 12, settings=settings)
    assert plan.settings.quality_sessions == 2
    assert plan.settings.difficulty_level == DifficultyLevel.DEMANDING
    assert plan.plan_vdot == runner.effective_vdot


# T2 — Settings override on regenerate
def test_t2_settings_override_on_regenerate():
    runner = _runner()
    plan = generate_plan(runner, Distance.K5, 12, settings=PlanSettings(quality_sessions=1))
    new_settings = PlanSettings(quality_sessions=2)
    regenerated = regenerate_plan(plan, from_week=5, settings=new_settings)
    assert regenerated.settings.quality_sessions == 2
    # Weeks before 5 should be unchanged
    for w in regenerated.week_plans[:4]:
        assert w == plan.week_plans[:4][regenerated.week_plans.index(w)]


# T3 — Mid-week freeze
def test_t3_mid_week_freeze():
    runner = _runner()
    plan = generate_plan(runner, Distance.K5, 12)
    # Mark a session in week 5 as completed
    w5 = plan.week_plans[4]
    for s in w5.sessions:
        if s.type == "quality":
            s.status = SessionStatus.COMPLETED
            frozen_workout = s.workout.name if s.workout else ""
            break
    regenerated = regenerate_plan(plan, from_week=5)
    new_w5 = regenerated.week_plans[4]
    frozen = [s for s in new_w5.sessions if s.status == SessionStatus.COMPLETED]
    assert len(frozen) >= 1
    assert frozen[0].workout and frozen[0].workout.name == frozen_workout


# T4 — _carry_statuses type safety
def test_t4_carry_statuses_type_safe():
    runner = _runner()
    plan = generate_plan(runner, Distance.K5, 12)
    # Mark quality on wed as completed
    w3 = plan.week_plans[2]
    for s in w3.sessions:
        if s.type == "quality":
            s.status = SessionStatus.COMPLETED
    # Regenerate from week 3 — fresh easy on same day should NOT inherit COMPLETED
    regenerated = regenerate_plan(plan, from_week=3)
    new_w3 = regenerated.week_plans[2]
    for s in new_w3.sessions:
        if s.type == "easy" and s.status == SessionStatus.COMPLETED:
            assert False, "Easy session inherited COMPLETED from quality session"


# T5 — Skipped session zero load
def test_t5_skipped_zero_load():
    s = Session(day="mon", type="quality", distance_km=10.0, status=SessionStatus.SKIPPED)
    assert compute_session_load(s) == 0.0


# T6 — JSON round-trip preserves settings + plan_vdot
def test_t6_json_round_trip():
    runner = _runner()
    settings = PlanSettings(quality_sessions=2, difficulty_level=DifficultyLevel.DEMANDING)
    plan = generate_plan(runner, Distance.SEMI, 12, settings=settings)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_plan_json(plan, path)
        loaded = load_plan_json(path)
        assert loaded.settings.quality_sessions == 2
        assert loaded.settings.difficulty_level == DifficultyLevel.DEMANDING
        assert loaded.plan_vdot == plan.plan_vdot
    finally:
        os.unlink(path)


# T7 — VDOT gap warning
def test_t7_vdot_gap_warning():
    runner = _runner(vdot=50.0)
    plan = generate_plan(runner, Distance.K5, 12)
    plan.runner.current_vdot = 53.0  # gap of 3.0
    warnings = validate_plan(plan)
    gap_warnings = [w for w in warnings if w.code == "vdot_gap_warning"]
    assert len(gap_warnings) >= 1


# T8 — No VDOT gap warning when close
def test_t8_no_vdot_gap_warning():
    runner = _runner(vdot=50.0)
    plan = generate_plan(runner, Distance.K5, 12)
    plan.runner.current_vdot = 51.0  # gap of 1.0
    warnings = validate_plan(plan)
    gap_warnings = [w for w in warnings if w.code == "vdot_gap_warning"]
    assert len(gap_warnings) == 0


# T9 — Statistics: total distance
def test_t9_stats_total_distance():
    sessions = [
        {"status": "completed", "distance_km": 10.0, "scheduled_date": "2026-01-06", "plan_id": 1, "week": 1},
        {"status": "completed", "distance_km": 8.0, "scheduled_date": "2026-01-08", "plan_id": 1, "week": 1},
        {"status": "completed", "distance_km": 15.0, "scheduled_date": "2026-01-13", "plan_id": 1, "week": 2},
        {"status": "pending", "distance_km": 10.0, "scheduled_date": "2026-01-15", "plan_id": 1, "week": 2},
    ]
    plans = [{"id": 1, "distance": "5K"}]
    counts = {"completed": 3, "pending": 1, "skipped": 0}
    stats = compute_statistics(sessions, plans, counts)
    assert stats["total_distance_km"] == 33.0
    assert stats["total_activities"] == 3


# T10 — Statistics: counts
def test_t10_stats_counts():
    sessions = [
        {"status": "completed", "distance_km": 10.0, "scheduled_date": "2026-01-06", "plan_id": 1, "week": 1},
    ]
    plans = [{"id": 1, "distance": "5K"}]
    counts = {"completed": 10, "pending": 12, "skipped": 2, "pushed": 0}
    stats = compute_statistics(sessions, plans, counts)
    assert stats["completed_count"] + stats["skipped_count"] <= stats["planned_count"]


# T11 — Statistics: regularity
def test_t11_stats_regularity():
    sessions = [
        {"status": "completed", "distance_km": 10.0, "scheduled_date": "2026-01-06", "plan_id": 1, "week": 1},
    ]
    plans = [{"id": 1, "distance": "5K"}]
    counts = {"completed": 4, "pending": 0, "skipped": 0}
    stats = compute_statistics(sessions, plans, counts)
    assert 0.0 <= stats["regularity_score"] <= 1.0
    # When all completed, regularity = 1.0
    assert stats["regularity_score"] == 1.0
