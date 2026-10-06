import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { garminApi } from "@douini/shared";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

export function GarminActions({ planId, weeks, defaultWeek, notify, onSynced }: {
  planId: number;
  weeks: number;
  defaultWeek: number;
  notify: (type: "success" | "error" | "info", text: string) => void;
  onSynced: () => void;
}) {
  const qc = useQueryClient();
  const [week, setWeek] = useState(defaultWeek);
  const [busy, setBusy] = useState<"export" | "sync" | null>(null);

  const exportWeek = async () => {
    setBusy("export");
    try {
      let r = (await garminApi.autoPush(planId, week)) as unknown as Record<string, number | string>;
      if (r.status === "already_pushed") r = (await garminApi.autoPush(planId, week, true)) as unknown as Record<string, number | string>;
      if (r.status === "already_pushed") notify("info", `Semaine ${week} déjà envoyée (dernière semaine envoyée : ${r.week}).`);
      else notify(r.fail ? "info" : "success", `Semaine ${week} : ${r.ok} séance(s) envoyée(s), ${r.scheduled} planifiée(s), ${r.fail} échec(s).`);
    } catch (e) {
      notify("error", `Erreur Garmin : ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const sync = async () => {
    setBusy("sync");
    try {
      const r = await garminApi.sync(planId);
      if (r.matches) notify("success", `${r.matches} activité(s) associée(s). Complétez vos ressentis pour valider les séances.`);
      if (r.reviews) notify("info", `${r.reviews} correspondance(s) ambiguë(s) : aucune validation automatique pour ces séances.`);
      if (!r.matches && !r.reviews) notify("info", "Aucune activité correspondante trouvée.");
      await qc.invalidateQueries({ queryKey: ["plan"] });
      onSynced();
    } catch (e) {
      notify("error", `Erreur de synchronisation : ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">Montre connectée</h3>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm text-gray-700">
          Semaine{" "}
          <input type="number" min={1} max={weeks} value={week} onChange={(e) => setWeek(Math.max(1, Math.min(weeks, +e.target.value || 1)))} className="w-16 rounded-lg border border-gray-300 px-2 py-1 text-sm" />
        </label>
        <Button loading={busy === "export"} onClick={exportWeek}>Exporter la semaine</Button>
        <Button variant="secondary" loading={busy === "sync"} onClick={sync}>Synchroniser</Button>
      </div>
    </Card>
  );
}
