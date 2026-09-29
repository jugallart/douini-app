import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { router } from "expo-router";
import { profileApi, plansApi } from "@douini/shared";

const DISTANCES = ["5k", "10k", "semi", "marathon"];
const EXPERIENCES = ["debutant", "intermediaire", "avance"];

export default function Wizard() {
  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState("intermediaire");
  const [distance, setDistance] = useState("10k");
  const [targetTime, setTargetTime] = useState("");
  const [sessionsPerWeek, setSessionsPerWeek] = useState("4");
  const [currentWeeklyKm, setCurrentWeeklyKm] = useState("30");
  const [currentLongestRun, setCurrentLongestRun] = useState("10");
  const [loading, setLoading] = useState(false);

  async function handleGenerate() {
    setLoading(true);
    try {
      await profileApi.update({
        experience,
        race_distance: distance,
        target_time: targetTime || null,
        sessions_per_week: +sessionsPerWeek,
        current_weekly_km: +currentWeeklyKm,
        current_longest_run: +currentLongestRun,
      });
      await plansApi.generate({
        distance,
        target_time: targetTime || undefined,
        sessions_per_week: +sessionsPerWeek,
        current_weekly_km: +currentWeeklyKm,
        current_longest_run: +currentLongestRun,
        experience,
      });
      router.replace("/");
    } finally {
      setLoading(false);
    }
  }

  const steps = [
    {
      title: "Votre niveau",
      body: (
        <>
          {EXPERIENCES.map((exp) => (
            <TouchableOpacity key={exp} style={[styles.option, experience === exp && styles.optionActive]} onPress={() => setExperience(exp)}>
              <Text style={experience === exp ? styles.optionTextActive : styles.optionText}>{exp}</Text>
            </TouchableOpacity>
          ))}
          <Text style={styles.label}>Volume hebdo (km)</Text>
          <TextInput style={styles.input} value={currentWeeklyKm} onChangeText={setCurrentWeeklyKm} keyboardType="numeric" />
          <Text style={styles.label}>Plus longue sortie (km)</Text>
          <TextInput style={styles.input} value={currentLongestRun} onChangeText={setCurrentLongestRun} keyboardType="numeric" />
        </>
      ),
    },
    {
      title: "Objectif",
      body: (
        <>
          {DISTANCES.map((d) => (
            <TouchableOpacity key={d} style={[styles.option, distance === d && styles.optionActive]} onPress={() => setDistance(d)}>
              <Text style={distance === d ? styles.optionTextActive : styles.optionText}>{d}</Text>
            </TouchableOpacity>
          ))}
          <Text style={styles.label}>Temps visé (optionnel)</Text>
          <TextInput style={styles.input} value={targetTime} onChangeText={setTargetTime} placeholder="MM:SS" />
        </>
      ),
    },
    {
      title: "Planning",
      body: (
        <>
          <Text style={styles.label}>Séances par semaine</Text>
          <TextInput style={styles.input} value={sessionsPerWeek} onChangeText={setSessionsPerWeek} keyboardType="numeric" />
        </>
      ),
    },
  ];

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.stepTitle}>{steps[step].title} ({step + 1}/{steps.length})</Text>
      {steps[step].body}
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 24 }}>
        {step > 0 && (
          <TouchableOpacity style={styles.btnSecondary} onPress={() => setStep(step - 1)}>
            <Text style={styles.btnText}>Retour</Text>
          </TouchableOpacity>
        )}
        {step < steps.length - 1 ? (
          <TouchableOpacity style={styles.btnPrimary} onPress={() => setStep(step + 1)}>
            <Text style={styles.btnText}>Continuer</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.btnPrimary} onPress={handleGenerate} disabled={loading}>
            <Text style={styles.btnText}>{loading ? "…" : "Générer"}</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  stepTitle: { fontSize: 18, fontWeight: "bold", marginBottom: 16 },
  label: { fontSize: 14, fontWeight: "500", marginTop: 12, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, padding: 12, fontSize: 16 },
  option: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, padding: 12, marginBottom: 8 },
  optionActive: { borderColor: "#2563eb", backgroundColor: "#eff6ff" },
  optionText: { fontSize: 16, textAlign: "center" },
  optionTextActive: { fontSize: 16, textAlign: "center", color: "#2563eb", fontWeight: "600" },
  btnPrimary: { backgroundColor: "#2563eb", borderRadius: 8, padding: 14, flex: 1, marginLeft: 8, alignItems: "center" },
  btnSecondary: { backgroundColor: "#e5e7eb", borderRadius: 8, padding: 14, flex: 1, marginRight: 8, alignItems: "center" },
  btnText: { fontSize: 16, fontWeight: "600" },
});
