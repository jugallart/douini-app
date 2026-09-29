import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { raceResultsApi, type RaceResultPayload } from "@douini/shared";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

const DISTANCES = ["5k", "10k", "semi", "marathon"];

export function Pantheon() {
  const qc = useQueryClient();
  const { data: results } = useQuery({
    queryKey: ["race-results"],
    queryFn: raceResultsApi.list,
  });
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<RaceResultPayload>({ distance: "10k", actual_time: "", race_date: "", notes: "", location: "" });

  const addMutation = useMutation({
    mutationFn: (payload: RaceResultPayload) => raceResultsApi.add(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["race-results"] });
      setShowForm(false);
      setForm({ distance: "10k", actual_time: "", race_date: "", notes: "", location: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => raceResultsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["race-results"] }),
  });

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Palmarès</h2>
          <Button onClick={() => setShowForm(!showForm)} variant="secondary">
            {showForm ? "Annuler" : "Ajouter une course"}
          </Button>
        </div>

        {showForm && (
          <Card>
            {addMutation.isError && <Alert>{(addMutation.error as Error)?.message}</Alert>}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Distance</label>
                <select value={form.distance} onChange={(e) => setForm({ ...form, distance: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  {DISTANCES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <Input label="Temps (HH:MM:SS)" value={form.actual_time} onChange={(e) => setForm({ ...form, actual_time: e.target.value })} placeholder="00:45:00" />
              <Input label="Date" type="date" value={form.race_date ?? ""} onChange={(e) => setForm({ ...form, race_date: e.target.value })} />
              <Input label="Lieu" value={form.location ?? ""} onChange={(e) => setForm({ ...form, location: e.target.value })} />
              <Input label="Notes" value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="mt-4">
              <Button loading={addMutation.isPending} onClick={() => addMutation.mutate(form)}>Enregistrer</Button>
            </div>
          </Card>
        )}

        {results && results.length > 0 ? (
          <Card>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Distance</th>
                  <th className="pb-2">Temps</th>
                  <th className="pb-2">VDOT</th>
                  <th className="pb-2">Lieu</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100">
                    <td className="py-2">{r.race_date ?? "—"}</td>
                    <td className="py-2">{r.distance}</td>
                    <td className="py-2 font-mono">{r.actual_time}</td>
                    <td className="py-2">{r.derived_vdot?.toFixed(1) ?? "—"}</td>
                    <td className="py-2">{r.location || "—"}</td>
                    <td className="py-2 text-right">
                      <button onClick={() => deleteMutation.mutate(r.id)} className="text-xs text-red-500 hover:text-red-700">Supprimer</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : (
          <Card className="text-center text-gray-500">Aucune course enregistrée.</Card>
        )}

        {results && results.length > 1 && (
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-gray-700">Progression VDOT</h3>
            <div className="flex items-end gap-2" style={{ height: 120 }}>
              {results.map((r) => {
                const vdot = r.derived_vdot ?? 0;
                const maxVdot = Math.max(...results.map((x) => x.derived_vdot ?? 0), 1);
                const h = Math.max(4, (vdot / maxVdot) * 100);
                return (
                  <div key={r.id} className="flex flex-col items-center" style={{ width: 40 }}>
                    <div className="w-6 rounded-t bg-brand-500" style={{ height: `${h}%` }} />
                    <span className="mt-1 text-xs text-gray-500">{vdot.toFixed(0)}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
