import { View, Text, SectionList, StyleSheet } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { plansApi, type PlanSession } from "@douini/shared";
import { useLocalSearchParams } from "expo-router";
import { SessionCard } from "../../../components/SessionCard";

export default function PlanDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const planId = Number(id);
  const { data: plan } = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => plansApi.get(planId),
    enabled: !!planId,
  });

  const sessions = plan?.sessions ?? [];
  const weeks = [...new Set(sessions.map((s) => s.week))].sort((a, b) => a - b);
  const sections = weeks.map((w) => ({
    title: `Semaine ${w}`,
    data: sessions.filter((s) => s.week === w),
  }));

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{plan?.name ?? "Plan"}</Text>
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
  title: { fontSize: 20, fontWeight: "bold", marginBottom: 16 },
  sectionHeader: { fontSize: 14, fontWeight: "600", color: "#6b7280", marginTop: 12, marginBottom: 8 },
});
