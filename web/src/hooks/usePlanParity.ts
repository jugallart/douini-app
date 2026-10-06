import { useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, type PlanSession } from "@douini/shared";

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
      await plansApi.delete(planId, withGarmin);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["plan"] });
    },
  });
}
