import { useState, useEffect } from "react";
import { Link } from "react-router";
import { usePlans, usePlanDetail, usePatchSession, useAddFeedback } from "../hooks/usePlan";
import { useGarminStatus } from "../hooks/useGarmin";
import { useNotifications, useMarkAllNotificationsRead } from "../hooks/useNotifications";
import { currentWeek, useAutoGarminPush, useRefreshProposal, useReviewQueue, useAppliedAdjustments } from "../hooks/useDashboardParity";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { ProgressBar } from "../components/dashboard/ProgressBar";
import { WeekView } from "../components/dashboard/WeekView";
import { GarminBanner } from "../components/dashboard/GarminBanner";
import { GarminActions } from "../components/dashboard/GarminActions";
import { RefreshBanner } from "../components/dashboard/RefreshBanner";
import { AdjustmentBanner, type Adjustment } from "../components/dashboard/AdjustmentBanner";
import { FeedbackDialog } from "../components/dashboard/FeedbackDialog";
import { CelebrationModal } from "../components/celebration/CelebrationModal";
import type { ReviewQueueItem, SessionFeedbackPayload } from "@douini/shared";

type NoticeType = "success" | "error" | "info";
interface Target { id: number; status: string; title: string; queue?: ReviewQueueItem[]; index?: number }

