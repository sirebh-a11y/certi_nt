import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const STATUS_CLASSES = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  missing: "border-amber-200 bg-amber-50 text-amber-800",
  mismatch: "border-rose-200 bg-rose-50 text-rose-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
  not_checked: "border-slate-200 bg-slate-50 text-slate-700",
};

const STATUS_LABELS = {
  green: "Verde",
  yellow: "Giallo",
  red: "Rosso",
  ok: "OK",
  missing: "DDT mancante",
  mismatch: "Non coerente",
  error: "Errore",
  not_checked: "Non controllato",
};

const STATUS_SORT_RANK = {
  red: 1,
  yellow: 2,
  green: 3,
  error: 1,
  mismatch: 1,
  missing: 2,
  not_checked: 2,
  ok: 3,
};

const LIST_STATE_STORAGE_KEY = "certi_nt.quarta_taglio_list_state.v1";
const DEFAULT_LIST_STATE = {
  queryOne: "",
  queryTwo: "",
  queryThree: "",
  operatorOne: "and",
  operatorTwo: "and",
  rowLimit: "25",
  sortConfig: { field: null, direction: "asc" },
  scrollLeft: 0,
  scrollTop: 0,
  windowScrollY: 0,
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
    const sortConfig =
      parsed?.sortConfig && typeof parsed.sortConfig === "object"
        ? {
            field: typeof parsed.sortConfig.field === "string" ? parsed.sortConfig.field : null,
            direction: parsed.sortConfig.direction === "desc" ? "desc" : "asc",
          }
        : DEFAULT_LIST_STATE.sortConfig;
    return {
      queryOne: typeof parsed?.queryOne === "string" ? parsed.queryOne : DEFAULT_LIST_STATE.queryOne,
      queryTwo: typeof parsed?.queryTwo === "string" ? parsed.queryTwo : DEFAULT_LIST_STATE.queryTwo,
      queryThree: typeof parsed?.queryThree === "string" ? parsed.queryThree : DEFAULT_LIST_STATE.queryThree,
      operatorOne: parsed?.operatorOne === "or" ? "or" : DEFAULT_LIST_STATE.operatorOne,
      operatorTwo: parsed?.operatorTwo === "or" ? "or" : DEFAULT_LIST_STATE.operatorTwo,
      rowLimit: ["25", "50", "75", "100", "all"].includes(parsed?.rowLimit) ? parsed.rowLimit : DEFAULT_LIST_STATE.rowLimit,
      sortConfig,
      scrollLeft: Number.isFinite(Number(parsed?.scrollLeft)) ? Number(parsed.scrollLeft) : 0,
      scrollTop: Number.isFinite(Number(parsed?.scrollTop)) ? Number(parsed.scrollTop) : 0,
      windowScrollY: Number.isFinite(Number(parsed?.windowScrollY)) ? Number(parsed.windowScrollY) : 0,
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

function getScrollablePageContainer(element) {
  let current = element?.parentElement || null;
  while (current) {
    const style = window.getComputedStyle(current);
    const overflowY = style.overflowY;
    if ((overflowY === "auto" || overflowY === "scroll") && current.scrollHeight > current.clientHeight) {
      return current;
    }
    current = current.parentElement;
  }
  return document.scrollingElement || document.documentElement;
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("it-IT", { maximumFractionDigits: 2 });
}

function statusClass(color) {
  return STATUS_CLASSES[color] || STATUS_CLASSES.red;
}

function splitDisplayList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSortableNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  const match = String(value).trim().match(/-?\d+(?:[,.]\d+)?/);
  if (!match) {
    return null;
  }
  const parsed = Number(match[0].replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
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
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * multiplier;
  }
  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function searchableFieldValues(item) {
  return [
    item.cod_odp,
    item.cdq,
    item.colata,
    item.cod_art,
    item.codice_registro,
    item.data_registro,
    item.status_color,
    STATUS_LABELS[item.status_color],
    item.status_message,
    item.esolver_status,
    STATUS_LABELS[item.esolver_status],
    item.esolver_message,
    item.esolver_cliente,
    item.esolver_cod_f3,
    item.esolver_ordine_cliente,
    item.esolver_conferma_ordine,
    item.esolver_ddt,
    item.esolver_qta_totale,
    ...(item.status_details || []),
    ...(item.cod_lotti || []),
    item.qta_totale,
    item.lotti_count,
    ...(item.matching_row_ids || []),
    ...(item.certificates || []).flatMap((certificate) => [
      certificate.cdq,
      certificate.colata,
      certificate.cod_art,
      certificate.status_color,
      STATUS_LABELS[certificate.status_color],
      certificate.status_message,
      ...(certificate.status_details || []),
    ]),
  ]
    .filter((value) => value !== null && value !== undefined && value !== "")
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

function taglioSortValue(item, field) {
  switch (field) {
    case "status":
      return STATUS_SORT_RANK[item.status_color] || 0;
    case "cod_odp":
      return item.cod_odp || "";
    case "cdq":
      return item.cdq || "";
    case "colata":
      return item.colata || "";
    case "cod_art":
      return item.cod_art || "";
    case "qta_totale":
      return parseSortableNumber(item.qta_totale);
    case "lotti_count":
      return parseSortableNumber(item.lotti_count);
    case "codice_registro":
      return item.codice_registro || "";
    case "data_registro":
      return item.data_registro || "";
    case "status_message":
      return item.status_message || "";
    case "matching_rows":
      return item.matching_row_ids?.length || 0;
    case "esolver_status":
      return STATUS_SORT_RANK[item.esolver_status] || 0;
    case "esolver_cliente":
      return item.esolver_cliente || "";
    case "esolver_cod_f3":
      return item.esolver_cod_f3 || "";
    case "esolver_ddt":
      return item.esolver_ddt || "";
    case "esolver_qta_totale":
      return parseSortableNumber(item.esolver_qta_totale);
    default:
      return null;
  }
}

function SortableHeader({ field, label, onSort, sortConfig }) {
  const isActive = sortConfig.field === field;
  const indicator = !isActive ? "" : sortConfig.direction === "asc" ? "↑" : "↓";
  return (
    <th className="px-3 py-3">
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

export default function QuartaTaglioPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const initialListStateRef = useRef(loadPersistedListState());
  const [items, setItems] = useState([]);
  const [syncRun, setSyncRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [queryOne, setQueryOne] = useState(initialListStateRef.current.queryOne);
  const [queryTwo, setQueryTwo] = useState(initialListStateRef.current.queryTwo);
  const [queryThree, setQueryThree] = useState(initialListStateRef.current.queryThree);
  const [operatorOne, setOperatorOne] = useState(initialListStateRef.current.operatorOne);
  const [operatorTwo, setOperatorTwo] = useState(initialListStateRef.current.operatorTwo);
  const [rowLimit, setRowLimit] = useState(initialListStateRef.current.rowLimit);
  const [sortConfig, setSortConfig] = useState(initialListStateRef.current.sortConfig);
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 0, viewportWidth: 0 });
  const topScrollRef = useRef(null);
  const tableViewportRef = useRef(null);
  const tableRef = useRef(null);
  const syncingScrollRef = useRef(false);
  const restoredScrollRef = useRef(false);
  const sectionRef = useRef(null);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    apiRequest("/quarta-taglio", {}, token)
      .then((data) => {
        if (!ignore) {
          setItems(data.items || []);
          setSyncRun(data.sync_run || null);
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

  useEffect(() => {
    const viewport = tableViewportRef.current;
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    savePersistedListState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      sortConfig,
      scrollLeft: viewport ? viewport.scrollLeft : initialListStateRef.current.scrollLeft,
      scrollTop: viewport ? viewport.scrollTop : initialListStateRef.current.scrollTop,
      windowScrollY: pageScroller?.scrollTop || 0,
    });
  }, [operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rowLimit, sortConfig]);

  useEffect(() => {
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    function handlePageScroll() {
      const currentState = loadPersistedListState();
      savePersistedListState({
        ...currentState,
        windowScrollY: pageScroller?.scrollTop || 0,
      });
    }

    pageScroller?.addEventListener("scroll", handlePageScroll, { passive: true });
    return () => pageScroller?.removeEventListener("scroll", handlePageScroll);
  }, []);

  const visibleItems = useMemo(() => {
    let nextItems = items;
    if (queryOne.trim() || queryTwo.trim() || queryThree.trim()) {
      nextItems = nextItems.filter((item) => {
        const baseValues = searchableFieldValues(item);
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
        const byDate = compareValues(left.data_registro || "", right.data_registro || "", "desc");
        return byDate || compareValues(left.cod_odp || "", right.cod_odp || "", "asc") || compareValues(left.cdq || "", right.cdq || "", "asc");
      }
      const sorted = compareValues(taglioSortValue(left, sortConfig.field), taglioSortValue(right, sortConfig.field), sortConfig.direction);
      return sorted || compareValues(left.cod_odp || "", right.cod_odp || "", "asc") || compareValues(left.cdq || "", right.cdq || "", "asc");
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

  const summary = useMemo(() => {
    const ol = new Set(items.map((item) => item.cod_odp));
    return {
      total: items.length,
      ol: ol.size,
      cdq: items.reduce((total, item) => total + (item.certificates?.length || splitDisplayList(item.cdq).length), 0),
      green: items.filter((item) => item.status_color === "green").length,
      yellow: items.filter((item) => item.status_color === "yellow").length,
      red: items.filter((item) => item.status_color === "red").length,
    };
  }, [items]);

  useEffect(() => {
    function updateScrollMetrics() {
      const viewport = tableViewportRef.current;
      const table = tableRef.current;
      if (!viewport || !table) {
        return;
      }
      setScrollMetrics({
        contentWidth: table.scrollWidth,
        viewportWidth: viewport.clientWidth,
      });
    }

    updateScrollMetrics();

    const viewport = tableViewportRef.current;
    const table = tableRef.current;
    let observer = null;
    if (typeof ResizeObserver !== "undefined" && viewport && table) {
      observer = new ResizeObserver(updateScrollMetrics);
      observer.observe(viewport);
      observer.observe(table);
    }
    window.addEventListener("resize", updateScrollMetrics);
    return () => {
      window.removeEventListener("resize", updateScrollMetrics);
      observer?.disconnect();
    };
  }, [displayedItems.length, visibleItems.length]);

  useEffect(() => {
    if (loading || restoredScrollRef.current) {
      return;
    }
    const viewport = tableViewportRef.current;
    const topScroll = topScrollRef.current;
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    if (!viewport) {
      return;
    }
    const { scrollLeft, scrollTop, windowScrollY } = initialListStateRef.current;
    window.requestAnimationFrame(() => {
      viewport.scrollLeft = scrollLeft || 0;
      viewport.scrollTop = scrollTop || 0;
      if (topScroll) {
        topScroll.scrollLeft = scrollLeft || 0;
      }
      if (pageScroller) {
        pageScroller.scrollTop = windowScrollY || 0;
      }
      restoredScrollRef.current = true;
    });
  }, [loading, displayedItems.length]);

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
    const currentState = loadPersistedListState();
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    savePersistedListState({
      ...currentState,
      scrollLeft: source.scrollLeft,
      scrollTop: tableViewportRef.current ? tableViewportRef.current.scrollTop : currentState.scrollTop,
      windowScrollY: pageScroller?.scrollTop || currentState.windowScrollY || 0,
    });
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  function persistCurrentListState() {
    const viewport = tableViewportRef.current;
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    savePersistedListState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      sortConfig,
      scrollLeft: viewport?.scrollLeft || 0,
      scrollTop: viewport?.scrollTop || 0,
      windowScrollY: pageScroller?.scrollTop || 0,
    });
  }

  function openDetail(codOdp) {
    if (codOdp) {
      persistCurrentListState();
      navigate(`/quarta-taglio/${encodeURIComponent(codOdp)}`);
    }
  }

  return (
    <section className="space-y-3" ref={sectionRef}>
      <div className="flex flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Certificazione</p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-950">OL taglio saldati</h2>
          <p className="mt-1 text-sm text-slate-500">
            Aggiornamento automatico da Quarta all'apertura pagina. Le righe Incoming Quality restano in sola lettura.
          </p>
        </div>
        <div className="flex flex-col gap-2 text-sm text-slate-500 xl:items-end">
          <div>{syncRun?.finished_at ? `Ultimo aggiornamento ${formatDateTime(syncRun.finished_at)}` : "Aggiornamento in corso"}</div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            <span className="font-semibold text-ink">{displayedItems.length}</span> righe visibili
            {displayedItems.length !== visibleItems.length ? <span className="ml-2 text-slate-500">su {visibleItems.length}</span> : null}
          </div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-5">
        <SummaryCell label="OL" value={summary.ol} />
        <SummaryCell label="CDQ" value={summary.cdq} />
        <SummaryCell label="Verdi" value={summary.green} />
        <SummaryCell label="Gialli" value={summary.yellow} />
        <SummaryCell label="Rossi" value={summary.red} />
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <LegendCell color="green" title="Verde" text="CDQ presente, colata coerente, iter completo e qualità accettata." />
        <LegendCell color="yellow" title="Giallo" text="CDQ presente ma manca match, chimica, proprietà, note o qualità; include accettato con riserva." />
        <LegendCell color="red" title="Rosso" text="CDQ mancante, colata diversa o qualità respinta." />
      </div>

      <div className="flex items-end gap-2 overflow-x-auto pb-1">
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-search-1">
            Filtro 1
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quarta-taglio-search-1"
            onChange={(event) => setQueryOne(event.target.value)}
            placeholder="Tutti i campi"
            value={queryOne}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-operator-1">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quarta-taglio-operator-1"
            onChange={(event) => setOperatorOne(event.target.value)}
            value={operatorOne}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-search-2">
            Filtro 2
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quarta-taglio-search-2"
            onChange={(event) => setQueryTwo(event.target.value)}
            placeholder="Campi non presi dal 1"
            value={queryTwo}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-operator-2">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quarta-taglio-operator-2"
            onChange={(event) => setOperatorTwo(event.target.value)}
            value={operatorTwo}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-search-3">
            Filtro 3
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quarta-taglio-search-3"
            onChange={(event) => setQueryThree(event.target.value)}
            placeholder="Campi non presi da 1 e 2"
            value={queryThree}
          />
        </div>
        <div className="ml-auto min-w-[88px] max-w-[88px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-taglio-row-limit">
            Righe
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quarta-taglio-row-limit"
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

      {loading ? <p className="text-sm text-slate-500">Aggiornamento da Quarta in corso...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {syncRun?.status === "error" ? <p className="text-sm text-rose-600">{syncRun.message}</p> : null}

      <div className="sticky top-0 z-20 rounded-xl border border-border bg-slate-50 px-3 py-2 shadow-sm">
        <div
          className="incoming-top-scroll overflow-x-auto overflow-y-hidden"
          onScroll={(event) => syncScroll(tableViewportRef.current, event.currentTarget)}
          ref={topScrollRef}
        >
          <div
            className="h-4 min-w-full"
            style={{
              width: Math.max(scrollMetrics.contentWidth, scrollMetrics.viewportWidth),
            }}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border bg-white">
        <div
          className="incoming-grid-scroll overflow-x-hidden overflow-y-visible"
          onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
          ref={tableViewportRef}
        >
          <table className="min-w-[2320px] divide-y divide-slate-200 text-sm" ref={tableRef}>
            <thead className="bg-slate-50">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                <SortableHeader field="status" label="Stato" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cod_odp" label="OL" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cdq" label="CDQ" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="colata" label="Colata" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="esolver_cod_f3" label="Cod. F3" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="qta_totale" label="Qta" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="lotti_count" label="Lotti" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="codice_registro" label="Registro" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="data_registro" label="Data registro" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="esolver_status" label="eSolver" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="esolver_cliente" label="Cliente" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="esolver_ddt" label="DDT" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="esolver_qta_totale" label="Qta DDT" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="status_message" label="Motivo" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="matching_rows" label="Righe app" onSort={toggleSort} sortConfig={sortConfig} />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedItems.map((item) => (
                <tr
                  className="cursor-pointer align-top hover:bg-slate-50/70"
                  key={item.id}
                  onClick={() => openDetail(item.cod_odp)}
                  title={`Apri certificato OL ${item.cod_odp}`}
                >
                  <td className="px-3 py-2.5">
                    <span className={`inline-flex min-w-[74px] justify-center rounded-lg border px-2.5 py-1 text-xs font-semibold ${statusClass(item.status_color)}`}>
                      {STATUS_LABELS[item.status_color] || "Rosso"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 font-semibold">
                    <Link
                      className="text-accent hover:underline"
                      onClick={(event) => {
                        event.stopPropagation();
                        persistCurrentListState();
                      }}
                      to={`/quarta-taglio/${encodeURIComponent(item.cod_odp)}`}
                    >
                      {item.cod_odp}
                    </Link>
                  </td>
                  <td className="min-w-[260px] max-w-[320px] px-3 py-2.5 font-semibold text-slate-800">
                    {item.certificates?.length ? (
                      <div className="flex flex-wrap gap-1.5">
                        {item.certificates.map((certificate) => (
                          <span
                            className={`inline-flex rounded-lg border px-2 py-1 text-xs font-semibold ${statusClass(certificate.status_color)}`}
                            key={`${item.id}-${certificate.cdq}-${certificate.colata || ""}`}
                            title={certificate.status_message}
                          >
                            {certificate.cdq}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="whitespace-normal break-words">{item.cdq}</div>
                    )}
                  </td>
                  <td className="min-w-[180px] max-w-[240px] px-3 py-2.5 text-slate-700">
                    <div className="whitespace-normal break-words">{item.colata || "-"}</div>
                  </td>
                  <td className="min-w-[180px] max-w-[240px] px-3 py-2.5 text-slate-700">
                    <div className="whitespace-normal break-words font-medium">{item.esolver_cod_f3 || "-"}</div>
                    {item.cod_art ? <div className="mt-1 text-xs text-slate-500">Quarta: {item.cod_art}</div> : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-slate-700">{formatNumber(item.qta_totale)}</td>
                  <td className="px-3 py-2.5 text-slate-700">
                    <div className="font-medium">{item.lotti_count}</div>
                    <div className="mt-1 max-w-[260px] truncate text-xs text-slate-500" title={(item.cod_lotti || []).join(", ")}>
                      {(item.cod_lotti || []).join(", ") || "-"}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 font-medium text-slate-700">{item.codice_registro}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-slate-700">{formatDateTime(item.data_registro)}</td>
                  <td className="min-w-[160px] px-3 py-2.5">
                    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-semibold ${statusClass(item.esolver_status || "not_checked")}`}>
                      {STATUS_LABELS[item.esolver_status] || item.esolver_status || "Non controllato"}
                    </span>
                    {item.esolver_message ? <div className="mt-1 text-xs text-slate-500">{item.esolver_message}</div> : null}
                  </td>
                  <td className="min-w-[220px] max-w-[300px] px-3 py-2.5 text-slate-700">
                    <div className="whitespace-normal break-words">{item.esolver_cliente || "-"}</div>
                  </td>
                  <td className="min-w-[150px] max-w-[220px] px-3 py-2.5 text-slate-700">
                    <div className="whitespace-normal break-words">{item.esolver_ddt || "-"}</div>
                    {item.esolver_ordine_cliente ? <div className="mt-1 text-xs text-slate-500">Ord. {item.esolver_ordine_cliente}</div> : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-slate-700">{formatNumber(item.esolver_qta_totale)}</td>
                  <td className="min-w-[300px] px-3 py-2.5 text-slate-700">
                    <div className="font-medium">{item.status_message}</div>
                    {item.status_details?.length ? (
                      <div className="mt-1 space-y-0.5 text-xs text-slate-500">
                        {item.status_details.map((detail) => (
                          <div key={detail}>{detail}</div>
                        ))}
                      </div>
                    ) : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-slate-700">
                    {item.matching_row_ids?.length
                      ? item.matching_row_ids.map((rowId) => (
                          <Link
                            className="mr-2 font-semibold text-accent hover:underline"
                            key={rowId}
                            onClick={(event) => {
                              event.stopPropagation();
                              persistCurrentListState();
                            }}
                            to={`/acquisition/${rowId}`}
                          >
                            #{rowId}
                          </Link>
                        ))
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !visibleItems.length && !error ? <div className="px-4 py-6 text-sm text-slate-500">Nessun OL taglio saldato trovato.</div> : null}
      </div>
    </section>
  );
}

function SummaryCell({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-white px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function LegendCell({ color, title, text }) {
  return (
    <div className={`rounded-lg border px-3 py-2 ${statusClass(color)}`}>
      <div className="text-sm font-semibold">{title}</div>
      <div className="mt-1 text-xs leading-5 opacity-85">{text}</div>
    </div>
  );
}
