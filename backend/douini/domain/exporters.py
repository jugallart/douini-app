"""Exporter-neutral plan records and multi-format writers."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .models import (
    DAY_OFFSET,
    Paces,
    Session,
    TrainingPlan,
    WeekPlan,
    WorkoutDef,
    french_session_name,
)
from .planner import get_all_sessions, get_workout_names_for_plan


# ---------------------------------------------------------------------------
# Neutral records
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    order: int
    type: str
    duration_sec: int = 0
    distance_m: float = 0.0
    pace_key: str = ""
    repeat_count: int = 0
    children: list[StepRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"order": self.order, "type": self.type,
                    "duration_sec": self.duration_sec,
                    "distance_m": self.distance_m,
                    "pace_key": self.pace_key,
                    "repeat_count": self.repeat_count}
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclass
class SessionRecord:
    week: int
    bloc: str
    is_recovery: bool
    day: str
    type: str
    workout: Optional[str]
    structure: str
    distance_km: float
    pace: str
    category: str
    pace_key: Optional[str]
    load_score: float
    fatigue_contribution: float
    purpose: str
    steps: list[StepRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "week": self.week, "bloc": self.bloc,
            "is_recovery": self.is_recovery, "day": self.day,
            "type": self.type, "workout": self.workout,
            "structure": self.structure, "distance_km": self.distance_km,
            "pace": self.pace, "category": self.category,
            "pace_key": self.pace_key,
            "load_score": round(self.load_score, 2),
            "fatigue_contribution": round(self.fatigue_contribution, 2),
            "purpose": self.purpose,
            "steps": [s.to_dict() for s in self.steps],
        }

    def flat_dict(self) -> dict:
        """Flat row for CSV/XLSX (no steps)."""
        return {
            "week": self.week, "bloc": self.bloc,
            "recovery": "Y" if self.is_recovery else "",
            "day": self.day, "type": self.type,
            "workout": self.workout or "",
            "structure": self.structure,
            "pace": self.pace,
            "distance_km": self.distance_km,
            "category": self.category,
            "load_score": round(self.load_score, 2),
            "fatigue_contribution": round(self.fatigue_contribution, 2),
            "purpose": self.purpose,
        }


@dataclass
class WeekRecord:
    week_num: int
    bloc: str
    phase: Optional[str]
    is_recovery: bool
    is_taper: bool
    is_race_week: bool
    target_km: float
    actual_km: float
    weekly_load: float
    fatigue_index: float
    recovery_need: float
    sessions: list[SessionRecord]


@dataclass
class PlanRecord:
    distance: str
    weeks: int
    vdot: float
    goal_time: Optional[str]
    sessions_per_week: int
    start_date: Optional[str]
    paces: dict
    warnings: list[dict]
    race_day: Optional[dict]
    weeks_data: list[WeekRecord]

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "weeks": self.weeks,
            "vdot": self.vdot,
            "goal_time": self.goal_time,
            "sessions_per_week": self.sessions_per_week,
            "start_date": self.start_date,
            "paces": self.paces,
            "warnings": self.warnings,
            "race_day": self.race_day,
            "week_plans": [
                {
                    "week_num": w.week_num, "bloc": w.bloc,
                    "phase": w.phase, "is_recovery": w.is_recovery,
                    "is_taper": w.is_taper, "is_race_week": w.is_race_week,
                    "target_km": w.target_km, "actual_km": w.actual_km,
                    "weekly_load": round(w.weekly_load, 2),
                    "fatigue_index": round(w.fatigue_index, 2),
                    "recovery_need": round(w.recovery_need, 2),
                    "sessions": [s.to_dict() for s in w.sessions],
                }
                for w in self.weeks_data
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DAY_ORDER = list(DAY_OFFSET.keys())


def _purpose(session: Session) -> str:
    if session.workout:
        return session.workout.description
    if session.type == "long":
        return "Sortie longue - endurance aerobie"
    if session.type == "easy":
        return "Footing facile - recuperation"
    if session.type == "race":
        return "Course cible - jour de course"
    return session.structure or session.type


def _pace_str(session: Session) -> str:
    if session.workout:
        return f"{session.workout.pace_min}-{session.workout.pace_max}"
    return ""


def _build_step_records(session: Session) -> list[StepRecord]:
    """Build normalized step records from session workout or session data."""
    steps: list[StepRecord] = []
    if not session.workout:
        # Simple session: one interval step
        steps.append(StepRecord(
            order=0, type="time",
            duration_sec=int(session.distance_km * 400),
            pace_key=session.pace_key or "easy",
        ))
        return steps

    # Look up catalog entry for structure info
    from .engine.library import get_workout
    entry = get_workout(session.workout.name)
    structure = entry.get("structure", "uniform") if entry else "uniform"
    blocks = entry.get("blocks", []) if entry else []
    pace_key = entry.get("pace_key", "") if entry else ""
    rec_sec = session.workout.rec_sec

    if structure == "variable" and blocks:
        for i, blk in enumerate(blocks):
            steps.append(StepRecord(
                order=i * 2, type="interval",
                duration_sec=blk.get("sec", 0),
                pace_key=blk.get("pace_key", pace_key),
            ))
            steps.append(StepRecord(
                order=i * 2 + 1, type="recovery",
                duration_sec=rec_sec,
            ))
    elif structure == "progressive":
        for i in range(session.workout.reps):
            steps.append(StepRecord(
                order=i * 2, type="interval",
                duration_sec=session.workout.interval_sec,
                pace_key=pace_key,
            ))
            steps.append(StepRecord(
                order=i * 2 + 1, type="recovery",
                duration_sec=rec_sec,
            ))
    elif structure in ("distance", "time"):
        # Single work step
        dist_m = entry.get("distance_m", 0) if entry else 0
        dur_sec = entry.get("interval_sec", session.workout.interval_sec) if entry else session.workout.interval_sec
        steps.append(StepRecord(
            order=0, type="interval",
            duration_sec=dur_sec,
            distance_m=dist_m,
            pace_key=pace_key,
            repeat_count=session.workout.reps if session.workout.reps > 1 else 0,
        ))
        if session.workout.reps > 1:
            steps[-1].repeat_count = session.workout.reps
            steps[-1].type = "repeat"
            steps[-1].children = [
                StepRecord(order=0, type="interval",
                           duration_sec=dur_sec, distance_m=dist_m,
                           pace_key=pace_key),
                StepRecord(order=1, type="recovery",
                           duration_sec=rec_sec),
            ]
    else:
        # uniform
        steps.append(StepRecord(
            order=0, type="repeat", repeat_count=session.workout.reps,
            children=[
                StepRecord(order=0, type="interval",
                           duration_sec=session.workout.interval_sec,
                           pace_key=pace_key),
                StepRecord(order=1, type="recovery",
                           duration_sec=rec_sec),
            ],
        ))
    return steps


def _find_race_day(plan: TrainingPlan) -> Optional[dict]:
    for wk in plan.week_plans:
        for s in wk.sessions:
            if s.type == "race":
                return {"week": wk.week_num, "day": s.day,
                        "distance_km": s.distance_km}
    return None


def _is_taper_week(week: WeekPlan, plan: TrainingPlan) -> bool:
    if week.is_recovery:
        return False
    total = plan.weeks
    # ponytail: simple heuristic — last N weeks are taper
    from .engine.config import get_distance_rules
    try:
        rules = get_distance_rules(plan.distance)
        taper_count = rules.get("taper_weeks", 2)
    except Exception:
        taper_count = 2
    return week.week_num > total - taper_count


def _is_race_week(week: WeekPlan) -> bool:
    return any(s.type == "race" for s in week.sessions)


# ---------------------------------------------------------------------------
# Main record builder
# ---------------------------------------------------------------------------

def plan_to_records(plan: TrainingPlan) -> PlanRecord:
    """Map a TrainingPlan to exporter-neutral records."""
    p = plan.paces
    paces_dict = {
        "EF": {"min": str(p.ef[0]), "max": str(p.ef[1])},
        "SHORT": {"min": str(p.short[0]), "max": str(p.short[1])},
        "MEDIUM": {"min": str(p.medium[0]), "max": str(p.medium[1])},
        "LONG": {"min": str(p.long[0]), "max": str(p.long[1])},
    }

    warnings_list = [
        {"code": w.code, "message": w.message, "severity": w.severity}
        for w in (plan.warnings or [])
    ]

    race_day = _find_race_day(plan)

    week_records: list[WeekRecord] = []
    for wk in plan.week_plans:
        session_records: list[SessionRecord] = []
        for s in sorted(wk.sessions, key=lambda x: _DAY_ORDER.index(x.day) if x.day in _DAY_ORDER else 99):
            sr = SessionRecord(
                week=wk.week_num, bloc=wk.bloc,
                is_recovery=wk.is_recovery, day=s.day,
                type=s.type, workout=s.workout.name if s.workout else None,
                structure=s.structure, distance_km=s.distance_km,
                pace=_pace_str(s),
                category=s.category or s.type,
                pace_key=s.pace_key,
                load_score=getattr(s, "load_score", 0.0),
                fatigue_contribution=getattr(s, "fatigue_contribution", 0.0),
                purpose=_purpose(s),
                steps=_build_step_records(s),
            )
            session_records.append(sr)
        wr = WeekRecord(
            week_num=wk.week_num, bloc=wk.bloc,
            phase=getattr(wk, "phase", None),
            is_recovery=wk.is_recovery,
            is_taper=_is_taper_week(wk, plan),
            is_race_week=_is_race_week(wk),
            target_km=getattr(wk, "total_km", 0.0),
            actual_km=getattr(wk, "total_km", 0.0),
            weekly_load=getattr(wk, "weekly_load", 0.0),
            fatigue_index=getattr(wk, "fatigue_index", 0.0),
            recovery_need=getattr(wk, "recovery_need", 0.0),
            sessions=session_records,
        )
        week_records.append(wr)

    return PlanRecord(
        distance=plan.distance.value,
        weeks=plan.weeks,
        vdot=plan.runner.vdot,
        goal_time=getattr(plan.runner, "target_time", None),
        sessions_per_week=plan.sessions_per_week,
        start_date=plan.start_date.isoformat() if plan.start_date else None,
        paces=paces_dict,
        warnings=warnings_list,
        race_day=race_day,
        weeks_data=week_records,
    )


# ---------------------------------------------------------------------------
# Format writers
# ---------------------------------------------------------------------------

def export_json(plan: TrainingPlan, out_dir: str) -> str:
    """Export structured JSON suitable for round-trip."""
    os.makedirs(out_dir, exist_ok=True)
    rec = plan_to_records(plan)
    base = _base_name(plan)
    path = os.path.join(out_dir, f"{base}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec.to_dict(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def export_csv(plan: TrainingPlan, out_dir: str) -> str:
    """Export one session row per line with stable scalar columns."""
    os.makedirs(out_dir, exist_ok=True)
    rec = plan_to_records(plan)
    base = _base_name(plan)
    path = os.path.join(out_dir, f"{base}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "week", "bloc", "recovery", "day", "type", "workout",
            "structure", "pace", "distance_km", "category",
            "load_score", "fatigue_contribution", "purpose",
        ])
        for wk in rec.weeks_data:
            for s in wk.sessions:
                row = s.flat_dict()
                w.writerow([
                    row["week"], row["bloc"], row["recovery"],
                    row["day"], row["type"], row["workout"],
                    row["structure"], row["pace"], row["distance_km"],
                    row["category"], row["load_score"],
                    row["fatigue_contribution"], row["purpose"],
                ])
    return path


def export_xlsx(plan: TrainingPlan, out_dir: str) -> str:
    """Export multi-worksheet .xlsx (plan, weeks, sessions, steps)."""
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise ImportError(
            "openpyxl is required for XLSX export. "
            "Install with: pip install openpyxl"
        ) from e

    os.makedirs(out_dir, exist_ok=True)
    rec = plan_to_records(plan)
    base = _base_name(plan)
    path = os.path.join(out_dir, f"{base}.xlsx")

    wb = Workbook()

    # --- Plan sheet ---
    ws_plan = wb.active
    ws_plan.title = "Plan"
    ws_plan.append(["Field", "Value"])
    ws_plan.append(["Distance", rec.distance])
    ws_plan.append(["Weeks", rec.weeks])
    ws_plan.append(["VDOT", rec.vdot])
    ws_plan.append(["Goal Time", rec.goal_time or ""])
    ws_plan.append(["Sessions/Week", rec.sessions_per_week])
    ws_plan.append(["Start Date", rec.start_date or ""])
    if rec.race_day:
        ws_plan.append(["Race Week", rec.race_day["week"]])
        ws_plan.append(["Race Day", rec.race_day["day"]])
        ws_plan.append(["Race Distance (km)", rec.race_day["distance_km"]])

    ws_plan.append([])
    ws_plan.append(["Zone", "Min", "Max"])
    for zone, bounds in rec.paces.items():
        ws_plan.append([zone, bounds["min"], bounds["max"]])

    ws_plan.append([])
    if rec.warnings:
        ws_plan.append(["Warning", "Severity"])
        for w in rec.warnings:
            ws_plan.append([w["message"], w["severity"]])
    else:
        ws_plan.append(["No warnings"])

    # --- Weeks sheet ---
    ws_weeks = wb.create_sheet("Weeks")
    ws_weeks.append([
        "Week", "Bloc", "Phase", "Recovery", "Taper", "Race Week",
        "Target km", "Actual km", "Load", "Fatigue", "Recovery Need",
    ])
    for wk in rec.weeks_data:
        ws_weeks.append([
            wk.week_num, wk.bloc, wk.phase or "",
            "Y" if wk.is_recovery else "",
            "Y" if wk.is_taper else "",
            "Y" if wk.is_race_week else "",
            wk.target_km, wk.actual_km,
            round(wk.weekly_load, 2),
            round(wk.fatigue_index, 2),
            round(wk.recovery_need, 2),
        ])

    # --- Sessions sheet ---
    ws_sessions = wb.create_sheet("Sessions")
    ws_sessions.append([
        "Week", "Bloc", "Recovery", "Day", "Type", "Workout",
        "Structure", "Pace", "Distance km", "Category",
        "Load", "Fatigue", "Purpose",
    ])
    for wk in rec.weeks_data:
        for s in wk.sessions:
            ws_sessions.append([
                s.week, s.bloc, "Y" if s.is_recovery else "",
                s.day, s.type, s.workout or "",
                s.structure, s.pace, s.distance_km,
                s.category, round(s.load_score, 2),
                round(s.fatigue_contribution, 2),
                s.purpose,
            ])

    # --- Steps sheet ---
    ws_steps = wb.create_sheet("Steps")
    ws_steps.append([
        "Week", "Day", "Workout", "Step Order", "Type",
        "Duration sec", "Distance m", "Pace Key", "Repeat",
    ])
    for wk in rec.weeks_data:
        for s in wk.sessions:
            _write_steps_flat(ws_steps, wk.week_num, s.day,
                               s.workout or "", s.steps)

    wb.save(path)
    return path


def _write_steps_flat(ws, week: int, day: str, workout: str,
                      steps: list[StepRecord]) -> None:
    for step in steps:
        ws.append([
            week, day, workout, step.order, step.type,
            step.duration_sec, step.distance_m,
            step.pace_key, step.repeat_count,
        ])
        if step.children:
            for child in step.children:
                ws.append([
                    week, day, workout, child.order,
                    f"  {child.type}",
                    child.duration_sec, child.distance_m,
                    child.pace_key, child.repeat_count,
                ])


def export_markdown(plan: TrainingPlan, out_dir: str) -> str:
    """Export Markdown summary with paces, table, warnings, load."""
    os.makedirs(out_dir, exist_ok=True)
    rec = plan_to_records(plan)
    base = _base_name(plan)
    path = os.path.join(out_dir, f"{base}.md")

    lines: list[str] = [
        f"# Plan {rec.distance.upper()} — {rec.weeks} semaines — VDOT {rec.vdot}",
        "",
    ]

    if rec.goal_time:
        lines.append(f"> Objectif: {rec.goal_time}")
    if rec.start_date:
        lines.append(f"> Début: {rec.start_date}")
    if rec.race_day:
        lines.append(f"> Course: semaine {rec.race_day['week']} — {rec.race_day['day']} — {rec.race_day['distance_km']} km")
    lines.append("")

    # Paces
    lines.extend(["## Allures", "",
                   "| Zone | Min | Max |",
                   "|------|-----|-----|"])
    for zone, bounds in rec.paces.items():
        lines.append(f"| {zone} | {bounds['min']} | {bounds['max']} |")
    lines.append("")

    # Warnings
    if rec.warnings:
        lines.extend(["## Avertissements", ""])
        for w in rec.warnings:
            emoji = "⚠️" if w["severity"] == "warning" else "❌"
            lines.append(f"- {emoji} {w['message']}")
        lines.append("")

    # Weekly table
    lines.extend(["## Planning hebdomadaire", ""])
    active_days = _active_days(rec)
    day_headers = " | ".join(d.capitalize() for d in active_days)
    day_sep = " | ".join("-" * 5 for _ in active_days)
    lines.append(f"| Wk | Bloc | R | {day_headers} | km | Load |")
    lines.append(f"|----|------|---|{day_sep}|----|------|")
    for wk in rec.weeks_data:
        cells = {d: "-" for d in active_days}
        for s in wk.sessions:
            if s.workout:
                cells[s.day] = s.workout
            else:
                cells[s.day] = s.structure[:25] or s.type
        rec_mark = "R" if wk.is_recovery else ("T" if wk.is_taper else "")
        day_cells = " | ".join(cells[d] for d in active_days)
        lines.append(
            f"| {wk.week_num} | {wk.bloc} | {rec_mark} | {day_cells} "
            f"| {wk.actual_km} | {wk.weekly_load:.1f} |"
        )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def export_plan(plan: TrainingPlan, out_dir: str,
                formats: tuple[str, ...] = ("md", "csv")) -> list[str]:
    """Export plan in requested formats. Returns list of written paths."""
    paths: list[str] = []
    for fmt in formats:
        if fmt == "json":
            paths.append(export_json(plan, out_dir))
        elif fmt == "csv":
            paths.append(export_csv(plan, out_dir))
        elif fmt == "xlsx":
            paths.append(export_xlsx(plan, out_dir))
        elif fmt in ("md", "markdown"):
            paths.append(export_markdown(plan, out_dir))
    return paths


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------

def _base_name(plan: TrainingPlan) -> str:
    return f"plan-{plan.distance.value}-{plan.weeks}w-vdot{plan.runner.vdot}"


def _active_days(rec: PlanRecord) -> list[str]:
    seen: list[str] = []
    for d in _DAY_ORDER:
        if any(s.day == d for wk in rec.weeks_data for s in wk.sessions):
            seen.append(d)
    return seen


# ---------------------------------------------------------------------------
# JSON round-trip (replaces cli._save_plan_json / _load_plan_json)
# ---------------------------------------------------------------------------

def save_plan_json(plan: TrainingPlan, path: str) -> str:
    """Save plan state as JSON for in-progress editing."""
    from dataclasses import asdict
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {
        "distance": plan.distance.value,
        "weeks": plan.weeks,
        "sessions_per_week": plan.sessions_per_week,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "vdot": plan.plan_vdot if plan.plan_vdot is not None else plan.runner.vdot,
        "current_vdot": plan.runner.effective_vdot,
        "settings": asdict(plan.settings),
        "name": plan.name,
        "paces": plan.paces.to_dict(),
        "sessions": [],
    }
    for week in plan.week_plans:
        for s in week.sessions:
            data["sessions"].append({
                "week": week.week_num,
                "bloc": week.bloc,
                "is_recovery": week.is_recovery,
                "day": s.day,
                "type": s.type,
                "workout": s.workout.name if s.workout else None,
                "structure": s.structure,
                "distance_km": s.distance_km,
                "category": s.category,
                "pace_key": s.pace_key,
                "status": s.status.value if s.status else "pending",
                "id": s.id,
            })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def load_plan_json(path: str) -> TrainingPlan:
    """Reconstruct a TrainingPlan from saved JSON."""
    from .models import Pace, PlanSettings, RunnerProfile, SessionStatus
    from .planner import build_workout

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    p = data["paces"]
    paces = Paces(
        ef=(Pace.from_str(p["ef"][0]), Pace.from_str(p["ef"][1])),
        short=(Pace.from_str(p["short"][0]), Pace.from_str(p["short"][1])),
        medium=(Pace.from_str(p["medium"][0]), Pace.from_str(p["medium"][1])),
        long=(Pace.from_str(p["long"][0]), Pace.from_str(p["long"][1])),
    )

    runner = RunnerProfile(vdot=data.get("current_vdot", data["vdot"]), paces=paces)
    settings = PlanSettings(**data.get("settings", {"sessions_per_week": data.get("sessions_per_week", 4)}))
    start_date = None
    if data.get("start_date"):
        from datetime import date as _date
        start_date = _date.fromisoformat(data["start_date"])

    from .engine.pace_engine import PaceEngine
    pace_profile = PaceEngine(data["vdot"]).build_profile()
    weeks_map: dict[int, WeekPlan] = {}
    for entry in data["sessions"]:
        wn = entry["week"]
        if wn not in weeks_map:
            weeks_map[wn] = WeekPlan(
                week_num=wn,
                bloc=entry["bloc"],
                is_recovery=entry.get("is_recovery", False),
            )
        workout = None
        if entry.get("workout"):
            workout = build_workout(entry["workout"], paces, profile=pace_profile)
        session = Session(
            day=entry["day"],
            workout=workout,
            type=entry["type"],
            structure=entry.get("structure", ""),
            distance_km=entry.get("distance_km", 0.0),
            category=entry.get("category"),
            pace_key=entry.get("pace_key"),
            status=SessionStatus(entry.get("status", "pending")),
            id=entry.get("id"),
        )
        weeks_map[wn].sessions.append(session)

    for wn in sorted(weeks_map):
        wp = weeks_map[wn]
        wp.total_km = round(sum(s.distance_km for s in wp.sessions), 1)

    return TrainingPlan(
        runner=runner,
        distance=Distance(data["distance"]),
        weeks=data["weeks"],
        paces=paces,
        week_plans=[weeks_map[i] for i in sorted(weeks_map)],
        sessions_per_week=data.get("sessions_per_week", 4),
        start_date=start_date,
        pace_profile=pace_profile,
        settings=settings,
        plan_vdot=data["vdot"],
        name=data.get("name"),
    )


from .models import Distance  # at end to avoid circular
