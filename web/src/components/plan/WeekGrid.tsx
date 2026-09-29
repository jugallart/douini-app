import type { PlanSession } from "@douini/shared";
import { SessionCard } from "./SessionCard";

export function WeekGrid({ sessions, onSessionClick }: { sessions: PlanSession[]; onSessionClick?: (s: PlanSession) => void }) {
  const weeks = [...new Set(sessions.map((s) => s.week))].sort((a, b) => a - b);
  const currentWeek = weeks.length > 0 ? Math.ceil(weeks.length / 2) : 0;

  return (
    <div className="space-y-4">
      {weeks.map((week) => {
        const weekSessions = sessions.filter((s) => s.week === week);
        return (
          <div
            key={week}
            className={`rounded-xl border p-4 ${week === currentWeek ? "border-brand-400 bg-brand-50/30" : "border-gray-200"}`}
          >
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700">Semaine {week}</h3>
              {weekSessions[0] && (
                <span className="text-xs text-gray-500">
                  {weekSessions[0].bloc} {weekSessions[0].phase && `· ${weekSessions[0].phase}`}
                  {weekSessions[0].is_recovery && " · Récup"}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
              {weekSessions.map((s, i) => (
                <SessionCard key={i} session={s} onClick={onSessionClick ? () => onSessionClick(s) : undefined} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
