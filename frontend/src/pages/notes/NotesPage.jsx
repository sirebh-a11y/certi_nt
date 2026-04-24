import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

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
        className="rounded-2xl border border-border bg-white p-5"
        key={item.id}
        onSubmit={(event) => {
          event.preventDefault();
          handleSave(item.id);
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{item.code}</p>
            <p className="mt-2 text-sm text-slate-500">
              {item.note_key ? `${item.note_key}${item.note_value ? ` = ${item.note_value}` : ""}` : "Nota custom"}
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              item.is_system ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-700"
            }`}
          >
            {item.is_system ? "di sistema" : "custom"}
          </span>
        </div>

        <label className="mt-4 block text-sm font-medium">Testo nota</label>
        <textarea
          className="mt-2 min-h-28 w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-ink"
          rows={5}
          value={draft.text}
          onChange={(event) =>
            setDrafts((currentValue) => ({
              ...currentValue,
              [item.id]: { ...draft, text: event.target.value },
            }))
          }
        />

        <label className="mt-4 flex items-center gap-3 text-sm text-slate-600">
          <input
            checked={draft.is_active}
            onChange={(event) =>
              setDrafts((currentValue) => ({
                ...currentValue,
                [item.id]: { ...draft, is_active: event.target.checked },
              }))
            }
            type="checkbox"
          />
          Attiva
        </label>

        <div className="mt-4">
          <button
            className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
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
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
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

      <div className="mt-8">
        <h3 className="text-lg font-semibold">Note fisse</h3>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {systemItems.map(renderCard)}
        </div>
      </div>

      <div className="mt-8">
        <h3 className="text-lg font-semibold">Nuova nota custom</h3>
        <form className="mt-4 rounded-2xl border border-border bg-white p-5" onSubmit={handleCreate}>
          <label className="block text-sm font-medium">Testo nota</label>
          <textarea
            className="mt-2 min-h-28 w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-ink"
            rows={5}
            value={createForm.text}
            onChange={(event) => setCreateForm((currentValue) => ({ ...currentValue, text: event.target.value }))}
          />
          <label className="mt-4 flex items-center gap-3 text-sm text-slate-600">
            <input
              checked={createForm.is_active}
              onChange={(event) => setCreateForm((currentValue) => ({ ...currentValue, is_active: event.target.checked }))}
              type="checkbox"
            />
            Attiva
          </label>
          <div className="mt-4">
            <button
              className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              disabled={creating}
              type="submit"
            >
              {creating ? "Creazione..." : "Crea nota"}
            </button>
          </div>
        </form>
      </div>

      <div className="mt-8">
        <h3 className="text-lg font-semibold">Note custom esistenti</h3>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {customItems.map(renderCard)}
        </div>
        {!customItems.length && !loading ? <p className="mt-4 text-sm text-slate-500">Nessuna nota custom disponibile.</p> : null}
      </div>
    </section>
  );
}
