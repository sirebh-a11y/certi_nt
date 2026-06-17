import { useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const emptyDraft = {
  smtp_host: "",
  smtp_port: 587,
  smtp_user: "",
  smtp_password: "",
  clear_smtp_password: false,
  smtp_tls: true,
  mail_from_email: "",
  mail_from_name: "",
  acquisition_notification_admin_email: "",
};

function buildDraft(data) {
  return {
    smtp_host: data.smtp_host || "",
    smtp_port: data.smtp_port || 587,
    smtp_user: data.smtp_user || "",
    smtp_password: "",
    clear_smtp_password: false,
    smtp_tls: Boolean(data.smtp_tls),
    mail_from_email: data.mail_from_email || "",
    mail_from_name: data.mail_from_name || "",
    acquisition_notification_admin_email: data.acquisition_notification_admin_email || "",
  };
}

export default function EmailSettingsPage() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState(emptyDraft);
  const [testEmail, setTestEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const data = await apiRequest("/email-settings", {}, token);
    setSettings(data);
    setDraft(buildDraft(data));
  }

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    apiRequest("/email-settings", {}, token)
      .then((data) => {
        if (ignore) {
          return;
        }
        setSettings(data);
        setDraft(buildDraft(data));
      })
      .catch((requestError) => {
        if (!ignore) {
          setMessage(requestError.message);
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  function updateDraft(patch) {
    setDraft((current) => ({
      ...current,
      ...patch,
    }));
  }

  async function saveSettings(event) {
    event.preventDefault();
    setMessage("");
    setSaving("settings");
    try {
      await apiRequest(
        "/email-settings",
        {
          method: "PATCH",
          body: JSON.stringify({
            ...draft,
            smtp_port: Number(draft.smtp_port),
            acquisition_notification_admin_email: draft.acquisition_notification_admin_email || null,
            smtp_password: draft.smtp_password || null,
          }),
        },
        token,
      );
      await refresh();
      setMessage("Configurazione email salvata");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  async function sendTest(event) {
    event.preventDefault();
    setMessage("");
    setSaving("test");
    try {
      const response = await apiRequest(
        "/email-settings/test",
        {
          method: "POST",
          body: JSON.stringify({ to_email: testEmail || null }),
        },
        token,
      );
      setMessage(response.message || "Email di test inviata");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  async function resetToEnv() {
    const confirmed = window.confirm(
      "Vuoi ripristinare la configurazione server? Le impostazioni email salvate nell'app verranno annullate e torneranno valide quelle del file .env.",
    );
    if (!confirmed) {
      return;
    }
    setMessage("");
    setSaving("reset");
    try {
      await apiRequest(
        "/email-settings/reset-to-env",
        {
          method: "POST",
        },
        token,
      );
      await refresh();
      setMessage("Configurazione server ripristinata");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Email</p>
          <h2 className="mt-2 text-2xl font-semibold">Configurazione email</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Parametri SMTP usati per le notifiche dell'Assistente AI. Se il DB e vuoto, la pagina legge i valori da env.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          Origine attuale:{" "}
          <span className="font-semibold text-ink">{settings?.source === "db" ? "DB" : "env"}</span>
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento configurazione email...</p> : null}
      {message ? <p className="mt-6 text-sm text-slate-600">{message}</p> : null}

      <div className="mt-8 grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={saveSettings}>
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-xl font-semibold text-slate-950">SMTP</h3>
            <p className="mt-1 text-sm text-slate-500">
              La password non viene mostrata. Lascia il campo vuoto per mantenerla.
            </p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              Server SMTP
              <input value={draft.smtp_host} onChange={(event) => updateDraft({ smtp_host: event.target.value })} />
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              Porta
              <input type="number" value={draft.smtp_port} onChange={(event) => updateDraft({ smtp_port: event.target.value })} />
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              Utente SMTP
              <input value={draft.smtp_user} onChange={(event) => updateDraft({ smtp_user: event.target.value })} />
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              Password SMTP
              <input
                autoComplete="new-password"
                placeholder={settings?.smtp_password_configured ? "Configurata: lascia vuoto per mantenerla" : "Non configurata"}
                type="password"
                value={draft.smtp_password}
                onChange={(event) => updateDraft({ smtp_password: event.target.value, clear_smtp_password: false })}
              />
            </label>
            <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
              <input
                checked={draft.smtp_tls}
                className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
                type="checkbox"
                onChange={(event) => updateDraft({ smtp_tls: event.target.checked })}
              />
              TLS / STARTTLS
            </label>
            <label className="flex items-center gap-3 rounded-xl border border-rose-100 bg-rose-50 px-3 py-3 text-sm text-rose-700">
              <input
                checked={draft.clear_smtp_password}
                className="h-4 w-4 rounded border-rose-300 p-0 text-rose-600 focus:ring-2 focus:ring-rose-200"
                type="checkbox"
                onChange={(event) => updateDraft({ clear_smtp_password: event.target.checked, smtp_password: "" })}
              />
              Cancella password salvata
            </label>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Mittente e report</h4>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm font-medium text-slate-700">
                Email mittente
                <input value={draft.mail_from_email} onChange={(event) => updateDraft({ mail_from_email: event.target.value })} />
              </label>
              <label className="grid gap-2 text-sm font-medium text-slate-700">
                Nome mittente
                <input value={draft.mail_from_name} onChange={(event) => updateDraft({ mail_from_name: event.target.value })} />
              </label>
              <label className="grid gap-2 text-sm font-medium text-slate-700 md:col-span-2">
                Email admin per report Assistente AI
                <input
                  placeholder="Opzionale"
                  value={draft.acquisition_notification_admin_email}
                  onChange={(event) => updateDraft({ acquisition_notification_admin_email: event.target.value })}
                />
              </label>
            </div>
          </div>

          <div className="mt-5 flex justify-end border-t border-slate-100 pt-4">
            <button
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              disabled={saving === "settings"}
              type="submit"
            >
              {saving === "settings" ? "Salvataggio..." : "Salva configurazione"}
            </button>
          </div>
        </form>

        <div className="grid gap-6">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
            <div className="border-b border-amber-100 pb-4">
              <h3 className="text-xl font-semibold text-slate-950">Configurazione server</h3>
              <p className="mt-1 text-sm text-amber-800">
                Annulla i valori salvati nel DB e torna ai parametri impostati da IT nel file .env.
              </p>
            </div>
            <button
              className="mt-5 w-full rounded-xl border border-amber-300 bg-white px-4 py-2.5 text-sm font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-60"
              disabled={saving === "reset"}
              type="button"
              onClick={resetToEnv}
            >
              {saving === "reset" ? "Ripristino..." : "Ripristina configurazione server"}
            </button>
          </div>

          <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={sendTest}>
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-xl font-semibold text-slate-950">Test invio</h3>
            <p className="mt-1 text-sm text-slate-500">Usa la configurazione effettiva, quindi DB se presente.</p>
          </div>
          <div className="mt-5 grid gap-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              Password:{" "}
              <span className="font-semibold text-ink">{settings?.smtp_password_configured ? "configurata" : "non configurata"}</span>
            </div>
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              Destinatario test
              <input placeholder="Vuoto = utente corrente" value={testEmail} onChange={(event) => setTestEmail(event.target.value)} />
            </label>
            <button
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={saving === "test"}
              type="submit"
            >
              {saving === "test" ? "Invio..." : "Invia email test"}
            </button>
          </div>
          </form>
        </div>
      </div>
    </section>
  );
}
