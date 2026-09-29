"""VDOT calculation (Jack Daniels) and pace derivation for Norwegian Singles."""

from __future__ import annotations

import math
from datetime import timedelta

from .models import (
    FatigueDuration,
    FatigueLevel,
    Pace,
    PaceRating,
    Paces,
    PainImpact,
    PainLevel,
    SessionFeedback,
    Zone,
)

# Race distances in meters (compat)
DISTANCE_M = {
    "5k": 5000,
    "10k": 10000,
    "semi": 21097.5,
    "marathon": 42195.0,
}


class VDOTCalculator:
    """Centralized VDOT and pace mathematics with decimal precision.

    All pace values are float seconds/km internally; rounding happens
    only at display boundaries via format_pace / format_pace_range.
    """

    @staticmethod
    def _coeffs() -> dict:
        from .engine.config import get_vdot_config
        return get_vdot_config()

    @staticmethod
    def _distance_metres(distance: str) -> float:
        from .engine.config import get_distance_metres
        return get_distance_metres(distance)

    # --- core formula ---

    @staticmethod
    def _vo2(v_m_per_min: float) -> float:
        c = VDOTCalculator._coeffs()["formula"]["vo2_coefficients"]
        return c["a"] * v_m_per_min**2 + c["b"] * v_m_per_min + c["c"]

    @staticmethod
    def _pct_vo2max(t_min: float) -> float:
        c = VDOTCalculator._coeffs()["formula"]["pct_vo2max_coefficients"]
        return (
            c["base"]
            + c["decay1_amplitude"] * math.exp(-c["decay1_rate"] * t_min)
            + c["decay2_amplitude"] * math.exp(-c["decay2_rate"] * t_min)
        )

    @staticmethod
    def threshold_fraction() -> float:
        return VDOTCalculator._coeffs()["formula"]["threshold_fraction"]

    # --- VDOT ↔ performance ---

    @staticmethod
    def from_race(distance: str, time: str) -> float:
        """Calculate VDOT from a race performance."""
        d = VDOTCalculator._distance_metres(distance)
        t_sec = parse_time_to_seconds(time)
        t_min = t_sec / 60.0
        v = d / t_min
        pct = VDOTCalculator._pct_vo2max(t_min)
        vo2 = VDOTCalculator._vo2(v)
        return round(vo2 / pct, 1)

    @staticmethod
    def race_time(vdot: float, distance: str) -> str:
        """Predict race time from VDOT. Returns formatted time string."""
        bs = VDOTCalculator._coeffs()["binary_search"]
        d = VDOTCalculator._distance_metres(distance)
        lo, hi = bs["min_seconds"], bs["max_seconds"]
        for _ in range(bs["iterations"]):
            mid = (lo + hi) / 2
            v = VDOTCalculator.from_race(distance, seconds_to_time_str(mid))
            if v > vdot:
                lo = mid
            else:
                hi = mid
        return seconds_to_time_str(round((lo + hi) / 2))

    @staticmethod
    def race_time_float(vdot: float, distance: str) -> float:
        """Predict race time as float seconds."""
        return parse_time_to_seconds(VDOTCalculator.race_time(vdot, distance))

    @staticmethod
    def race_pace(vdot: float, distance: str) -> Pace:
        """Predict race pace as Pace (int s/km)."""
        return VDOTCalculator.race_pace_float(vdot, distance).to_pace()

    @staticmethod
    def race_pace_float(vdot: float, distance: str) -> "_FloatPace":
        """Predict race pace as float s/km."""
        d = VDOTCalculator._distance_metres(distance)
        t_sec = VDOTCalculator.race_time_float(vdot, distance)
        return _FloatPace(t_sec * 1000.0 / d)

    @staticmethod
    def threshold_pace(vdot: float) -> Pace:
        """Threshold pace as Pace (int s/km). Compat wrapper."""
        return VDOTCalculator.threshold_pace_float(vdot).to_pace()

    @staticmethod
    def threshold_pace_float(vdot: float) -> "_FloatPace":
        """Threshold pace as float s/km via inverse Daniels formula."""
        target_vo2 = vdot * VDOTCalculator.threshold_fraction()
        c = VDOTCalculator._coeffs()["formula"]["vo2_coefficients"]
        a, b, cc = c["a"], c["b"], c["c"]
        discriminant = b**2 - 4 * a * (cc - target_vo2)
        v = (-b + math.sqrt(discriminant)) / (2 * a)  # m/min
        return _FloatPace(60.0 / v * 1000.0)

    # --- conversions ---

    @staticmethod
    def pace_from_time_distance(time_str: str, distance: str) -> float:
        """Pace (s/km) from time string and distance."""
        d = VDOTCalculator._distance_metres(distance)
        t_sec = parse_time_to_seconds(time_str)
        return t_sec * 1000.0 / d

    @staticmethod
    def time_from_pace_distance(pace_s_per_km: float, distance: str) -> str:
        """Time string from pace (s/km) and distance."""
        d = VDOTCalculator._distance_metres(distance)
        t_sec = pace_s_per_km * d / 1000.0
        return seconds_to_time_str(t_sec)

    @staticmethod
    def distance_from_time_pace(time_str: str, pace_s_per_km: float) -> float:
        """Distance (km) from time and pace."""
        t_sec = parse_time_to_seconds(time_str)
        return t_sec / pace_s_per_km

    @staticmethod
    def pace_to_kmh(pace_s_per_km: float) -> float:
        return 3600.0 / pace_s_per_km

    @staticmethod
    def kmh_to_pace(kmh: float) -> float:
        return 3600.0 / kmh

    # --- formatting ---

    @staticmethod
    def format_pace(pace_s_per_km: float) -> str:
        """Format float s/km as M'SS."""
        s = int(round(pace_s_per_km))
        return f"{s // 60}'{s % 60:02d}"

    @staticmethod
    def format_pace_range(min_pace: float, max_pace: float) -> str:
        """Format pace range as M'SS–M'SS."""
        return f"{VDOTCalculator.format_pace(min_pace)}\u2013{VDOTCalculator.format_pace(max_pace)}"

    # --- VDOT resolution ---

    @staticmethod
    def resolve_vdot(
        explicit: float | None = None,
        race_results: list | None = None,
        estimated: float | None = None,
    ) -> tuple[float, str]:
        """Resolve VDOT by precedence: explicit > recent race > estimated."""
        if explicit is not None:
            return explicit, "explicit"
        if race_results:
            vdots = [
                VDOTCalculator.from_race(r.distance, r.time) for r in race_results
            ]
            return max(vdots), "race"
        if estimated is not None:
            return estimated, "estimated"
        return 49.4, "default"

    @staticmethod
    def update_vdot_from_performance(
        distance: str, time: str, current_vdot: float
    ) -> dict:
        """Calculate new VDOT from a test or race performance."""
        new_vdot = VDOTCalculator.from_race(distance, time)
        return {
            "new_vdot": new_vdot,
            "delta": round(new_vdot - current_vdot, 1),
            "applies_to": "subsequent",
        }


