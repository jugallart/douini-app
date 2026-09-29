"""User training statistics — pure functions over session data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class UserStatistics:
    total_distance_km: float = 0.0
    total_activities: int = 0
    total_running_time_min: float = 0.0
    longest_run_km: float = 0.0
    completed_count: int = 0
    planned_count: int = 0
    skipped_count: int = 0
    regularity_score: float = 0.0
    period_stats: list[dict] = field(default_factory=list)
    distance_stats: dict[str, dict] = field(default_factory=dict)


def compute_statistics(
    sessions: list[dict],
    plans: list[dict],
    counts: dict | None = None,
) -> dict:
    """Compute aggregated statistics from DB session rows and plan metadata."""
    counts = counts or {}
    completed = [s for s in sessions if s.get("status") == "completed"]
    total_distance = sum(s.get("distance_km", 0) for s in completed)
    longest = max((s.get("distance_km", 0) for s in completed), default=0.0)

    # Estimate running time: distance / estimated pace (use 5 min/km as fallback)
    total_time = total_distance * 5.0

    completed_count = len(completed)
    skipped_count = counts.get("skipped", 0)
    pending_count = counts.get("pending", 0)
    planned_count = completed_count + skipped_count + pending_count + counts.get("pushed", 0)

    # Regularity: completed / (completed + skipped + pending) if any
    total_expected = completed_count + skipped_count + pending_count
    regularity = (completed_count / total_expected) if total_expected > 0 else 0.0

    # Period stats (weekly)
    period_stats = _weekly_breakdown(completed)

    # Distance stats (per plan distance)
    distance_stats = _distance_breakdown(completed, plans)

    return {
        "total_distance_km": round(total_distance, 1),
        "total_activities": completed_count,
        "total_running_time_min": round(total_time, 0),
        "longest_run_km": round(longest, 1),
        "completed_count": completed_count,
        "planned_count": planned_count,
        "skipped_count": skipped_count,
        "regularity_score": round(regularity, 3),
        "period_stats": period_stats,
        "distance_stats": distance_stats,
    }


def _weekly_breakdown(sessions: list[dict]) -> list[dict]:
    """Group completed sessions by week start date."""
    weeks: dict[str, list[dict]] = {}
    for s in sessions:
        d = s.get("scheduled_date")
        if not d:
            continue
        if isinstance(d, str):
            d = date.fromisoformat(d)
        week_start = d - timedelta(days=d.weekday())
        key = week_start.isoformat()
        weeks.setdefault(key, []).append(s)
    return [
        {
            "week_start": key,
            "distance_km": round(sum(s.get("distance_km", 0) for s in sess), 1),
            "activities": len(sess),
            "sessions_completed": len(sess),
        }
        for key, sess in sorted(weeks.items())
    ]


def _distance_breakdown(sessions: list[dict], plans: list[dict]) -> dict[str, dict]:
    """Group completed sessions by plan distance."""
    plan_distance: dict[int, str] = {p["id"]: p["distance"] for p in plans}
    by_dist: dict[str, list[dict]] = {}
    for s in sessions:
        pid = s.get("plan_id")
        dist = plan_distance.get(pid, "unknown")
        by_dist.setdefault(dist, []).append(s)
    return {
        dist: {
            "plans": len({s.get("plan_id") for s in sess}),
            "total_km": round(sum(s.get("distance_km", 0) for s in sess), 1),
            "avg_weekly_km": round(sum(s.get("distance_km", 0) for s in sess) / max(len({s.get("week") for s in sess}), 1), 1),
        }
        for dist, sess in by_dist.items()
    }
