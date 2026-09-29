"""Profile engine: validate runner profiles and derive planning variables."""

from __future__ import annotations

from ..models import (
    DAY_OFFSET,
    Distance,
    Experience,
    MIN_WEEKS,
    MAX_WEEKS,
    ProfileValidationResult,
    DerivedVars,
    RunnerProfile,
    SESSION_DAYS,
    sessions_for_training_days,
)
from .config import get_distance_rules, get_distances, resolve_distance, get_load_rules


class ProfileEngine:
    """Validates runner profiles and derives planning variables."""

    MANDATORY_FIELDS = [
        "target_weekly_km",
        "sessions_per_week",
        "race_distance",
        "weeks",
        "target_time",
    ]

    SUPPORTED_DISTANCES = {"5k", "10k", "semi", "marathon"}

    # --- public API ---

    def validate(self, profile: RunnerProfile) -> ProfileValidationResult:
        missing = self._check_missing(profile)
        if missing:
            return ProfileValidationResult(valid=False, missing_fields=missing)

        errors = self._check_errors(profile)
        if errors:
            return ProfileValidationResult(valid=False, errors=errors)

        warnings = self._check_feasibility(profile)
        derived = self._derive(profile)
        return ProfileValidationResult(
            valid=True,
            warnings=warnings,
            derived=derived,
        )

    def apply_defaults(self, profile: RunnerProfile) -> RunnerProfile:
        """Fill recommended fields with sensible defaults (mutates and returns)."""
        if profile.current_weekly_km is None:
            profile.current_weekly_km = (
                profile.target_weekly_km
                if profile.target_weekly_km
                else profile.weekly_volume_km
            )
        if profile.preferred_days is None:
            n = profile.sessions_per_week or 4
            profile.preferred_days = SESSION_DAYS.get(n, list(profile.training_days))
        if profile.long_run_day is None:
            days = profile.preferred_days or profile.training_days
            profile.long_run_day = days[-1] if days else "sun"
        if profile.current_longest_run is None:
            dist = profile.race_distance or "semi"
            rules = self._safe_distance_rules(dist)
            ratio = get_load_rules().get("long_run_ratio", {}).get(
                resolve_distance(dist), 0.30
            )
            target = profile.target_weekly_km or profile.weekly_volume_km or 70
            profile.current_longest_run = round(target * ratio * 0.6, 1)
        if profile.experience is None:
            profile.experience = Experience.INTERMEDIATE
        return profile

    # --- internals ---

    def _check_missing(self, p: RunnerProfile) -> list[str]:
        missing = []
        if p.target_weekly_km is None or p.target_weekly_km <= 0:
            missing.append("target_weekly_km")
        if not p.race_distance:
            missing.append("race_distance")
        if not p.target_time:
            missing.append("target_time")
        # sessions_per_week and weeks have defaults, but check ranges
        if p.sessions_per_week < 3 or p.sessions_per_week > 7:
            missing.append("sessions_per_week")
        if p.weeks < 1:
            missing.append("weeks")
        return missing

    def _check_errors(self, p: RunnerProfile) -> list[str]:
        errors = []

        # VDOT
        if p.vdot <= 0 or p.vdot > 100:
            errors.append(f"VDOT invalide: {p.vdot} (attendu 1-100)")

        # Distance
        if p.race_distance and p.race_distance.lower() not in self.SUPPORTED_DISTANCES:
            errors.append(f"Distance non supportee: {p.race_distance}")

        # Weeks range
        if p.weeks < 1 or p.weeks > MAX_WEEKS:
            errors.append(f"Nombre de semaines invalide: {p.weeks} (1-{MAX_WEEKS})")
        elif p.race_distance:
            dist_key = p.race_distance.lower()
            dist_enum = {
                "5k": Distance.K5,
                "10k": Distance.K10,
                "semi": Distance.SEMI,
                "marathon": Distance.MARATHON,
            }.get(dist_key)
            if dist_enum and dist_enum in MIN_WEEKS:
                min_w = MIN_WEEKS[dist_enum]
                if p.weeks < min_w:
                    errors.append(
                        f"Minimum {min_w} semaines pour {dist_key}, actuel: {p.weeks}"
                    )

        # Frequency
        if p.sessions_per_week < 3 or p.sessions_per_week > 7:
            errors.append(f"Sessions/semaine invalide: {p.sessions_per_week} (3-7)")

        # Training days distinct
        if len(set(p.training_days)) != len(p.training_days):
            errors.append("Jours d'entrainement en doublon")

        # Long run day membership
        if p.long_run_day and p.long_run_day not in DAY_OFFSET:
            errors.append(f"Jour de sortie longue invalide: {p.long_run_day}")
        elif p.long_run_day and p.preferred_days:
            if p.long_run_day not in p.preferred_days:
                errors.append(
                    f"Jour de sortie longue ({p.long_run_day}) "
                    f"absent des jours preferes"
                )

        # Preferred days distinct
        if p.preferred_days and len(set(p.preferred_days)) != len(p.preferred_days):
            errors.append("Jours preferes en doublon")

        return errors

    def _check_feasibility(self, p: RunnerProfile) -> list[str]:
        warnings = []
        self.apply_defaults(p)

        target_vol = p.target_weekly_km or p.weekly_volume_km or 70
        current_vol = p.current_weekly_km or target_vol

        if current_vol < target_vol * 0.70:
            gap = target_vol - current_vol
            warnings.append(
                f"Volume actuel ({current_vol} km) bien inferieur a l'objectif "
                f"({target_vol} km), ecart de {gap} km"
            )

        if p.current_longest_run and p.race_distance:
            rules = self._safe_distance_rules(p.race_distance)
            lr_cap = rules.get("long_run_cap_km", 25)
            if p.current_longest_run < lr_cap * 0.5:
                warnings.append(
                    f"Sortie longue actuelle ({p.current_longest_run} km) "
                    f"bien inferieure au besoin ({lr_cap} km)"
                )

        return warnings

    def _derive(self, p: RunnerProfile) -> DerivedVars:
        self.apply_defaults(p)
        target_vol = p.target_weekly_km or p.weekly_volume_km or 70
        current_vol = p.current_weekly_km or target_vol

        # volume_level
        if target_vol < 40:
            vol_level = "low"
        elif target_vol <= 60:
            vol_level = "moderate"
        else:
            vol_level = "high"

        # frequency_level
        if p.sessions_per_week <= 3:
            freq_level = "low"
        elif p.sessions_per_week <= 5:
            freq_level = "moderate"
        else:
            freq_level = "high"

        # specificity_need + speed_requirement
        dist_key = (p.race_distance or "semi").lower()
        if dist_key in ("5k", "10k"):
            spec_need = "high"
            speed_req = "high"
        elif dist_key == "semi":
            spec_need = "moderate"
            speed_req = "moderate"
        else:
            spec_need = "low"
            speed_req = "low"

        # aerobic_strength
        ratio = current_vol / target_vol if target_vol > 0 else 1.0
        if ratio < 0.70:
            aerobic = "developing"
        elif ratio < 0.90:
            aerobic = "adequate"
        else:
            aerobic = "strong"

        # long_run_requirement
        rules = self._safe_distance_rules(p.race_distance or "semi")
        lr_req = rules.get("long_run_cap_km", 25)

        # recovery_requirement
        if vol_level == "high" and freq_level == "high":
            recovery = "high"
        elif vol_level == "low" and freq_level == "low":
            recovery = "low"
        else:
            recovery = "moderate"

        # training_load_tolerance
        base = {Experience.BEGINNER: 0.7, Experience.INTERMEDIATE: 0.85,
                Experience.ADVANCED: 1.0}.get(p.experience, 0.85)
        # scale down for high volume
        if vol_level == "high":
            tol = base * 0.9
        elif vol_level == "low":
            tol = base * 1.1
        else:
            tol = base
        tol = min(1.0, tol)

        return DerivedVars(
            volume_level=vol_level,
            frequency_level=freq_level,
            specificity_need=spec_need,
            aerobic_strength=aerobic,
            speed_requirement=speed_req,
            long_run_requirement=lr_req,
            recovery_requirement=recovery,
            training_load_tolerance=round(tol, 2),
        )

    def _safe_distance_rules(self, distance: str) -> dict:
        try:
            return get_distance_rules(distance)
        except (ValueError, KeyError):
            return {"long_run_cap_km": 25}
