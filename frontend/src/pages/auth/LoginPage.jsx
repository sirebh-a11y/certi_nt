import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth";
import { EMAIL_ERROR_MESSAGE, isValidEmail } from "../../app/validation";

export default function LoginPage() {
  const { isAuthenticated, login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to={user?.force_password_change ? "/change-password" : "/dashboard"} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    if (!isValidEmail(email)) {
      setError(EMAIL_ERROR_MESSAGE);
      return;
    }

    setSubmitting(true);

    try {
      const response = await login(email, password);
      if (response.requires_set_password) {
        navigate("/set-password", { replace: true });
        return;
      }
      navigate(response.requires_password_change ? "/change-password" : "/dashboard", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,#dff6f3_0%,#f5f7fb_55%,#edf2f7_100%)] p-6">
      <div className="w-full max-w-md rounded-3xl border border-white/80 bg-white/90 p-8 shadow-2xl shadow-slate-200/70 backdrop-blur">
        <p className="text-sm uppercase tracking-[0.35em] text-slate-500">CERTI_nt</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Login</h1>
        <p className="mt-2 text-sm text-slate-500">Accedi al core platform con email e password.</p>

        <form className="mt-8 space-y-4" noValidate onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-ink">Email</label>
            <input
              type="text"
              inputMode="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-ink">Password</label>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            <p className="mt-2 text-xs text-slate-500">
              Se l&apos;utente non ha ancora una password, il sistema avvierà il flusso Set Password.
            </p>
          </div>
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <button
            className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Accesso in corso..." : "Accedi"}
          </button>
        </form>
      </div>
    </div>
  );
}
