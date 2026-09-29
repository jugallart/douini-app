import { View, Text } from "react-native";

export function PaceTable({ paces }: { paces: Record<string, string> | undefined }) {
  if (!paces) return null;
  const entries = Object.entries(paces);
  return (
    <View style={{ borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 12 }}>
      <Text style={{ fontSize: 14, fontWeight: "600", marginBottom: 8 }}>Allures cibles</Text>
      {entries.map(([zone, pace]) => (
        <View key={zone} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4, borderTopWidth: 0.5, borderColor: "#e5e7eb" }}>
          <Text style={{ textTransform: "capitalize" }}>{zone}</Text>
          <Text>{pace}</Text>
        </View>
      ))}
    </View>
  );
}
