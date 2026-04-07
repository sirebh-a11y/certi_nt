import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function SuppliersListPage() {
  const { token } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [error, setError] = useState("");
  const [showOnlyActive, setShowOnlyActive] = useState(false);

  useEffect(() => {
    let ignore = false;

    apiRequest("/suppliers", {}, token)
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

    return () => {
      ignore = true;
    };
  }, [token]);

  const visibleSuppliers = useMemo(
    () => suppliers.filter((item) => (showOnlyActive ? item.attivo : true)),
    [showOnlyActive, suppliers],
  );

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Fornitori</p>
          <h2 className="mt-2 text-2xl font-semibold">Anagrafica Fornitori</h2>
          <p className="mt-2 text-sm text-slate-500">
            Prima anagrafica amministrata manualmente, dopo il seed iniziale da CSV.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            className={`rounded-xl border px-4 py-3 text-sm font-medium ${
              showOnlyActive ? "border-accent bg-accent/10 text-accent" : "border-border bg-white text-slate-600"
            }`}
            onClick={() => setShowOnlyActive((currentValue) => !currentValue)}
            type="button"
          >
            {showOnlyActive ? "Mostra tutti" : "Solo attivi"}
          </button>
          <Link className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700" to="/suppliers/new">
            Nuovo fornitore
          </Link>
        </div>
      </div>

      {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-6 overflow-hidden rounded-2xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">Ragione sociale</th>
              <th className="px-4 py-3 text-left font-semibold">Città</th>
              <th className="px-4 py-3 text-left font-semibold">Nazione</th>
              <th className="px-4 py-3 text-left font-semibold">Email</th>
              <th className="px-4 py-3 text-left font-semibold">Alias</th>
              <th className="px-4 py-3 text-left font-semibold">Stato</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {visibleSuppliers.map((item) => (
              <tr className="hover:bg-slate-50" key={item.id}>
                <td className="px-4 py-3">
                  <Link className="font-medium text-accent hover:underline" to={`/suppliers/${item.id}`}>
                    {item.ragione_sociale}
                  </Link>
                </td>
                <td className="px-4 py-3">{item.citta || "-"}</td>
                <td className="px-4 py-3">{item.nazione || "-"}</td>
                <td className="px-4 py-3">{item.email || "-"}</td>
                <td className="px-4 py-3">{item.alias_count}</td>
                <td className="px-4 py-3">{item.attivo ? "Attivo" : "Disattivo"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!visibleSuppliers.length && !error ? <p className="mt-4 text-sm text-slate-500">Nessun fornitore disponibile.</p> : null}
    </section>
  );
}
