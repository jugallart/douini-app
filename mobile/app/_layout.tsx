import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { QueryClientProvider } from "@tanstack/react-query";
import * as SplashScreen from "expo-splash-screen";
import { queryClient } from "../lib/queryClient";
import { tokenStore } from "../lib/tokenStore";
import { configureClient, authApi } from "@douini/shared";

SplashScreen.preventAutoHideAsync();
configureClient(tokenStore);

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(!!tokenStore.getAccessToken());

  useEffect(() => {
    async function init() {
      if (tokenStore.getAccessToken()) {
        try {
          await authApi.me();
          setLoggedIn(true);
        } catch {
          tokenStore.clear();
          setLoggedIn(false);
        }
      }
      setReady(true);
      SplashScreen.hideAsync();
    }
    init();
  }, []);

  if (!ready) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }}>
        {!loggedIn ? (
          <Stack.Screen name="(auth)" />
        ) : (
          <>
            <Stack.Screen name="(app)" />
            <Stack.Screen name="wizard" />
          </>
        )}
      </Stack>
    </QueryClientProvider>
  );
}
