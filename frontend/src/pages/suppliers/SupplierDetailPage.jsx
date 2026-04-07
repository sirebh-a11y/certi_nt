import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { EMAIL_ERROR_MESSAGE, isValidEmail } from "../../app/validation";

const emptyForm = {
  ragione_sociale: "",
  partita_iva: "",
  codice_fiscale: "",
  indirizzo: "",
  cap: "",
  citta: "",
  provincia: "",
  nazione: "",
  email: "",
  telefono: "",
  attivo: true,
  note: "",
};

const emptyAliasForm = {
  nome_alias: "",
  fonte: "",
  attivo: true,
};

export default function SupplierDetailPage() {
  const { token } = useAuth();
  const { supplierId } = useParams();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [aliasDrafts, setAliasDrafts] = useState({});
  const [newAlias, setNewAlias] = useState(emptyAliasForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [savingSupplier, setSavingSupplier] = useState(false);
  const [savingAliasId, setSavingAliasId] = useState(null);
  const [creatingAlias, setCreatingAlias] = useState(false);

  useEffect(() => {
    let ignore = false;

    apiRequest(`/suppliers/${supplierId}`, {}, token)
      .then((data) => {
        if (!ignore) {
          hydrateSupplier(data);
        }
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
  }, [supplierId, token]);

  function hydrateSupplier(data) {
    setSupplier(data);
    setForm({
      ragione_sociale: data.ragione_sociale || "",
      partita_iva: data.partita_iva || "",
      codice_fiscale: data.codice_fiscale || "",
      indirizzo: data.indirizzo || "",
      cap: data.cap || "",
      citta: data.citta || "",
      provincia: data.provincia || "",
      nazione: data.nazione || "",
      email: data.email || "",
      telefono: data.telefono || "",
      attivo: data.attivo,
      note: data.note || "",
    });
    setAliasDrafts(
      Object.fromEntries(
        data.aliases.map((alias) => [
          alias.id,
          {
            nome_alias: alias.nome_alias,
            fonte: alias.fonte || "",
            attivo: alias.attivo,
          },
        ]),
      ),
    );
  }

  async function handleSupplierSave(event) {
    event.preventDefault();
    setError("");
    setStatusMessage("");

    if (form.email && !isValidEmail(form.email)) {
      setError(EMAIL_ERROR_MESSAGE);
      return;
    }

    setSavingSupplier(true);
    try {
      const updatedSupplier = await apiRequest(
        `/suppliers/${supplierId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...form,
            email: form.email || null,
          }),
        },
        token,
      );
      hydrateSupplier(updatedSupplier);
      setStatusMessage("Fornitore aggiornato");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingSupplier(false);
    }
  }

  async function handleAliasSave(aliasId) {
    setError("");
    setStatusMessage("");
    setSavingAliasId(aliasId);
    try {
      const updatedSupplier = await apiRequest(
        `/suppliers/aliases/${aliasId}`,
        {
          method: "PATCH",
          body: JSON.stringify(aliasDrafts[aliasId]),
        },
        token,
      );
      hydrateSupplier(updatedSupplier);
      setStatusMessage("Alias aggiornato");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingAliasId(null);
    }
  }

  async function handleAliasCreate(event) {
    event.preventDefault();
    setError("");
    setStatusMessage("");
    setCreatingAlias(true);
    try {
      const updatedSupplier = await apiRequest(
        `/suppliers/${supplierId}/aliases`,
        {
          method: "POST",
          body: JSON.stringify(newAlias),
        },
        token,
      );
      hydrateSupplier(updatedSupplier);
      setNewAlias(emptyAliasForm);
      setStatusMessage("Alias creato");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCreatingAlias(false);
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <button className="text-sm font-medium text-accent hover:underline" onClick={() => navigate("/suppliers")}>
        Torna alla lista
      </button>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      {supplier ? (
        <div className="mt-6 space-y-6">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Fornitore</p>
            <h2 className="mt-2 text-2xl font-semibold">{supplier.ragione_sociale}</h2>
            <p className="mt-2 text-sm text-slate-500">
              Il record è manuale: i PDF aiutano il mapping, ma non aggiornano automaticamente questa anagrafica.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Città</p>
              <p className="mt-2 text-sm font-medium">{supplier.citta || "-"}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Nazione</p>
              <p className="mt-2 text-sm font-medium">{supplier.nazione || "-"}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Partita IVA</p>
              <p className="mt-2 text-sm font-medium">{supplier.partita_iva || "-"}</p>
            </article>
            <article className="rounded-2xl bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Stato</p>
              <p className="mt-2 text-sm font-medium">{supplier.attivo ? "Attivo" : "Disattivo"}</p>
            </article>
          </div>

          {statusMessage ? <p className="text-sm text-slate-600">{statusMessage}</p> : null}

          <form className="grid gap-4 rounded-2xl border border-border p-5 md:grid-cols-2" onSubmit={handleSupplierSave}>
            <div className="md:col-span-2">
              <h3 className="text-lg font-semibold">Modifica fornitore</h3>
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium">Ragione sociale</label>
              <input
                required
                value={form.ragione_sociale}
                onChange={(event) => setForm({ ...form, ragione_sociale: event.target.value })}
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Partita IVA</label>
              <input value={form.partita_iva} onChange={(event) => setForm({ ...form, partita_iva: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Codice fiscale</label>
              <input
                value={form.codice_fiscale}
                onChange={(event) => setForm({ ...form, codice_fiscale: event.target.value })}
              />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium">Indirizzo</label>
              <input value={form.indirizzo} onChange={(event) => setForm({ ...form, indirizzo: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">CAP</label>
              <input value={form.cap} onChange={(event) => setForm({ ...form, cap: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Città</label>
              <input value={form.citta} onChange={(event) => setForm({ ...form, citta: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Provincia</label>
              <input value={form.provincia} onChange={(event) => setForm({ ...form, provincia: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Nazione</label>
              <input value={form.nazione} onChange={(event) => setForm({ ...form, nazione: event.target.value })} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Email</label>
              <input
                inputMode="email"
                type="text"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Telefono</label>
              <input value={form.telefono} onChange={(event) => setForm({ ...form, telefono: event.target.value })} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium">Stato</label>
              <select
                value={form.attivo ? "active" : "inactive"}
                onChange={(event) => setForm({ ...form, attivo: event.target.value === "active" })}
              >
                <option value="active">Attivo</option>
                <option value="inactive">Disattivo</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium">Note</label>
              <textarea rows={5} value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} />
            </div>
            <div className="md:col-span-2">
              <button
                className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                disabled={savingSupplier}
                type="submit"
              >
                {savingSupplier ? "Salvataggio..." : "Salva modifiche"}
              </button>
            </div>
          </form>

          <div className="rounded-2xl border border-border p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold">Alias fornitore</h3>
                <p className="mt-2 text-sm text-slate-500">
                  Gli alias supportano OCR, nomi cartella, naming storico e varianti documentali.
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-4">
              {supplier.aliases.map((alias) => {
                const draft = aliasDrafts[alias.id];
                return (
                  <form
                    className="grid gap-4 rounded-2xl border border-border p-4 md:grid-cols-[2fr_1fr_160px_auto]"
                    key={alias.id}
                    onSubmit={(event) => {
                      event.preventDefault();
                      handleAliasSave(alias.id);
                    }}
                  >
                    <div>
                      <label className="mb-2 block text-sm font-medium">Nome alias</label>
                      <input
                        required
                        value={draft?.nome_alias || ""}
                        onChange={(event) =>
                          setAliasDrafts({
                            ...aliasDrafts,
                            [alias.id]: { ...draft, nome_alias: event.target.value },
                          })
                        }
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium">Fonte</label>
                      <input
                        value={draft?.fonte || ""}
                        onChange={(event) =>
                          setAliasDrafts({
                            ...aliasDrafts,
                            [alias.id]: { ...draft, fonte: event.target.value },
                          })
                        }
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium">Stato</label>
                      <select
                        value={draft?.attivo ? "active" : "inactive"}
                        onChange={(event) =>
                          setAliasDrafts({
                            ...aliasDrafts,
                            [alias.id]: { ...draft, attivo: event.target.value === "active" },
                          })
                        }
                      >
                        <option value="active">Attivo</option>
                        <option value="inactive">Disattivo</option>
                      </select>
                    </div>
                    <div className="self-end">
                      <button
                        className="w-full rounded-xl border border-border px-4 py-3 text-sm font-semibold text-ink hover:bg-slate-50 disabled:opacity-60"
                        disabled={savingAliasId === alias.id}
                        type="submit"
                      >
                        {savingAliasId === alias.id ? "Salvataggio..." : "Salva"}
                      </button>
                    </div>
                  </form>
                );
              })}

              {!supplier.aliases.length ? <p className="text-sm text-slate-500">Nessun alias presente.</p> : null}
            </div>

            <form className="mt-6 grid gap-4 rounded-2xl bg-slate-50 p-4 md:grid-cols-[2fr_1fr_160px_auto]" onSubmit={handleAliasCreate}>
              <div>
                <label className="mb-2 block text-sm font-medium">Nuovo alias</label>
                <input
                  required
                  value={newAlias.nome_alias}
                  onChange={(event) => setNewAlias({ ...newAlias, nome_alias: event.target.value })}
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium">Fonte</label>
                <input value={newAlias.fonte} onChange={(event) => setNewAlias({ ...newAlias, fonte: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium">Stato</label>
                <select
                  value={newAlias.attivo ? "active" : "inactive"}
                  onChange={(event) => setNewAlias({ ...newAlias, attivo: event.target.value === "active" })}
                >
                  <option value="active">Attivo</option>
                  <option value="inactive">Disattivo</option>
                </select>
              </div>
              <div className="self-end">
                <button
                  className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                  disabled={creatingAlias}
                  type="submit"
                >
                  {creatingAlias ? "Creazione..." : "Aggiungi alias"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
