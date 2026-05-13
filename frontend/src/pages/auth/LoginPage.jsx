import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth";
import { EMAIL_ERROR_MESSAGE, isValidEmail } from "../../app/validation";

const LOGIN_BACKGROUNDS = [
  { src: "/assets/branding/login-billette.png", mirrored: false },
  { src: "/assets/branding/login-componenti.png", mirrored: true },
  { src: "/assets/branding/login-stabilimento.png", mirrored: true },
  { src: "/assets/branding/login-trattamenti-termici.png", mirrored: true },
];

export default function LoginPage() {
  const { isAuthenticated, login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [backgroundIndex, setBackgroundIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setBackgroundIndex((current) => (current + 1) % LOGIN_BACKGROUNDS.length);
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);

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
    <div className="flex min-h-screen items-center justify-center bg-[#eef3f5] px-6 py-8">
      <div className="relative h-[calc(100vh-4rem)] min-h-[560px] max-h-[760px] w-full max-w-6xl overflow-hidden rounded-[2rem] rounded-br-xl border border-slate-400/70 bg-slate-900 shadow-2xl shadow-slate-300/45 ring-4 ring-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.18)]">
        {LOGIN_BACKGROUNDS.map((background, index) => (
          <img
            key={background.src}
            alt=""
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ${
              index === backgroundIndex ? "opacity-100" : "opacity-0"
            }`}
            src={background.src}
            style={{ transform: background.mirrored ? "scaleX(-1)" : undefined }}
          />
        ))}
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/18 via-transparent to-slate-950/10" />
        <div className="absolute inset-y-0 right-0 w-[52%] bg-gradient-to-l from-white/45 via-white/20 to-transparent" />

        <div className="absolute left-8 top-8 z-10 rounded-2xl rounded-br-md border border-emerald-900/30 bg-[#f7fbf5] px-5 py-3 shadow-xl shadow-slate-950/22">
          <img
            alt="Forgialluminio 3"
            className="h-28 w-auto"
            src="/assets/branding/forgialluminio-logo-transparent.png"
          />
        </div>

        <div className="relative z-10 flex h-full items-center px-6 py-8 sm:px-10 lg:px-12">
          <div className="ml-auto w-full max-w-md rounded-[1.75rem] rounded-bl-md rounded-tr-xl border border-slate-100 bg-white p-7 shadow-2xl shadow-slate-900/20 sm:p-8">
            <p className="text-sm font-semibold tracking-[0.08em] text-slate-500">CERTificazione Intelligente</p>
            <h1 className="mt-3 text-3xl font-semibold text-ink">Login</h1>
            <p className="mt-2 text-sm text-slate-600">Accedi al core platform con email e password.</p>

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

        <div className="absolute bottom-7 left-8 z-10 max-w-xl rounded-2xl rounded-tr-sm border border-white/70 bg-white/90 px-4 py-3 text-sm font-semibold text-slate-900 shadow-lg shadow-slate-900/15">
          <p className="flex flex-wrap items-center gap-2">
            <span>Software proprietario</span>
            <img
              alt="SiRe"
              className="h-5 w-auto"
              src="/assets/branding/sire-logo-black-transparent.png"
            />
            <span>– Silvano Rech</span>
          </p>
          <p className="mt-1 text-xs text-slate-700">Concesso in uso a Forgialluminio 3</p>
        </div>
      </div>
    </div>
  );
}
