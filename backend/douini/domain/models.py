"""Data models for runner profiles, workouts, and training plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Distance(str, Enum):
    K5 = "5k"
    K10 = "10k"
    SEMI = "semi"
    MARATHON = "marathon"


class Zone(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


# Duration constraints per distance (min weeks, max 16 weeks)
MIN_WEEKS = {
    Distance.K5: 4,
    Distance.K10: 6,
    Distance.SEMI: 10,
    Distance.MARATHON: 12,
}
MAX_WEEKS = 16

# Recommended duration range (weeks) per distance
RECOMMENDED_WEEKS = {
    Distance.K5: (6, 10),
    Distance.K10: (8, 12),
    Distance.SEMI: (10, 14),
    Distance.MARATHON: (12, 16),
}

# Taper length (weeks) per distance
TAPER_WEEKS = {
    Distance.K5: 1,
    Distance.K10: 1,
    Distance.SEMI: 2,
    Distance.MARATHON: 3,
}

# Volume ratios relative to runner baseline volume per distance
# 5K/10K slightly lower specific weekly volume, Semi/Marathon higher
DISTANCE_VOLUME_RATIOS = {
    Distance.K5: 0.85,
    Distance.K10: 0.90,
    Distance.SEMI: 0.95,
    Distance.MARATHON: 1.00,
}

# Volume ceilings per distance (km/week) - default baseline reference
VOLUME_CAPS = {
    Distance.K5: 65,
    Distance.K10: 70,
    Distance.SEMI: 75,
    Distance.MARATHON: 78,
}

# Long run max per distance (km)
LONG_RUN_CAPS = {
    Distance.K5: 24,
    Distance.K10: 26,
    Distance.SEMI: 29,
    Distance.MARATHON: 32,
}

# Default training days
DEFAULT_DAYS = ["mon", "wed", "fri", "sun"]

# French day abbreviations for Garmin workout naming
DAY_FR = {
    "mon": "Lun",
    "tue": "Mar",
    "wed": "Mer",
    "thu": "Jeu",
    "fri": "Ven",
    "sat": "Sam",
    "sun": "Dim",
}

# Day → ISO weekday offset (Mon=0, Sun=6) for date calculation
DAY_OFFSET = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

# Session count options → which days to use.
# Quality (Mon/Wed) stays capped at 2/week per Norwegian Singles method —
# progression comes from density, not from adding more intensity days.
# Extra sessions beyond 5 add easy volume on Tue/Thu.
SESSION_DAYS = {
    3: ["mon", "fri", "sun"],                              # 1 quality + 1 easy + 1 long
    4: ["mon", "wed", "fri", "sun"],                       # 2 quality + 1 easy + 1 long (default)
    5: ["mon", "wed", "fri", "sat", "sun"],                # 2 quality + 2 easy + 1 long
    6: ["mon", "tue", "wed", "fri", "sat", "sun"],         # 2 quality + 3 easy + 1 long
    7: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],  # 2 quality + 4 easy + 1 long
}

SESSIONS_FOR_DAYS = {3: 3, 4: 4, 5: 5, 6: 6, 7: 7}


def sessions_for_training_days(days: list[str]) -> int:
    """Map training days list to closest valid sessions per week (3-7)."""
    n = len(days)
    if n <= 3:
        return 3
    if n >= 7:
        return 7
    return n


# Recovery weeks (deload)
RECOVERY_WEEKS = {4, 8, 12}

# Blocs
BLOCS = {
    1: "Adaptation",
    2: "Adaptation",
    3: "Adaptation",
    4: "Adaptation",
    5: "Accumulation",
    6: "Accumulation",
    7: "Accumulation",
    8: "Accumulation",
    9: "Developpement",
    10: "Developpement",
    11: "Developpement",
    12: "Developpement",
}


class PaceRating(str, Enum):
    TRES_FACILE = "tres_facile"
    FACILE = "facile"
    CONTROLEE = "controlee"
    DIFFICILE = "difficile"
    INTENABLE = "intenable"


class FatigueLevel(str, Enum):
    NORMALE = "none"
    LEGERE = "light"
    MODEREE = "moderate"
    ELEVEE = "heavy"


class FatigueDuration(str, Enum):
    AUCUNE = "aucune"
    ISOLEE = "isolee"
    REPETEE = "repetee"
    PERSISTANTE = "persistante"


class PainLevel(str, Enum):
    AUCUNE = "none"
    LEGERE = "light"
    MODEREE = "moderate"
    SEVERE = "severe"


class PainImpact(str, Enum):
    AUCUN = "aucun"
    ALLURE_MODIFIEE = "allure_modifiee"
    SEANCE_ARRETEE = "seance_arretee"
    VIE_QUOTIDIENNE = "vie_quotidienne"


class Experience(str, Enum):
    BEGINNER = "debutant"
    INTERMEDIATE = "intermediaire"
    ADVANCED = "avance"


class TrainingPhase(str, Enum):
    BASE = "BASE"
    BUILD = "BUILD"
    SPECIFIC = "SPECIFIC"
    PEAK = "PEAK"
    TAPER = "TAPER"


class SessionCategory(str, Enum):
    QUALITY = "quality"
    EASY = "easy"
    SECONDARY = "secondary"
    LONG_RUN = "long_run"


class StepType(str, Enum):
    WARMUP = "warmup"
    INTERVAL = "interval"
    RECOVERY = "recovery"
    REPEAT = "repeat"
    COOLDOWN = "cooldown"
    DISTANCE = "distance"
    MIXED_BLOCK = "mixed_block"


class PaceKey(str, Enum):
    EASY = "easy"
    RECOVERY = "recovery"
    LONG_RUN = "long_run"
    THRESHOLD = "threshold"
    VO2 = "vo2"
    ECONOMY = "economy"
    NORWEGIAN = "norwegian"


class DifficultyLevel(str, Enum):
    COMFORTABLE = "comfortable"
    BALANCED = "balanced"
    DEMANDING = "demanding"


class VolumeStrategy(str, Enum):
    GRADUAL = "gradual"
    CONSTANT = "constant"
    PROGRESSIVE = "progressive"


class SessionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class SessionFeedback:
    plan_session_id: int
    pace_rating: PaceRating
    rpe: float
    fatigue_level: FatigueLevel = FatigueLevel.NORMALE
    fatigue_duration: FatigueDuration = FatigueDuration.AUCUNE
    pain_level: PainLevel = PainLevel.AUCUNE
    pain_impact: PainImpact = PainImpact.AUCUN
    pain_location: str = ""
    pain_onset: str = ""
    pain_evolution: str = ""
    temp_cause: str = ""
    difficulty_streak: int = 0
    rules_version: str = "2026.1"
    id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: str = ""


@dataclass
class PlanAdjustment:
    plan_id: int
    reason: str
    diff_json: str
    trigger_session_id: Optional[int] = None
    status: str = "pending"  # pending | accepted_unsynced | synced | rejected
    confidence: float = 1.0
    horizon_weeks: int = 2
    old_vdot: Optional[float] = None
    new_vdot: Optional[float] = None
    rules_version: str = "2026.1"
    id: Optional[int] = None
    created_at: str = ""
    reviewed_at: Optional[str] = None


@dataclass
class Pace:
    """Pace in seconds per km."""
    s_per_km: int

    @classmethod
    def from_str(cls, s: str) -> "Pace":
        """'4'18' -> Pace(258)"""
        parts = s.strip().replace("'", " ").split()
        return cls(int(parts[0]) * 60 + int(parts[1]))

    @classmethod
    def from_s_per_100m(cls, v: float) -> "Pace":
        """Garmin s/100m -> Pace"""
        return cls(int(v * 10))

    @classmethod
    def from_float(cls, s_per_km: float) -> "Pace":
        """Float s/km -> Pace (rounded to int)."""
        return cls(int(round(s_per_km)))

    def __str__(self) -> str:
        return f"{self.s_per_km // 60}'{self.s_per_km % 60:02d}"

    @property
    def s_per_100m(self) -> float:
        return round(self.s_per_km / 10, 1)

    def scaled(self, factor: float) -> "Pace":
        return Pace(int(round(self.s_per_km * factor)))


