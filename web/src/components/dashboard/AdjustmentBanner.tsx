import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { plansApi } from "@douini/shared";
import { Button } from "../ui/Button";

// Shape of FeedbackResult.adjustment (backend services/feedback.py) + the feedback reason.
export interface Adjustment {
  id: number;
  reason: string;
  old_vdot?: number;
  new_vdot?: number;
  diff?: Array<{
    week: number; day: string;
    old_workout?: string; new_workout?: string;
    old_structure?: string; new_structure?: string;
    old_type?: string; new_type?: string;
    old_distance_km?: number; new_distance_km?: number;
  }>;
}

interface PaceChange { zone: string; old_pace: string; new_pace: string; delta: string }

const ZONES: Record<string, string> = { ef: "Endurance", short: "Seuil court", medium: "Seuil moyen", long: "Seuil long" };

const isVdot = (a: Adjustment) => a.old_vdot != null && a.new_vdot != null && Number(a.old_vdot) !== Number(a.new_vdot);
const norm = (s?: string) => (s ?? "").toLowerCase().replace(/×/g, "x").replace(/\s+/g, "");

function VdotSummary({ planId, adj }: { planId: number; adj: Adjustment }) {
  const { data } = useQuery({
    queryKey: ["plan", planId, "adjustment", adj.id, "pace-changes"],
    queryFn: () => plansApi.paceChanges(planId, adj.id) as unknown as Promise<PaceChange[]>,
  });
  const diff = adj.diff ?? [];
  const structures = diff.filter((d) => norm(d.old_structure || d.old_workout) !== norm(d.new_structure || d.new_workout) || d.old_type !== d.new_type);
  return (
    <div className="space-y-1 text-sm">
      <p className="font-semibold">Ajustement des allures</p>
      {data?.map((c) => <p key={c.zone}>{ZONES[c.zone] ?? c.zone} : {c.old_pace} → {c.new_pace} ({c.delta})</p>)}
      <p>VDOT : {Number(adj.old_vdot).toFixed(1)} → {Number(adj.new_vdot).toFixed(1)}</p>
      {structures.length > 0 && (
        <ul className="list-disc pl-5">
          {structures.map((d) => <li key={`${d.week}-${d.day}`}>Semaine {d.week} · {d.day} : {d.old_structure || d.old_workout || "—"} → {d.new_structure || d.new_workout || "—"}</li>)}
        </ul>
      )}
      {diff.length > 0 && <p className="text-gray-500">{diff.length} séance(s) impactée(s){structures.length ? `, dont ${structures.length} avec modification de structure` : ""}.</p>}
      <p className="text-xs text-gray-500">Allures indiquées : milieu de la plage de chaque zone.</p>
    </div>
  );
}

// Backend applies adjustments immediately (status "applied"): "Accepter" = keep + sync to Garmin, "Refuser" = revert.
export function AdjustmentBanner({ planId, adj, onDone, notify }: {
  planId: number;
  adj: Adjustment;
  onDone: () => void;
  notify: (type: "success" | "error" | "info", text: string) => void;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    try {
      notify("success", await fn());
      qc.invalidateQueries({ queryKey: ["plan"] });
      onDone();
    } catch (e) {
      notify("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
      <div>
        <p className="text-xs uppercase">Ajustement appliqué</p>
        <p>{adj.reason}</p>
        {!isVdot(adj) && <p className="text-gray-600">{adj.diff?.length ?? 0} séance(s) concernée(s)</p>}
      </div>
      {isVdot(adj) ? <VdotSummary planId={planId} adj={adj} /> : (
        <div className="space-y-2">
          {adj.diff?.map((d) => (
            <div key={`${d.week}-${d.day}`} className="rounded bg-white/60 p-2">
              <p className="text-xs uppercase text-gray-500">Semaine {d.week} · {d.day}</p>
              <p>{d.old_structure || d.old_workout || "Séance"} → {d.new_structure || d.new_workout || "Endurance facile"}</p>
              <p>Distance : {d.old_distance_km ?? 0} km → {d.new_distance_km ?? 0} km</p>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" loading={busy === "reject"} onClick={() => run("reject", async () => {
          const r = await plansApi.rejectAdjustment(planId, adj.id);
          return r.restored ? "Ajustement refusé, plan restauré." : "Ajustement refusé.";
        })}>Refuser</Button>
        <Button variant="secondary" onClick={onDone}>Plus tard</Button>
        <Button variant="secondary" loading={busy === "restore"} onClick={() => run("restore", async () => {
          const r = (await plansApi.restore(planId)) as { restored_adjustments?: number[] };
          return `${r.restored_adjustments?.length ?? 0} ajustement(s) annulé(s), plan d'origine restauré.`;
        })}>Restaurer le plan d'origine</Button>
        <Button loading={busy === "sync"} onClick={() => run("sync", async () => {
          const r = (await plansApi.syncAdjustmentGarmin(planId, adj.id)) as { synced?: number; failed?: number; reason?: string };
          return r.reason ?? `Plan adapté. Garmin : ${r.synced ?? 0} envoyée(s), ${r.failed ?? 0} échec(s).`;
        })}>Accepter et synchroniser Garmin</Button>
      </div>
    </div>
  );
}
