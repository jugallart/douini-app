import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { plansApi } from "@douini/shared";
import { router } from "expo-router";

export default function PlanList() {
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list });

  if (!plans?.length) {
    return <View style={styles.container}><Text style={styles.empty}>Aucun plan.</Text></View>;
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={plans}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card} onPress={() => router.push(`/plan/${item.id}`)}>
            <Text style={styles.cardTitle}>{item.name ?? `Plan ${item.id}`}</Text>
            <Text style={styles.cardSub}>{item.distance} · {item.weeks} sem · VDOT {item.vdot}</Text>
          </TouchableOpacity>
        )}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  empty: { color: "#6b7280", textAlign: "center", marginTop: 40 },
  card: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 12 },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSub: { fontSize: 14, color: "#6b7280", marginTop: 4 },
});
