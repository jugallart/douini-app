import { useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi } from "@douini/shared";

export function useCelebrationSeen() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) => plansApi.markCelebrationSeen(planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}

export function useRegenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, fromWeek }: { planId: number; fromWeek?: number }) =>
      plansApi.regenerate(planId, fromWeek),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}