class _FloatPace:
    """Internal float pace wrapper for engine calculations."""

    __slots__ = ("s_per_km",)

    def __init__(self, s_per_km: float):
        self.s_per_km = s_per_km

    def to_pace(self) -> Pace:
        return Pace(int(round(self.s_per_km)))

    def scaled(self, factor: float) -> "_FloatPace":
        return _FloatPace(self.s_per_km * factor)

    def __repr__(self) -> str:
        return f"_FloatPace({self.s_per_km:.2f})"


def parse_time_to_seconds(t: str) -> float:
    """'19:30' -> 1170.0, '1:32:40' -> 5560.0, '40:43' -> 2443.0"""
    parts = t.strip().split(":")
    if (
        len(parts) not in {2, 3}
        or any(not part.isdigit() for part in parts)
        or any(len(part) != 2 for part in parts[1:])
    ):
        raise ValueError("Time must use MM:SS or HH:MM:SS")
    values = [int(part) for part in parts]
    if any(value >= 60 for value in values[-2:]):
        raise ValueError("Minutes and seconds must be below 60")
    seconds = sum(value * (60 ** i) for i, value in enumerate(reversed(values)))
    if seconds <= 0:
        raise ValueError("Time must be positive")
    return float(seconds)


def seconds_to_time_str(s: float) -> str:
    """1170.0 -> '19:30', 5560.0 -> '1:32:40', 2443.0 -> '40:43'"""
    s = int(round(s))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def calc_vdot(distance: str, time: str) -> float:
    """Jack Daniels VDOT. Compat wrapper for VDOTCalculator.from_race."""
    return VDOTCalculator.from_race(distance, time)


