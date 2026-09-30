export interface Notification {
  id: number;
  plan_id: number | null;
  session_id: number | null;
  message: string;
  type: string;
  read_at: string | null;
  created_at: string;
}
