import { useState } from "react";
import { useNavigate, Link } from "react-router";
import { authApi } from "@douini/shared";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Alert } from "../../components/ui/Alert";
import { tokenStore } from "../../lib/tokenStore";

export function Signup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Le mot de passe doit faire au moins 8 caractères");
      return;
    }
    setLoading(true);
    try {
      const tokens = await authApi.signup({ email, password });
      tokenStore.setTokens(tokens.access_token, tokens.refresh_token);
      navigate("/verify-email");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur d'inscription");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout title="Créer un compte">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Input label="Mot de passe" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <Button type="submit" loading={loading} className="w-full">S'inscrire</Button>
      </form>
      <div className="mt-4 text-center text-sm text-gray-500">
        <Link to="/login" className="hover:text-brand-600">Déjà un compte ? Se connecter</Link>
      </div>
    </AuthLayout>
  );
}
