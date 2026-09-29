export interface Session {
  id: number;
  plan_id: number;
  week: number;
  day: string;
  scheduled_date: string | null;
  type: string;
  workout_name: string | null;
  distance_km: number;
  status: string;
}

export interface SessionFeedbackPayload {
  pace_rating: string;
  rpe: number;
  fatigue_level?: string;
  fatigue_duration?: string;
  pain_level?: string;
  pain_impact?: string;
  pain_location?: string;
  pain_onset?: string;
  pain_evolution?: string;
  temp_cause?: string;
}
