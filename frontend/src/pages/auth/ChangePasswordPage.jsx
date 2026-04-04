import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth";

export default function ChangePasswordPage() {
  const { changePassword } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await changePassword(currentPassword, newPassword);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-shell p-6">
      <div className="mx-auto mt-10 max-w-xl rounded-3xl border border-border bg-panel p-8 shadow-xl shadow-slate-200/60">
        <h1 className="text-3xl font-semibold text-ink">Change Password</h1>
        <p className="mt-2 text-sm text-slate-500">Inserisci password attuale e nuova password.</p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium">Password attuale</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Nuova password</label>
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
          </div>
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <button
            className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Aggiornamento..." : "Aggiorna password"}
          </button>
        </form>
      </div>
    </div>
  );
}
