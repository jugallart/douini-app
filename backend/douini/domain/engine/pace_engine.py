"""Independent PaceEngine: produces training parameters without workout or calendar knowledge.

Pipeline: VDOTCalculator -> PaceEngine -> PaceProfile -> Workout Engine -> ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import (
    FeasibilityResult,
    FeasibilityStatus,
    Pace,
    PaceProfile,
    PaceTarget,
    RaceResult,
)
from ..vdot import VDOTCalculator, _FloatPace
from .config import (
    get_distance_metres,
    get_norwegian_paces,
    get_pace_zones,
    get_vdot_config,
    resolve_distance,
)


class PaceEngine:
    """Produces training pace parameters from VDOT.

    Does not know about workouts, calendars, or plan selection.
    Accepts optional profile context (volume, frequency, experience,
    phase, fatigue) to widen ranges, never to prescribe exact paces.
    """

    def __init__(self, vdot: float, context: dict | None = None):
        self.vdot = vdot
        self.context = context or {}
        self._t = VDOTCalculator.threshold_pace_float(vdot)
        self._zones = get_pace_zones()
        self._ns = get_norwegian_paces()
        self._fatigue_widening = self._compute_fatigue_widening()

    def _compute_fatigue_widening(self) -> float:
        """Fatigue widens easy/recovery/long-run slow bound."""
        fatigue = self.context.get("fatigue", "none")
        if fatigue in ("heavy", "tres_elevee"):
            return 0.05
        if fatigue in ("moderate", "elevee"):
            return 0.025
        return 0.0

    def _make_target(
        self, fast_factor: float, slow_factor: float,
        zone: str, reference: str, widen: bool = False,
    ) -> PaceTarget:
        fast = self._t.s_per_km * fast_factor
        slow = self._t.s_per_km * slow_factor
        if widen:
            slow *= (1 + self._fatigue_widening)
        target = (fast + slow) / 2
        return PaceTarget(fast=fast, slow=slow, target=target, zone=zone, reference=reference)

    # --- race paces ---

    def get_race_pace(self, distance: str) -> PaceTarget:
        pace_s = VDOTCalculator.race_pace_float(self.vdot, distance).s_per_km
        return PaceTarget(fast=pace_s, slow=pace_s, target=pace_s, zone="RACE", reference=resolve_distance(distance))

    def get_race_time(self, distance: str) -> str:
        return VDOTCalculator.race_time(self.vdot, distance)

    # --- training zones ---

    def get_easy_pace(self) -> PaceTarget:
        z = self._zones["easy"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "EASY", z["reference"], widen=True)

    def get_recovery_pace(self) -> PaceTarget:
        z = self._zones["recovery"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "RECOVERY", z["reference"], widen=True)

    def get_long_run_pace(self) -> PaceTarget:
        z = self._zones["long_run"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "LONG_RUN", z["reference"], widen=True)

    def get_threshold_pace(self) -> PaceTarget:
        z = self._zones["threshold"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "THRESHOLD", z["reference"])

    def get_vo2_pace(self) -> PaceTarget:
        z = self._zones["vo2"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "VO2", z["reference"])

    def get_economy_pace(self) -> PaceTarget:
        z = self._zones["economy"]
        return self._make_target(z["fast_factor"], z["slow_factor"], "ECONOMY", z["reference"])

    def get_pace_range(self, zone: str) -> PaceTarget:
        """Generic zone lookup by name."""
        methods = {
            "easy": self.get_easy_pace,
            "recovery": self.get_recovery_pace,
            "long_run": self.get_long_run_pace,
            "threshold": self.get_threshold_pace,
            "vo2": self.get_vo2_pace,
            "economy": self.get_economy_pace,
        }
        if zone in methods:
            return methods[zone]()
        raise ValueError(f"Unknown zone: {zone}")

    # --- Norwegian continuous model ---

    def get_norwegian_pace(self, duration_minutes: float) -> PaceTarget:
        """Continuous interpolation from 3-12 min using configured anchors."""
        anchors = self._ns["anchors"]
        d_min = self._ns["min_duration_minutes"]
        d_max = self._ns["max_duration_minutes"]
        d = max(d_min, min(d_max, duration_minutes))

        # Find bracketing anchors
        if d <= anchors[0]["duration"]:
            a = anchors[0]
            return self._ns_target(a)
        if d >= anchors[-1]["duration"]:
            a = anchors[-1]
            return self._ns_target(a)

        for i in range(len(anchors) - 1):
            a1, a2 = anchors[i], anchors[i + 1]
            if a1["duration"] <= d <= a2["duration"]:
                t = (d - a1["duration"]) / (a2["duration"] - a1["duration"])
                fast = a1["fast_factor"] + t * (a2["fast_factor"] - a1["fast_factor"])
                slow = a1["slow_factor"] + t * (a2["slow_factor"] - a1["slow_factor"])
                ref = a1["reference"] if t < 0.5 else a2["reference"]
                return self._make_target(fast, slow, "NORWEGIAN", ref)
        # ponytail: unreachable but safe fallback
        return self._ns_target(anchors[-1])

    def _ns_target(self, anchor: dict) -> PaceTarget:
        return self._make_target(
            anchor["fast_factor"], anchor["slow_factor"], "NORWEGIAN", anchor["reference"]
        )

    def get_norwegian_label(self, label: str) -> PaceTarget:
        """Get Norwegian pace by compat label (SHORT/MEDIUM/LONG)."""
        labels = self._ns["compat_labels"]
        if label.upper() not in labels:
            raise ValueError(f"Unknown Norwegian label: {label}")
        rng = labels[label.upper()]
        mid = (rng["min_minutes"] + rng["max_minutes"]) / 2
        return self.get_norwegian_pace(mid)

    # --- full profile ---

    def build_profile(self) -> PaceProfile:
        race_distances = ["5K", "10K", "HM", "MARATHON"]
        race_paces = {d: self.get_race_pace(d) for d in race_distances}
        ns_durations = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]
        ns = {str(int(d)): self.get_norwegian_pace(d) for d in ns_durations}
        ns["short"] = self.get_norwegian_label("SHORT")
        ns["medium"] = self.get_norwegian_label("MEDIUM")
        ns["long"] = self.get_norwegian_label("LONG")
        return PaceProfile(
            vdot=self.vdot,
            race_paces=race_paces,
            easy=self.get_easy_pace(),
            recovery=self.get_recovery_pace(),
            long_run=self.get_long_run_pace(),
            threshold=self.get_threshold_pace(),
            vo2=self.get_vo2_pace(),
            economy=self.get_economy_pace(),
            norwegian=ns,
        )


class GoalFeasibilityChecker:
    """Compare current fitness with race goal without inflating training intensity."""

    @staticmethod
    def check(
        current_vdot: float,
        target_distance: str,
        target_time: str,
    ) -> FeasibilityResult:
        target_vdot = VDOTCalculator.from_race(target_distance, target_time)
        gap = round(target_vdot - current_vdot, 1)
        cfg = get_vdot_config()["feasibility"]
        if gap <= cfg["realistic_max"]:
            status = FeasibilityStatus.REALISTIC
            warning = ""
        elif gap <= cfg["ambitious_max"]:
            status = FeasibilityStatus.AMBITIOUS
            warning = "Objectif ambitieux: ecart modere avec le niveau actuel."
        elif gap <= cfg["aggressive_max"]:
            status = FeasibilityStatus.AGGRESSIVE
            warning = "Objectif agressif: ecart important avec le niveau actuel."
        else:
            status = FeasibilityStatus.UNREALISTIC
            warning = "Objectif peu realiste par rapport au niveau actuel."
        return FeasibilityResult(
            current_vdot=current_vdot,
            target_vdot=target_vdot,
            vdot_gap=gap,
            status=status,
            warning=warning,
        )


class PaceValidator:
    """Detect physiologically inverted pace profiles."""

    @staticmethod
    def validate(profile: PaceProfile) -> list[str]:
        """Return list of finding strings (empty = valid)."""
        findings: list[str] = []
        tol = get_pace_zones()["tolerance_seconds"]

        # Training zone ordering (s/km: higher = slower)
        # recovery > easy > long_run > threshold > vo2
        zones = [
            ("recovery", profile.recovery),
            ("easy", profile.easy),
            ("long_run", profile.long_run),
            ("threshold", profile.threshold),
            ("vo2", profile.vo2),
        ]
        for i in range(len(zones) - 1):
            n1, t1 = zones[i]
            n2, t2 = zones[i + 1]
            if t1.target < t2.target - tol:
                findings.append(
                    f"Inverted: {n1} ({t1.target:.1f}) faster than {n2} ({t2.target:.1f})"
                )

        # Race pace ordering (s/km: lower = faster)
        # 5K < 10K < HM < MARATHON
        race = profile.race_paces
        race_order = [("5K", "10K"), ("10K", "HM"), ("HM", "MARATHON")]
        for d1, d2 in race_order:
            if d1 in race and d2 in race:
                if race[d1].target > race[d2].target + tol:
                    findings.append(
                        f"Inverted: {d1} ({race[d1].target:.1f}) slower than {d2} ({race[d2].target:.1f})"
                    )

        # Norwegian ordering (s/km: lower = faster)
        # short < medium < long
        ns = profile.norwegian
        if "short" in ns and "medium" in ns:
            if ns["short"].target > ns["medium"].target + tol:
                findings.append("Norwegian short slower than medium")
        if "medium" in ns and "long" in ns:
            if ns["medium"].target > ns["long"].target + tol:
                findings.append("Norwegian medium slower than long")

        return findings


class PaceAdjustmentEngine:
    """No-op boundary for future environmental adjustments."""

    @staticmethod
    def adjust(pace_s_per_km: float, conditions: dict | None = None) -> float:
        """Return pace unchanged. Future: temperature, wind, altitude."""
        return pace_s_per_km


def debug_output(
    vdot: float,
    target_distance: str | None = None,
    target_time: str | None = None,
) -> str:
    """Produce debug output for VDOT, paces, feasibility, and Norwegian ranges."""
    fmt = VDOTCalculator.format_pace
    fmt_r = VDOTCalculator.format_pace_range
    engine = PaceEngine(vdot)
    profile = engine.build_profile()

    lines: list[str] = []
    lines.append(f"VDOT : {vdot}")
    lines.append("")

    lines.append("PERFORMANCES THEORIQUES")
    for d in ("5K", "10K", "HM", "MARATHON"):
        lines.append(f"  {d:10s} : {engine.get_race_time(d)}")
    lines.append("")

    lines.append("ZONES D'ENTRAINEMENT")
    for name, pt in [
        ("Recovery", profile.recovery),
        ("Easy", profile.easy),
        ("Long Run", profile.long_run),
        ("Threshold", profile.threshold),
        ("VO2", profile.vo2),
    ]:
        lines.append(f"  {name:12s} : {fmt_r(pt.fast, pt.slow)}")
    lines.append("")

    lines.append("NORWEGIAN")
    for d in (3, 4, 6, 8, 10, 12):
        ns = engine.get_norwegian_pace(float(d))
        lines.append(f"  {d:>2}'         : {fmt_r(ns.fast, ns.slow)}")
    lines.append("")

    if target_distance and target_time:
        result = GoalFeasibilityChecker.check(vdot, target_distance, target_time)
        lines.append("FAISABILITE")
        lines.append(f"  VDOT actuel  : {result.current_vdot}")
        lines.append(f"  VDOT cible   : {result.target_vdot}")
        lines.append(f"  Ecart        : {result.vdot_gap:+.1f}")
        lines.append(f"  Statut       : {result.status.value}")
        if result.warning:
            lines.append(f"  Alerte       : {result.warning}")
        lines.append("")

    return "\n".join(lines)
