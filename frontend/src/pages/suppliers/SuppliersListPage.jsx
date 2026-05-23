import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function SuppliersListPage() {
  const { token, user } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [esolverSuppliers, setEsolverSuppliers] = useState([]);
  const [esolverSearch, setEsolverSearch] = useState("");
  const [error, setError] = useState("");
  const [loadingEsolver, setLoadingEsolver] = useState(false);
  const [importingCode, setImportingCode] = useState(null);
  const [syncingEsolver, setSyncingEsolver] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    let ignore = false;

    loadSuppliers(ignore);

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

  function loadSuppliers(ignore = false) {
    return apiRequest("/suppliers", {}, token)
      .then((data) => {
        if (!ignore) {
          setSuppliers(data.items);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
        }
      });
  }

  async function loadEsolverSuppliers() {
    setLoadingEsolver(true);
    try {
      const params = new URLSearchParams({ limit: "60" });
      if (esolverSearch.trim()) {
        params.set("search", esolverSearch.trim());
      }
      const data = await apiRequest(`/suppliers/esolver?${params.toString()}`, {}, token);
      setEsolverSuppliers(data.items);
    } catch (requestError) {
      setError(requestError.message);
      setEsolverSuppliers([]);
    } finally {
      setLoadingEsolver(false);
    }
  }

  async function handleImportFromEsolver(codClifor) {
    setError("");
    setStatusMessage("");
    setImportingCode(codClifor);
    try {
      await apiRequest(
        "/suppliers/esolver/import",
        {
          method: "POST",
          body: JSON.stringify({ cod_clifor: codClifor }),
        },
        token,
      );
      await loadSuppliers();
      await loadEsolverSuppliers();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setImportingCode(null);
    }
  }

  async function handleSyncLinkedEsolver() {
    setError("");
    setStatusMessage("");
    setSyncingEsolver(true);
    try {
      const response = await apiRequest(
        "/suppliers/esolver/sync-linked",
        {
          method: "POST",
        },
        token,
      );
      setStatusMessage(`Collegamenti eSolver aggiornati: ${response.updated}. Invariati: ${response.unchanged}.`);
      await loadSuppliers();
      await loadEsolverSuppliers();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSyncingEsolver(false);
    }
  }

  const visibleSuppliers = suppliers;

  const externalOnlySuppliers = useMemo(() => esolverSuppliers.filter((item) => !item.in_app), [esolverSuppliers]);

  return (
    <section className="space-y-6 rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Fornitori</p>
          <h2 className="mt-2 text-2xl font-semibold">Fornitori</h2>
          <p className="mt-2 text-sm text-slate-500">
            Blu: fornitori in app. Nero: fornitori eSolver disponibili da aggiungere senza cambiare i riconoscimenti esistenti.
          </p>
        </div>
      </div>

      {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      {statusMessage ? <p className="mt-4 text-sm text-slate-600">{statusMessage}</p> : null}

      <div className="overflow-hidden rounded-2xl border border-sky-200">
        <div className="border-b border-sky-100 bg-sky-50 px-4 py-3">
          <h3 className="text-sm font-semibold text-sky-950">Fornitori in app</h3>
          <p className="mt-1 text-xs text-sky-700">Questi alimentano caricamento, mascheramento, riconoscimento e controlli locali.</p>
        </div>
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">Ragione sociale</th>
              <th className="px-4 py-3 text-left font-semibold">Lettura</th>
              <th className="px-4 py-3 text-left font-semibold">eSolver</th>
              <th className="px-4 py-3 text-left font-semibold">Città</th>
              <th className="px-4 py-3 text-left font-semibold">Nazione</th>
              <th className="px-4 py-3 text-left font-semibold">Alias</th>
              <th className="px-4 py-3 text-left font-semibold">Stato</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {visibleSuppliers.map((item) => (
              <tr className="bg-sky-50/45 hover:bg-sky-50" key={item.id}>
                <td className="px-4 py-3">
                  <Link className="font-medium text-accent hover:underline" to={`/suppliers/${item.id}`}>
                    {item.ragione_sociale}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {item.reader_template_key ? (
                    <span className="rounded-full border border-sky-300 bg-sky-100 px-2 py-1 text-xs font-semibold text-sky-800">
                      Speciale
                    </span>
                  ) : (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs text-slate-500">Standard</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {item.esolver_cod_clifor ? (
                    <span className="text-xs text-slate-600">
                      {item.esolver_cod_clifor}
                      <br />
                      {item.esolver_name || "-"}
                    </span>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="px-4 py-3">{item.citta || "-"}</td>
                <td className="px-4 py-3">{item.nazione || "-"}</td>
                <td className="px-4 py-3">{item.alias_count}</td>
                <td className="px-4 py-3">{item.attivo ? "Attivo" : "Disattivo"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!visibleSuppliers.length && !error ? <p className="mt-4 text-sm text-slate-500">Nessun fornitore disponibile.</p> : null}

      <div className="overflow-hidden rounded-2xl border border-border">
        <div className="flex flex-col gap-3 border-b border-border bg-white px-4 py-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Fornitori eSolver non in app</h3>
            <p className="mt-1 text-xs text-slate-500">Sono mostrati in nero. Aggiungili solo quando devono diventare gestiti da Certi.</p>
          </div>
          <div className="flex w-full flex-col gap-3 md:w-auto md:flex-row md:items-end">
            {isAdmin ? (
              <button
                className="rounded-xl border border-border px-3 py-2 text-xs font-semibold text-ink hover:bg-slate-50 disabled:opacity-60"
                disabled={syncingEsolver}
                onClick={handleSyncLinkedEsolver}
                type="button"
              >
                {syncingEsolver ? "Aggiornamento..." : "Aggiorna collegati"}
              </button>
            ) : null}
            <div className="w-full md:w-80">
              <label className="mb-1 block text-xs uppercase tracking-[0.22em] text-slate-500">Cerca eSolver</label>
              <input
                value={esolverSearch}
                onChange={(event) => setEsolverSearch(event.target.value)}
                placeholder="Nome, codice, P.IVA"
              />
            </div>
          </div>
        </div>
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">Codice</th>
              <th className="px-4 py-3 text-left font-semibold">Ragione sociale eSolver</th>
              <th className="px-4 py-3 text-left font-semibold">P.IVA</th>
              <th className="px-4 py-3 text-left font-semibold">Città</th>
              <th className="px-4 py-3 text-left font-semibold">Azione</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {externalOnlySuppliers.map((item) => (
              <tr className="text-slate-950 hover:bg-slate-50" key={item.cod_clifor}>
                <td className="px-4 py-3 font-medium">{item.cod_clifor}</td>
                <td className="px-4 py-3">{item.ragione_sociale}</td>
                <td className="px-4 py-3">{item.partita_iva || "-"}</td>
                <td className="px-4 py-3">{item.citta || "-"}</td>
                <td className="px-4 py-3">
                  {isAdmin ? (
                    <button
                      className="rounded-xl border border-border px-3 py-2 text-xs font-semibold text-ink hover:bg-slate-50 disabled:opacity-60"
                      disabled={importingCode === item.cod_clifor}
                      onClick={() => handleImportFromEsolver(item.cod_clifor)}
                      type="button"
                    >
                      {importingCode === item.cod_clifor ? "Aggiungo..." : "Aggiungi in app"}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-500">Solo admin</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loadingEsolver ? <p className="px-4 py-3 text-sm text-slate-500">Lettura eSolver...</p> : null}
        {!loadingEsolver && !externalOnlySuppliers.length ? (
          <p className="px-4 py-3 text-sm text-slate-500">Nessun fornitore eSolver esterno visibile.</p>
        ) : null}
      </div>
    </section>
  );
}