def vdot_to_threshold_pace(vdot: float) -> Pace:
    """Threshold pace in s/km. Compat wrapper for VDOTCalculator.threshold_pace."""
    return VDOTCalculator.threshold_pace(vdot)


def derive_paces(vdot: float) -> Paces:
    """
    Derive all Norwegian Singles paces from VDOT.

    All zones use [fast, slow] ordering.

        SHORT  = [T,        T * 1.03]   (at threshold → slightly above)
        MEDIUM = [T * 1.02, T * 1.06]   (slightly below threshold)
        LONG   = [T * 1.05, T * 1.08]   (below threshold, HM-ish)
        EF     = [T * 1.35, T * 1.45]   (easy/endurance, fast→slow)
    """
    t = vdot_to_threshold_pace(vdot)

    return Paces(
        ef=(t.scaled(1.35), t.scaled(1.45)),
        short=(t, t.scaled(1.03)),
        medium=(t.scaled(1.02), t.scaled(1.06)),
        long=(t.scaled(1.05), t.scaled(1.08)),
    )


def predict_race_time(vdot: float, distance: str) -> str:
    """Predict race time from VDOT. Compat wrapper."""
    return VDOTCalculator.race_time(vdot, distance)


def predict_race_pace(vdot: float, distance: str) -> Pace:
    """Predict race pace (s/km) from VDOT. Compat wrapper."""
    return VDOTCalculator.race_pace(vdot, distance)


ZONE_WORKOUTS = {
    Zone.SHORT: ["NS-S01", "NS-S02", "NS-S03", "NS-S04", "NS-S05", "NS-S06"],
    Zone.MEDIUM: ["NS-M01", "NS-M02", "NS-M03", "NS-M04", "NS-M05", "NS-M06"],
    Zone.LONG: ["NS-L01", "NS-L02", "NS-L03", "NS-L04", "NS-L05", "NS-L06"],
}


def get_workout_zone(name: str) -> Zone | None:
    """Return zone for a workout ID. Delegates to engine library."""
    from .engine.library import get_workout_zone as _gz
    return _gz(name)


def get_adjacent_workout(name: str, step: int) -> str:
    """Returns adjacent canonical workout in same zone (-1 = lighter, +1 = denser)."""
    from .engine.library import get_adjacent_workout as _ga
    return _ga(name, step)


def recalibrate_vdot(vdot: float, zone: Zone, pace_factor: float) -> float:
    """Move a zone's midpoint pace by 1%, capped to one VDOT point."""
    current = getattr(derive_paces(vdot), zone.value)
    target = sum(pace.s_per_km for pace in current) / 2 * pace_factor
    direction = 1 if pace_factor < 1 else -1
    candidates = [round(vdot + direction * step / 10, 1) for step in range(1, 11)]
    return min(
        candidates,
        key=lambda candidate: abs(
            sum(pace.s_per_km for pace in getattr(derive_paces(candidate), zone.value)) / 2
            - target
        ),
    )


