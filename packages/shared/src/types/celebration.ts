export interface CelebrationStats {
  total_km: number;
  sessions_completed: number;
  sessions_skipped: number;
  longest_run_km: number;
  vdot_start: number | null;
  vdot_end: number | null;
  vdot_delta: number | null;
}

export interface Celebration {
  plan_id: number;
  seen_at: string | null;
  stats: CelebrationStats;
}
