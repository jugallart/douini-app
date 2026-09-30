import { useState } from "react";
import { usePlans, usePlanDetail, usePatchSession, useAddFeedback } from "../hooks/usePlan";
import { useRegenerate } from "../hooks/useCelebration";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { WeekGrid } from "../components/plan/WeekGrid";
import { PaceTable } from "../components/plan/PaceTable";
import { FeedbackDialog } from "../components/plan/FeedbackDialog";
import type { PlanSession, FeedbackResult } from "@douini/shared";

export function Plan() {
  const { data: plans } = usePlans();
  const [selectedId, setSelectedId] = useState<number | null>(plans?.[0]?.id ?? null);
  const activeId = selectedId ?? plans?.[0]?.id ?? null;
  const { data: plan, isLoading } = usePlanDetail(activeId);
  const regenerate = useRegenerate();
  const patchSession = usePatchSession();
  const addFeedback = useAddFeedback();
  const [regenMsg, setRegenMsg] = useState("");
  const [feedbackSession, setFeedbackSession] = useState<PlanSession | null>(null);
  const [feedbackResult, setFeedbackResult] = useState<FeedbackResult | null>(null);

  if (!plans?.length) {
    return <AppShell><Card className="text-center text-gray-500">Aucun plan. Lancez le wizard.</Card></AppShell>;
  }

  async function handleRegenerate() {
    if (!activeId) return;
    try {
      await regenerate.mutateAsync({ planId: activeId });
      setRegenMsg("Plan régénéré à partir de la première semaine non commencée.");
    } catch {
      setRegenMsg("Impossible de régénérer (aucune séance en attente).");
    }
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {regenMsg && <Alert type="info">{regenMsg}</Alert>}
        {plans.length > 1 && (
          <div className="flex flex-wrap gap-2">
            {plans.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`rounded-lg border px-3 py-1.5 text-sm ${(activeId === p.id) ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300"}`}
              >
                {p.name ?? `Plan ${p.id}`}
              </button>
            ))}
          </div>
        )}
        {isLoading ? <Spinner /> : plan && (
          <>
            <div className="flex items-center justify-between">
              <PaceTable plan={plan} />
              <Button variant="secondary" onClick={handleRegenerate} loading={regenerate.isPending}>Régénérer</Button>
            </div>
            <WeekGrid sessions={plan.sessions ?? []} onSessionClick={(s) => setFeedbackSession(s)} />
          </>
        )}
      </div>

      {feedbackResult && (
        <div className="fixed bottom-4 right-4 z-50 max-w-sm">
          <Alert type={feedbackResult.action === "maintain" ? "success" : feedbackResult.action.startsWith("suspend") ? "error" : "info"}>
            <p className="font-medium">{feedbackResult.action.replace(/_/g, " ")}</p>
            <p className="mt-1 text-xs opacity-80">{feedbackResult.reason}</p>
          </Alert>
        </div>
      )}

      {feedbackSession && (
        <FeedbackDialog
          session={feedbackSession}
          onClose={() => setFeedbackSession(null)}
          onSubmit={async (fb) => {
            if (feedbackSession.id != null) {
              await patchSession.mutateAsync({ id: feedbackSession.id, status: "completed" });
              const result = await addFeedback.mutateAsync({ id: feedbackSession.id, feedback: fb });
              setFeedbackResult(result);
            }
            setFeedbackSession(null);
          }}
        />
      )}
    </AppShell>
  );
}
