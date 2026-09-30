export interface UserPreferences {
  metric_units: boolean;
  notifications: boolean;
  long_run_reminder: boolean;
  [key: string]: unknown;
}
