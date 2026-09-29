import { useState } from "react";
import { useGarminStatus, useGarminConnect, useGarminDisconnect, useGarminPush } from "../hooks/useGarmin";
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
  const { data: plans } = usePlans();
  const activePlan = plans?.find((p) => p.status === "active") ?? plans?.[0];
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");

  async function handleConnect() {
    await connect.mutateAsync({ email, password });
    setMsg("Garmin connecté.");
  }

  async function handlePush() {
    if (!activePlan) return;
    const r = await push.mutateAsync(activePlan.id);
    setMsg(`${r.ok} séances envoyées, ${r.fail} échecs, ${r.scheduled} programmées.`);
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {msg && <Alert type="success">{msg}</Alert>}
        <Card>
          <h2 className="mb-4 text-lg font-semibold">Garmin</h2>
          {garminStatus?.connected ? (
            <div className="space-y-3">
              <Alert type="success">Compte Garmin connecté.</Alert>
              <Button onClick={handlePush} loading={push.isPending}>Envoyer le plan vers Garmin</Button>
              <Button variant="danger" onClick={() => disconnect.mutate()} loading={disconnect.isPending}>Déconnecter</Button>
            </div>
          ) : (
            <div className="space-y-3">
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
