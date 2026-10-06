import { useState } from "react";
import type { PlanSession } from "@douini/shared";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Alert } from "../ui/Alert";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS: Record<string, string> = { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Jeu", fri: "Ven", sat: "Sam", sun: "Dim" };
const TYPES = ["easy", "long_run", "recovery", "quality"];
const field = "rounded-lg border border-gray-300 px-2 py-1.5 text-sm";

// ponytail: free-text workout id (no catalog endpoint yet); quality = catalog id like "NS-S04".
export function WeekEditor({ week, sessions, onClose, onSave, saving }: {
  week: number;
  sessions: PlanSession[];
  onClose: () => void;
  onSave: (sessions: Partial<PlanSession>[]) => void;
  saving?: boolean;
}) {
  const [rows, setRows] = useState<Partial<PlanSession>[]>(() => sessions.map((s) => ({ ...s })));
  const meta = sessions[0] ? { bloc: sessions[0].bloc, phase: sessions[0].phase, is_recovery: sessions[0].is_recovery } : {};
  const days = rows.map((r) => r.day);
  const dupDay = days.some((d, i) => days.indexOf(d) !== i);

  const set = (i: number, patch: Partial<PlanSession>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const add = () => {
    const free = DAYS.find((d) => !days.includes(d));
    if (free) setRows([...rows, { ...meta, day: free, type: "easy", workout: "", distance_km: 8, status: "pending" }]);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <Card className="w-full max-w-2xl">
        <div onClick={(e) => e.stopPropagation()}>
          <h3 className="mb-4 text-lg font-semibold">Modifier la semaine {week}</h3>
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <select className={field} value={r.day} onChange={(e) => set(i, { day: e.target.value })}>
                  {DAYS.map((d) => <option key={d} value={d}>{DAY_LABELS[d]}</option>)}
                </select>
                <select className={field} value={r.type} onChange={(e) => set(i, { type: e.target.value })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input className={`${field} flex-1`} placeholder="Séance" value={r.workout ?? ""} onChange={(e) => set(i, { workout: e.target.value })} />
                <input className={`${field} w-20`} type="number" min={0} step={0.5} value={r.distance_km ?? 0} onChange={(e) => set(i, { distance_km: +e.target.value })} />
                <span className="text-xs text-gray-500">km</span>
                <Button variant="secondary" onClick={() => setRows(rows.filter((_, j) => j !== i))}>Repos</Button>
              </div>
            ))}
          </div>
          {dupDay && <div className="mt-3"><Alert type="error">Un seul entraînement par jour.</Alert></div>}
          <div className="mt-6 flex justify-between gap-2">
            <Button variant="secondary" onClick={add} disabled={rows.length >= DAYS.length}>+ Séance</Button>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={onClose}>Annuler</Button>
              <Button onClick={() => onSave(rows)} disabled={dupDay} loading={saving}>Enregistrer</Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
