"""Tests for Phase 3 plan parameters: quality_sessions, difficulty_level, volume_strategy."""

import pytest
from douini.domain.planner import generate_plan
from douini.domain.models import RunnerProfile, Distance, DifficultyLevel, VolumeStrategy
from douini.domain.vdot import derive_paces

paces = derive_paces(53)


def _count_quality(week_plans, week_num):
    return sum(1 for s in week_plans[week_num - 1].sessions if s.type == "quality")


class TestQualitySessions:
    def test_qs1_gives_one_quality(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        plan = generate_plan(runner, Distance.K5, 12, paces, sessions_per_week=4, quality_sessions=1)
        assert _count_quality(plan.week_plans, 3) == 1

    def test_qs2_gives_two_quality(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        plan = generate_plan(runner, Distance.K5, 12, paces, sessions_per_week=4, quality_sessions=2)
        assert _count_quality(plan.week_plans, 3) == 2

    def test_qs3_gives_three_quality(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        plan = generate_plan(runner, Distance.K5, 12, paces, sessions_per_week=5, quality_sessions=3)
        assert _count_quality(plan.week_plans, 3) == 3

    def test_qs_capped_by_spw(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        # 3 sessions/week, qs=3 -> capped to 1 (3-2=1 max)
        plan = generate_plan(runner, Distance.K5, 12, paces, sessions_per_week=3, quality_sessions=3)
        assert _count_quality(plan.week_plans, 3) <= 1

    def test_qs_from_runner_profile(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70, quality_sessions=2)
        plan = generate_plan(runner, Distance.K5, 12, sessions_per_week=4)
        assert _count_quality(plan.week_plans, 3) == 2

    def test_qs_none_uses_static_lookup(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        plan = generate_plan(runner, Distance.K5, 12, paces, sessions_per_week=4)
        assert _count_quality(plan.week_plans, 3) == 1


class TestDifficultyLevel:
    def test_difficulty_factor_values(self):
        assert RunnerProfile(difficulty_level=DifficultyLevel.COMFORTABLE).difficulty_factor == 0.90
        assert RunnerProfile(difficulty_level=DifficultyLevel.BALANCED).difficulty_factor == 1.00
        assert RunnerProfile(difficulty_level=DifficultyLevel.DEMANDING).difficulty_factor == 1.10

    def test_demanding_more_volume(self):
        runner_b = RunnerProfile(vdot=53, weekly_volume_km=70, difficulty_level=DifficultyLevel.BALANCED)
        runner_d = RunnerProfile(vdot=53, weekly_volume_km=70, difficulty_level=DifficultyLevel.DEMANDING)
        plan_b = generate_plan(runner_b, Distance.SEMI, 12, paces, sessions_per_week=4)
        plan_d = generate_plan(runner_d, Distance.SEMI, 12, paces, sessions_per_week=4)
        w10_b = plan_b.week_plans[9].total_km
        w10_d = plan_d.week_plans[9].total_km
        assert w10_d >= w10_b

    def test_comfortable_less_volume(self):
        runner_b = RunnerProfile(vdot=53, weekly_volume_km=70, difficulty_level=DifficultyLevel.BALANCED)
        runner_c = RunnerProfile(vdot=53, weekly_volume_km=70, difficulty_level=DifficultyLevel.COMFORTABLE)
        plan_b = generate_plan(runner_b, Distance.SEMI, 12, paces, sessions_per_week=4)
        plan_c = generate_plan(runner_c, Distance.SEMI, 12, paces, sessions_per_week=4)
        w10_b = plan_b.week_plans[9].total_km
        w10_c = plan_c.week_plans[9].total_km
        assert w10_c <= w10_b


class TestVolumeStrategy:
    def test_gradual_slower_ramp(self):
        runner_g = RunnerProfile(vdot=53, weekly_volume_km=70, current_weekly_km=40,
                                   volume_strategy=VolumeStrategy.GRADUAL)
        runner_p = RunnerProfile(vdot=53, weekly_volume_km=70, current_weekly_km=40,
                                   volume_strategy=VolumeStrategy.PROGRESSIVE)
        plan_g = generate_plan(runner_g, Distance.SEMI, 12, paces, sessions_per_week=4)
        plan_p = generate_plan(runner_p, Distance.SEMI, 12, paces, sessions_per_week=4)
        assert plan_g.week_plans[1].total_km < plan_p.week_plans[1].total_km

    def test_constant_jumps_to_target(self):
        runner_c = RunnerProfile(vdot=53, weekly_volume_km=70, current_weekly_km=40,
                                   volume_strategy=VolumeStrategy.CONSTANT)
        plan_c = generate_plan(runner_c, Distance.SEMI, 12, paces, sessions_per_week=4)
        w2 = plan_c.week_plans[1].total_km
        # BASE cap = 70*0.9 = 63
        assert abs(w2 - 63.0) < 1.0

    def test_progressive_is_default(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70)
        assert runner.volume_strategy == VolumeStrategy.PROGRESSIVE

    def test_strategy_from_runner_profile(self):
        runner = RunnerProfile(vdot=53, weekly_volume_km=70, current_weekly_km=40,
                               volume_strategy=VolumeStrategy.GRADUAL)
        plan = generate_plan(runner, Distance.SEMI, 12, paces, sessions_per_week=4)
        w1 = plan.week_plans[0].total_km
        w2 = plan.week_plans[1].total_km
        # 3% ramp from 40: 40 * 1.03 = 41.2
        assert abs(w2 - 41.2) < 0.5


class TestLoadRulesConfig:
    def test_load_rules_used(self):
        from douini.domain.engine.load import _rules
        assert "quality_load_factor" in _rules or "recovery_load_factor" in _rules

    def test_fatigue_decay_from_config(self):
        from douini.domain.engine.load import _FATIGUE_DECAY, _rules
        expected = 1.0 - _rules.get("recovery_load_factor", 0.75)
        assert _FATIGUE_DECAY == expected


class TestPlanSettingsConfig:
    def test_plan_settings_loaded(self):
        from douini.domain.engine.config import get_plan_settings
        s = get_plan_settings()
        assert "difficulty_factors" in s
        assert "volume_strategies" in s
        assert s["difficulty_factors"]["comfortable"] == 0.90
        assert s["difficulty_factors"]["demanding"] == 1.10
        assert s["volume_strategies"]["gradual"]["weekly_increase_pct"] == 3
        assert s["volume_strategies"]["progressive"]["weekly_increase_pct"] == 5
        assert s["volume_strategies"]["constant"]["weekly_increase_pct"] == 0


class TestCombinedParams:
    def test_all_params_together(self):
        runner = RunnerProfile(
            vdot=53, weekly_volume_km=70,
            quality_sessions=2,
            difficulty_level=DifficultyLevel.DEMANDING,
            volume_strategy=VolumeStrategy.GRADUAL,
        )
        plan = generate_plan(runner, Distance.K5, 12, sessions_per_week=4)
        assert _count_quality(plan.week_plans, 3) == 2
        assert plan.pace_profile is not None
        assert plan.pace_profile.vo2 is not None