@dataclass
class Paces:
    """Training paces for the Norwegian method."""
    ef: tuple[Pace, Pace]
    short: tuple[Pace, Pace]
    medium: tuple[Pace, Pace]
    long: tuple[Pace, Pace]

    def to_dict(self) -> dict:
        return {
            "ef": (str(self.ef[0]), str(self.ef[1])),
            "short": (str(self.short[0]), str(self.short[1])),
            "medium": (str(self.medium[0]), str(self.medium[1])),
            "long": (str(self.long[0]), str(self.long[1])),
        }


class FeasibilityStatus(str, Enum):
    REALISTIC = "realistic"
    AMBITIOUS = "ambitious"
    AGGRESSIVE = "aggressive"
    UNREALISTIC = "unrealistic"


@dataclass
class PaceTarget:
    """Pace range with physiological context. Floats in s/km internally."""
    fast: float    # lower s/km = faster
    slow: float    # higher s/km = slower
    target: float  # midpoint
    zone: str
    reference: str = ""

    @property
    def pace_min(self) -> "Pace":
        return Pace(int(round(self.fast)))

    @property
    def pace_max(self) -> "Pace":
        return Pace(int(round(self.slow)))

    def __str__(self) -> str:
        from .vdot import VDOTCalculator
        fmt = VDOTCalculator.format_pace
        return f"{fmt(self.fast)}\u2013{fmt(self.slow)}"


