import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const CHECKBOX_CLASSNAME =
  "h-4 w-4 shrink-0 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20";

function emptyCreateForm() {
  return {
    text: "",
    is_active: true,
  };
}

export default function NotesPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [createForm, setCreateForm] = useState(emptyCreateForm());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [savingId, setSavingId] = useState(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let ignore = false;

    apiRequest("/notes", {}, token)
      .then((data) => {
        if (ignore) {
          return;
        }
        setItems(data.items);
        setDrafts(
          Object.fromEntries(
            data.items.map((item) => [
              item.id,
              {
                text: item.text,
                is_active: item.is_active,
              },
            ]),
          ),
        );
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
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

  const systemItems = useMemo(() => items.filter((item) => item.is_system), [items]);
  const customItems = useMemo(() => items.filter((item) => !item.is_system), [items]);

  function hydrate(data) {
    setItems(data.items);
    setDrafts(
      Object.fromEntries(
        data.items.map((item) => [
          item.id,
          {
            text: item.text,
            is_active: item.is_active,
          },
        ]),
      ),
    );
  }

  async function refresh() {
    const data = await apiRequest("/notes", {}, token);
    hydrate(data);
  }

  async function handleSave(noteId) {
    setError("");
    setStatusMessage("");
    setSavingId(noteId);
    try {
      await apiRequest(
        `/notes/${noteId}`,
        {
          method: "PATCH",
          body: JSON.stringify(drafts[noteId]),
        },
        token,
      );
      await refresh();
      setStatusMessage("Nota aggiornata");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    setStatusMessage("");
    setCreating(true);
    try {
      await apiRequest(
        "/notes",
        {
          method: "POST",
          body: JSON.stringify(createForm),
        },
        token,
      );
      await refresh();
      setCreateForm(emptyCreateForm());
      setStatusMessage("Nota creata");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCreating(false);
    }
  }

  function renderCard(item) {
    const draft = drafts[item.id] || { text: item.text, is_active: item.is_active };
    return (
      <form
        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        key={item.id}
        onSubmit={(event) => {
          event.preventDefault();
          handleSave(item.id);
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{item.code}</p>
            <p className="mt-1 text-sm text-slate-500">
              {item.note_key ? `${item.note_key}${item.note_value ? ` = ${item.note_value}` : ""}` : "Nota custom"}
            </p>
          </div>
          <span
            className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold ${
              item.is_system ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-700"
            }`}
          >
            {item.is_system ? "di sistema" : "custom"}
          </span>
        </div>

        <label className="mt-4 block text-sm font-medium text-slate-700">Testo nota</label>
        <textarea
          className="mt-2 min-h-[112px] w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-ink"
          rows={4}
          value={draft.text}
          onChange={(event) =>
            setDrafts((currentValue) => ({
              ...currentValue,
              [item.id]: { ...draft, text: event.target.value },
            }))
          }
        />

        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <label className="flex items-center gap-3 text-sm text-slate-600">
            <input
              checked={draft.is_active}
              className={CHECKBOX_CLASSNAME}
              onChange={(event) =>
                setDrafts((currentValue) => ({
                  ...currentValue,
                  [item.id]: { ...draft, is_active: event.target.checked },
                }))
              }
              type="checkbox"
            />
            <span>Attiva</span>
          </label>

          <button
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={savingId === item.id}
            type="submit"
          >
            {savingId === item.id ? "Salvataggio..." : "Salva"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Note</p>
        <h2 className="mt-2 text-2xl font-semibold">Catalogo note</h2>
        <p className="mt-2 text-sm text-slate-500">
          Qui gestiamo le 4 note fisse di sistema e le note custom aggiuntive. Il flusso AI esistente non viene toccato.
        </p>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
      {statusMessage ? <p className="mt-6 text-sm text-slate-600">{statusMessage}</p> : null}

      <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-1 border-b border-slate-200 pb-4">
          <h3 className="text-lg font-semibold">Note fisse</h3>
          <p className="text-sm text-slate-500">Le quattro note di sistema restano modificabili ma sempre riconoscibili come canoniche.</p>
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {systemItems.map(renderCard)}
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.05fr),minmax(0,0.95fr)]">
        <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={handleCreate}>
          <div className="mb-4 border-b border-slate-100 pb-4">
            <h3 className="text-lg font-semibold">Nuova nota custom</h3>
            <p className="mt-1 text-sm text-slate-500">Crea una nota aggiuntiva da rendere disponibile nelle sezioni note delle righe acquisition.</p>
          </div>

          <label className="block text-sm font-medium text-slate-700">Testo nota</label>
          <textarea
            className="mt-2 min-h-[132px] w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-ink"
            rows={5}
            value={createForm.text}
            onChange={(event) => setCreateForm((currentValue) => ({ ...currentValue, text: event.target.value }))}
          />
          <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <label className="flex items-center gap-3 text-sm text-slate-600">
              <input
                checked={createForm.is_active}
                className={CHECKBOX_CLASSNAME}
                onChange={(event) => setCreateForm((currentValue) => ({ ...currentValue, is_active: event.target.checked }))}
                type="checkbox"
              />
              <span>Attiva</span>
            </label>
            <button
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              disabled={creating}
              type="submit"
            >
              {creating ? "Creazione..." : "Crea nota"}
            </button>
          </div>
        </form>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-1 border-b border-slate-200 pb-4">
            <h3 className="text-lg font-semibold">Note custom esistenti</h3>
            <p className="text-sm text-slate-500">Le note custom possono essere modificate e disattivate senza toccare il catalogo fisso.</p>
          </div>
          <div className="grid gap-4">
            {customItems.map(renderCard)}
          </div>
          {!customItems.length && !loading ? <p className="mt-2 text-sm text-slate-500">Nessuna nota custom disponibile.</p> : null}
        </div>
      </div>
    </section>
  );
}
