import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "@douini/shared";

export default function Notifications() {
  const qc = useQueryClient();
  const { data: notifications } = useQuery({ queryKey: ["notifications"], queryFn: notificationsApi.list });

  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = notifications?.filter((n) => !n.read_at).length ?? 0;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Notifications</Text>
        {unread > 0 && (
          <TouchableOpacity onPress={() => markAllRead.mutate()}>
            <Text style={styles.markAll}>Tout marquer lu ({unread})</Text>
          </TouchableOpacity>
        )}
      </View>
      <FlatList
        data={notifications}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.item, !item.read_at && styles.unread]}
            onPress={() => !item.read_at && markRead.mutate(item.id)}
            disabled={!!item.read_at}
          >
            <Text style={styles.msg}>{item.message}</Text>
            <Text style={styles.date}>{new Date(item.created_at).toLocaleDateString("fr-FR")}</Text>
          </TouchableOpacity>
        )}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        ListEmptyComponent={<Text style={styles.empty}>Aucune notification</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  title: { fontSize: 20, fontWeight: "bold" },
  markAll: { fontSize: 14, color: "#2563eb" },
  item: { backgroundColor: "#fff", borderRadius: 8, padding: 14, borderWidth: 1, borderColor: "#e5e7eb" },
  unread: { backgroundColor: "#eff6ff", borderColor: "#bfdbfe" },
  msg: { fontSize: 14, color: "#374151" },
  date: { fontSize: 12, color: "#9ca3af", marginTop: 4 },
  empty: { color: "#9ca3af", textAlign: "center", marginTop: 40 },
});
