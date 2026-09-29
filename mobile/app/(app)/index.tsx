import { useState } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Modal } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, sessionsApi, authApi, type PlanSession, type SessionFeedbackPayload } from "@douini/shared";
import { tokenStore } from "../../lib/tokenStore";
import { SessionCard } from "../../components/SessionCard";

export default function Dashboard() {
  const qc = useQueryClient();
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list });
  const activePlan = plans?.find((p) => p.status === "active") ?? plans?.[0];
  const { data: plan } = useQuery({
    queryKey: ["plan", activePlan?.id],
    queryFn: () => plansApi.get(activePlan!.id),
    enabled: !!activePlan,
  });
  const [modalSession, setModalSession] = useState<PlanSession | null>(null);

  const patchMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => sessionsApi.patch(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });

  const sessions = plan?.sessions ?? [];
  const completed = sessions.filter((s) => s.status === "completed").length;
  const upcoming = sessions.filter((s) => s.status === "pending").slice(0, 10);

  function logout() {
    tokenStore.clear();
    location?.replace?.("/") ?? (() => {})();
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{plan?.name ?? "Aucun plan"}</Text>
        <Text style={styles.stats}>{completed}/{sessions.length} séances complétées</Text>
      </View>

      {upcoming.length === 0 ? (
        <Text style={styles.empty}>Aucune séance à venir.</Text>
      ) : (
        <FlatList
          data={upcoming}
          keyExtractor={(_, i) => String(i)}
          renderItem={({ item }) => (
            <SessionCard session={item} onPress={() => setModalSession(item)} />
          )}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        />
      )}

      <Modal visible={!!modalSession} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{modalSession?.workout || modalSession?.type}</Text>
            <TouchableOpacity style={styles.doneBtn} onPress={() => {
              const id = Number(modalSession?.id);
              if (id) patchMutation.mutate({ id, status: "completed" });
              setModalSession(null);
            }}>
              <Text style={styles.doneBtnText}>Marquer comme fait</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setModalSession(null)}>
              <Text style={styles.cancelText}>Annuler</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  header: { marginBottom: 16 },
  title: { fontSize: 20, fontWeight: "bold" },
  stats: { fontSize: 14, color: "#6b7280", marginTop: 4 },
  empty: { color: "#6b7280", textAlign: "center", marginTop: 40 },
  modalOverlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.3)" },
  modalContent: { backgroundColor: "#fff", borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 24 },
  modalTitle: { fontSize: 18, fontWeight: "600", marginBottom: 16, textAlign: "center" },
  doneBtn: { backgroundColor: "#2563eb", borderRadius: 8, padding: 14, alignItems: "center", marginBottom: 12 },
  doneBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelText: { color: "#6b7280", textAlign: "center", fontSize: 14 },
});
