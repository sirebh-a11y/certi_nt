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

function evaluateProgressiveFilter(values, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return { active: false, matched: true, remainingValues: values };
  }
  const matchedIndexes = [];
  values.forEach((value, index) => {
    if (value.includes(normalizedQuery)) {
      matchedIndexes.push(index);
    }
  });
  return {
    active: true,
    matched: matchedIndexes.length > 0,
    remainingValues: values.filter((_, index) => !matchedIndexes.includes(index)),
  };
}

function combineFilterResults(first, second, operator) {
  if (first === null) {
    return second;
  }
  if (second === null) {
    return first;
  }
  return operator === "or" ? first || second : first && second;
}

function compareValues(left, right, direction) {
  const multiplier = direction === "asc" ? 1 : -1;
  const leftEmpty = left === null || left === undefined || left === "";
  const rightEmpty = right === null || right === undefined || right === "";
  if (leftEmpty && rightEmpty) {
    return 0;
  }
  if (leftEmpty) {
    return 1;
  }
  if (rightEmpty) {
    return -1;
  }
  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function certificateSortValue(item, field) {
  switch (field) {
    case "certificate_number":
      return item.certificate_number || "";
    case "cert_date":
      return item.cert_date || item.created_at || "";
    case "cdq":
      return item.cdq || "";
    case "cod_odp":
      return item.cod_odp || "";
    case "lega_cod_f3":
      return item.lega_cod_f3 || "";
    case "fornitore_cliente":
      return item.fornitore_cliente || "";
    case "status":
      return item.status || "";
    case "file":
      return `${item.has_word ? "1" : "0"}-${item.has_pdf ? "1" : "0"}`;
    default:
      return null;
  }
}

function SortableHeader({ field, label, onSort, sortConfig }) {
  const isActive = sortConfig.field === field;
  const indicator = !isActive ? "" : sortConfig.direction === "asc" ? "↑" : "↓";
  return (
    <th className="px-4 py-3">
      <button
        className={`inline-flex items-center gap-1 text-left transition hover:text-slate-700 ${
          isActive ? "text-slate-700" : "text-slate-500"
        }`}
        onClick={() => onSort(field)}
        type="button"
      >
        <span>{label}</span>
        <span className={`min-w-[10px] text-[10px] ${isActive ? "text-slate-700" : "text-slate-400"}`}>{indicator}</span>
      </button>
    </th>
  );
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
  const [queryOne, setQueryOne] = useState("");
  const [queryTwo, setQueryTwo] = useState("");
  const [queryThree, setQueryThree] = useState("");
  const [operatorOne, setOperatorOne] = useState("and");
  const [operatorTwo, setOperatorTwo] = useState("and");
  const [rowLimit, setRowLimit] = useState("25");
  const [sortConfig, setSortConfig] = useState({ field: null, direction: "asc" });
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
    let nextItems = items;
    if (queryOne.trim() || queryTwo.trim() || queryThree.trim()) {
      nextItems = nextItems.filter((item) => {
        const baseValues = searchableValues(item);
        const firstResult = evaluateProgressiveFilter(baseValues, queryOne);
        const secondResult = evaluateProgressiveFilter(firstResult.remainingValues, queryTwo);
        const thirdResult = evaluateProgressiveFilter(secondResult.remainingValues, queryThree);
        const firstMatch = firstResult.active ? firstResult.matched : null;
        const secondMatch = secondResult.active ? secondResult.matched : null;
        const thirdMatch = thirdResult.active ? thirdResult.matched : null;
        const firstCombined = combineFilterResults(firstMatch, secondMatch, operatorOne);
        const finalCombined = combineFilterResults(firstCombined, thirdMatch, operatorTwo);
        return finalCombined ?? true;
      });
    }

    return [...nextItems].sort((left, right) => {
      if (!sortConfig.field) {
        return compareValues(left.created_at, right.created_at, "desc");
      }
      return compareValues(
        certificateSortValue(left, sortConfig.field),
        certificateSortValue(right, sortConfig.field),
        sortConfig.direction,
      );
    });
  }, [items, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, sortConfig]);

  const displayedItems = useMemo(() => {
    if (rowLimit === "all") {
      return visibleItems;
    }
    const limit = Number(rowLimit);
    if (!Number.isFinite(limit) || limit <= 0) {
      return visibleItems;
    }
    return visibleItems.slice(0, limit);
  }, [rowLimit, visibleItems]);

  function toggleSort(field) {
    setSortConfig((current) => {
      if (current.field !== field) {
        return { field, direction: "asc" };
      }
      return { field, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Registro certificazione</p>
          <h2 className="mt-2 text-2xl font-semibold">Certificati numerati</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Elenco dei certificati che hanno già ricevuto il numero. Se il certificato è ancora aperto, la riga rimanda alla pagina OL; quando sarà chiuso,
            qui resterà l'accesso al PDF finale.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{displayedItems.length}</span> certificati visibili
          {visibleItems.length !== items.length || displayedItems.length !== visibleItems.length ? (
            <span className="ml-2 text-slate-500">su {visibleItems.length} filtrati / {items.length} totali</span>
          ) : null}
        </div>
      </div>

      <div className="mt-8 flex items-end gap-2 overflow-x-auto pb-1">
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-search-1">
            Filtro 1
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="certificate-register-search-1"
            onChange={(event) => setQueryOne(event.target.value)}
            placeholder="Tutti i campi"
            value={queryOne}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-operator-1">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="certificate-register-operator-1"
            onChange={(event) => setOperatorOne(event.target.value)}
            value={operatorOne}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-search-2">
            Filtro 2
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="certificate-register-search-2"
            onChange={(event) => setQueryTwo(event.target.value)}
            placeholder="Campi non presi dal 1"
            value={queryTwo}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-operator-2">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="certificate-register-operator-2"
            onChange={(event) => setOperatorTwo(event.target.value)}
            value={operatorTwo}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-search-3">
            Filtro 3
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="certificate-register-search-3"
            onChange={(event) => setQueryThree(event.target.value)}
            placeholder="Campi non presi da 1 e 2"
            value={queryThree}
          />
        </div>
        <div className="ml-auto min-w-[88px] max-w-[88px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="certificate-register-row-limit">
            Righe
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="certificate-register-row-limit"
            onChange={(event) => setRowLimit(event.target.value)}
            value={rowLimit}
          >
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="75">75</option>
            <option value="100">100</option>
            <option value="all">Tutte</option>
          </select>
        </div>
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
                <SortableHeader field="certificate_number" label="Cert. Nr." onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cert_date" label="Data" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cdq" label="CDQ" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cod_odp" label="OL" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="lega_cod_f3" label="Cod. F3" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="fornitore_cliente" label="Cliente" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="status" label="Stato" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="file" label="File" onSort={toggleSort} sortConfig={sortConfig} />
              </tr>
            </thead>
            <tbody>
              {displayedItems.map((item) => (
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
