import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest, resolveApiAssetUrl } from "../../app/api";
import { useAuth } from "../../app/auth";

const STATUS_LABELS = {
  draft: "Word aperto",
  pdf_final: "PDF chiuso",
};

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

function searchableValues(item) {
  return [
    item.certificate_number,
    item.cdq,
    item.cod_odp,
    item.lega_cod_f3,
    item.fornitore_cliente,
    item.status,
    STATUS_LABELS[item.status],
  ]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());
}

function statusClass(status) {
  if (status === "pdf_final") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export default function QuartaTaglioCertificatesRegisterPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    apiRequest("/quarta-taglio/certificates/register", {}, token)
      .then((response) => {
        if (!ignore) {
          setItems(response.items || []);
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
  }, [token]);

  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return items;
    }
    return items.filter((item) => searchableValues(item).some((value) => value.includes(normalizedQuery)));
  }, [items, query]);

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Registro certificati</p>
          <h2 className="mt-2 text-2xl font-semibold">Certificati numerati</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Elenco dei certificati che hanno già ricevuto il numero. Se il certificato è ancora aperto, la riga rimanda alla pagina OL; quando sarà chiuso,
            qui resterà l'accesso al PDF finale.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{visibleItems.length}</span> certificati
          {visibleItems.length !== items.length ? <span className="ml-2 text-slate-500">su {items.length}</span> : null}
        </div>
      </div>

      <div className="mt-8 flex max-w-md flex-col gap-1">
        <label className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-search">
          Filtro
        </label>
        <input
          className="rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
          id="certificate-register-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Numero, CDQ, OL, Cod. F3, cliente..."
          value={query}
        />
      </div>

      <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-500">
        Placeholder sviluppo: chiusura PDF finale, impaginazione Word ricaricato, archivio PDF ed esportazione eSolver sono descritti in
        {" "}
        <span className="font-semibold text-slate-700">docs/modules/quarta_taglio_final_certificate_flow_placeholder.md</span>.
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento registro certificati...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-[980px] w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Cert. Nr.</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">CDQ</th>
                <th className="px-4 py-3">OL</th>
                <th className="px-4 py-3">Cod. F3</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">File</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr className="border-b border-slate-100 align-middle hover:bg-slate-50/70 last:border-0" key={item.id}>
                  <td className="px-4 py-3 font-semibold text-slate-950">{item.certificate_number}</td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(item.cert_date || item.created_at)}</td>
                  <td className="px-4 py-3 font-semibold text-slate-800">{item.cdq || "-"}</td>
                  <td className="px-4 py-3">
                    <Link className="font-semibold text-accent hover:underline" to={`/quarta-taglio/${encodeURIComponent(item.cod_odp)}`}>
                      {item.cod_odp}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.lega_cod_f3 || "-"}</td>
                  <td className="px-4 py-3 text-slate-700">{item.fornitore_cliente || "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-semibold ${statusClass(item.status)}`}>
                      {STATUS_LABELS[item.status] || item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {item.word_download_url ? (
                      <a
                        className="font-semibold text-accent hover:underline"
                        href={resolveApiAssetUrl(item.word_download_url)}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Word
                      </a>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                    {item.has_pdf ? <span className="ml-3 font-semibold text-emerald-700">PDF</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !visibleItems.length && !error ? <p className="px-5 py-8 text-sm text-slate-500">Nessun certificato numerato trovato.</p> : null}
      </div>
    </section>
  );
}
