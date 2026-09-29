import { useState } from "react";
import { usePlans, usePlanDetail } from "../hooks/usePlan";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { WeekGrid } from "../components/plan/WeekGrid";
import { PaceTable } from "../components/plan/PaceTable";

export function Plan() {
  const { data: plans } = usePlans();
  const [selectedId, setSelectedId] = useState<number | null>(plans?.[0]?.id ?? null);
  const activeId = selectedId ?? plans?.[0]?.id ?? null;
  const { data: plan, isLoading } = usePlanDetail(activeId);

  if (!plans?.length) {
    return <AppShell><Card className="text-center text-gray-500">Aucun plan. Lancez le wizard.</Card></AppShell>;
  }

  return (
    <AppShell>
      <div className="space-y-4">
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
            <PaceTable plan={plan} />
            <WeekGrid sessions={plan.sessions ?? []} />
          </>
        )}
      </div>
    </AppShell>
  );
}
