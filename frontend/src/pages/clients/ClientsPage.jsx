import { useEffect, useMemo, useRef, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const LIST_STATE_STORAGE_KEY = "certi_nt.clients_esolver_list_state.v1";
const DEFAULT_LIST_STATE = {
  search: "",
  rowLimit: "25",
  sortConfig: { field: "ragione_sociale", direction: "asc" },
  scrollLeft: 0,
};

function loadPersistedListState() {
  if (typeof window === "undefined") {
    return DEFAULT_LIST_STATE;
  }
  try {
    const raw = window.sessionStorage.getItem(LIST_STATE_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_LIST_STATE;
    }
    const parsed = JSON.parse(raw);
    return {
      search: typeof parsed?.search === "string" ? parsed.search : DEFAULT_LIST_STATE.search,
      rowLimit: ["25", "50", "75", "100", "all"].includes(parsed?.rowLimit) ? parsed.rowLimit : DEFAULT_LIST_STATE.rowLimit,
      sortConfig:
        parsed?.sortConfig && typeof parsed.sortConfig === "object"
          ? {
              field: typeof parsed.sortConfig.field === "string" ? parsed.sortConfig.field : DEFAULT_LIST_STATE.sortConfig.field,
              direction: parsed.sortConfig.direction === "desc" ? "desc" : "asc",
            }
          : DEFAULT_LIST_STATE.sortConfig,
      scrollLeft: Number.isFinite(Number(parsed?.scrollLeft)) ? Number(parsed.scrollLeft) : 0,
    };
  } catch {
    return DEFAULT_LIST_STATE;
  }
}

function savePersistedListState(nextState) {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(LIST_STATE_STORAGE_KEY, JSON.stringify(nextState));
}

function textValue(value) {
  return value || "-";
}

function sortValue(item, field) {
  return item[field] || "";
}

function compareValues(left, right, direction) {
  const multiplier = direction === "asc" ? 1 : -1;
  const leftEmpty = left === null || left === undefined || left === "";
  const rightEmpty = right === null || right === undefined || right === "";
  if (leftEmpty && rightEmpty) {
    return 0;
  }
  if (leftEmpty) {
    return direction === "asc" ? -1 : 1;
  }
  if (rightEmpty) {
    return direction === "asc" ? 1 : -1;
  }
  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function SortableHeader({ field, label, onSort, sortConfig }) {
  const isActive = sortConfig.field === field;
  const indicator = !isActive ? "↕" : sortConfig.direction === "asc" ? "↑" : "↓";
  return (
    <th className="px-4 py-3 text-left align-middle">
      <button
        className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 hover:text-slate-800"
        onClick={() => onSort(field)}
        type="button"
      >
        <span>{label}</span>
        <span className={isActive ? "text-slate-800" : "text-slate-400"}>{indicator}</span>
      </button>
    </th>
  );
}

export default function ClientsPage() {
  const { token } = useAuth();
  const initialStateRef = useRef(loadPersistedListState());
  const topScrollRef = useRef(null);
  const tableScrollRef = useRef(null);
  const tableRef = useRef(null);
  const syncingScrollRef = useRef(false);
  const restoredScrollRef = useRef(false);
  const [clients, setClients] = useState([]);
  const [search, setSearch] = useState(initialStateRef.current.search);
  const [rowLimit, setRowLimit] = useState(initialStateRef.current.rowLimit);
  const [sortConfig, setSortConfig] = useState(initialStateRef.current.sortConfig);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [totalClients, setTotalClients] = useState(0);
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 1600, viewportWidth: 0 });

  const pageSize = rowLimit === "all" ? 20000 : Number(rowLimit);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadClients();
    }, 250);
    return () => window.clearTimeout(timeoutId);
  }, [rowLimit, search, token]);

  useEffect(() => {
    savePersistedListState({
      search,
      rowLimit,
      sortConfig,
      scrollLeft: tableScrollRef.current?.scrollLeft || initialStateRef.current.scrollLeft || 0,
    });
  }, [rowLimit, search, sortConfig]);

  useEffect(() => {
    function updateScrollMetrics() {
      const table = tableRef.current;
      const viewport = tableScrollRef.current;
      setScrollMetrics({
        contentWidth: Math.max(table?.scrollWidth || 0, 1600),
        viewportWidth: viewport?.clientWidth || 0,
      });
    }

    updateScrollMetrics();
    window.addEventListener("resize", updateScrollMetrics);
    return () => window.removeEventListener("resize", updateScrollMetrics);
  }, [clients.length, rowLimit]);

  useEffect(() => {
    if (restoredScrollRef.current) {
      return;
    }
    const left = initialStateRef.current.scrollLeft || 0;
    window.requestAnimationFrame(() => {
      if (topScrollRef.current) {
        topScrollRef.current.scrollLeft = left;
      }
      if (tableScrollRef.current) {
        tableScrollRef.current.scrollLeft = left;
      }
      restoredScrollRef.current = true;
    });
  }, [scrollMetrics.contentWidth]);

  async function loadClients({ append = false } = {}) {
    const offset = append ? clients.length : 0;
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) });
      if (search.trim()) {
        params.set("search", search.trim());
      }
      const data = await apiRequest(`/clients/esolver?${params.toString()}`, {}, token);
      setTotalClients(Number(data.total || 0));
      setClients((current) => {
        if (!append) {
          return data.items;
        }
        const seen = new Set(current.map((item) => item.cod_clifor));
        const nextItems = data.items.filter((item) => !seen.has(item.cod_clifor));
        return [...current, ...nextItems];
      });
    } catch (requestError) {
      if (!append) {
        setClients([]);
        setTotalClients(0);
      }
      setError(requestError.message);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  const sortedClients = useMemo(() => {
    return [...clients].sort((left, right) => {
      const sorted = compareValues(sortValue(left, sortConfig.field), sortValue(right, sortConfig.field), sortConfig.direction);
      return sorted || compareValues(left.cod_clifor, right.cod_clifor, "asc");
    });
  }, [clients, sortConfig]);

  const visibleClients = sortedClients;
  const hasMoreClients = totalClients > clients.length;

  function toggleSort(field) {
    setSortConfig((current) => {
      if (current.field !== field) {
        return { field, direction: "asc" };
      }
      return { field, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  }

  function syncScroll(target, source) {
    if (!target || !source || syncingScrollRef.current) {
      return;
    }
    syncingScrollRef.current = true;
    target.scrollLeft = source.scrollLeft;
    savePersistedListState({
      search,
      rowLimit,
      sortConfig,
      scrollLeft: source.scrollLeft,
    });
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  return (
    <div className="w-full max-w-none space-y-6">
      <section className="w-full rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Clienti</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Clienti eSolver</h2>
            <p className="mt-2 text-sm text-slate-500">Vista sola lettura dell'anagrafica clienti esposta da eSolver.</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            <span className="font-semibold text-ink">{clients.length}</span> clienti caricati
            {totalClients ? <span className="ml-2 text-slate-500">su {totalClients}</span> : null}
          </div>
        </div>

        <div className="mt-8 flex items-end gap-3 overflow-x-auto pb-1">
          <label className="block min-w-[360px] max-w-[420px]">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Filtro</span>
            <input
              className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Nome, codice, P.IVA, codice alternativo"
              value={search}
            />
          </label>
          <label className="ml-auto block min-w-[88px] max-w-[88px]">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Righe</span>
            <select
              className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
              onChange={(event) => setRowLimit(event.target.value)}
              value={rowLimit}
            >
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="75">75</option>
              <option value="100">100</option>
              <option value="all">Tutte</option>
            </select>
          </label>
        </div>

        {error ? <p className="mt-5 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="w-full">
        <div className="sticky top-0 z-20 rounded-xl border border-border bg-slate-50 px-3 py-2 shadow-sm">
          <div
            className="incoming-top-scroll overflow-x-auto overflow-y-hidden"
            onScroll={(event) => syncScroll(tableScrollRef.current, event.currentTarget)}
            ref={topScrollRef}
          >
            <div className="h-4 min-w-full" style={{ width: Math.max(scrollMetrics.contentWidth, scrollMetrics.viewportWidth) }} />
          </div>
        </div>

        <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div
            className="incoming-grid-scroll overflow-x-hidden overflow-y-visible"
            onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
            ref={tableScrollRef}
          >
            <table className="min-w-[1600px] table-fixed border-collapse text-sm" ref={tableRef}>
              <colgroup>
                <col className="w-[110px]" />
                <col className="w-[320px]" />
                <col className="w-[130px]" />
                <col className="w-[140px]" />
                <col className="w-[140px]" />
                <col className="w-[280px]" />
                <col className="w-[80px]" />
                <col className="w-[170px]" />
                <col className="w-[80px]" />
                <col className="w-[90px]" />
                <col className="w-[230px]" />
                <col className="w-[150px]" />
              </colgroup>
              <thead className="sticky-list-head bg-slate-50">
                <tr className="border-b border-slate-200">
                  <SortableHeader field="cod_clifor" label="Codice" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="ragione_sociale" label="Ragione sociale" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="cod_alternativo2" label="Cod. alt." onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="partita_iva" label="P.IVA" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="codice_fiscale" label="Cod. fiscale" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="indirizzo" label="Indirizzo" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="cap" label="CAP" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="citta" label="Città" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="provincia" label="Prov." onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="nazione" label="Nazione" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="email" label="Email" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="telefono" label="Telefono" onSort={toggleSort} sortConfig={sortConfig} />
                </tr>
              </thead>
              <tbody>
                {visibleClients.map((item) => (
                  <tr className="border-b border-slate-100 hover:bg-slate-50/70 last:border-0" key={item.cod_clifor}>
                    <td className="px-4 py-3 font-semibold text-slate-950">{textValue(item.cod_clifor)}</td>
                    <td className="px-4 py-3 font-semibold text-slate-900">{textValue(item.ragione_sociale)}</td>
                    <td className="px-4 py-3">{textValue(item.cod_alternativo2)}</td>
                    <td className="px-4 py-3">{textValue(item.partita_iva)}</td>
                    <td className="px-4 py-3">{textValue(item.codice_fiscale)}</td>
                    <td className="px-4 py-3">{textValue(item.indirizzo)}</td>
                    <td className="px-4 py-3">{textValue(item.cap)}</td>
                    <td className="px-4 py-3">{textValue(item.citta)}</td>
                    <td className="px-4 py-3">{textValue(item.provincia)}</td>
                    <td className="px-4 py-3">{textValue(item.nazione)}</td>
                    <td className="px-4 py-3">{textValue(item.email)}</td>
                    <td className="px-4 py-3">{textValue(item.telefono)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {loading ? <p className="px-4 py-3 text-sm text-slate-500">Lettura clienti eSolver...</p> : null}
          {!loading && !visibleClients.length && !error ? (
            <p className="px-4 py-3 text-sm text-slate-500">Nessun cliente trovato con i criteri attuali.</p>
          ) : null}
          {!loading && hasMoreClients ? (
            <div className="border-t border-slate-100 px-4 py-4 text-center">
              <button
                className="rounded-xl border border-sky-200 bg-sky-50 px-5 py-2 text-sm font-semibold text-sky-700 hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={loadingMore}
                onClick={() => loadClients({ append: true })}
                type="button"
              >
                {loadingMore ? "Caricamento..." : `Carica altri ${pageSize} (${clients.length} su ${totalClients})`}
              </button>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
