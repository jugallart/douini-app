import { useState, useEffect } from "react";
import { useProfile } from "../hooks/useProfile";
import type { RunnerProfile } from "@douini/shared";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

const EXPERIENCES = ["debutant", "intermediaire", "avance"];
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS: Record<string, string> = { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Jeu", fri: "Ven", sat: "Sam", sun: "Dim" };
const DISTANCES = ["5k", "10k", "semi", "marathon"];

export function Profile() {
  const { profile, isLoading, updateProfile, isUpdating } = useProfile();
  const [form, setForm] = useState<Partial<RunnerProfile>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (profile) setForm(profile);
  }, [profile]);

  if (isLoading) return <AppShell><Card>Chargement…</Card></AppShell>;

  function set<K extends keyof RunnerProfile>(key: K, value: RunnerProfile[K] | null) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    await updateProfile(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function toggleDay(day: string) {
    const days = (form.training_days as string[]) ?? [];
    set("training_days", days.includes(day) ? days.filter((d) => d !== day) : [...days, day]);
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {saved && <Alert type="success">Profil mis à jour.</Alert>}
        <Card>
          <h2 className="mb-4 text-lg font-semibold">Profil du coureur</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Expérience</label>
              <select value={(form.experience as string) ?? ""} onChange={(e) => set("experience", e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                {EXPERIENCES.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Distance cible</label>
              <select value={(form.race_distance as string) ?? ""} onChange={(e) => set("race_distance", e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                <option value="">—</option>
                {DISTANCES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <Input label="VDOT" type="number" value={(form.vdot as number) ?? ""} onChange={(e) => set("vdot", e.target.value ? +e.target.value : null)} />
            <Input label="Temps visé" value={(form.target_time as string) ?? ""} onChange={(e) => set("target_time", e.target.value || null)} placeholder="MM:SS" />
            <Input label="Volume hebdo (km)" type="number" value={(form.weekly_volume_km as number) ?? 0} onChange={(e) => set("weekly_volume_km", +e.target.value)} />
            <Input label="Volume cible (km)" type="number" value={(form.target_weekly_km as number) ?? ""} onChange={(e) => set("target_weekly_km", e.target.value ? +e.target.value : null)} />
            <Input label="Séances/sem" type="number" value={(form.sessions_per_week as number) ?? 4} onChange={(e) => set("sessions_per_week", +e.target.value)} />
            <Input label="Sortie longue (km)" type="number" value={(form.current_longest_run as number) ?? ""} onChange={(e) => set("current_longest_run", e.target.value ? +e.target.value : null)} />
          </div>
          <div className="mt-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">Jours d'entraînement</label>
            <div className="flex flex-wrap gap-2">
              {DAYS.map((day) => (
                <button
                  key={day}
                  onClick={() => toggleDay(day)}
                  className={`rounded-lg border px-3 py-1.5 text-sm ${((form.training_days as string[]) ?? []).includes(day) ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300"}`}
                >
                  {DAY_LABELS[day]}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-6">
            <Button loading={isUpdating} onClick={handleSave}>Enregistrer</Button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
