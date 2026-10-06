import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { preferencesApi, type UserPreferences } from "@douini/shared";

export function usePreferences() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<UserPreferences>({
    queryKey: ["preferences"],
    queryFn: preferencesApi.get,
  });

  const update = useMutation({
    mutationFn: (prefs: Partial<UserPreferences>) => preferencesApi.update(prefs),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preferences"] }),
  });

  // Backend stores interval unit as metric_units = !use_distance and rewrites plans.
  const intervalUnit = useMutation({
    mutationFn: (useDistance: boolean) => preferencesApi.setIntervalUnit(useDistance),
    onSuccess: () => qc.invalidateQueries(), // plans rewritten too
  });

  return {
    preferences: data,
    isLoading,
    updatePreferences: update.mutateAsync,
    isUpdating: update.isPending || intervalUnit.isPending,
    setIntervalUnit: intervalUnit.mutateAsync,
  };
}
