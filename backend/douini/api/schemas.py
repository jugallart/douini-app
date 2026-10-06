from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunnerProfileIn(BaseModel):
    vdot: float | None = None
    weekly_volume_km: float = 0
    mileage_tolerance_km: float = 0
    training_days: list[str] = []
    target_weekly_km: float | None = None
    sessions_per_week: int = 4
    race_distance: str | None = None
    weeks: int = 12
    target_time: str | None = None
    experience: str = "intermediaire"
    current_weekly_km: float | None = None
    current_longest_run: float | None = None
    long_run_day: str | None = None
    preferred_days: list[str] = []
    quality_sessions: int | None = None
    difficulty_level: str = "balanced"
    volume_strategy: str = "progressive"


class RunnerProfileOut(BaseModel):
    model_config = {"from_attributes": True}
    vdot: float | None = None
    weekly_volume_km: float = 0
    mileage_tolerance_km: float = 0
    training_days: list[str] = []
    target_weekly_km: float | None = None
    sessions_per_week: int = 4
    race_distance: str | None = None
    weeks: int = 12
    target_time: str | None = None
    experience: str = "intermediaire"
    current_weekly_km: float | None = None
    current_longest_run: float | None = None
    long_run_day: str | None = None
    preferred_days: list[str] = []
    quality_sessions: int | None = None
    difficulty_level: str = "balanced"
    volume_strategy: str = "progressive"


class UserIdentityIn(BaseModel):
    pseudo: str | None = None
    prenom: str | None = None
    nom: str | None = None


class ProfileCompletenessOut(BaseModel):
    model_config = {"from_attributes": True}
    complete: bool
    missing: list[str]


class PlanGenerateIn(BaseModel):
    plan_name: str | None = None
    distance: str
    weeks: int = 12
    vdot: float | None = None
    target_time: str | None = None
    sessions_per_week: int = 4
    training_days: list[str] = []
    long_run_day: str | None = None
    current_weekly_km: float | None = None
    current_longest_run: float | None = None
    target_weekly_km: float | None = None
    experience: str = "intermediaire"
    quality_sessions: int | None = None
    difficulty_level: str = "balanced"
    volume_strategy: str = "progressive"
    start_date: str | None = None
    race_date: str | None = None
    interval_adapted: bool = False


class PlanOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str | None = None
    distance: str | None = None
    weeks: int | None = None
    vdot: float | None = None
    start_date: str | None = None
    goal_time: str | None = None
    status: str = "active"
    created_at: str | None = None


class PlanDetailOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str | None = None
    distance: str | None = None
    weeks: int | None = None
    vdot: float | None = None
    start_date: str | None = None
    goal_time: str | None = None
    status: str = "active"
    sessions: list[dict[str, Any]] = []
    settings: dict[str, Any] = {}
    created_at: str | None = None


class SessionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    plan_id: int
    week: int
    day: str
    scheduled_date: str | None = None
    type: str = "easy"
    workout_name: str | None = None
    distance_km: float = 0
    status: str = "pending"


class SessionPatchIn(BaseModel):
    status: str | None = None


class SessionFeedbackIn(BaseModel):
    pace_rating: str
    rpe: int
    fatigue_level: str = "none"
    fatigue_duration: str = "aucune"
    pain_level: str = "none"
    pain_impact: str = "aucun"
    pain_location: str = ""
    pain_onset: str = ""
    pain_evolution: str = ""
    temp_cause: str = ""


class RaceResultIn(BaseModel):
    distance: str
    actual_time: str
    race_date: str | None = None
    notes: str = ""
    location: str = ""


class RaceResultOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    distance: str
    actual_time: str
    race_date: str | None = None
    derived_vdot: float | None = None
    notes: str = ""
    location: str = ""
    created_at: str | None = None


class StatsOut(BaseModel):
    model_config = {"from_attributes": True}
    total_distance_km: float = 0
    total_activities: int = 0
    total_running_time_min: float = 0
    longest_run_km: float = 0
    completed_count: int = 0
    planned_count: int = 0
    skipped_count: int = 0
    regularity_score: float = 0
    period_stats: dict[str, Any] = {}
    distance_stats: dict[str, Any] = {}


class RefreshProposalOut(BaseModel):
    model_config = {"from_attributes": True}
    old_vdot: float | None = None
    proposed_vdot: float | None = None
    old_current_weekly_km: float | None = None
    proposed_current_weekly_km: float | None = None
    old_current_longest_run: float | None = None
    proposed_current_longest_run: float | None = None
    evidence: dict[str, Any] = {}
    confidence: str = "medium"
    assumptions: list[str] = []
