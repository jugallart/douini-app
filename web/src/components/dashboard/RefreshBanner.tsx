import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { plansApi, type PlanDetail, type RefreshProposal } from "@douini/shared";
import { Button } from "../ui/Button";

export function RefreshBanner({ plan, proposal, notify }: {
  plan: PlanDetail;
  proposal: RefreshProposal;
  notify: (type: "success" | "error" | "info", text: string) => void;
}) {
  const qc = useQueryClient();
  // ponytail: GET /refresh-proposal regenerates the proposal on every call, so a decline only hides it until reload.
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  if (hidden) return null;

  const act = async (accept: boolean) => {
    setBusy(true);
    try {
      if (accept) {
        await plansApi.acceptRefresh(plan.id, { distance: plan.distance, target_time: plan.goal_time, weeks: plan.weeks });
        notify("success", "Profil actualisé");
        qc.invalidateQueries({ queryKey: ["profile"] });
      } else {
        await plansApi.declineRefresh(plan.id);
        notify("info", "Proposition ignorée");
      }
      setHidden(true);
    } catch (e) {
      notify("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
      <div className="flex-1">
        <p className="text-xs uppercase">Plan terminé — Actualiser votre profil</p>
        <p>VDOT proposé : {proposal.proposed_vdot ?? "—"}</p>
        <p className="text-gray-600">Volume hebdo : {proposal.proposed_current_weekly_km ?? "—"} km</p>
      </div>
      <Button loading={busy} onClick={() => act(true)}>Actualiser</Button>
      <Button variant="secondary" disabled={busy} onClick={() => act(false)}>Plus tard</Button>
    </div>
  );
}
