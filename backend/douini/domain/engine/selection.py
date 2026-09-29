"""Score and select workouts from the catalog."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Experience
from .library import query_workouts


@dataclass
class SelectionContext:
    distance: str            # canonical: "5K", "10K", "HM", "MARATHON"
    phase: str               # "BASE", "BUILD", "SPECIFIC", "PEAK", "TAPER"
    week_num: int
    weeks_total: int
    weeks_to_race: int
    quality_count: int
    sessions_per_week: int
    volume_level: str        # "low", "moderate", "high"
    frequency_level: str
    experience: str
    history: list[str] = field(default_factory=list)  # workout IDs from prior 2 weeks


@dataclass
class ScoreComponent:
    name: str
    delta: float


@dataclass
class ScoredWorkout:
    workout_id: str
    score: float
    components: list[ScoreComponent] = field(default_factory=list)
    reason: str = ""


_VOL_LOAD = {"low": 2, "moderate": 3, "high": 4}
# ponytail: 0-1 scale matching catalog specificity field
_SPEC_NEED = {"5K": 0.90, "10K": 0.85, "HM": 0.75, "MARATHON": 0.70}


def _workout_method(entry: dict) -> str:
    """Deduce workout method from catalog fields (no JSON change needed)."""
    wid = entry.get("id", "")
    if wid.startswith("NS-"):
        return "norwegian"
    pace_key = entry.get("pace_key", "")
    if pace_key in ("5K", "10K", "HM", "MARATHON"):
        return "race_specific"
    if pace_key == "vo2":
        return "vo2"
    if pace_key == "threshold":
        return "race_specific"
    if pace_key == "economy":
        return "economy"
    cat = entry.get("category", "")
    if cat == "secondary":
        return "secondary"
    return "norwegian"


def _race_proximity(weeks_to_race: int) -> str | None:
    if weeks_to_race > 8:
        return "early"
    if weeks_to_race > 3:
        return "mid"
    return "late"


def _filter(ctx: SelectionContext) -> list[dict]:
    """Filter catalog entries matching the context."""
    candidates = query_workouts(distance=ctx.distance, phase=ctx.phase, category="quality")
    if not candidates:
        # Fallback: NS workouts for any distance/phase
        candidates = query_workouts(category="quality")
    # Filter by race proximity
    prox = _race_proximity(ctx.weeks_to_race)
    filtered = [
        e for e in candidates
        if e.get("race_proximity", "all") in ("all", "not-pre-race")
        or e.get("race_proximity") == prox
    ]
    # "not-pre-race" means: exclude in race week (weeks_to_race <= 1)
    if prox == "late" and ctx.weeks_to_race <= 1:
        filtered = [
            e for e in filtered
            if e.get("race_proximity", "all") != "not-pre-race"
        ]
    return filtered if filtered else candidates


def _score(entry: dict, ctx: SelectionContext, slot_index: int) -> ScoredWorkout:
    wid = entry["id"]
    score = 0.0
    components: list[ScoreComponent] = []

    # Distance specificity (0-10)
    if ctx.distance in entry.get("distances", []):
        s = 10.0
    elif wid.startswith("NS-"):
        s = 6.0  # NS workouts are always relevant
    else:
        s = 2.0
    score += s
    components.append(ScoreComponent("distance_specificity", s))

    # Volume match (0-5): workout load vs volume level
    load = entry.get("load", 3)
    vol_target = _VOL_LOAD.get(ctx.volume_level, 3)
    s = max(0.0, 5.0 - abs(load - vol_target))
    score += s
    components.append(ScoreComponent("volume", s))

    # Specificity match (0-5): 0-1 scale, distance-specific need vs catalog specificity
    spec = entry.get("specificity", 0.5)
    spec_need = _SPEC_NEED.get(ctx.distance, 0.5)
    s = max(0.0, 5.0 - abs(spec - spec_need) * 10.0)
    score += s
    components.append(ScoreComponent("specificity", s))

    # Fatigue allowance (0-3): higher fatigue ok when frequency/experience allow it
    fatigue = entry.get("fatigue", 3)
    exp_tol = {"BEGINNER": 2, "INTERMEDIATE": 3, "ADVANCED": 5}.get(ctx.experience, 3)
    freq_tolerance = {"low": 2, "moderate": 3, "high": 5}.get(ctx.frequency_level, 3)
    tol = max(exp_tol, freq_tolerance)
    s = max(0.0, 3.0 - max(0, fatigue - tol))
    score += s
    components.append(ScoreComponent("fatigue", s))

    # Progression (0-4): alternate dimensions by week
    prog_dim = (ctx.week_num + slot_index) % 4  # 0=volume, 1=duration, 2=intensity, 3=specificity
    prog_values = {
        0: entry.get("load", 3),
        1: entry.get("interval_sec", entry.get("duration_sec", 0)) / 60,
        2: entry.get("specificity", 0.5) * 10,  # scale 0-1 to 0-10
        3: entry.get("fatigue", 3),
    }
    s = min(4.0, prog_values.get(prog_dim, 2) * 0.8)
    score += s
    components.append(ScoreComponent("progression", s))

    # Method match (0-4): reward method appropriate to phase
    method = _workout_method(entry)
    method_score = {
        "BASE": {"norwegian": 4.0, "race_specific": 0.0, "vo2": 1.0, "economy": 1.0, "secondary": 2.0},
        "BUILD": {"norwegian": 3.0, "race_specific": 2.0, "vo2": 2.0, "economy": 1.0, "secondary": 2.0},
        "SPECIFIC": {"norwegian": 2.0, "race_specific": 4.0, "vo2": 4.0, "economy": 2.0, "secondary": 1.0},
        "PEAK": {"norwegian": 1.0, "race_specific": 4.0, "vo2": 4.0, "economy": 3.0, "secondary": 1.0},
        "TAPER": {"norwegian": 2.0, "race_specific": 1.0, "vo2": 1.0, "economy": 1.0, "secondary": 1.0},
    }
    ms = method_score.get(ctx.phase, {}).get(method, 1.0)
    score += ms
    components.append(ScoreComponent("method", ms))

    # Variety penalty: -penalty if seen in prior 2 weeks
    if wid in ctx.history:
        penalty = -float(entry.get("repetition_penalty", 5))
        score += penalty
        components.append(ScoreComponent("variety", penalty))

    reason = ", ".join(f"{c.name}={c.delta:+.1f}" for c in components)
    return ScoredWorkout(workout_id=wid, score=round(score, 2), components=components, reason=reason)


def select(ctx: SelectionContext, slot_index: int = 0) -> ScoredWorkout | None:
    """Select best workout for a quality slot. Returns None if no candidates."""
    candidates = _filter(ctx)
    if not candidates:
        return None

    scored = [_score(e, ctx, slot_index) for e in candidates]
    # Sort by score desc, then workout ID asc for deterministic tie-break
    scored.sort(key=lambda s: (-s.score, s.workout_id))
    return scored[0] if scored else None


def select_multiple(
    ctx: SelectionContext, count: int
) -> list[ScoredWorkout]:
    """Select multiple workouts for quality slots, avoiding same-method repetition."""
    results: list[ScoredWorkout] = []
    used_methods: set[str] = set()
    history = list(ctx.history)

    for slot in range(count):
        candidates = _filter(ctx)
        if not candidates:
            break

        scored = [_score(e, ctx, slot) for e in candidates]

        # Penalize same-method as already-selected in this week
        for sw in scored:
            entry = next((e for e in candidates if e["id"] == sw.workout_id), None)
            if entry:
                m = _workout_method(entry)
                if m in used_methods:
                    sw.score -= 3.0
                    sw.components.append(ScoreComponent("method_repeat", -3.0))
                    sw.reason = ", ".join(f"{c.name}={c.delta:+.1f}" for c in sw.components)

        scored.sort(key=lambda s: (-s.score, s.workout_id))

        if scored:
            best = scored[0]
            results.append(best)
            entry = next((e for e in candidates if e["id"] == best.workout_id), None)
            if entry:
                used_methods.add(_workout_method(entry))
            history.append(best.workout_id)

    return results
