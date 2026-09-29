"""Frequency-aware session slot placement for 3-7 training days."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from ..models import DEFAULT_DAYS, DAY_OFFSET, Distance, Experience, SESSION_DAYS, VOLUME_CAPS

_WEEKDAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class WeekStructure:
    long_run_day: str
    quality_days: list[str] = field(default_factory=list)
    easy_days: list[str] = field(default_factory=list)
    quality_count: int = 0
    template_id: str = ""
    selection_reason: str = ""

    @property
    def all_days(self) -> list[str]:
        return sorted(self.quality_days + self.easy_days + [self.long_run_day],
                      key=lambda d: DAY_OFFSET.get(d, 0))


def quality_count_for(
    sessions_per_week: int,
    distance: Distance,
    interval_adapted: bool = False,
    quality_sessions: int | None = None,
) -> int:
    """Max quality sessions per week based on frequency and distance.

    When *quality_sessions* is explicitly set (1-3), it takes priority
    over the static lookup, subject to a safety cap based on sessions_per_week.
    """
    if quality_sessions is not None:
        # Need >=1 long run + >=1 easy day; rest can be quality
        cap = max(0, sessions_per_week - 2)
        # interval_adapted gate: 4-day plans cap at 1 quality if not adapted
        if not interval_adapted and sessions_per_week == 4:
            cap = min(cap, 1)
        return max(0, min(quality_sessions, cap))
    spw = sessions_per_week
    if spw <= 2:
        return 0
    if spw == 3:
        return 1
    if spw == 4:
        return 2 if interval_adapted else 1
    if spw == 5:
        return 2
    # 6-7 sessions
    return 2 if distance == Distance.MARATHON else 3


def assign_sessions(
    preferred_days: list[str] | None,
    sessions_per_week: int,
    distance: Distance,
    interval_adapted: bool = False,
    long_run_day: str | None = None,
    quality_sessions: int | None = None,
) -> WeekStructure:
    """Assign session days: long run, quality, easy."""
    if preferred_days and len(preferred_days) == sessions_per_week:
        days = list(preferred_days)
    else:
        days = SESSION_DAYS.get(sessions_per_week, DEFAULT_DAYS.copy())

    q_count = quality_count_for(sessions_per_week, distance, interval_adapted, quality_sessions)
    long_day, q_days, easy_days = select_quality_days(days, q_count)

    if long_run_day and long_run_day in days:
        long_day = long_run_day
        # Recompute quality/easy excluding long day
        available = [d for d in days if d != long_day]
        q_days, easy_days = _place_quality(available, q_count)

    return WeekStructure(
        long_run_day=long_day,
        quality_days=q_days,
        easy_days=easy_days,
        quality_count=q_count,
    )


def _place_quality(available: list[str], max_quality: int) -> tuple[list[str], list[str]]:
    """Place quality sessions with >=1 gap day."""
    sorted_avail = sorted(available, key=lambda d: DAY_OFFSET.get(d, 0))
    if max_quality <= 0 or not sorted_avail:
        return [], sorted_avail
    if max_quality == 1:
        return [sorted_avail[0]], sorted_avail[1:]
    if max_quality >= 3:
        triple = next(
            (c for c in combinations(sorted_avail, 3)
             if all(DAY_OFFSET[b] - DAY_OFFSET[a] >= 2 for a, b in zip(c, c[1:]))),
            None,
        )
        if triple:
            q = list(triple)
            return q, [d for d in sorted_avail if d not in q]

    best_pair = None
    for i in range(len(sorted_avail)):
        for j in range(i + 1, len(sorted_avail)):
            d1, d2 = sorted_avail[i], sorted_avail[j]
            if DAY_OFFSET[d2] - DAY_OFFSET[d1] >= 2:
                best_pair = (d1, d2)
                break
        if best_pair:
            break
    if best_pair:
        q = list(best_pair)
        return q, [d for d in sorted_avail if d not in q]
    return [sorted_avail[0]], sorted_avail[1:]


# --- Compat wrapper (preserves legacy signature) ---


def select_quality_days(
    training_days: list[str], max_quality: int = 2
) -> tuple[str, list[str], list[str]]:
    """Legacy: returns (long_run_day, quality_days, easy_days)."""
    sorted_days = sorted(training_days, key=lambda d: DAY_OFFSET.get(d, 0))
    if not sorted_days:
        sorted_days = DEFAULT_DAYS.copy()

    long_run_day = sorted_days[-1]
    available = [d for d in sorted_days if d != long_run_day]

    if max_quality <= 0:
        return long_run_day, [], available
    if len(sorted_days) <= 3 or len(available) < 2:
        q_days = [available[0]] if available else []
        return long_run_day, q_days, [d for d in available if d not in q_days]
    if max_quality == 1:
        return long_run_day, [available[0]], available[1:]
    if max_quality >= 3:
        triple = next(
            (c for c in combinations(available, 3)
             if all(DAY_OFFSET[b] - DAY_OFFSET[a] >= 2 for a, b in zip(c, c[1:]))),
            None,
        )
        if triple:
            q_days = list(triple)
            return long_run_day, q_days, [d for d in available if d not in q_days]

    best_pair = None
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            d1, d2 = available[i], available[j]
            if DAY_OFFSET[d2] - DAY_OFFSET[d1] >= 2:
                is_before_long = DAY_OFFSET[long_run_day] - DAY_OFFSET[d2] == 1
                candidate = (j - i if len(sorted_days) == 4 else 0, not is_before_long, d1, d2)
                if best_pair is None or candidate[:2] > best_pair[:2]:
                    best_pair = candidate
    if best_pair is not None:
        q_days = [best_pair[2], best_pair[3]]
    else:
        q_days = [available[0]]
    return long_run_day, q_days, [d for d in available if d not in q_days]


# ---------------------------------------------------------------------------
# Adaptive week structure (4-day plans)
# ---------------------------------------------------------------------------

@dataclass
class WeekTemplate:
    """Static template for 4-day week structure."""
    id: str
    quality_count: int
    quality_days: list[str]
    easy_days: list[str]
    long_run_day: str
    description: str  # e.g. "E-Q-E-LR"


def _build_templates_for_days(available: list[str], long_run_day: str) -> list[WeekTemplate]:
    """Build templates A/B/C for 3 available days + long run.

    A: quality on middle day (1 quality)
    B: quality on middle+last (2 quality, spaced) — preferred
    C: quality on first+middle (2 quality, adjacent) — conditional
    """
    sorted_avail = sorted(available, key=lambda d: DAY_OFFSET.get(d, 0))
    if len(sorted_avail) < 3:
        if not sorted_avail:
            return [WeekTemplate("A", 0, [], [], long_run_day, "empty")]
        d0 = sorted_avail[0]
        rest = sorted_avail[1:]
        return [WeekTemplate("A", 1, [d0], rest, long_run_day, "fallback")]

    d1, d2, d3 = sorted_avail[0], sorted_avail[1], sorted_avail[2]
    return [
        WeekTemplate("A", 1, [d2], [d1, d3], long_run_day, "E-Q-E-LR"),
        WeekTemplate("B", 2, [d2, d3], [d1], long_run_day, "E-Q-Qs-LR"),
        WeekTemplate("C", 2, [d1, d2], [d3], long_run_day, "Q-Q-E-LR"),
    ]


def quality_load_budget(
    weekly_volume: float,
    sessions_per_week: int,
    experience: Experience,
    phase: str,
    distance: Distance,
    previous_week_load: float = 0.0,
) -> float:
    """0-1 budget for quality load. >0.75 => 2 quality justified.

    Factors: volume ratio, experience, phase, previous load penalty.
    """
    vol_cap = VOLUME_CAPS.get(distance, 70.0)
    vol_ratio = min(weekly_volume / vol_cap, 1.3)

    exp_factor = {
        Experience.BEGINNER: 0.80,
        Experience.INTERMEDIATE: 1.0,
        Experience.ADVANCED: 1.10,
    }.get(experience, 1.0)

    phase_factor = {
        "BASE": 0.90,
        "BUILD": 1.0,
        "SPECIFIC": 1.05,
        "PEAK": 0.75,
        "TAPER": 0.35,
    }.get(phase, 1.0)

    raw = vol_ratio * exp_factor * phase_factor

    if previous_week_load > 0:
        prev_ratio = min(previous_week_load / vol_cap, 1.3)
        raw -= prev_ratio * 0.12

    return max(0.0, min(1.0, raw))


def _score_template(
    template: WeekTemplate,
    phase: str,
    distance: Distance,
    budget: float,
    previous_template_id: str,
    week_num: int,
    weeks_total: int,
) -> tuple[float, list[str]]:
    """Deterministic score for a template given week context.

    Returns (score, reasons).
    Decision priority: safety/recovery > load > phase > distance > specificity > progression > variety.
    """
    score = 0.0
    reasons: list[str] = []

    # 1. Safety / recovery
    if template.quality_count == 1:
        score += 1.0
        reasons.append("+ recovery (single quality)")
    elif template.id == "B":
        score += 1.5
        reasons.append("+ recovery spacing (Wed+Fri)")
    elif template.id == "C":
        score -= 0.5
        reasons.append("- recovery concern (adjacent quality)")

    # 2. Load budget match
    if template.quality_count == 1:
        if budget < 0.6:
            score += 2.0
            reasons.append("+ budget match (low budget -> 1 quality)")
        elif budget < 0.75:
            score += 0.5
            reasons.append("+ budget ok (medium, 1 quality safe)")
        else:
            score -= 1.0
            reasons.append("- budget underuse (high budget, only 1 quality)")
    else:
        if budget >= 0.75:
            score += 2.0
            reasons.append("+ budget match (high -> 2 quality)")
        elif budget >= 0.5:
            score += 0.3
            reasons.append("+ budget borderline (2 quality marginal)")
        else:
            score -= 2.5
            reasons.append("- budget overload (low budget, 2 quality)")

    # 3. Phase match
    if phase == "TAPER":
        if template.quality_count == 1:
            score += 2.5
            reasons.append("+ taper match (reduced quality)")
        else:
            score -= 2.5
            reasons.append("- taper mismatch (too much quality)")
    elif phase == "PEAK":
        if template.quality_count == 2 and template.id == "B":
            score += 1.0
            reasons.append("+ peak match (specific + spaced)")
        elif template.quality_count == 1:
            score += 0.5
            reasons.append("+ peak caution (reduced)")
    elif phase == "SPECIFIC":
        if template.quality_count == 2 and template.id == "B":
            score += 1.0
            reasons.append("+ specific match (2 quality, spaced)")
        elif template.quality_count == 1:
            score -= 0.5
            reasons.append("- specific mismatch (need 2 quality)")
    elif phase == "BUILD":
        if template.quality_count == 2 and budget >= 0.75:
            score += 0.5
            reasons.append("+ build progression (2 quality)")
        elif template.quality_count == 1:
            score += 0.5
            reasons.append("+ build conservative (1 quality)")
    elif phase == "BASE":
        if template.quality_count == 1:
            score += 1.0
            reasons.append("+ base match (1 quality)")
        elif template.quality_count == 2 and budget >= 0.85:
            score += 0.3
            reasons.append("+ base progressive (2 quality if budget high)")

    # 4. Distance match
    if distance in (Distance.MARATHON, Distance.SEMI):
        if template.quality_count == 2 and template.id == "B":
            score += 0.5
            reasons.append("+ distance match (endurance focus)")
    elif distance == Distance.K5:
        if template.id == "B":
            score += 0.3
            reasons.append("+ distance match (5K specificity)")

    # 5. Progression: early weeks slightly prefer 1 quality
    progress = week_num / max(weeks_total, 1)
    if progress < 0.2 and template.quality_count == 2:
        score -= 0.5
        reasons.append("- early plan (2 quality premature)")
    elif progress > 0.5 and template.quality_count == 1 and budget >= 0.8 and phase not in ("TAPER", "PEAK"):
        score -= 0.3
        reasons.append("- late plan (should have 2 quality)")

    # 6. Variety (deterministic, small bonus)
    if previous_template_id and template.id != previous_template_id:
        score += 0.3
        reasons.append("+ variety (different from prev week)")

    return score, reasons


def choose_week_structure(
    sessions_per_week: int,
    days: list[str],
    long_run_day: str | None,
    distance: Distance,
    phase: str,
    week_num: int,
    weeks_total: int,
    weekly_volume: float,
    interval_adapted: bool,
    previous_week_load: float = 0.0,
    previous_template_id: str = "",
    runner_experience: Experience = Experience.INTERMEDIATE,
    quality_sessions: int | None = None,
) -> WeekStructure:
    """Choose the best week structure for the given context.

    For 4-day plans: evaluates templates A/B/C via deterministic scoring.
    For other frequencies: delegates to assign_sessions() (unchanged).

    interval_adapted=True AUTHORIZES up to 2 quality (does not force).
    interval_adapted=False => max 1 quality.
    quality_sessions (1-3) overrides static lookup when set.
    """
    # Non-4-day: use existing logic unchanged
    if sessions_per_week != 4:
        ws = assign_sessions(
            preferred_days=days,
            sessions_per_week=sessions_per_week,
            distance=distance,
            interval_adapted=interval_adapted,
            long_run_day=long_run_day,
            quality_sessions=quality_sessions,
        )
        ws.template_id = "legacy"
        ws.selection_reason = f"Non-4-day plan (spw={sessions_per_week}): legacy placement"
        return ws

    # 4-day plan: evaluate templates
    lr_day = long_run_day if long_run_day and long_run_day in days else "sun"
    available = [d for d in days if d != lr_day]

    templates = _build_templates_for_days(available, lr_day)

    # Compute quality budget
    budget = quality_load_budget(
        weekly_volume, sessions_per_week, runner_experience,
        phase, distance, previous_week_load,
    )

    # interval_adapted=False: only 1-quality templates
    if not interval_adapted:
        templates = [t for t in templates if t.quality_count <= 1]
        if not templates:
            templates = _build_templates_for_days(available, lr_day)

    # quality_sessions override: filter to exact count
    if quality_sessions is not None:
        templates = [t for t in templates if t.quality_count == quality_sessions]
        if not templates:
            fallback = _build_templates_for_days(available, lr_day)
            if not interval_adapted:
                fallback = [t for t in fallback if t.quality_count <= 1]
            templates = [t for t in fallback if t.quality_count == quality_sessions]
        if not templates:
            templates = _build_templates_for_days(available, lr_day)

    # Score each template
    scored: list[tuple[float, WeekTemplate, list[str]]] = []
    for tmpl in templates:
        s, reasons = _score_template(
            tmpl, phase, distance, budget,
            previous_template_id, week_num, weeks_total,
        )
        scored.append((s, tmpl, reasons))

    # Deterministic selection: highest score, tie-break B > A > C
    _tiebreak = {"B": 0, "A": 1, "C": 2}
    scored.sort(key=lambda x: (-x[0], _tiebreak.get(x[1].id, 9)))

    best_score, best_tmpl, best_reasons = scored[0]

    reason_str = (
        f"Template {best_tmpl.id} ({best_tmpl.description}) "
        f"budget={budget:.2f} score={best_score:.1f} | "
        + " | ".join(best_reasons)
    )

    return WeekStructure(
        long_run_day=best_tmpl.long_run_day,
        quality_days=list(best_tmpl.quality_days),
        easy_days=list(best_tmpl.easy_days),
        quality_count=best_tmpl.quality_count,
        template_id=best_tmpl.id,
        selection_reason=reason_str,
    )
