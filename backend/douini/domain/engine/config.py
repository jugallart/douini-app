"""Load and validate engine configuration from packaged JSON files."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


def _load_json(filename: str) -> dict:
    pkg = resources.files("douini_run.engine.data")
    return json.loads((pkg / filename).read_text(encoding="utf-8"))


# --- Phase 0 config loaders ---

@lru_cache(maxsize=1)
def get_vdot_config() -> dict:
    return _load_json("vdot.json")


@lru_cache(maxsize=1)
def get_distance_models() -> dict:
    return _load_json("distance_models.json")


@lru_cache(maxsize=1)
def get_pace_zones() -> dict:
    return _load_json("pace_zones.json")


@lru_cache(maxsize=1)
def get_norwegian_paces() -> dict:
    return _load_json("norwegian_paces.json")


# --- Phase 1 config loaders ---

@lru_cache(maxsize=1)
def get_distances() -> dict:
    return _load_json("distances.json")


@lru_cache(maxsize=1)
def get_phases() -> dict:
    return _load_json("phases.json")


@lru_cache(maxsize=1)
def get_session_types() -> dict:
    return _load_json("session_types.json")


@lru_cache(maxsize=1)
def get_load_rules() -> dict:
    return _load_json("load_rules.json")


@lru_cache(maxsize=1)
def get_progression_rules() -> dict:
    return _load_json("progression_rules.json")


@lru_cache(maxsize=1)
def get_validation_rules() -> dict:
    return _load_json("validation_rules.json")


@lru_cache(maxsize=1)
def get_plan_settings() -> dict:
    return _load_json("plan_settings.json")


# --- distance resolution ---

def resolve_distance(distance: str) -> str:
    """Resolve a distance identifier (compat alias -> canonical ID)."""
    distances = get_distances()
    aliases = distances.get("compat_aliases", {})
    return aliases.get(distance.lower(), distance.upper())


def get_distance_metres(distance: str) -> float:
    """Get metres for a distance ID (accepts compat aliases)."""
    distances = get_distances()
    did = resolve_distance(distance)
    if did in distances["distances"]:
        return distances["distances"][did]["metres"]
    # Fallback to distance_models.json for non-planning distances (1500, 3000, etc.)
    models = get_distance_models()
    for d in models["distances"]:
        if d["id"] == did:
            return d["metres"]
    raise ValueError(f"Unknown distance: {distance}")


def get_distance_rules(distance: str) -> dict:
    """Get planning rules for a distance (volume, long run cap, taper)."""
    distances = get_distances()
    did = resolve_distance(distance)
    if did not in distances["distances"]:
        raise ValueError(f"No planning rules for distance: {distance} (resolved: {did})")
    return distances["distances"][did]


def resolve_phase(bloc: str) -> str:
    """Map legacy French bloc label to canonical phase ID."""
    phases = get_phases()
    compat = phases.get("compat_labels", {})
    return compat.get(bloc, bloc.upper())


# --- validation ---

def validate_config() -> list[str]:
    """Validate all config. Returns list of error messages (empty = OK)."""
    errors: list[str] = []

    # Distance models (Phase 0)
    models = get_distance_models()
    seen: set[str] = set()
    for d in models["distances"]:
        did = d["id"]
        if did in seen:
            errors.append(f"Duplicate distance ID in distance_models: {did}")
        seen.add(did)
        if d["metres"] <= 0:
            errors.append(f"Distance {did} has non-positive metres")

    # Distances (Phase 1)
    distances = get_distances()
    for did, d in distances["distances"].items():
        if d["metres"] <= 0:
            errors.append(f"Distance {did} has non-positive metres")
        if d["volume_target_km"] <= 0:
            errors.append(f"Distance {did} has non-positive volume target")
        if d["long_run_cap_km"] <= 0:
            errors.append(f"Distance {did} has non-positive long run cap")
        # Cross-reference: metres must match distance_models.json
        for dm in models["distances"]:
            if dm["id"] == did and dm["metres"] != d["metres"]:
                errors.append(f"Distance {did}: metres mismatch ({dm['metres']} vs {d['metres']})")

    # Pace zones
    zones = get_pace_zones()
    for name in ("easy", "recovery", "long_run", "threshold", "vo2", "economy"):
        if name not in zones:
            errors.append(f"Missing pace zone: {name}")
            continue
        z = zones[name]
        if z["fast_factor"] > z["slow_factor"]:
            errors.append(f"Zone {name}: fast_factor > slow_factor (inverted)")

    # Norwegian anchors
    ns = get_norwegian_paces()
    anchors = ns["anchors"]
    for i in range(len(anchors) - 1):
        if anchors[i]["duration"] >= anchors[i + 1]["duration"]:
            errors.append("Norwegian anchors not monotonically increasing in duration")
        if anchors[i]["fast_factor"] > anchors[i + 1]["fast_factor"] + 0.001:
            errors.append("Norwegian fast factors not monotonically non-decreasing")
        if anchors[i]["slow_factor"] > anchors[i + 1]["slow_factor"] + 0.001:
            errors.append("Norwegian slow factors not monotonically non-decreasing")

    # Phases
    phases = get_phases()
    phase_ids = [p["id"] for p in phases["phases"]]
    if len(phase_ids) != len(set(phase_ids)):
        errors.append("Duplicate phase IDs")
    for p in phases["phases"]:
        if p["default_weeks_pct"] < 0 or p["default_weeks_pct"] > 1:
            errors.append(f"Phase {p['id']}: default_weeks_pct out of range")

    # Session types
    st = get_session_types()
    cat_ids = [c["id"] for c in st["categories"]]
    if len(cat_ids) != len(set(cat_ids)):
        errors.append("Duplicate session category IDs")
    for c in st["categories"]:
        if c["pace_key"] not in zones:
            errors.append(f"Session category {c['id']}: unknown pace_key '{c['pace_key']}'")

    # Load rules
    lr = get_load_rules()
    for did, ratio in lr.get("long_run_ratio", {}).items():
        if ratio <= 0 or ratio > 0.5:
            errors.append(f"Long run ratio for {did}: out of range ({ratio})")

    # Validation rules
    vr = get_validation_rules()
    for check in vr["checks"]:
        if check["severity"] not in ("warning", "error", "info"):
            errors.append(f"Validation check {check['id']}: invalid severity '{check['severity']}'")

    return errors
