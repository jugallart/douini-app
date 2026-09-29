export interface RaceResult {
  id: number;
  distance: string;
  actual_time: string;
  race_date: string | null;
  derived_vdot: number | null;
  notes: string;
  location: string;
  created_at: string | null;
}

export interface RaceResultPayload {
  distance: string;
  actual_time: string;
  race_date?: string;
  notes?: string;
  location?: string;
  plan_id?: number;
}
