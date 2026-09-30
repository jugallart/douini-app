export interface PlanSummary {
  id: number;
  name: string | null;
  distance: string | null;
  weeks: number | null;
  vdot: number | null;
  start_date: string | null;
  goal_time: string | null;
  status: string;
  created_at: string | null;
}

export interface PlanDetail extends PlanSummary {
  sessions: PlanSession[];
  settings: Record<string, unknown>;
}

export interface PlanSession {
  week: number;
  bloc: string;
  is_recovery: boolean;
  phase: string;
  day: string;
  type: string;
  workout: string;
  structure: string;
  distance_km: number;
  category: string;
  pace_key: string;
  goal: string;
  duration: string;
  pace_label: string;
  status: string;
  id: number | null;
}

export interface PlanGeneratePayload {
  plan_name?: string;
  distance: string;
  weeks?: number;
  vdot?: number;
  target_time?: string;
  sessions_per_week?: number;
  training_days?: string[];
  long_run_day?: string;
  current_weekly_km?: number;
  current_longest_run?: number;
  target_weekly_km?: number;
  experience?: string;
  quality_sessions?: number;
  difficulty_level?: string;
  volume_strategy?: string;
  start_date?: string;
  race_date?: string;
  interval_adapted?: boolean;
}

export interface RefreshProposal {
  old_vdot: number | null;
  proposed_vdot: number | null;
  old_current_weekly_km: number | null;
  proposed_current_weekly_km: number | null;
  old_current_longest_run: number | null;
  proposed_current_longest_run: number | null;
  evidence: Record<string, unknown>;
  confidence: string;
  assumptions: string[];
}

export interface RegenerateResult {
  plan_id: number;
  from_week: number;
}
