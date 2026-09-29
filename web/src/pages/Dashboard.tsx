import { useState } from "react";
import { Link } from "react-router";
import { usePlans, usePlanDetail, usePatchSession, useAddFeedback } from "../hooks/usePlan";
import { useGarminStatus } from "../hooks/useGarmin";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { ProgressBar } from "../components/dashboard/ProgressBar";
import { WeekView } from "../components/dashboard/WeekView";
import { GarminBanner } from "../components/dashboard/GarminBanner";
import { FeedbackDialog } from "../components/plan/FeedbackDialog";
import type { PlanSession } from "@douini/shared";

export function Dashboard() {
  const { data: plans } = usePlans();
  const activePlan = plans?.find((p) => p.status === "active") ?? plans?.[0];
  const { data: planDetail, isLoading } = usePlanDetail(activePlan?.id ?? null);
  const { data: garminStatus } = useGarminStatus();
  const patchSession = usePatchSession();
  const addFeedback = useAddFeedback();
  const [feedbackSession, setFeedbackSession] = useState<PlanSession | null>(null);

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

  return (
    <AppShell>
      <div className="space-y-4">
        <GarminBanner connected={garminStatus?.connected ?? false} />
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{planDetail.name ?? "Plan actif"}</h2>
            <Link to="/plan" className="text-sm text-brand-600 hover:underline">Voir le plan complet</Link>
          </div>
          <ProgressBar completed={completed} total={sessions.length} />
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-gray-700">Prochaines séances</h3>
          <WeekView sessions={sessions} onSessionClick={(s) => setFeedbackSession(s)} />
        </Card>
      </div>

      {feedbackSession && (
        <FeedbackDialog
          session={feedbackSession}
          onClose={() => setFeedbackSession(null)}
          onSubmit={async (fb) => {
            const sessionDbId = Number(feedbackSession.id);
            if (sessionDbId) {
              await patchSession.mutateAsync({ id: sessionDbId, status: "completed" });
              await addFeedback.mutateAsync({ id: sessionDbId, feedback: fb });
            }
            setFeedbackSession(null);
          }}
        />
      )}
    </AppShell>
  );
}
