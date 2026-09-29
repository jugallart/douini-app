"""Phase allocation and recovery week scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Distance, MIN_WEEKS, MAX_WEEKS, RECOVERY_WEEKS
from .config import get_distance_rules, resolve_distance

_PHASE_FR = {
    "BASE": "Adaptation",
    "BUILD": "Accumulation",
    "SPECIFIC": "Developpement",
    "PEAK": "Pic",
    "TAPER": "Affutage",
}


@dataclass
class PeriodizationResult:
    phase_for_week: dict[int, str] = field(default_factory=dict)
    recovery_weeks: set[int] = field(default_factory=set)
    taper_weeks: set[int] = field(default_factory=set)
    taper_count: int = 0

    def bloc_for_week(self, week_num: int) -> str:
        """French label for compat with legacy bloc system."""
        phase = self.phase_for_week.get(week_num, "BASE")
        return _PHASE_FR.get(phase, phase)


def _get_taper_count(distance: Distance) -> int:
    """Taper weeks from JSON config, falling back to TAPER_WEEKS."""
    try:
        did = resolve_distance(distance.value)
        return get_distance_rules(did).get("taper_weeks", 2)
    except (ValueError, KeyError):
        return 2


def allocate(distance: Distance, weeks: int, name: str | None = None) -> PeriodizationResult:
    """Allocate phases, recovery weeks, and taper across the plan."""
    is_tst_dev = bool(name and name.strip() == "TST_DEV")
    min_w = 1 if is_tst_dev else MIN_WEEKS[distance]
    if weeks < min_w:
        raise ValueError(
            f"Un plan {distance.value} nécessite au moins {min_w} semaines de préparation."
        )
    if weeks > MAX_WEEKS:
        raise ValueError(f"La durée maximale supportée est de {MAX_WEEKS} semaines.")

    if is_tst_dev and weeks < MIN_WEEKS[distance]:
        return PeriodizationResult(phase_for_week={1: "BASE"})

    t_count = _get_taper_count(distance)
    b = weeks - t_count

    recovery_set = {r for r in RECOVERY_WEEKS if r <= b - 2}
    taper_set = set(range(b + 1, weeks + 1))

    loading_weeks = sorted(
        w for w in range(1, weeks + 1) if w not in recovery_set and w not in taper_set
    )
    num_loading = len(loading_weeks)

    phase_for_week: dict[int, str] = {}
    for idx, w in enumerate(loading_weeks):
        if num_loading >= 3:
            # Split: 1/3 BASE, 1/3 BUILD, last 1/3 split into SPECIFIC + PEAK
            # PEAK gets last ~1/4 of the final third (min 1 week if enough weeks)
            third = num_loading / 3.0
            if idx < third:
                phase_for_week[w] = "BASE"
            elif idx < 2.0 * third:
                phase_for_week[w] = "BUILD"
            else:
                # Final third: assign PEAK to the last portion
                peak_count = max(1, int(third * 0.4)) if num_loading >= 6 else 0
                if peak_count > 0 and idx >= num_loading - peak_count:
                    phase_for_week[w] = "PEAK"
                else:
                    phase_for_week[w] = "SPECIFIC"
        else:
            phase_for_week[w] = "BASE"

    for rw in recovery_set:
        preceding = [lw for lw in loading_weeks if lw < rw]
        phase_for_week[rw] = phase_for_week.get(preceding[-1], "BASE") if preceding else "BASE"

    for tw in taper_set:
        phase_for_week[tw] = "TAPER"

    return PeriodizationResult(
        phase_for_week=phase_for_week,
        recovery_weeks=recovery_set,
        taper_weeks=taper_set,
        taper_count=t_count,
    )


# --- Compat wrappers (preserve legacy signatures) ---


def get_plan_structure(
    distance: Distance, weeks: int, name: str | None = None
) -> tuple[int, set[int], set[int]]:
    """Legacy: returns (taper_count, recovery_weeks, taper_weeks)."""
    r = allocate(distance, weeks, name)
    return r.taper_count, r.recovery_weeks, r.taper_weeks


def bloc_for_week(week_num: int, weeks: int) -> str:
    """Legacy: returns French bloc label."""
    third = max(1, weeks // 3)
    two_thirds = max(2, weeks * 2 // 3)
    if week_num <= third:
        return "Adaptation"
    if week_num <= two_thirds:
        return "Accumulation"
    return "Developpement"
