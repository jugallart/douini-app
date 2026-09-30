import { useEffect, useState } from "react";
import { View, Text, Modal, TouchableOpacity, StyleSheet } from "react-native";
import { Stack } from "expo-router";
import { QueryClientProvider, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as SplashScreen from "expo-splash-screen";
import { queryClient } from "../lib/queryClient";
import { tokenStore } from "../lib/tokenStore";
import { configureClient, authApi, releasesApi, type ReleaseNote } from "@douini/shared";

SplashScreen.preventAutoHideAsync();
configureClient(tokenStore);

function ReleaseNotesModal() {
  const qc = useQueryClient();
  const { data: unread } = useQuery<ReleaseNote[]>({ queryKey: ["releases", "unread"], queryFn: releasesApi.unread });
  const [dismissed, setDismissed] = useState(false);
  const markRead = useMutation({
    mutationFn: (version: string) => releasesApi.markRead(version),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["releases"] }),
  });

  if (!unread?.length || dismissed) return null;
  const latest = unread[0];

  return (
    <Modal visible transparent animationType="fade">
      <View style={styles.overlay}>
        <View style={styles.content}>
          <Text style={styles.title}>Nouveautés — v{latest.version}</Text>
          <Text style={styles.date}>{latest.date}</Text>
          <Text style={styles.subtitle}>{latest.title}</Text>
          {latest.items.map((item, i) => <Text key={i} style={styles.item}>• {item}</Text>)}
          <TouchableOpacity style={styles.button} onPress={() => { markRead.mutate(latest.version); setDismissed(true); }}>
            <Text style={styles.buttonText}>J'ai lu</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "rgba(0,0,0,0.4)" },
  content: { backgroundColor: "#fff", borderRadius: 16, padding: 28, marginHorizontal: 32, maxWidth: 400 },
  title: { fontSize: 20, fontWeight: "bold", color: "#2563eb", marginBottom: 4 },
  date: { fontSize: 12, color: "#9ca3af", marginBottom: 12 },
  subtitle: { fontSize: 16, fontWeight: "600", marginBottom: 12 },
  item: { fontSize: 14, color: "#374151", marginVertical: 3 },
  button: { backgroundColor: "#2563eb", borderRadius: 8, padding: 14, alignItems: "center", marginTop: 20 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});

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
      {loggedIn && <ReleaseNotesModal />}
    </QueryClientProvider>
  );
}
