import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

function emptyForm() {
  return {
    codice: "",
    fornitore_id: "",
    esolver_cod_clifor: "",
    esolver_ragione_sociale: "",
    etichetta_manuale: "",
    target: "manual:",
  };
}

function toDraft(item) {
  const draft = {
    codice: item.codice || "",
    fornitore_id: item.fornitore_id ? String(item.fornitore_id) : "",
    esolver_cod_clifor: item.esolver_cod_clifor || "",
    esolver_ragione_sociale: item.esolver_ragione_sociale || "",
    etichetta_manuale: item.etichetta_manuale || "",
  };
  return { ...draft, target: targetFromDraft(draft) };
}

function payloadFromDraft(draft) {
  const [targetType, targetValue = ""] = String(draft.target || "manual:").split(":", 2);
  return {
    codice: draft.codice.trim(),
    fornitore_id: targetType === "local" && targetValue ? Number(targetValue) : null,
    esolver_cod_clifor: targetType === "esolver" ? draft.esolver_cod_clifor || targetValue || null : null,
    esolver_ragione_sociale: targetType === "esolver" ? draft.esolver_ragione_sociale || null : null,
    etichetta_manuale: targetType === "manual" ? draft.etichetta_manuale.trim() : null,
  };
}

function targetFromDraft(draft) {
  if (draft.fornitore_id) {
    return `local:${draft.fornitore_id}`;
  }
  if (draft.esolver_cod_clifor) {
    return `esolver:${draft.esolver_cod_clifor}`;
  }
  return "manual:";
}

