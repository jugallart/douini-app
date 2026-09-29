import { View, Text, TouchableOpacity } from "react-native";

const STATUS_COLORS: Record<string, string> = {
  pending: "#6b7280",
  completed: "#16a34a",
  skipped: "#dc2626",
  rest: "#3b82f6",
  review: "#ca8a04",
};

export function SessionCard({ session, onPress }: {
  session: { day: string; workout?: string | null; type: string; distance_km: number; status: string; duration?: string; pace_label?: string };
  onPress?: () => void;
}) {
  return (
    <TouchableOpacity onPress={onPress} style={{ borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 12 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 12, color: "#6b7280" }}>{session.day}</Text>
        <Text style={{ fontSize: 12, color: STATUS_COLORS[session.status] ?? "#6b7280" }}>{session.status}</Text>
      </View>
      <Text style={{ fontSize: 14, fontWeight: "500", marginTop: 4 }}>{session.workout || session.type}</Text>
      <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
        {session.distance_km > 0 && <Text style={{ fontSize: 12, color: "#6b7280" }}>{session.distance_km} km</Text>}
        {session.duration && <Text style={{ fontSize: 12, color: "#6b7280" }}>{session.duration}</Text>}
      </View>
    </TouchableOpacity>
  );
}
