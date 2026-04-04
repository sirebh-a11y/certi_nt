import { useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

export default function UserDetailPage({ currentUser, error, loading, onBack, userData }) {
  const { token, user, setUser } = useAuth();
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleKeyUpdate(event) {
    event.preventDefault();
    setSaving(true);
    setStatusMessage("");
    try {
      const data = await apiRequest(
        "/users/me/openai-key",
        {
          method: "PUT",
          body: JSON.stringify({ openai_api_key: openaiApiKey || null }),
        },
        token,
      );
      setUser({ ...user, openai_key_configured: data.configured });
      setStatusMessage("OpenAI API key aggiornata");
      setOpenaiApiKey("");
    } catch (requestError) {
      setStatusMessage(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <button className="text-sm font-medium text-accent hover:underline" onClick={onBack}>
        Torna alla lista
      </button>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      {userData ? (
        <div className="mt-6 space-y-6">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Utente</p>
            <h2 className="mt-2 text-2xl font-semibold">{userData.name}</h2>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Email</p>
              <p className="mt-2 text-sm font-medium">{userData.email}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Reparto</p>
              <p className="mt-2 text-sm font-medium">{userData.department}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Ruolo</p>
              <p className="mt-2 text-sm font-medium">{userData.role}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">OpenAI API Key</p>
              <div className="mt-2">
                <StatusBadge active={userData.openai_key_configured} />
              </div>
            </article>
          </div>

          {currentUser?.id === userData.id ? (
            <form className="rounded-2xl border border-border p-5" onSubmit={handleKeyUpdate}>
              <h3 className="text-lg font-semibold">Gestisci OpenAI API key</h3>
              <p className="mt-2 text-sm text-slate-500">
                Il valore non viene mai mostrato in chiaro dopo il salvataggio.
              </p>
              <div className="mt-4">
                <label className="mb-2 block text-sm font-medium">Nuova chiave o vuoto per rimuovere</label>
                <input value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} />
              </div>
              {statusMessage ? <p className="mt-3 text-sm text-slate-600">{statusMessage}</p> : null}
              <button
                className="mt-4 rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                disabled={saving}
                type="submit"
              >
                {saving ? "Salvataggio..." : "Salva"}
              </button>
            </form>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