@dataclass
class PaceProfile:
    """Complete pace profile for a runner."""
    vdot: float
    race_paces: dict[str, PaceTarget]
    easy: PaceTarget
    recovery: PaceTarget
    long_run: PaceTarget
    threshold: PaceTarget
    vo2: PaceTarget
    economy: PaceTarget
    norwegian: dict[str, PaceTarget]

    def to_paces(self) -> "Paces":
        """Derive legacy 4-zone Paces from PaceProfile for display consumers."""
        return Paces(
            ef=(self.easy.pace_min, self.easy.pace_max),
            short=(self.norwegian["short"].pace_min, self.norwegian["short"].pace_max),
            medium=(self.norwegian["medium"].pace_min, self.norwegian["medium"].pace_max),
            long=(self.norwegian["long"].pace_min, self.norwegian["long"].pace_max),
        )


@dataclass
class FeasibilityResult:
    """Goal feasibility assessment."""
    current_vdot: float
    target_vdot: float
    vdot_gap: float
    status: FeasibilityStatus
    warning: str = ""


@dataclass
class RaceResult:
    distance: str
    time: str  # "1:32:40" or "19:30"
    date: str = ""


@dataclass
class PlanWarning:
    """Planning warning or validation finding."""
    code: str
    message: str
    severity: str = "warning"  # warning | error | info


@dataclass
class SelectionExplanation:
    """Why a workout was selected for a slot."""
    workout_id: str
    score: float
    reason: str


