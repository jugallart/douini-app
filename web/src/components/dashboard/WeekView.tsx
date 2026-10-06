import type { PlanSession } from "@douini/shared";
import { SessionCard } from "../plan/SessionCard";

export function WeekView({ sessions, onSessionClick }: { sessions: PlanSession[]; onSessionClick?: (s: PlanSession) => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = sessions
    .filter((s) => s.status === "pending")
    .slice(0, 6);

  if (upcoming.length === 0) {
    return <p className="text-sm text-gray-500">Aucune séance à venir.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {upcoming.map((s, i) => (
        <SessionCard key={i} detailed session={s} onClick={onSessionClick ? () => onSessionClick(s) : undefined} />
      ))}
    </div>
  );
}
