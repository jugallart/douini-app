export interface RunnerProfile {
  vdot: number | null;
  weekly_volume_km: number;
  mileage_tolerance_km: number;
  training_days: string[];
  target_weekly_km: number | null;
  sessions_per_week: number;
  race_distance: string | null;
  weeks: number;
  target_time: string | null;
  experience: string;
  current_weekly_km: number | null;
  current_longest_run: number | null;
  long_run_day: string | null;
  preferred_days: string[];
  quality_sessions: number | null;
  difficulty_level: string;
  volume_strategy: string;
}

export interface ProfileCompleteness {
  complete: boolean;
  missing: string[];
}
