import { View, Text, FlatList } from "react-native";
import { SessionCard } from "./SessionCard";
import type { PlanSession } from "@douini/shared";

export function WeekList({ sessions, onSessionPress }: {
  sessions: PlanSession[];
  onSessionPress?: (s: PlanSession) => void;
}) {
  const upcoming = sessions.filter((s) => s.status === "pending").slice(0, 10);
  return (
    <FlatList
      data={upcoming}
      keyExtractor={(_, i) => String(i)}
      renderItem={({ item }) => <SessionCard session={item} onPress={onSessionPress ? () => onSessionPress(item) : undefined} />}
      ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
      ListEmptyComponent={<Text style={{ color: "#6b7280", textAlign: "center" }}>Aucune séance à venir.</Text>}
    />
  );
}
