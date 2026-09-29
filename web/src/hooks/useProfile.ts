import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { profileApi, type RunnerProfile, type ProfileCompleteness } from "@douini/shared";

export function useProfile() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
  });

  const update = useMutation({
    mutationFn: (data: Partial<RunnerProfile>) => profileApi.update(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile"] }),
  });

  return { profile: data, isLoading, updateProfile: update.mutateAsync, isUpdating: update.isPending };
}

export function useProfileCompleteness() {
  return useQuery({
    queryKey: ["profile", "completeness"],
    queryFn: profileApi.completeness,
  });
}
