import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { plansApi, type Celebration } from "@douini/shared";
import { useCelebrationSeen } from "../../hooks/useCelebration";

export function CelebrationModal({ planId }: { planId: number }) {
  const { data: celebration } = useQuery<Celebration>({
    queryKey: ["plan", planId, "celebration"],
    queryFn: () => plansApi.getCelebration(planId),
    retry: false,
  });
  const markSeen = useCelebrationSeen();
  const [closed, setClosed] = useState(false);

  if (!celebration || closed) return null;
  if (celebration.seen_at) return null;

  const s = celebration.stats;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
        <div className="mb-2 text-4xl">🎉</div>
        <h2 className="mb-4 text-xl font-bold text-brand-700">Plan terminé !</h2>
        <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-gray-50 p-3">
            <p className="text-2xl font-bold text-brand-600">{s.total_km}</p>
            <p className="text-xs text-gray-500">km total</p>
          </div>
          <div className="rounded-lg bg-gray-50 p-3">
            <p className="text-2xl font-bold text-brand-600">{s.sessions_completed}</p>
            <p className="text-xs text-gray-500">séances</p>
          </div>
          <div className="rounded-lg bg-gray-50 p-3">
            <p className="text-2xl font-bold text-brand-600">{s.longest_run_km}</p>
            <p className="text-xs text-gray-500">plus longue (km)</p>
          </div>
          <div className="rounded-lg bg-gray-50 p-3">
            <p className="text-2xl font-bold text-brand-600">{s.vdot_delta != null ? (s.vdot_delta >= 0 ? `+${s.vdot_delta}` : s.vdot_delta) : "—"}</p>
            <p className="text-xs text-gray-500">VDOT delta</p>
          </div>
        </div>
        <button
          className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          onClick={async () => { await markSeen.mutateAsync(planId); setClosed(true); }}
        >
          Fermer
        </button>
      </div>
    </div>
  );
}
