import type { PlanDetail } from "@douini/shared";

export function PaceTable({ plan }: { plan: PlanDetail }) {
  const paces = (plan.settings as Record<string, unknown>)?.paces;
  if (!paces || typeof paces !== "object") return null;

  const entries = Object.entries(paces);
  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-700">Allures cibles</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500">
            <th className="pb-2">Zone</th>
            <th className="pb-2">Allure</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([zone, pace]) => (
            <tr key={zone} className="border-t border-gray-100">
              <td className="py-1.5 capitalize">{zone}</td>
              <td className="py-1.5 text-gray-700">{String(pace)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