@dataclass
class RefreshProposal:
    """Deterministic profile refresh proposal after plan completion."""
    old_vdot: float
    proposed_vdot: float
    old_current_weekly_km: int | None
    proposed_current_weekly_km: int
    old_current_longest_run: float | None
    proposed_current_longest_run: float
    evidence: dict = field(default_factory=dict)
    confidence: str = "medium"  # high (race-derived) | medium (feedback) | low (retained)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class RunnerProfile:
    vdot: float = 49.4
    weekly_volume_km: int = 70
    mileage_tolerance_km: int = 0
    training_days: list[str] = field(default_factory=lambda: DEFAULT_DAYS.copy())
    recent_races: list[RaceResult] = field(default_factory=list)
    vo2max_trend: list[dict] = field(default_factory=list)
    paces: Optional[Paces] = None  # auto-derived if None
    pseudo: str = ""
    prenom: str = ""
    # mandatory planning fields (Phase 1)
    target_weekly_km: Optional[int] = None
    sessions_per_week: int = 4
    race_distance: Optional[str] = None
    weeks: int = 12
    target_time: Optional[str] = None
    experience: Experience = Experience.INTERMEDIATE
    # recommended planning fields (Phase 3)
    current_weekly_km: Optional[int] = None
    current_longest_run: Optional[float] = None
    long_run_day: Optional[str] = None
    preferred_days: Optional[list[str]] = None
    # configurable planning fields (Phase 3 — params)
    quality_sessions: Optional[int] = None  # 1-3; overrides static lookup when set
    difficulty_level: DifficultyLevel = DifficultyLevel.BALANCED
    volume_strategy: VolumeStrategy = VolumeStrategy.PROGRESSIVE
    current_vdot: Optional[float] = None
    vdot_history: list[dict] = field(default_factory=list)

    @property
    def effective_vdot(self) -> float:
        return self.current_vdot if self.current_vdot is not None else self.vdot

    @property
    def volume_cap(self) -> int:
        return self.weekly_volume_km + max(0, self.mileage_tolerance_km)

    @property
    def difficulty_factor(self) -> float:
        vals = {
            DifficultyLevel.COMFORTABLE: 0.90,
            DifficultyLevel.BALANCED: 1.00,
            DifficultyLevel.DEMANDING: 1.10,
        }
        return vals.get(self.difficulty_level, 1.00)


@dataclass
class PlanSettings:
    target_weekly_km: Optional[int] = None
    sessions_per_week: int = 4
    training_days: Optional[list[str]] = None
    long_run_day: Optional[str] = None
    quality_sessions: Optional[int] = None
    difficulty_level: DifficultyLevel = DifficultyLevel.BALANCED
    volume_strategy: VolumeStrategy = VolumeStrategy.PROGRESSIVE
    interval_adapted: bool = False
    target_time: Optional[str] = None

    @property
    def difficulty_factor(self) -> float:
        return {DifficultyLevel.COMFORTABLE: 0.9,
                DifficultyLevel.BALANCED: 1.0,
                DifficultyLevel.DEMANDING: 1.1}[DifficultyLevel(self.difficulty_level)]


@dataclass
class DerivedVars:
    """Derived planning variables recomputed from stored inputs."""
    volume_level: str            # low / moderate / high
    frequency_level: str         # low / moderate / high
    specificity_need: str        # low / moderate / high
    aerobic_strength: str        # developing / adequate / strong
    speed_requirement: str       # low / moderate / high
    long_run_requirement: float  # km
    recovery_requirement: str    # low / moderate / high
    training_load_tolerance: float  # 0-1 scale


@dataclass
class ProfileValidationResult:
    """Result of profile validation by ProfileEngine."""
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    derived: Optional[DerivedVars] = None


@dataclass
class WorkoutDef:
    """Canonical Norwegian Singles workout definition."""
    name: str        # NS-S01, NS-M03, etc.
    zone: Zone
    reps: int
    interval_sec: int
    pace_min: Pace    # faster end
    pace_max: Pace    # slower end
    rec_sec: int = 60
    description: str = ""

    @property
    def work_time_sec(self) -> int:
        return self.reps * self.interval_sec

    @property
    def total_interval_time(self) -> str:
        t = self.work_time_sec
        return f"{t // 60}'{t % 60:02d}" if t % 60 else f"{t // 60}'"


@dataclass
class WorkoutStep:
    """Normalized workout step for planning and export."""
    type: StepType
    duration_sec: float = 0
    distance_m: float = 0
    pace_key: str = ""          # empty = open target
    repeat_count: int = 0       # for repeat steps
    children: list["WorkoutStep"] = field(default_factory=list)
    order: int = 0

    @property
    def is_work(self) -> bool:
        return self.type in (StepType.INTERVAL, StepType.DISTANCE)

    @property
    def step_duration_sec(self) -> float:
        if self.type == StepType.REPEAT:
            return sum(c.step_duration_sec for c in self.children) * self.repeat_count
        return self.duration_sec

    @property
    def step_distance_m(self) -> float:
        if self.type == StepType.REPEAT:
            return sum(c.step_distance_m for c in self.children) * self.repeat_count
        return self.distance_m


