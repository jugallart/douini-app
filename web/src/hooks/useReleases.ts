import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { releasesApi, type ReleaseNote } from "@douini/shared";

export function useUnreadReleases() {
  return useQuery<ReleaseNote[]>({
    queryKey: ["releases", "unread"],
    queryFn: releasesApi.unread,
  });
}

export function useMarkReleaseRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (version: string) => releasesApi.markRead(version),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["releases"] }),
  });
}
