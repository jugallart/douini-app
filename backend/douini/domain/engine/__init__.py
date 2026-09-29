"""Norwegian Singles training engine."""

from .config import (
    get_distances,
    get_load_rules,
    get_phases,
    get_progression_rules,
    get_session_types,
    get_validation_rules,
    resolve_distance,
    resolve_phase,
    validate_config,
)
from .library import (
    all_workout_ids,
    build_steps,
    build_workout_def,
    get_adjacent_workout,
    get_catalog,
    get_workout,
    get_workout_zone,
    ns_workout_ids,
    query_workouts,
    resolve_pace,
    validate_catalog,
)
from .profile import ProfileEngine
from . import periodization, progression, selection, taper, week_structure
from . import load, validation
