import { useState } from "react";
import { usePlans, usePlanDetail, usePatchSession, useAddFeedback } from "../hooks/usePlan";
import { useRegenerate } from "../hooks/useCelebration";
import { useGarminStatus, useGarminPush } from "../hooks/useGarmin";
import { useEditWeek, useDeleteWeek, useDeletePlan } from "../hooks/usePlanParity";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { WeekGrid } from "../components/plan/WeekGrid";
import { PaceTable } from "../components/plan/PaceTable";
import { FeedbackDialog } from "../components/plan/FeedbackDialog";
import { WeekEditor } from "../components/plan/WeekEditor";
import { DeletePlanDialog } from "../components/plan/DeletePlanDialog";
import type { PlanSession, FeedbackResult } from "@douini/shared";

export function Plan() {
  const { data: plans } = usePlans();
  const [selectedId, setSelectedId] = useState<number | null>(plans?.[0]?.id ?? null);
  const activeId = selectedId ?? plans?.[0]?.id ?? null;
  const { data: plan, isLoading } = usePlanDetail(activeId);
  const regenerate = useRegenerate();
  const patchSession = usePatchSession();
  const addFeedback = useAddFeedback();
  const [msg, setMsg] = useState<{ type: "error" | "success" | "info"; text: string } | null>(null);
  const { data: garmin } = useGarminStatus();
  const garminPush = useGarminPush();
  const editWeek = useEditWeek();
  const deleteWeek = useDeleteWeek();
  const deletePlan = useDeletePlan();
  const [editing, setEditing] = useState<{ week: number; sessions: PlanSession[] } | null>(null);
  const [resyncPending, setResyncPending] = useState(false);
  const [confirmDeletePlan, setConfirmDeletePlan] = useState(false);
  const [feedbackSession, setFeedbackSession] = useState<PlanSession | null>(null);
  const [feedbackResult, setFeedbackResult] = useState<FeedbackResult | null>(null);

  if (!plans?.length) {
    return <AppShell><Card className="text-center text-gray-500">Aucun plan. Lancez le wizard.</Card></AppShell>;
  }

  async function run(action: () => Promise<unknown>, ok: string) {
    try {
      await action();
      setMsg({ type: "success", text: ok });
    } catch (e) {
      setMsg({ type: "error", text: (e as Error).message });
    }
  }

  async function handleRegenerate(fromWeek?: number) {
    if (!activeId) return;
    if (fromWeek && !confirm(`Régénérer le plan à partir de la semaine ${fromWeek} ? Les séances terminées sont conservées.`)) return;
    await run(() => regenerate.mutateAsync({ planId: activeId, fromWeek }),
      fromWeek ? `Plan régénéré à partir de la semaine ${fromWeek}.` : "Plan régénéré à partir de la première semaine non commencée.");
  }

  async function handleDeleteWeek(week: number) {
    if (!activeId || !confirm(`Supprimer la semaine ${week} ? Cette action est irréversible.`)) return;
    await run(() => deleteWeek.mutateAsync({ planId: activeId, week }), `Semaine ${week} supprimée.`);
  }

  async function handleSaveWeek(sessions: Partial<PlanSession>[]) {
    if (!activeId || !editing) return;
    try {
      await editWeek.mutateAsync({ planId: activeId, week: editing.week, sessions });
      setMsg({ type: "success", text: "Semaine modifiée." });
      setResyncPending(!!garmin?.connected);
      setEditing(null);
    } catch (e) {
      setMsg({ type: "error", text: (e as Error).message });
    }
  }

  async function handleResync() {
    if (!activeId) return;
    setResyncPending(false);
    await run(async () => {
      const r = await garminPush.mutateAsync(activeId);
      if (r.fail) throw new Error(`Garmin : ${r.ok} envoyée(s), ${r.scheduled} planifiée(s), ${r.fail} échec(s).`);
    }, "Séances synchronisées sur Garmin.");
  }

  async function handleDeletePlan(withGarmin: boolean) {
    if (!activeId) return;
    await run(async () => {
      await deletePlan.mutateAsync({ planId: activeId, withGarmin });
      setSelectedId(null);
    }, "Plan supprimé.");
    setConfirmDeletePlan(false);
  }

  // Weeks with completed/skipped sessions are locked server-side (409 on edit/delete).
  const isLocked = (ss: PlanSession[]) => ss.some((s) => s.status === "completed" || s.status === "skipped");

  return (
    <AppShell>
      <div className="space-y-4">
        {msg && <Alert type={msg.type}>{msg.text}</Alert>}
        {resyncPending && (
          <Alert type="info">
            <div className="flex items-center justify-between gap-2">
              <span>Synchroniser Garmin ? Les séances Garmin seront remplacées par les séances mises à jour.</span>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setResyncPending(false)}>Plus tard</Button>
                <Button onClick={handleResync} loading={garminPush.isPending}>Synchroniser</Button>
              </div>
            </div>
          </Alert>
        )}
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
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => handleRegenerate()} loading={regenerate.isPending}>Régénérer</Button>
                <Button variant="danger" onClick={() => setConfirmDeletePlan(true)}>Supprimer le plan</Button>
              </div>
            </div>
            <WeekGrid
              sessions={plan.sessions ?? []}
              onSessionClick={(s) => (import.meta.env.DEV || s.status === "review") && setFeedbackSession(s)}
              weekActions={(week, ss) => {
                const locked = isLocked(ss);
                const title = locked ? "Semaine verrouillée (séances terminées ou sautées)" : undefined;
                return (
                  <>
                    <Button variant="secondary" className="px-2 py-1 text-xs" disabled={locked} title={title} onClick={() => setEditing({ week, sessions: ss })}>Modifier</Button>
                    <Button variant="secondary" className="px-2 py-1 text-xs" disabled={locked} title={title} onClick={() => handleDeleteWeek(week)}>Supprimer</Button>
                    <Button variant="secondary" className="px-2 py-1 text-xs" onClick={() => handleRegenerate(week)}>Régénérer dès ici</Button>
                  </>
                );
              }}
            />
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

      {editing && (
        <WeekEditor
          week={editing.week}
          sessions={editing.sessions}
          saving={editWeek.isPending}
          onClose={() => setEditing(null)}
          onSave={handleSaveWeek}
        />
      )}

      {confirmDeletePlan && (
        <DeletePlanDialog
          garminConnected={!!garmin?.connected}
          deleting={deletePlan.isPending}
          onClose={() => setConfirmDeletePlan(false)}
          onConfirm={handleDeletePlan}
        />
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