export function Dashboard() {
  const { data: plans } = usePlans();
  const activePlan = plans?.find((p) => p.status === "active") ?? plans?.[0];
  const { data: planDetail, isLoading } = usePlanDetail(activePlan?.id ?? null);
  const { data: garminStatus } = useGarminStatus();
  const { data: reviewQueue, refetch: refetchQueue } = useReviewQueue(activePlan?.id);
  const { data: refreshProposal } = useRefreshProposal(activePlan?.id);
  const { data: appliedAdjustments } = useAppliedAdjustments(activePlan?.id);
  const { data: notifications } = useNotifications();
  const markAllRead = useMarkAllNotificationsRead();
  const patchSession = usePatchSession();
  const addFeedback = useAddFeedback();
  const [target, setTarget] = useState<Target | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [adjustment, setAdjustment] = useState<Adjustment | null>(null);
  const [notices, setNotices] = useState<{ id: number; type: NoticeType; text: string }[]>([]);

  // Reload applied adjustments on mount/page refresh (banner was lost on reload before this).
  useEffect(() => {
    if (!adjustment && appliedAdjustments && appliedAdjustments.length > 0) {
      const a = appliedAdjustments[0] as unknown as Adjustment;
      if (typeof a.id === "number") setAdjustment(a);
    }
  }, [appliedAdjustments, adjustment]);

  const notify = (type: NoticeType, text: string) => {
    const id = Date.now() + Math.random();
    setNotices((n) => [...n, { id, type, text }]);
    setTimeout(() => setNotices((n) => n.filter((x) => x.id !== id)), 6000);
  };

  const connected = garminStatus?.connected ?? false;
  useAutoGarminPush(planDetail, connected, (msg) => notify("info", msg));

  const openQueue = (queue: ReviewQueueItem[], index = 0) => {
    if (index >= queue.length) {
      if (queue.length) notify("success", "Tous les ressentis sont enregistrés.");
      setTarget(null);
      return;
    }
    const s = queue[index];
    setTarget({ id: s.id, status: "review", title: s.workout_name || "Séance", queue, index });
  };

  const submitFeedback = async (fb: SessionFeedbackPayload) => {
    if (!target) return;
    setSubmitting(true);
    try {
      // Backend refuses feedback on "review" sessions => mark completed first.
      if (target.status !== "completed") await patchSession.mutateAsync({ id: target.id, status: "completed" });
      const r = await addFeedback.mutateAsync({ id: target.id, feedback: fb });
      const adj = r.adjustment as (Partial<Adjustment> & { restored_adjustments?: number[] }) | null;
      if (adj && typeof adj.id === "number") setAdjustment({ ...adj, id: adj.id, reason: r.reason });
      else if (adj?.restored_adjustments) notify("info", `Plan restauré : ${adj.restored_adjustments.length} ajustement(s) annulé(s). ${r.reason ?? ""}`);
      else notify("success", `Ressenti enregistré. ${r.reason ?? ""}`);
      if (target.queue) openQueue(target.queue, (target.index ?? 0) + 1);
      else setTarget(null);
    } catch (e) {
      notify("error", (e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) return <AppShell><Spinner /></AppShell>;

  if (!planDetail) {
    return (
      <AppShell>
        <Card className="text-center">
          <h2 className="mb-2 text-lg font-semibold">Aucun plan actif</h2>
          <p className="mb-4 text-sm text-gray-500">Créez votre premier plan d'entraînement.</p>
          <Link to="/wizard" className="inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            Démarrer le wizard
          </Link>
        </Card>
      </AppShell>
    );
  }

  const sessions = planDetail.sessions ?? [];
  const completed = sessions.filter((s) => s.status === "completed").length;
  const queue = reviewQueue ?? [];
  const unread = (notifications ?? []).filter((n) => !n.read_at && n.plan_id === planDetail.id);

  return (
    <AppShell>
      <div className="space-y-4">
        <GarminBanner connected={connected} />

        {adjustment && (
          <AdjustmentBanner planId={planDetail.id} adj={adjustment} notify={notify} onDone={() => setAdjustment(null)} />
        )}

        {refreshProposal && <RefreshBanner plan={planDetail} proposal={refreshProposal} notify={notify} />}

        {unread.length > 0 && (
          <Alert type="success">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex-1">{unread.length} séance(s) synchronisée(s).</span>
              <Button variant="secondary" loading={markAllRead.isPending} onClick={() => markAllRead.mutate()}>OK</Button>
            </div>
          </Alert>
        )}

        {queue.length > 0 && (
          <Alert type="info">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex-1">
                <p className="text-xs uppercase">Séances réalisées à compléter</p>
                <p>{queue.length} séance(s) en attente de ressenti.</p>
              </div>
              <Button onClick={() => openQueue(queue)}>Compléter le ressenti</Button>
            </div>
          </Alert>
        )}

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{planDetail.name ?? "Plan actif"}</h2>
            <Link to="/plan" className="text-sm text-brand-600 hover:underline">Voir le plan complet</Link>
          </div>
          <ProgressBar completed={completed} total={sessions.length} />
        </Card>

        {connected && (
          <GarminActions
            planId={planDetail.id}
            weeks={planDetail.weeks ?? 1}
            defaultWeek={currentWeek(planDetail)}
            notify={notify}
            onSynced={async () => {
              const { data } = await refetchQueue();
              const q = (data ?? []).filter((s) => s.garmin_activity_id);
              if (q.length) openQueue(q);
            }}
          />
        )}

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-gray-700">Prochaines séances</h3>
          <WeekView
            sessions={sessions}
            onSessionClick={(s) => import.meta.env.DEV && s.id != null && setTarget({ id: s.id, status: s.status, title: s.workout || s.type })}
          />
        </Card>
      </div>

      {activePlan && <CelebrationModal planId={activePlan.id} />}

      {notices.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 max-w-sm space-y-2">
          {notices.map((n) => <Alert key={n.id} type={n.type}>{n.text}</Alert>)}
        </div>
      )}

      {target && (
        <FeedbackDialog
          key={target.id}
          title={target.title}
          description={target.queue ? `Ressenti ${(target.index ?? 0) + 1}/${target.queue.length} · Renseignez votre ressenti en quelques secondes.` : "Renseignez votre ressenti en quelques secondes."}
          loading={submitting}
          onClose={() => setTarget(null)}
          onSubmit={submitFeedback}
        />
      )}
    </AppShell>
  );
}
