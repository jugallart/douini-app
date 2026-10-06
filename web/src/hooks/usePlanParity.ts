import { useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, garminApi, type PlanSession } from "@douini/shared";

export function useEditWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, week, sessions }: { planId: number; week: number; sessions: Partial<PlanSession>[] }) =>
      plansApi.editWeek(planId, week, sessions),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}

export function useDeleteWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, week }: { planId: number; week: number }) => plansApi.deleteWeek(planId, week),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}

export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ planId, withGarmin }: { planId: number; withGarmin: boolean }) => {
      // Garmin first: the backend needs the plan's sessions to find workout ids.
      const garmin = withGarmin ? await garminApi.deleteWorkouts(planId) : null;
      await plansApi.delete(planId);
      return garmin;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["plan"] });
    },
  });
}
