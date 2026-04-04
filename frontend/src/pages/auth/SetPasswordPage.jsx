import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth";

export default function SetPasswordPage() {
  const { isAuthenticated, setPassword, setupToken } = useAuth();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  if (!setupToken) {
    return <Navigate to="/login" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Le password non coincidono");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await setPassword(newPassword);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-shell p-6">
      <div className="w-full max-w-md rounded-3xl border border-border bg-panel p-8 shadow-xl shadow-slate-200/60">
        <h1 className="text-3xl font-semibold text-ink">Set Password</h1>
        <p className="mt-2 text-sm text-slate-500">Crea la password per completare il primo accesso.</p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium">Nuova password</label>
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Conferma password</label>
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
          </div>
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <button
            className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Salvataggio..." : "Salva password"}
          </button>
        </form>
      </div>
    </div>
  );
}
