import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { profileApi, type RunnerProfile } from "@douini/shared";
import { useState, useEffect } from "react";

export default function Profile() {
  const qc = useQueryClient();
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const [form, setForm] = useState<Partial<RunnerProfile>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => { if (profile) setForm(profile); }, [profile]);

  const update = useMutation({
    mutationFn: (data: Partial<RunnerProfile>) => profileApi.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["profile"] }); setSaved(true); },
  });

  return (
    <ScrollView style={styles.container}>
      {saved && <Text style={styles.saved}>Profil mis à jour.</Text>}
      <Text style={styles.label}>VDOT</Text>
      <TextInput style={styles.input} value={String(form.vdot ?? "")} onChangeText={(v) => setForm({ ...form, vdot: v ? +v : null })} keyboardType="numeric" />
      <Text style={styles.label}>Volume hebdo (km)</Text>
      <TextInput style={styles.input} value={String(form.weekly_volume_km ?? "")} onChangeText={(v) => setForm({ ...form, weekly_volume_km: +v })} keyboardType="numeric" />
      <Text style={styles.label}>Séances/sem</Text>
      <TextInput style={styles.input} value={String(form.sessions_per_week ?? "")} onChangeText={(v) => setForm({ ...form, sessions_per_week: +v })} keyboardType="numeric" />
      <Text style={styles.label}>Volume cible (km)</Text>
      <TextInput style={styles.input} value={String(form.target_weekly_km ?? "")} onChangeText={(v) => setForm({ ...form, target_weekly_km: v ? +v : null })} keyboardType="numeric" />
      <Text style={styles.label}>Temps visé</Text>
      <TextInput style={styles.input} value={form.target_time ?? ""} onChangeText={(v) => setForm({ ...form, target_time: v || null })} placeholder="MM:SS" />
      <TouchableOpacity style={styles.button} onPress={() => update.mutate(form)}>
        <Text style={styles.buttonText}>Enregistrer</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  label: { fontSize: 14, fontWeight: "500", marginBottom: 4, marginTop: 12 },
  input: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, padding: 12, fontSize: 16 },
  button: { backgroundColor: "#2563eb", borderRadius: 8, padding: 14, alignItems: "center", marginTop: 24 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  saved: { color: "#16a34a", marginBottom: 12, textAlign: "center" },
});
