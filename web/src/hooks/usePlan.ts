import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, type PlanDetail, type PlanSummary } from "@douini/shared";
import { sessionsApi, type SessionFeedbackPayload } from "@douini/shared";

export function usePlans() {
  return useQuery<PlanSummary[]>({
    queryKey: ["plans"],
    queryFn: plansApi.list,
  });
}

export function usePlanDetail(id: number | null) {
  return useQuery<PlanDetail>({
    queryKey: ["plan", id],
    queryFn: () => plansApi.get(id!),
    enabled: !!id,
  });
}

export function usePatchSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      sessionsApi.patch(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}

export function useAddFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, feedback }: { id: number; feedback: SessionFeedbackPayload }) =>
      sessionsApi.addFeedback(id, feedback),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}
