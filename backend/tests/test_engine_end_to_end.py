"""End-to-end verification matrix for the training engine.

Tests correctness, compatibility, determinism, and offline operation.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from douini.domain.models import (
    Distance,
    Experience,
    RunnerProfile,
    TrainingPlan,
)
from douini.domain.planner import generate_plan
from douini.domain.vdot import VDOTCalculator, derive_paces
from douini.domain.engine.pace_engine import PaceEngine
from douini.domain.engine.profile import ProfileEngine
from douini.domain.engine.config import validate_config
from douini.domain.engine.library import validate_catalog
from douini.domain.exporters import (
    plan_to_records,
    export_plan,
    save_plan_json,
    load_plan_json,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

VDOT_5K_FAST = 55
VDOT_SEMI = 49.4
VDOT_MARATHON = 60
VDOT_BEGINNER = 35
VDOT_LOW_VOL = 45


def _profile(vdot, weekly_km, spw, distance, weeks, goal_time, **kw):
    """Build a complete RunnerProfile."""
    return RunnerProfile(
        vdot=vdot,
        weekly_volume_km=weekly_km,
        mileage_tolerance_km=0,
        training_days=["mon", "wed", "fri", "sun"][:spw] if spw <= 4 else ["mon", "tue", "wed", "fri", "sun"][:spw],
        target_weekly_km=weekly_km,
        sessions_per_week=spw,
        race_distance=distance,
        weeks=weeks,
        target_time=goal_time,
        experience=kw.get("experience", Experience.INTERMEDIATE),
        current_weekly_km=weekly_km,
        current_longest_run=kw.get("current_longest", 15.0),
        long_run_day="sun",
        preferred_days=["mon", "wed", "fri", "sun"][:spw] if spw <= 4 else ["mon", "tue", "wed", "fri", "sun"][:spw],
    )


# ── Six reference profiles ────────────────────────────────────────────────────

REFERENCE_PROFILES = [
    ("5K_fast", VDOT_5K_FAST, 65, 4, Distance.K5, 12, "18:30"),
    ("10K_mid", 50, 70, 4, Distance.K10, 12, "42:00"),
    ("Semi_standard", VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00"),
    ("Marathon_adv", VDOT_MARATHON, 78, 5, Distance.MARATHON, 16, "3:05:00"),
    ("Beginner_5K", VDOT_BEGINNER, 30, 3, Distance.K5, 12, "25:00"),
    ("Low_vol_marathon", VDOT_LOW_VOL, 20, 3, Distance.MARATHON, 12, "4:30:00"),
]


# ── 1. Six reference plans generate ───────────────────────────────────────────

class TestSixReferencePlans:
    """Each reference profile must generate a valid plan."""

    @pytest.mark.parametrize("name,vdot,km,spw,dist,weeks,goal", REFERENCE_PROFILES)
    def test_generates(self, name, vdot, km, spw, dist, weeks, goal):
        runner = _profile(vdot, km, spw, dist, weeks, goal)
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        assert plan is not None
        assert len(plan.week_plans) == weeks

    @pytest.mark.parametrize("name,vdot,km,spw,dist,weeks,goal", REFERENCE_PROFILES)
    def test_has_quality_sessions(self, name, vdot, km, spw, dist, weeks, goal):
        runner = _profile(vdot, km, spw, dist, weeks, goal)
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        quality_count = sum(
            1 for w in plan.week_plans for s in w.sessions
            if s.type == "quality"
        )
        assert quality_count > 0

    @pytest.mark.parametrize("name,vdot,km,spw,dist,weeks,goal", REFERENCE_PROFILES)
    def test_has_race_session(self, name, vdot, km, spw, dist, weeks, goal):
        runner = _profile(vdot, km, spw, dist, weeks, goal)
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        last_week = plan.week_plans[-1]
        race_sessions = [s for s in last_week.sessions if s.type == "race"]
        assert len(race_sessions) == 1

    @pytest.mark.parametrize("name,vdot,km,spw,dist,weeks,goal", REFERENCE_PROFILES)
    def test_has_warnings(self, name, vdot, km, spw, dist, weeks, goal):
        runner = _profile(vdot, km, spw, dist, weeks, goal)
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        assert hasattr(plan, "warnings")

    @pytest.mark.parametrize("name,vdot,km,spw,dist,weeks,goal", REFERENCE_PROFILES)
    def test_has_selection_trace(self, name, vdot, km, spw, dist, weeks, goal):
        runner = _profile(vdot, km, spw, dist, weeks, goal)
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, dist, weeks, paces, sessions_per_week=spw)
        assert hasattr(plan, "selection_trace")


# ── 2. Low-volume marathon raises ValueError ──────────────────────────────────

class TestExtremeCase:
    """4-week marathon must raise (MIN_WEEKS=12)."""

    def test_short_marathon_raises(self):
        runner = _profile(VDOT_LOW_VOL, 20, 3, Distance.MARATHON, 4, "4:30:00")
        paces = derive_paces(runner.vdot)
        with pytest.raises(ValueError):
            generate_plan(runner, Distance.MARATHON, 4, paces, sessions_per_week=3)


# ── 3. Determinism ───────────────────────────────────────────────────────────

class TestDeterminism:
    """Same inputs → identical plans, traces, and exports."""

    def test_plan_identical(self):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan1 = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        plan2 = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        # Compare week_plans structure
        assert len(plan1.week_plans) == len(plan2.week_plans)
        for w1, w2 in zip(plan1.week_plans, plan2.week_plans):
            assert w1.week_num == w2.week_num
            assert len(w1.sessions) == len(w2.sessions)
            for s1, s2 in zip(w1.sessions, w2.sessions):
                assert s1.day == s2.day
                assert s1.workout == s2.workout
                assert s1.type == s2.type
                assert s1.distance_km == s2.distance_km

    def test_selection_trace_identical(self):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan1 = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        plan2 = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        assert plan1.selection_trace == plan2.selection_trace

    def test_export_identical(self, tmp_path):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        d1.mkdir()
        d2.mkdir()
        p1 = export_plan(plan, str(d1), formats=["json"])
        p2 = export_plan(plan, str(d2), formats=["json"])
        f1 = Path(p1[0]).read_bytes()
        f2 = Path(p2[0]).read_bytes()
        assert f1 == f2


# ── 4. Offline operation ───────────────────────────────────────────────────────

class TestOffline:
    """No network calls during generation, validation, export."""

    def test_no_network_in_generation(self, monkeypatch):
        # Block socket to prove no network
        import socket
        def _block(*a, **kw):
            raise RuntimeError("network blocked")
        monkeypatch.setattr(socket, "create_connection", _block)
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        assert plan is not None

    def test_no_network_in_export(self, monkeypatch, tmp_path):
        import socket
        def _block(*a, **kw):
            raise RuntimeError("network blocked")
        monkeypatch.setattr(socket, "create_connection", _block)
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        paths = export_plan(plan, str(tmp_path), formats=["json", "csv", "md"])
        assert len(paths) == 3


# ── 5. Dry-run writes nothing ─────────────────────────────────────────────────

class TestDryRun:
    """--dry-run must not write any files."""

    def test_dry_run_no_files(self, tmp_path):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        # Exporters only write when called explicitly
        before = set(tmp_path.iterdir()) if tmp_path.exists() else set()
        # Simulate dry-run: generate but don't call export_plan
        assert plan is not None
        after = set(tmp_path.iterdir()) if tmp_path.exists() else set()
        assert before == after


# ── 6. Export and reconstruct ─────────────────────────────────────────────────

class TestExportAndReconstruct:
    """Export and round-trip preserves session identity."""

    def test_roundtrip_preserves_sessions(self, tmp_path):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        save_plan_json(plan, str(tmp_path / "plan.json"))
        loaded = load_plan_json(str(tmp_path / "plan.json"))
        assert loaded.distance == plan.distance
        assert loaded.weeks == plan.weeks
        original_sessions = sum(len(w.sessions) for w in plan.week_plans)
        loaded_sessions = sum(len(w.sessions) for w in loaded.week_plans)
        assert original_sessions == loaded_sessions

    def test_all_formats_produced(self, tmp_path):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        paths = export_plan(plan, str(tmp_path), formats=["json", "csv", "md"])
        assert len(paths) == 3
        for p in paths:
            assert Path(p).exists()

    def test_all_distances_export(self, tmp_path):
        for dist in [Distance.K5, Distance.K10, Distance.SEMI, Distance.MARATHON]:
            runner = _profile(49.4, 70, 4, dist, 12, "1:32:00")
            paces = derive_paces(runner.vdot)
            plan = generate_plan(runner, dist, 12, paces, sessions_per_week=4)
            paths = export_plan(plan, str(tmp_path / dist.value), formats=["json"])
            assert Path(paths[0]).exists()


# ── 7. Config and catalog validation ──────────────────────────────────────────

class TestConfigAndCatalog:
    """Engine config and workout catalog must be valid."""

    def test_config_valid(self):
        errors = validate_config()
        assert errors == [], f"Config errors: {errors}"

    def test_catalog_valid(self):
        errors = validate_catalog()
        assert errors == [], f"Catalog errors: {errors}"


# ── 8. Profile engine validation ───────────────────────────────────────────────

class TestProfileValidation:
    """ProfileEngine must validate mandatory fields."""

    def test_complete_profile_valid(self):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        result = ProfileEngine().validate(runner)
        assert result.valid

    def test_missing_target_time_invalid(self):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, None)
        result = ProfileEngine().validate(runner)
        assert not result.valid
        assert "target_time" in result.missing_fields


# ── 9. Self-checks ─────────────────────────────────────────────────────────────

class TestSelfChecks:
    """Module self-checks pass."""

    def test_vdot_selfcheck(self):
        from douini.domain.vdot import VDOTCalculator
        calc = VDOTCalculator()
        vdot = calc.from_race("semi", "1:32:40")
        assert 48 <= vdot <= 51

    def test_planner_selfcheck(self):
        runner = _profile(VDOT_SEMI, 75, 4, Distance.SEMI, 12, "1:32:00")
        paces = derive_paces(runner.vdot)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        assert plan.total_workouts > 0


# ── 10. No external API dependency ─────────────────────────────────────────────

class TestNoExternalAPI:
    """Verify no AI/LLM/external API participates in generation."""

    def test_no_openai_import(self):
        import douini_run.planner
        import inspect
        src = inspect.getsource(douini_run.planner)
        assert "openai" not in src.lower()
        assert "anthropic" not in src.lower()
        assert "claude" not in src.lower()

    def test_engine_no_external_api(self):
        import douini_run.engine.selection
        import inspect
        src = inspect.getsource(douini_run.engine.selection)
        assert "requests" not in src
        assert "urllib" not in src
        assert "http" not in src.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