def evaluate_feedback(
    feedback: SessionFeedback,
    current_workout_name: str,
    previous_streak: int = 0,
) -> dict:
    """
    Evaluates session feedback deterministically.
    Returns dict with decision, reason, updated difficulty streak, and proposed adaptation if any.
    Priority: Pain > Fatigue > Pace/Difficulty.
    """
    # 1. Pain check
    has_pain_impact = feedback.pain_impact in (
        PainImpact.ALLURE_MODIFIEE,
        PainImpact.SEANCE_ARRETEE,
        PainImpact.VIE_QUOTIDIENNE,
    )
    if feedback.pain_level in (PainLevel.MODEREE, PainLevel.SEVERE) or has_pain_impact:
        return {
            "action": "suspend_running",
            "reason": "Douleur avec impact fonctionnel ou intensité modérée/forte : suspension de la qualité et recommandation d'évaluation par un professionnel de santé.",
            "difficulty_streak": previous_streak,
            "proposal": {
                "kind": "suspend_quality",
                "workout_target": None,
                "horizon_weeks": 2,
            },
        }
    if feedback.pain_level == PainLevel.LEGERE:
        return {
            "action": "suspend_progression",
            "reason": "Douleur légère signalée : pause de la progression, surveillance et recommandation d'activité indolore.",
            "difficulty_streak": previous_streak,
            "proposal": None,
        }

    # 2. Fatigue check
    if (
        feedback.fatigue_level == FatigueLevel.ELEVEE
        or feedback.fatigue_duration in (FatigueDuration.REPETEE, FatigueDuration.PERSISTANTE)
    ):
        return {
            "action": "suspend_next_quality",
            "reason": "Fatigue très élevée ou répétée : suspension de la prochaine séance de qualité et allègement de charge.",
            "difficulty_streak": previous_streak,
            "proposal": {
                "kind": "replace_with_easy",
                "workout_target": None,
                "horizon_weeks": 1,
            },
        }
    if feedback.fatigue_level == FatigueLevel.MODEREE:
        lighter = get_adjacent_workout(current_workout_name, -1)
        return {
            "action": "lighten_next_quality",
            "reason": "Fatigue élevée isolée : proposition d'une séance moins dense de même zone.",
            "difficulty_streak": previous_streak,
            "proposal": {
                "kind": "lighten_workout",
                "workout_target": lighter,
                "horizon_weeks": 1,
            },
        }

    # 3. Dominant temporary cause
    if (feedback.temp_cause or "").strip():
        return {
            "action": "monitor_temp_cause",
            "reason": f"Cause temporaire signalée ({feedback.temp_cause.strip()}) : surveillance sans modification du plan.",
            "difficulty_streak": previous_streak,
            "proposal": None,
        }

    # 4. Pace & Difficulty — exact conjunctions only:
    #    (INTENABLE + RPE∈{9,10}) or (TRES_FACILE + RPE∈{1,2})
    if feedback.pace_rating == PaceRating.INTENABLE and feedback.rpe >= 9:
        if previous_streak == 0:
            lighter = get_adjacent_workout(current_workout_name, -1)
            return {
                "action": "monitor_difficulty",
                "reason": "Premier signal intenable (RPE≥9) : proposition d'une séance moins dense de même zone.",
                "difficulty_streak": 1,
                "proposal": {
                    "kind": "lighten_workout",
                    "workout_target": lighter,
                    "workout_step": -1,
                    "horizon_weeks": 1,
                },
            }
        else:
            return {
                "action": "recalibrate_vdot",
                "reason": "Deuxième retour intenable (RPE≥9) dans cette zone : proposition de baisse VDOT bornée.",
                "difficulty_streak": 0,
                "proposal": {
                    "kind": "recalibrate_vdot",
                    "pace_factor": 1.01,
                    "workout_step": -2,
                },
            }

    if feedback.pace_rating == PaceRating.TRES_FACILE and feedback.rpe <= 2:
        if previous_streak:
            return {
                "action": "recalibrate_vdot",
                "reason": "Deuxième retour très facile (RPE≤2) dans cette zone : proposition de hausse VDOT bornée.",
                "difficulty_streak": 0,
                "proposal": {
                    "kind": "recalibrate_vdot",
                    "pace_factor": 0.99,
                    "workout_step": 2,
                },
            }
        denser = get_adjacent_workout(current_workout_name, 2)
        return {
            "action": "local_progression_trial",
            "reason": "Premier signal très facile (RPE≤2) : proposition d'essai de la séance supérieure de même zone.",
            "difficulty_streak": 1,
            "proposal": {
                "kind": "progression_trial",
                "workout_target": denser,
                "workout_step": 2,
                "horizon_weeks": 1,
            },
        }

    # All other ratings (controlee, facile, difficile, or conjunctions not met): no proposal
    return {
        "action": "maintain",
        "reason": "Allure contrôlée et conforme aux attentes du plan.",
        "difficulty_streak": 0,
        "proposal": None,
    }


