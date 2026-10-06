import type { PlanSession } from "@douini/shared";

const DAY_LABELS: Record<string, string> = { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Jeu", fri: "Ven", sat: "Sam", sun: "Dim" };
const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  completed: "bg-green-100 text-green-700",
  skipped: "bg-red-100 text-red-600",
  rest: "bg-blue-50 text-blue-500",
  review: "bg-yellow-100 text-yellow-700",
};

export function SessionCard({ session, onClick, detailed }: { session: PlanSession; onClick?: () => void; detailed?: boolean }) {
  const statusClass = STATUS_COLORS[session.status] ?? STATUS_COLORS.pending;
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer rounded-lg border p-3 ${onClick ? "hover:border-brand-400 hover:shadow-sm" : ""} border-gray-200`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500">{DAY_LABELS[session.day] ?? session.day}</span>
        <span className={`rounded px-1.5 py-0.5 text-xs ${statusClass}`}>{session.status}</span>
      </div>
      <p className="mt-1 text-sm font-medium text-gray-800">{session.workout || session.type}</p>
      <div className="mt-1 flex gap-3 text-xs text-gray-500">
        <span>{session.distance_km > 0 ? `${session.distance_km} km` : ""}</span>
        <span>{session.duration}</span>
      </div>
      {session.pace_label && <span className="text-xs text-brand-600">{session.pace_label}</span>}
      {detailed && (
        <dl className="mt-2 space-y-1.5 border-t border-gray-100 pt-2 text-xs text-gray-600">
          {[
            ["Structure", session.structure],
            ["Objectif", session.goal],
            ["Allure de référence", [session.pace || session.pace_label, session.distance_km > 0 && `${session.distance_km} km`].filter(Boolean).join(" · ")],
          ].map(([k, v]) => v && (
            <div key={k}><dt className="font-semibold text-gray-700">{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
      )}
    </div>
  );
}
