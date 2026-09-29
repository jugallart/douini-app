import { useQuery } from "@tanstack/react-query";
import { authApi } from "@douini/shared";
import { tokenStore } from "../lib/tokenStore";

export function useAuth() {
  const { data: user, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    enabled: !!tokenStore.getAccessToken(),
    retry: false,
  });

  function logout() {
    const rt = tokenStore.getRefreshToken();
    if (rt) authApi.logout(rt).catch(() => {});
    tokenStore.clear();
    window.location.href = "/login";
  }

  return { user, isLoading, logout };
}
