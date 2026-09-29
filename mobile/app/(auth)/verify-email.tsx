import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from "react-native";
import { authApi } from "@douini/shared";

export default function VerifyEmail() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");

  async function handleResend() {
    if (!email) return;
    await authApi.resendVerification(email);
    setMsg("Email renvoyé.");
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Vérification email</Text>
      <Text style={styles.info}>Un email de vérification a été envoyé. Cliquez sur le lien pour confirmer votre compte.</Text>
      {msg ? <Text style={styles.success}>{msg}</Text> : null}
      <TextInput style={styles.input} placeholder="Email" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
      <TouchableOpacity style={styles.button} onPress={handleResend}>
        <Text style={styles.buttonText}>Renvoyer</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, justifyContent: "center" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 16, textAlign: "center" },
  info: { color: "#6b7280", marginBottom: 16, textAlign: "center" },
  input: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 16 },
  button: { backgroundColor: "#2563eb", borderRadius: 8, padding: 14, alignItems: "center" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  success: { color: "#16a34a", marginBottom: 12, textAlign: "center" },
});
