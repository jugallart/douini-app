import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { garminApi, plansApi, type PlanDetail, type RefreshProposal, type ReviewQueueItem } from "@douini/shared";

export function currentWeek(plan: PlanDetail): number {
  if (!plan.start_date) return 1;
  const days = Math.floor((Date.now() - new Date(plan.start_date).getTime()) / 86400000);
  return Math.max(1, Math.min(plan.weeks ?? 1, Math.floor(days / 7) + 1));
}

export function useReviewQueue(planId: number | undefined) {
  return useQuery<ReviewQueueItem[]>({
    queryKey: ["plan", planId, "review-queue"],
    queryFn: () => plansApi.reviewQueue(planId!),
    enabled: !!planId,
  });
}

export function useAppliedAdjustments(planId: number | undefined) {
  return useQuery<Record<string, unknown>[]>({
    queryKey: ["plan", planId, "adjustments"],
    queryFn: () => plansApi.adjustments(planId!),
    enabled: !!planId,
  });
}

export function useRefreshProposal(planId: number | undefined) {
  // Backend answers 400 while the plan is not complete => treated as "no proposal".
  return useQuery<RefreshProposal>({
    queryKey: ["plan", planId, "refresh-proposal"],
    queryFn: () => plansApi.getRefreshProposal(planId!),
    enabled: !!planId,
    retry: false,
  });
}

// Legacy auto_push_check: push current week once started, and next week on Sundays.
// Backend auto-push is idempotent per week (auto_pushed_week), so repeated calls are safe.
// ponytail: runs only while the dashboard is open (like legacy ui.timer); server scheduler if it must run with the tab closed.
export function useAutoGarminPush(plan: PlanDetail | undefined, connected: boolean, onPushed: (msg: string) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!plan || !connected || !plan.start_date) return;
    const tick = async () => {
      const today = new Date();
      const start = new Date(plan.start_date!);
      if (start.getTime() > today.getTime() + 6 * 86400000) return;
      const week = currentWeek(plan);
      const targets = start <= today ? [week] : [];
      if (today.getDay() === 0 && week + 1 <= (plan.weeks ?? 0)) targets.push(week + 1);
      for (const w of targets) {
        try {
          const r = (await garminApi.autoPush(plan.id, w)) as unknown as Record<string, unknown>;
          if (r.status !== "already_pushed") onPushed(`Semaine ${w} : ${r.ok ?? 0} séance(s) envoyée(s) vers Garmin automatiquement.`);
        } catch (e) {
          onPushed(`Auto-push Garmin échoué : ${(e as Error).message}`);
        }
      }
      qc.invalidateQueries({ queryKey: ["garmin"] });
    };
    tick();
    const id = setInterval(tick, 3600_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan?.id, plan?.start_date, connected]);
}
