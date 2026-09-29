import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router";
import { authApi } from "@douini/shared";
import { AuthLayout } from "../../components/layout/AuthLayout";
import { Button } from "../../components/ui/Button";
import { Alert } from "../../components/ui/Alert";
import { Input } from "../../components/ui/Input";

export function VerifyEmail() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"idle" | "verifying" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  const [email, setEmail] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const token = params.get("token");
    if (token) {
      setStatus("verifying");
      authApi.verifyEmail(token).then(() => {
        setStatus("done");
        setMsg("Email vérifié ! Vous pouvez vous connecter.");
        setTimeout(() => navigate("/login"), 2000);
      }).catch(() => {
        setStatus("error");
        setMsg("Token invalide ou expiré.");
      });
    }
  }, [params, navigate]);

  async function handleResend() {
    if (!email) return;
    await authApi.resendVerification(email);
    setMsg("Email de vérification renvoyé.");
  }

  return (
    <AuthLayout title="Vérification email">
      {status === "verifying" && <Alert type="info">Vérification en cours…</Alert>}
      {status === "done" && <Alert type="success">{msg}</Alert>}
      {status === "error" && <Alert>{msg}</Alert>}
      {(status === "idle" || status === "error") && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Un email de vérification a été envoyé. Cliquez sur le lien dans l'email pour confirmer votre compte.
          </p>
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Renvoyer la vérification" />
          <Button onClick={handleResend} variant="secondary" className="w-full">Renvoyer l'email</Button>
        </div>
      )}
    </AuthLayout>
  );
}
