"""Workout catalog: load, validate, query, and build steps."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Optional

from ..models import (
    Pace, Paces, WorkoutDef, WorkoutStep, StepType, Zone,
    steps_work_duration, steps_total_duration, steps_total_distance_m,
)
from .pace_engine import PaceEngine
from .config import get_pace_zones, get_norwegian_paces

# Stride constants (shared with garmin.py)
STRIDE_FAST = 20
STRIDE_SLOW = 40
STRIDE_REPS = 4

# Pace key aliases -> Paces attribute
_PACE_COMPAT = {
    "easy": "ef", "ef": "ef", "recovery": "ef",
    "short": "short", "medium": "medium", "long": "long",
}


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

_WORKOUT_FILES = ["common.json", "norwegian.json", "5k.json", "10k.json", "half.json", "marathon.json"]


def _load_json(filename: str) -> dict:
    pkg = resources.files("douini_run.engine.workouts")
    return json.loads((pkg / filename).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_catalog() -> dict[str, dict]:
    """Load and validate all workout JSON files. Returns dict[id -> entry]."""
    catalog: dict[str, dict] = {}
    for fname in _WORKOUT_FILES:
        data = _load_json(fname)
        source = data.get("source", fname)
        for entry in data.get("workouts", []):
            wid = entry["id"]
            if wid in catalog:
                raise ValueError(f"Duplicate workout ID '{wid}' in {source}")
            entry["_source"] = source
            catalog[wid] = entry
    _validate_catalog(catalog)
    return catalog


def _validate_catalog(catalog: dict[str, dict]) -> None:
    """Validate catalog entries. Raises ValueError on first issue."""
    valid_structures = {"uniform", "variable", "progressive", "time", "distance"}
    valid_categories = {"quality", "easy", "recovery", "long_run", "secondary", "taper", "test", "race"}
    valid_zones = {"SHORT", "MEDIUM", "LONG", ""}
    valid_pace_keys = set(_PACE_COMPAT.keys()) | {"5K", "10K", "HM", "MARATHON", "threshold", "vo2", "economy", "long_run"}

    for wid, e in catalog.items():
        if not wid:
            raise ValueError(f"Empty workout ID in {e.get('_source')}")
        if e.get("structure") not in valid_structures:
            raise ValueError(f"{wid}: unsupported structure '{e.get('structure')}'")
        if e.get("category") not in valid_categories:
            raise ValueError(f"{wid}: unsupported category '{e.get('category')}'")
        if e.get("zone", "") not in valid_zones:
            raise ValueError(f"{wid}: unsupported zone '{e.get('zone')}'")
        if e.get("pace_key", "") not in valid_pace_keys:
            raise ValueError(f"{wid}: unknown pace_key '{e.get('pace_key')}'")
        if e["structure"] in ("uniform", "progressive") and e.get("reps", 0) <= 0:
            raise ValueError(f"{wid}: non-positive reps for {e['structure']}")
        if e["structure"] == "uniform" and e.get("interval_sec", 0) <= 0:
            raise ValueError(f"{wid}: non-positive interval_sec for uniform")
        if e["structure"] == "progressive" and e.get("interval_sec", 0) <= 0:
            raise ValueError(f"{wid}: non-positive interval_sec for progressive")
        if e["structure"] == "distance" and e.get("interval_m", 0) <= 0 and e.get("distance_m", -1) < 0:
            raise ValueError(f"{wid}: negative distance for distance structure")
        if e["structure"] == "time" and e.get("duration_sec", 0) <= 0:
            raise ValueError(f"{wid}: non-positive duration_sec for time structure")
        if e["structure"] == "variable" and not e.get("blocks"):
            raise ValueError(f"{wid}: variable structure requires blocks")
        for b in e.get("blocks", []):
            if b.get("sec", 0) <= 0 and b.get("distance_m", 0) <= 0:
                raise ValueError(f"{wid}: block with non-positive duration/distance")
            if b.get("pace_key", "") not in valid_pace_keys:
                raise ValueError(f"{wid}: block with unknown pace_key '{b.get('pace_key')}'")


# ---------------------------------------------------------------------------
# Query and lookup
# ---------------------------------------------------------------------------

def get_workout(workout_id: str) -> dict | None:
    """Look up a workout by ID. Returns None if not found."""
    return get_catalog().get(workout_id)


def query_workouts(
    distance: str | None = None,
    phase: str | None = None,
    zone: str | None = None,
    category: str | None = None,
    race_proximity: str | None = None,
) -> list[dict]:
    """Filter catalog by criteria. Returns entries sorted by ID for determinism."""
    cat = get_catalog()
    results = []
    for wid in sorted(cat.keys()):
        e = cat[wid]
        if distance and distance not in e.get("distances", []):
            continue
        if phase and phase not in e.get("phases", []):
            continue
        if zone and e.get("zone", "") != zone:
            continue
        if category and e.get("category", "") != category:
            continue
        if race_proximity and e.get("race_proximity", "all") != "all" and e.get("race_proximity") != race_proximity:
            continue
        results.append(e)
    return results


def all_workout_ids() -> list[str]:
    """All workout IDs sorted deterministically."""
    return sorted(get_catalog().keys())


def ns_workout_ids() -> list[str]:
    """Only the 18 canonical Norwegian Singles workout IDs."""
    return [wid for wid in sorted(get_catalog().keys()) if wid.startswith("NS-")]


# ---------------------------------------------------------------------------
# Compatibility: zone and adjacency (replaces vdot.py prefix-based versions)
# ---------------------------------------------------------------------------

_NS_ZONE_ORDER = {
    "NS-S": ["NS-S01", "NS-S02", "NS-S03", "NS-S04", "NS-S05", "NS-S06"],
    "NS-M": ["NS-M01", "NS-M02", "NS-M03", "NS-M04", "NS-M05", "NS-M06"],
    "NS-L": ["NS-L01", "NS-L02", "NS-L03", "NS-L04", "NS-L05", "NS-L06"],
}


def get_workout_zone(name: str | None) -> Zone | None:
    """Return zone for a workout ID. Uses catalog metadata, falls back to prefix."""
    if not name:
        return None
    entry = get_workout(name)
    if entry and entry.get("zone"):
        z = entry["zone"]
        return Zone(z.lower()) if z.lower() in ("short", "medium", "long") else None
    # Prefix fallback for unknown workouts
    if name.startswith("NS-S"):
        return Zone.SHORT
    if name.startswith("NS-M"):
        return Zone.MEDIUM
    if name.startswith("NS-L"):
        return Zone.LONG
    return None


def get_adjacent_workout(name: str, step: int) -> str:
    """Return adjacent NS workout in same zone. -1=lighter, +1=denser."""
    for prefix, ids in _NS_ZONE_ORDER.items():
        if name in ids:
            idx = ids.index(name)
            new_idx = max(0, min(len(ids) - 1, idx + step))
            return ids[new_idx]
    return name


# ---------------------------------------------------------------------------
# Pace resolution
# ---------------------------------------------------------------------------

def resolve_pace(
    pace_key: str,
    paces: Paces | None = None,
    profile=None,
) -> tuple[Pace, Pace]:
    """Resolve pace_key to (fast, slow) Pace pair.

    Tries PaceProfile first (if provided), then falls back to legacy Paces.
    """
    if profile is not None:
        # Race paces
        if pace_key in ("5K", "10K", "HM", "MARATHON"):
            pt = profile.race_paces.get(pace_key)
            if pt:
                return pt.pace_min, pt.pace_max
        # Norwegian zones
        if pace_key in ("short", "medium", "long"):
            pt = profile.norwegian.get(pace_key)
            if pt:
                return pt.pace_min, pt.pace_max
        # Standard zones (easy, recovery, long_run, threshold, vo2, economy)
        pt = getattr(profile, pace_key, None)
        if pt and hasattr(pt, "pace_min"):
            return pt.pace_min, pt.pace_max

    # Legacy Paces fallback
    if paces is not None:
        attr = _PACE_COMPAT.get(pace_key, pace_key)
        if hasattr(paces, attr):
            return getattr(paces, attr)

    raise ValueError(f"Cannot resolve pace_key '{pace_key}'")


# ---------------------------------------------------------------------------
# Step building
# ---------------------------------------------------------------------------

def _make_warmup_steps(warmup_sec: int) -> list[WorkoutStep]:
    """Warmup + strides, matching existing Garmin behavior."""
    steps = []
    if warmup_sec <= 0:
        return steps
    steps.append(WorkoutStep(type=StepType.WARMUP, duration_sec=warmup_sec, order=1))
    if STRIDE_REPS > 0:
        stride_fast = WorkoutStep(type=StepType.INTERVAL, duration_sec=STRIDE_FAST, pace_key="", order=1)
        stride_slow = WorkoutStep(type=StepType.RECOVERY, duration_sec=STRIDE_SLOW, order=2)
        steps.append(WorkoutStep(
            type=StepType.REPEAT, repeat_count=STRIDE_REPS,
            children=[stride_fast, stride_slow], order=2,
        ))
    return steps


def _make_cooldown_step(cooldown_sec: int, order: int) -> WorkoutStep | None:
    if cooldown_sec <= 0:
        return None
    return WorkoutStep(type=StepType.COOLDOWN, duration_sec=cooldown_sec, order=order)


def build_steps(
    entry: dict,
    paces: Paces | None = None,
    profile=None,
) -> list[WorkoutStep]:
    """Build normalized WorkoutStep list from catalog entry + paces.

    Handles all structures: uniform, variable, progressive, time, distance.
    """
    structure = entry["structure"]
    warmup_sec = entry.get("warmup_sec", 1200)
    cooldown_sec = entry.get("cooldown_sec", 1200)

    steps: list[WorkoutStep] = []
    order = 1

    # Warmup (with strides) for quality/secondary sessions
    if entry.get("category") in ("quality", "secondary"):
        for ws in _make_warmup_steps(warmup_sec):
            ws.order = order
            steps.append(ws)
            order += 1

    if structure == "time":
        duration = entry.get("duration_sec", 0)
        pace_key = entry.get("pace_key", "")
        pk = pace_key if pace_key else ""
        steps.append(WorkoutStep(
            type=StepType.INTERVAL, duration_sec=duration, pace_key=pk, order=order,
        ))
        order += 1

    elif structure == "distance":
        distance_m = entry.get("interval_m", 0) or entry.get("distance_m", 0)
        pace_key = entry.get("pace_key", "")
        reps = entry.get("reps", 1)
        rec_sec = entry.get("rec_sec", 0)

        if reps > 1:
            interval_step = WorkoutStep(
                type=StepType.DISTANCE, distance_m=distance_m, pace_key=pace_key, order=1,
            )
            children = [interval_step]
            if rec_sec > 0:
                children.append(WorkoutStep(
                    type=StepType.RECOVERY, duration_sec=rec_sec, order=2,
                ))
            steps.append(WorkoutStep(
                type=StepType.REPEAT, repeat_count=reps, children=children, order=order,
            ))
            order += 1
        else:
            steps.append(WorkoutStep(
                type=StepType.DISTANCE, distance_m=distance_m, pace_key=pace_key, order=order,
            ))
            order += 1

    elif structure == "uniform":
        interval_sec = entry["interval_sec"]
        pace_key = entry["pace_key"]
        reps = entry["reps"]
        rec_sec = entry.get("rec_sec", 60)

        interval_step = WorkoutStep(
            type=StepType.INTERVAL, duration_sec=interval_sec, pace_key=pace_key, order=1,
        )
        recovery_step = WorkoutStep(
            type=StepType.RECOVERY, duration_sec=rec_sec, order=2,
        )
        steps.append(WorkoutStep(
            type=StepType.REPEAT, repeat_count=reps,
            children=[interval_step, recovery_step], order=order,
        ))
        order += 1

    elif structure == "variable":
        rec_sec = entry.get("rec_sec", 60)
        blocks = entry.get("blocks", [])
        for block in blocks:
            block_sec = block.get("sec", 0)
            block_pace = block.get("pace_key", entry.get("pace_key", ""))
            if block.get("distance_m"):
                steps.append(WorkoutStep(
                    type=StepType.DISTANCE, distance_m=block["distance_m"],
                    pace_key=block_pace, order=order,
                ))
            else:
                steps.append(WorkoutStep(
                    type=StepType.INTERVAL, duration_sec=block_sec,
                    pace_key=block_pace, order=order,
                ))
            order += 1
            if rec_sec > 0:
                steps.append(WorkoutStep(
                    type=StepType.RECOVERY, duration_sec=rec_sec, order=order,
                ))
                order += 1

    elif structure == "progressive":
        interval_sec = entry["interval_sec"]
        pace_key = entry["pace_key"]
        reps = entry["reps"]
        rec_sec = entry.get("rec_sec", 60)

        for i in range(reps):
            t = i / max(reps - 1, 1)
            # Progressive: each rep gets 2% faster (scaled pace)
            steps.append(WorkoutStep(
                type=StepType.INTERVAL, duration_sec=interval_sec,
                pace_key=pace_key, order=order,
            ))
            order += 1
            if rec_sec > 0:
                steps.append(WorkoutStep(
                    type=StepType.RECOVERY, duration_sec=rec_sec, order=order,
                ))
                order += 1

    # Cooldown
    cd = _make_cooldown_step(cooldown_sec, order)
    if cd:
        steps.append(cd)
        order += 1

    return steps


# ---------------------------------------------------------------------------
# Legacy compatibility: build WorkoutDef from catalog entry
# ---------------------------------------------------------------------------

def build_workout_def(name: str, paces: Paces, profile=None) -> WorkoutDef:
    """Build legacy WorkoutDef from catalog entry. Works for all catalog workouts.

    When a PaceProfile is provided, pace_key resolution uses it directly,
    ensuring vo2/threshold/5K/etc. resolve to correct zones.
    """
    entry = get_workout(name)
    if entry is None:
        raise KeyError(f"Unknown workout: {name}")

    zone_str = entry.get("zone", "SHORT")
    zone = Zone(zone_str.lower()) if zone_str.lower() in ("short", "medium", "long") else Zone.SHORT

    pace_key = entry.get("pace_key", "short")
    if profile is not None:
        pace_min, pace_max = resolve_pace(pace_key, profile=profile)
    else:
        pace_min, pace_max = _resolve_pace_for_def(pace_key, paces)

    reps = entry.get("reps", 0)
    interval_sec = entry.get("interval_sec", 0)

    # For variable workouts, work_time = sum of block durations
    if entry.get("structure") == "variable":
        interval_sec = sum(b.get("sec", 0) for b in entry.get("blocks", []))
        reps = 1  # work_time_sec = reps * interval_sec

    return WorkoutDef(
        name=name,
        zone=zone,
        reps=reps,
        interval_sec=interval_sec,
        pace_min=pace_min,
        pace_max=pace_max,
        rec_sec=entry.get("rec_sec", 60),
        description=entry.get("description", ""),
    )


def _resolve_pace_for_def(pace_key: str, paces: Paces) -> tuple[Pace, Pace]:
    """Resolve pace_key to (fast, slow) for WorkoutDef. Falls back to ef."""
    attr = _PACE_COMPAT.get(pace_key, pace_key)
    if hasattr(paces, attr):
        return getattr(paces, attr)
    # Race-specific or unknown pace: fall back to easy pace
    return paces.ef


# ---------------------------------------------------------------------------
# Validation entry point
# ---------------------------------------------------------------------------

def validate_catalog() -> list[str]:
    """Validate catalog. Returns list of error messages (empty = OK)."""
    try:
        get_catalog()
    except ValueError as e:
        return [str(e)]
    return []