def steps_work_duration(steps: list[WorkoutStep]) -> float:
    """Total duration of work intervals only (excludes warmup/cooldown/recovery)."""
    total = 0.0
    for s in steps:
        if s.type == StepType.REPEAT:
            for c in s.children:
                if c.is_work:
                    total += c.duration_sec * s.repeat_count
        elif s.is_work:
            total += s.duration_sec
    return total


def steps_total_duration(steps: list[WorkoutStep]) -> float:
    return sum(s.step_duration_sec for s in steps)


def steps_total_distance_m(steps: list[WorkoutStep]) -> float:
    return sum(s.step_distance_m for s in steps)


@dataclass
class Session:
    """A single training session on a given day."""
    day: str
    workout: Optional[WorkoutDef] = None
    type: str = "easy"  # easy | quality | long | rest
    structure: str = ""
    distance_km: float = 0.0
    category: Optional[SessionCategory] = None
    pace_key: Optional[PaceKey] = None
    load_score: float = 0.0
    fatigue_contribution: float = 0.0
    status: SessionStatus = SessionStatus.PENDING
    id: Optional[int] = None


@dataclass
class WeekPlan:
    week_num: int
    bloc: str
    sessions: list[Session] = field(default_factory=list)
    is_recovery: bool = False
    total_km: float = 0.0
    phase: Optional[TrainingPhase] = None
    weekly_load: float = 0.0
    fatigue_index: float = 0.0
    recovery_need: float = 0.0


@dataclass
class TrainingPlan:
    runner: RunnerProfile
    distance: Distance
    weeks: int
    paces: Paces
    name: Optional[str] = None
    week_plans: list[WeekPlan] = field(default_factory=list)
    sessions_per_week: int = 4
    start_date: Optional[date] = None  # program start (Monday of week 1)
    pace_profile: Optional[PaceProfile] = None
    feasibility_result: Optional[FeasibilityResult] = None
    warnings: list[PlanWarning] = field(default_factory=list)
    selection_trace: dict[int, list[SelectionExplanation]] = field(default_factory=dict)
    settings: PlanSettings = field(default_factory=PlanSettings)
    plan_vdot: Optional[float] = None
    mode: str = "prod"

    @property
    def total_workouts(self) -> int:
        return sum(
            1 for w in self.week_plans for s in w.sessions
            if s.workout is not None
        )

    def session_date(self, week_num: int, day: str) -> Optional[date]:
        """Compute the calendar date for a session, given start_date."""
        if self.start_date is None:
            return None
        from datetime import timedelta
        offset = (week_num - 1) * 7 + DAY_OFFSET.get(day, 0)
        return self.start_date + timedelta(days=offset)


_ZONE_TITLES = {
    Zone.SHORT: "Norwegian · intervalles courts",
    Zone.MEDIUM: "Norwegian · intervalles moyens",
    Zone.LONG: "Norwegian · intervalles longs",
}


def french_session_name(week_num: int, day: str, session: Session, plan_name: str | None = None) -> str:
    """Generate a French display name for a session in Garmin context.

    Examples:
        '[Mon plan] S01 Dim - Endurance fondamentale'
        '[Mon plan] S01 Mer - Norwegian · intervalles courts'
        '[Mon plan] S01 Dim - Sortie longue'
    """
    day_fr = DAY_FR.get(day, day)
    prefix = f"[{plan_name}] S{week_num:02d} {day_fr}" if plan_name else f"S{week_num:02d} {day_fr}"
    if session.type == "quality" and session.workout:
        title = _ZONE_TITLES.get(session.workout.zone)
        if title:
            return f"{prefix} - {title}"
    cat = session.category.value if session.category else None
    if cat == "long_run" or session.type == "long":
        return f"{prefix} - Sortie longue"
    if cat == "recovery":
        return f"{prefix} - Récupération"
    if session.type == "easy":
        return f"{prefix} - Endurance fondamentale"
    if session.type == "rest":
        return f"{prefix} - Repos"
    return f"{prefix} - {session.structure or session.type}"
