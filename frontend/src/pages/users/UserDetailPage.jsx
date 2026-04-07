import { useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

const ROLE_OPTIONS = ["user", "manager", "admin"];

const emptyForm = {
  name: "",
  department: "",
  role: "user",
  active: true,
};

export default function UserDetailPage({ currentUser, error, loading, onBack, userData }) {
  const { token } = useAuth();
  const isAdmin = currentUser?.role === "admin";
  const isManager = currentUser?.role === "manager";
  const [departments, setDepartments] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [viewUser, setViewUser] = useState(null);
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingOpenAi, setSavingOpenAi] = useState(false);
  const [runningAction, setRunningAction] = useState("");

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    let ignore = false;
    apiRequest("/departments", {}, token)
      .then((data) => {
        if (!ignore) {
          setDepartments(data.items);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setStatusMessage(requestError.message);
        }
      });

    return () => {
      ignore = true;
    };
  }, [isAdmin, token]);

  useEffect(() => {
    if (!userData) {
      setViewUser(null);
      setForm(emptyForm);
      return;
    }

    setViewUser(userData);
    setForm({
      name: userData.name,
      department: userData.department,
      role: userData.role,
      active: userData.active,
    });
  }, [userData]);

  async function handleProfileSave(event) {
    event.preventDefault();
    if (!viewUser) {
      return;
    }

    setSavingProfile(true);
    setStatusMessage("");
    try {
      const updatedUser = await apiRequest(
        `/users/${viewUser.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(form),
        },
        token,
      );
      setViewUser(updatedUser);
      setForm({
        name: updatedUser.name,
        department: updatedUser.department,
        role: updatedUser.role,
        active: updatedUser.active,
      });
      setStatusMessage("Utente aggiornato");
    } catch (requestError) {
      setStatusMessage(requestError.message);
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleOpenAiKeySave(event) {
    event.preventDefault();
    if (!viewUser) {
      return;
    }

    setSavingOpenAi(true);
    setStatusMessage("");
    try {
      const response = await apiRequest(
        `/users/${viewUser.id}/openai-key`,
        {
          method: "PUT",
          body: JSON.stringify({ openai_api_key: openaiApiKey || null }),
        },
        token,
      );
      setViewUser({ ...viewUser, openai_key_configured: response.configured });
      setOpenaiApiKey("");
      setStatusMessage("OpenAI API key aggiornata");
    } catch (requestError) {
      setStatusMessage(requestError.message);
    } finally {
      setSavingOpenAi(false);
    }
  }

  async function handleResetPassword() {
    if (!viewUser) {
      return;
    }

    setRunningAction("reset-password");
    setStatusMessage("");
    try {
      await apiRequest(
        `/users/${viewUser.id}/reset-password`,
        {
          method: "PATCH",
        },
        token,
      );
      setViewUser({ ...viewUser, force_password_change: true });
      setStatusMessage("Password reimpostata: al prossimo accesso partirà Set Password");
    } catch (requestError) {
      setStatusMessage(requestError.message);
    } finally {
      setRunningAction("");
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <button className="text-sm font-medium text-accent hover:underline" onClick={onBack}>
        Torna alla lista
      </button>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      {viewUser ? (
        <div className="mt-6 space-y-6">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Utente</p>
            <h2 className="mt-2 text-2xl font-semibold">{viewUser.name}</h2>
            <p className="mt-2 text-sm text-slate-500">
              {isAdmin ? "Area operativa admin" : null}
              {isManager ? "Consultazione sola lettura" : null}
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Email</p>
              <p className="mt-2 text-sm font-medium">{viewUser.email}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Reparto</p>
              <p className="mt-2 text-sm font-medium">{viewUser.department}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Ruolo</p>
              <p className="mt-2 text-sm font-medium">{viewUser.role}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Stato</p>
              <p className="mt-2 text-sm font-medium">{viewUser.active ? "Attivo" : "Disattivo"}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Set Password richiesto</p>
              <p className="mt-2 text-sm font-medium">{viewUser.force_password_change ? "Sì" : "No"}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">OpenAI API Key</p>
              <div className="mt-2">
                <StatusBadge active={viewUser.openai_key_configured} />
              </div>
            </article>
          </div>

          {statusMessage ? <p className="text-sm text-slate-600">{statusMessage}</p> : null}

          {isAdmin ? (
            <>
              <form className="grid gap-4 rounded-2xl border border-border p-5 md:grid-cols-2" onSubmit={handleProfileSave}>
                <div className="md:col-span-2">
                  <h3 className="text-lg font-semibold">Modifica utente</h3>
                </div>
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium">Nome</label>
                  <input
                    required
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium">Reparto</label>
                  <select
                    value={form.department}
                    onChange={(event) => setForm({ ...form, department: event.target.value })}
                  >
                    {departments.map((department) => (
                      <option key={department.id} value={department.name}>
                        {department.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium">Ruolo</label>
                  <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
                    {ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium">Stato</label>
                  <select
                    value={form.active ? "active" : "inactive"}
                    onChange={(event) => setForm({ ...form, active: event.target.value === "active" })}
                  >
                    <option value="active">Attivo</option>
                    <option value="inactive">Disattivo</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <button
                    className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    disabled={savingProfile}
                    type="submit"
                  >
                    {savingProfile ? "Salvataggio..." : "Salva modifiche"}
                  </button>
                </div>
              </form>

              <form className="rounded-2xl border border-border p-5" onSubmit={handleOpenAiKeySave}>
                <h3 className="text-lg font-semibold">Gestione OpenAI API key</h3>
                <p className="mt-2 text-sm text-slate-500">
                  Solo admin può impostare o rimuovere la chiave. Il valore non viene mai mostrato in chiaro dopo il salvataggio.
                </p>
                <div className="mt-4">
                  <label className="mb-2 block text-sm font-medium">Nuova chiave o vuoto per rimuovere</label>
                  <input value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} />
                </div>
                <button
                  className="mt-4 rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                  disabled={savingOpenAi}
                  type="submit"
                >
                  {savingOpenAi ? "Salvataggio..." : "Aggiorna OpenAI key"}
                </button>
              </form>

              <div className="rounded-2xl border border-border p-5">
                <h3 className="text-lg font-semibold">Azioni amministrative</h3>
                <p className="mt-2 text-sm text-slate-500">
                  Le azioni sensibili restano nella scheda utente e non nella lista.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-ink hover:bg-slate-50 disabled:opacity-60"
                    disabled={runningAction === "reset-password"}
                    onClick={handleResetPassword}
                    type="button"
                  >
                    {runningAction === "reset-password" ? "Reset in corso..." : "Reset password"}
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
