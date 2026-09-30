import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { garminApi } from "@douini/shared";

export function useGarminStatus() {
  return useQuery({
    queryKey: ["garmin", "status"],
    queryFn: garminApi.status,
  });
}

export function useGarminConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      garminApi.connect(email, password),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["garmin"] }),
  });
}

export function useGarminPush() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) => garminApi.push(planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["garmin"] }),
  });
}

export function useGarminSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) => garminApi.sync(planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
}

export function useGarminDeleteWorkouts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) => garminApi.deleteWorkouts(planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["garmin"] }),
  });
}

export function useGarminDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => garminApi.disconnect(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["garmin"] }),
  });
}