def vdot_from_history(base_vdot: float, history: list[float]) -> float:
    """Blend base_vdot with a recency-weighted average of past derived VDOTs.

    history is ordered oldest -> newest. No history -> base_vdot unchanged.
    """
    if not history:
        return base_vdot

    # ponytail: fixed 0.6^i decay + 50/50 blend ratio, hardcoded ceiling —
    # make configurable if a user wants more/less race-history weight.
    n = len(history)
    weights = [0.6 ** i for i in range(n)]  # i=0 for newest, counting backward
    total_w = sum(weights)
    weighted_avg = sum(v * w for v, w in zip(reversed(history), weights)) / total_w

    return round(0.5 * base_vdot + 0.5 * weighted_avg, 1)


# --- Self-check ---
if __name__ == "__main__":
    # Semi 1:32:40 -> VDOT ~49.4
    v = calc_vdot("semi", "1:32:40")
    print(f"VDOT from semi 1:32:40: {v}")
    assert abs(v - 49.4) < 1.0, f"Expected ~49.4, got {v}"

    t = vdot_to_threshold_pace(v)
    print(f"Threshold pace: {t} s/km = {t}")

    p = derive_paces(v)
    print(f"EF:      {p.ef[0]} - {p.ef[1]}")
    print(f"SHORT:   {p.short[0]} - {p.short[1]}")
    print(f"MEDIUM:  {p.medium[0]} - {p.medium[1]}")
    print(f"LONG:    {p.long[0]} - {p.long[1]}")

    # 5K 19:00 -> VDOT ~50.6 (Daniels formula; tables give ~53 with empirical adjustment)
    v2 = calc_vdot("5k", "19:00")
    print(f"\nVDOT from 5K 19:00: {v2}")
    assert abs(v2 - 50.6) < 1.0, f"Expected ~50.6, got {v2}"

    # Garmin pace encoding check
    assert Pace.from_str("4'22").s_per_100m == 26.2, "pace encoding broken"
    assert Pace.from_str("3'52").s_per_100m == 23.2, "pace encoding broken"

    # Time prediction check: VDOT 49.4 → semi ~1:32:40
    pred = predict_race_time(49.4, "semi")
    print(f"\nPredicted semi time from VDOT 49.4: {pred}")
    assert abs(parse_time_to_seconds(pred) - 5560) < 60, f"Expected ~1:32:40, got {pred}"

    # 5K prediction from VDOT 50.6 → ~19:00
    pred5 = predict_race_time(50.6, "5k")
    print(f"Predicted 5K time from VDOT 50.6: {pred5}")
    assert abs(parse_time_to_seconds(pred5) - 1140) < 30, f"Expected ~19:00, got {pred5}"

    # Time str format check
    assert seconds_to_time_str(2443) == "40:43", f"Expected 40:43, got {seconds_to_time_str(2443)}"
    assert seconds_to_time_str(5454) == "1:30:54", f"Expected 1:30:54, got {seconds_to_time_str(5454)}"

    # VDOT history blending checks
    assert vdot_from_history(49.4, []) == 49.4, "no history should leave vdot unchanged"
    assert vdot_from_history(49.4, [50.0, 50.5]) > 49.4, "upward history should nudge vdot up"

    print("\nAll checks passed.")
