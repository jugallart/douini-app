import { View, Text, SectionList, StyleSheet, TouchableOpacity, Alert } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, type PlanSession } from "@douini/shared";
import { useLocalSearchParams } from "expo-router";
import { SessionCard } from "../../../components/SessionCard";

export default function PlanDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const planId = Number(id);
  const qc = useQueryClient();
  const { data: plan } = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => plansApi.get(planId),
    enabled: !!planId,
  });

  const regenerate = useMutation({
    mutationFn: () => plansApi.regenerate(planId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["plan", planId] }); Alert.alert("Plan régénéré."); },
    onError: () => Alert.alert("Impossible de régénérer."),
  });

  const sessions = plan?.sessions ?? [];
  const weeks = [...new Set(sessions.map((s) => s.week))].sort((a, b) => a - b);
  const sections = weeks.map((w) => ({
    title: `Semaine ${w}`,
    data: sessions.filter((s) => s.week === w),
  }));

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{plan?.name ?? "Plan"}</Text>
        <TouchableOpacity style={styles.regenBtn} onPress={() => regenerate.mutate()} disabled={regenerate.isPending}>
          <Text style={styles.regenBtnText}>{regenerate.isPending ? "…" : "Régénérer"}</Text>
        </TouchableOpacity>
      </View>
      <SectionList
        sections={sections}
        keyExtractor={(_, i) => String(i)}
        renderSectionHeader={({ section: { title } }) => <Text style={styles.sectionHeader}>{title}</Text>}
        renderItem={({ item }) => <SessionCard session={item} />}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  title: { fontSize: 20, fontWeight: "bold" },
  regenBtn: { backgroundColor: "#e5e7eb", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  regenBtnText: { fontSize: 14, fontWeight: "600", color: "#374151" },
  sectionHeader: { fontSize: 14, fontWeight: "600", color: "#6b7280", marginTop: 12, marginBottom: 8 },
});
