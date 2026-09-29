export interface Stats {
  total_distance_km: number;
  total_activities: number;
  total_running_time_min: number;
  longest_run_km: number;
  completed_count: number;
  planned_count: number;
  skipped_count: number;
  regularity_score: number;
  period_stats: Record<string, unknown>;
  distance_stats: Record<string, unknown>;
  [key: string]: unknown;
}
