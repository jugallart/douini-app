import { useState } from "react";
import { Link } from "react-router";
import type { UserPreferences } from "@douini/shared";
import { useGarminStatus, useGarminConnect, useGarminDisconnect, useGarminPush, useGarminSync, useGarminDeleteWorkouts } from "../hooks/useGarmin";
import { usePreferences } from "../hooks/usePreferences";
import { usePlans } from "../hooks/usePlan";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

export function Settings() {
  const { data: garminStatus } = useGarminStatus();
  const connect = useGarminConnect();
  const disconnect = useGarminDisconnect();
  const push = useGarminPush();
  const sync = useGarminSync();
  const deleteWorkouts = useGarminDeleteWorkouts();
  const { data: plans } = usePlans();
  const activePlan = plans?.find((p) => p.status === "active") ?? plans?.[0];
  const { preferences, updatePreferences, isUpdating, setIntervalUnit } = usePreferences();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [prefsMsg, setPrefsMsg] = useState("");

  async function handleConnect() {
    try {
      await connect.mutateAsync({ email, password });
      setMsg("Garmin connecté.");
    } catch {
      // shown via connect.error
    }
  }

  async function handlePush() {
    if (!activePlan) return;
    const r = await push.mutateAsync(activePlan.id);
    setMsg(`${r.ok} séances envoyées, ${r.fail} échecs, ${r.scheduled} programmées, ${r.skipped ?? 0} ignorées.`);
  }

  async function handleSync() {
    if (!activePlan) return;
    const r = await sync.mutateAsync(activePlan.id);
    setMsg(`Sync Garmin: ${r.matches} matchs exacts, ${r.reviews} à valider, ${r.unmatched} non trouvées.`);
  }

  async function handleDeleteWorkouts() {
    if (!activePlan) return;
    const r = await deleteWorkouts.mutateAsync(activePlan.id);
    setMsg(`${r.deleted} workouts supprimés, ${r.failed} échecs.`);
  }

  async function savePref(prefs: Partial<UserPreferences>) {
    await updatePreferences(prefs);
    setPrefsMsg("Préférences enregistrées.");
  }

  async function handleIntervalUnit(useDistance: boolean) {
    await setIntervalUnit(useDistance);
    setPrefsMsg("Unité des intervalles mise à jour, plan recalculé.");
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {msg && <Alert type="success">{msg}</Alert>}
        <Card>
          <h2 className="mb-4 text-lg font-semibold">Préférences</h2>
          {prefsMsg && <Alert type="success">{prefsMsg}</Alert>}
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" disabled={isUpdating} checked={!(preferences?.metric_units ?? true)} onChange={(e) => handleIntervalUnit(e.target.checked)} />
              Intervalles en distance
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" disabled={isUpdating} checked={preferences?.notifications ?? true} onChange={(e) => savePref({ notifications: e.target.checked })} />
              Notifications
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" disabled={isUpdating} checked={preferences?.long_run_reminder ?? false} onChange={(e) => savePref({ long_run_reminder: e.target.checked })} />
              Rappel sortie longue
            </label>
          </div>
          <Link to="/releases" className="mt-4 inline-block text-sm text-brand-600 hover:underline">Voir les nouveautés</Link>
        </Card>
        <Card>
          <h2 className="mb-4 text-lg font-semibold">Garmin</h2>
          {garminStatus?.connected ? (
            <div className="space-y-3">
              <Alert type="success">Compte Garmin connecté.</Alert>
              <Button onClick={handlePush} loading={push.isPending}>Envoyer le plan vers Garmin</Button>
              <Button onClick={handleSync} loading={sync.isPending}>Sync depuis Garmin</Button>
              <Button variant="danger" onClick={handleDeleteWorkouts} loading={deleteWorkouts.isPending}>Supprimer workouts Garmin</Button>
              <Button variant="danger" onClick={() => disconnect.mutate()} loading={disconnect.isPending}>Déconnecter</Button>
            </div>
          ) : (
            <div className="space-y-3">
              {connect.error && <Alert>Erreur : {connect.error.message}</Alert>}
              <Input label="Email Garmin" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              <Input label="Mot de passe Garmin" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <Button onClick={handleConnect} loading={connect.isPending}>Connecter</Button>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
