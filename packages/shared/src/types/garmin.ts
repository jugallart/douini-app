export interface GarminStatus {
  connected: boolean;
}

export interface GarminPushResult {
  ok: number;
  fail: number;
  scheduled: number;
  skipped?: number;
  results: Array<{
    week: number;
    day: string;
    status: string;
    workout_id?: string;
    error?: string;
  }>;
}

export interface GarminSyncResult {
  matches: number;
  reviews: number;
  unmatched: number;
}