export default function SupplierCodesPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [esolverSuppliers, setEsolverSuppliers] = useState([]);
  const [esolverSearch, setEsolverSearch] = useState("");
  const [drafts, setDrafts] = useState({});
  const [createForm, setCreateForm] = useState(emptyForm());
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [savingId, setSavingId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [loadingEsolver, setLoadingEsolver] = useState(false);

  useEffect(() => {
    let ignore = false;
    Promise.all([apiRequest("/supplier-codes", {}, token), apiRequest("/suppliers", {}, token)])
      .then(([codesData, suppliersData]) => {
        if (ignore) {
          return;
        }
        hydrateCodes(codesData.items || []);
        setSuppliers(suppliersData.items || []);
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

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      loadEsolverSuppliers();
    }, 250);
    return () => window.clearTimeout(timeoutId);
  }, [esolverSearch, token]);

  const filteredItems = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) =>
      [item.codice, item.nome_visualizzato, item.ragione_sociale_fornitore, item.etichetta_manuale]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle)),
    );
  }, [filter, items]);

  function hydrateCodes(nextItems) {
    setItems(nextItems);
    setDrafts(Object.fromEntries(nextItems.map((item) => [item.id, toDraft(item)])));
  }

  async function refreshCodes() {
    const data = await apiRequest("/supplier-codes", {}, token);
    hydrateCodes(data.items || []);
  }

  async function loadEsolverSuppliers() {
    setLoadingEsolver(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (esolverSearch.trim()) {
        params.set("search", esolverSearch.trim());
      }
      const data = await apiRequest(`/suppliers/esolver?${params.toString()}`, {}, token);
      setEsolverSuppliers(data.items || []);
    } catch (requestError) {
      setError(requestError.message);
      setEsolverSuppliers([]);
    } finally {
      setLoadingEsolver(false);
    }
  }

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    setStatusMessage("");
    setCreating(true);
    try {
      await apiRequest(
        "/supplier-codes",
        {
          method: "POST",
          body: JSON.stringify(payloadFromDraft(createForm)),
        },
        token,
      );
      await refreshCodes();
      setCreateForm(emptyForm());
      setStatusMessage("Codice creato");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleSave(itemId) {
    setError("");
    setStatusMessage("");
    setSavingId(itemId);
    try {
      await apiRequest(
        `/supplier-codes/${itemId}`,
        {
          method: "PUT",
          body: JSON.stringify(payloadFromDraft(drafts[itemId] || emptyForm())),
        },
        token,
      );
      await refreshCodes();
      setStatusMessage("Codice aggiornato");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) {
      return;
    }
    setError("");
    setStatusMessage("");
    try {
      await apiRequest(`/supplier-codes/${deleteTarget.id}`, { method: "DELETE" }, token);
      await refreshCodes();
      setStatusMessage("Codice eliminato");
      setDeleteTarget(null);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function resolveEsolverOption(draft) {
    if (!draft.esolver_cod_clifor) {
      return null;
    }
    return (
      esolverSuppliers.find((supplier) => supplier.cod_clifor === draft.esolver_cod_clifor) || {
        cod_clifor: draft.esolver_cod_clifor,
        ragione_sociale: draft.esolver_ragione_sociale || "Fornitore eSolver",
      }
    );
  }

  function updateConnection(currentDraft, value) {
    const [targetType, targetValue = ""] = String(value || "manual:").split(":", 2);
    if (targetType === "local") {
      return {
        ...currentDraft,
        target: value,
        fornitore_id: targetValue,
        esolver_cod_clifor: "",
        esolver_ragione_sociale: "",
        etichetta_manuale: "",
      };
    }
    if (targetType === "esolver") {
      const selected = esolverSuppliers.find((supplier) => supplier.cod_clifor === targetValue) || resolveEsolverOption({
        ...currentDraft,
        esolver_cod_clifor: targetValue,
      });
      return {
        ...currentDraft,
        target: value,
        fornitore_id: "",
        esolver_cod_clifor: selected?.cod_clifor || targetValue,
        esolver_ragione_sociale: selected?.ragione_sociale || "",
        etichetta_manuale: "",
      };
    }
    return {
      ...currentDraft,
      target: "manual:",
      fornitore_id: "",
      esolver_cod_clifor: "",
      esolver_ragione_sociale: "",
    };
  }

  function renderConnectionEditor(draft, onChange, disabled) {
    const currentEsolver = resolveEsolverOption(draft);
    const hasCurrentOutsideOptions =
      currentEsolver && !esolverSuppliers.some((supplier) => supplier.cod_clifor === currentEsolver.cod_clifor);
    return (
      <div className="space-y-2">
        <select
          className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink shadow-inner outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/10 disabled:bg-slate-100 disabled:text-slate-500"
          disabled={disabled}
          onChange={(event) => onChange(updateConnection(draft, event.target.value))}
          value={draft.target || targetFromDraft(draft)}
        >
          <option value="manual:">Manuale</option>
          <optgroup label="Fornitori speciali app">
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={`local:${supplier.id}`}>
                {supplier.ragione_sociale}
              </option>
            ))}
          </optgroup>
          <optgroup label="Fornitori eSolver">
            {hasCurrentOutsideOptions ? (
              <option value={`esolver:${currentEsolver.cod_clifor}`}>
                {currentEsolver.cod_clifor} - {currentEsolver.ragione_sociale}
              </option>
            ) : null}
            {esolverSuppliers.map((supplier) => (
              <option key={supplier.cod_clifor} value={`esolver:${supplier.cod_clifor}`}>
                {supplier.cod_clifor} - {supplier.ragione_sociale}
              </option>
            ))}
          </optgroup>
        </select>
        {(draft.target || targetFromDraft(draft)) === "manual:" ? (
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink shadow-inner outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 disabled:bg-slate-100"
            disabled={disabled}
            onChange={(event) => onChange({ ...draft, etichetta_manuale: event.target.value })}
            placeholder="Es. Materiale interno"
            value={draft.etichetta_manuale}
          />
        ) : null}
      </div>
    );
  }

  return (
    <section className="space-y-5 rounded-3xl border border-border bg-panel p-4 shadow-lg shadow-slate-200/40 xl:p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Strumenti qualità</p>
          <h2 className="mt-2 text-2xl font-semibold">Codici fornitori</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Codici installazione case sensitive collegati ai fornitori locali o a una voce manuale.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{filteredItems.length}</span> codici visibili su {items.length}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr),360px] xl:items-end">
        <label className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Filtro</span>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink shadow-inner outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-accent/10"
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Codice, fornitore, etichetta"
            value={filter}
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Cerca fornitore eSolver</span>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink shadow-inner outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-accent/10"
            onChange={(event) => setEsolverSearch(event.target.value)}
            placeholder="Nome, codice, P.IVA"
            value={esolverSearch}
          />
        </label>
      </div>

      {!isAdmin ? <p className="text-sm text-slate-500">Solo gli admin possono aggiungere, modificare o eliminare codici.</p> : null}
      {loadingEsolver ? <p className="text-sm text-slate-500">Lettura fornitori eSolver...</p> : null}

      {error ? <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      {statusMessage ? <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{statusMessage}</p> : null}

      <form className="rounded-2xl border border-sky-200 bg-sky-50 p-4" onSubmit={handleCreate}>
        <div className="grid gap-3 xl:grid-cols-[110px,minmax(420px,1fr),auto] xl:items-start">
          <label>
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">Codice</span>
            <input
              className="w-full rounded-xl border border-sky-200 bg-white px-3 py-2 text-sm font-semibold text-ink shadow-inner outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 disabled:bg-slate-100"
              disabled={!isAdmin}
              onChange={(event) => setCreateForm((current) => ({ ...current, codice: event.target.value }))}
              placeholder="Es. AB"
              value={createForm.codice}
            />
          </label>
          <label>
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">Collegamento</span>
            {renderConnectionEditor(
              createForm,
              (value) =>
                setCreateForm((current) => ({
                  ...current,
                  ...value,
                })),
              !isAdmin,
            )}
          </label>
          <button
            className="mt-7 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={!isAdmin || creating}
            type="submit"
          >
            {creating ? "Creo..." : "Aggiungi"}
          </button>
        </div>
      </form>

      <div className="overflow-hidden rounded-2xl border border-border bg-white">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Codice</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Collegamento</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Tipo</th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Azioni</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredItems.map((item) => {
              const draft = drafts[item.id] || toDraft(item);
              return (
                <tr key={item.id} className="align-top hover:bg-slate-50/70">
                  <td className="w-32 px-4 py-3">
                    <input
                      className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm font-semibold text-ink shadow-inner outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 disabled:bg-slate-100"
                      disabled={!isAdmin}
                      onChange={(event) =>
                        setDrafts((current) => ({ ...current, [item.id]: { ...draft, codice: event.target.value } }))
                      }
                      value={draft.codice}
                    />
                  </td>
                  <td className="min-w-[32rem] px-4 py-3">
                    {renderConnectionEditor(
                      draft,
                      (value) =>
                        setDrafts((current) => ({
                          ...current,
                          [item.id]: {
                            ...draft,
                            ...value,
                          },
                        })),
                      !isAdmin,
                    )}
                    {item.ragione_sociale_fornitore ? (
                      <p className="mt-1 text-xs text-slate-500">Locale: {item.ragione_sociale_fornitore}</p>
                    ) : null}
                    {item.esolver_cod_clifor ? (
                      <p className="mt-1 text-xs text-slate-500">
                        eSolver: {item.esolver_cod_clifor} - {item.esolver_ragione_sociale || "-"}
                      </p>
                    ) : null}
                    {item.etichetta_manuale && item.tipo_collegamento === "manuale" ? (
                      <p className="mt-1 text-xs text-slate-500">Manuale: {item.etichetta_manuale}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        item.tipo_collegamento === "locale"
                          ? "bg-sky-100 text-sky-800"
                          : item.tipo_collegamento === "esolver"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {item.tipo_collegamento === "locale" ? "Locale" : item.tipo_collegamento === "esolver" ? "eSolver" : "Manuale"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        className="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                        disabled={!isAdmin || savingId === item.id}
                        onClick={() => handleSave(item.id)}
                        type="button"
                      >
                        {savingId === item.id ? "Salvo..." : "Salva"}
                      </button>
                      <button
                        className="rounded-xl border border-rose-200 bg-white px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-60"
                        disabled={!isAdmin}
                        onClick={() => setDeleteTarget(item)}
                        type="button"
                      >
                        Elimina
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && !filteredItems.length ? <p className="px-4 py-4 text-sm text-slate-500">Nessun codice visibile.</p> : null}
        {loading ? <p className="px-4 py-4 text-sm text-slate-500">Caricamento...</p> : null}
      </div>

      {deleteTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-white p-5 shadow-2xl">
            <h3 className="text-lg font-semibold text-slate-900">Eliminare codice?</h3>
            <p className="mt-2 text-sm text-slate-600">
              Il codice <span className="font-semibold">{deleteTarget.codice}</span> verrà rimosso dalla tabella locale.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                className="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => setDeleteTarget(null)}
                type="button"
              >
                Annulla
              </button>
              <button
                className="rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
                onClick={handleDelete}
                type="button"
              >
                Elimina
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
