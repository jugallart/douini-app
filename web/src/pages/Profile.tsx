import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useProfile } from "../hooks/useProfile";
import { useAuth } from "../hooks/useAuth";
import { accountApi, type RunnerProfile } from "@douini/shared";
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
  const { user, logout } = useAuth();
  const qc = useQueryClient();
  const [identity, setIdentity] = useState({ pseudo: "", prenom: "" });
  const [identitySaved, setIdentitySaved] = useState(false);
  const updateIdentity = useMutation({
    mutationFn: (data: { pseudo?: string; prenom?: string }) => accountApi.updateIdentity(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); setIdentitySaved(true); setTimeout(() => setIdentitySaved(false), 2000); },
  });

  useEffect(() => {
    if (user) setIdentity({ pseudo: user.pseudo ?? "", prenom: user.prenom ?? "" });
  }, [user]);
  const resetData = useMutation({
    mutationFn: accountApi.resetData,
    onSuccess: () => qc.invalidateQueries(),
  });
  const deleteAccount = useMutation({
    mutationFn: accountApi.delete,
    onSuccess: logout, // clears tokens + redirects to /login
  });

  useEffect(() => {
    if (profile) setForm(profile);
  }, [profile]);

  if (isLoading) return <AppShell><Card>Chargement…</Card></AppShell>;

  async function handleSaveIdentity() {
    await updateIdentity.mutateAsync(identity);
  }

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
          <h2 className="mb-4 text-lg font-semibold">Identité</h2>
          {identitySaved && <Alert type="success">Identité mise à jour.</Alert>}
          {updateIdentity.error && <Alert>{(updateIdentity.error as Error).message}</Alert>}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input label="Pseudo" value={identity.pseudo} onChange={(e) => setIdentity((p) => ({ ...p, pseudo: e.target.value }))} />
            <Input label="Prénom" value={identity.prenom} onChange={(e) => setIdentity((p) => ({ ...p, prenom: e.target.value }))} />
          </div>
          <div className="mt-4">
            <Button loading={updateIdentity.isPending} onClick={handleSaveIdentity}>Enregistrer</Button>
          </div>
        </Card>
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
        <Card>
          <h2 className="mb-4 text-lg font-semibold">Gestion des données</h2>
          {resetData.isSuccess && <Alert type="success">Données supprimées.</Alert>}
          {(resetData.error || deleteAccount.error) && <Alert>{((resetData.error || deleteAccount.error) as Error).message}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              loading={resetData.isPending}
              onClick={() => confirm("Supprimer toutes mes données ? Vos plans, séances et résultats seront supprimés. Action irréversible.") && resetData.mutate()}
            >
              Supprimer mes données
            </Button>
            <Button
              variant="danger"
              loading={deleteAccount.isPending}
              onClick={() => confirm("Supprimer mon compte ? Votre compte et toutes vos données seront supprimés. Action irréversible.") && deleteAccount.mutate()}
            >
              Supprimer mon compte
            </Button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
