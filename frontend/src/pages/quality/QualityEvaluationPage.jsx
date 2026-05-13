import { useEffect, useMemo, useRef, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { formatRowFieldDisplay } from "../acquisition/fieldFormatting";

const EVALUATION_OPTIONS = [
  { value: "", label: "Da valutare" },
  { value: "accettato", label: "Accettato" },
  { value: "accettato_con_riserva", label: "Accettato con riserva" },
  { value: "respinto", label: "Respinto" },
];

const EVALUATION_SORT_RANK = {
  "": 0,
  accettato: 1,
  accettato_con_riserva: 2,
  respinto: 3,
};

const EDITABLE_FIELDS = [
  "qualita_data_ricezione",
  "qualita_data_accettazione",
  "qualita_data_richiesta",
  "qualita_numero_analisi",
];

const AUTOSAVE_DELAY_MS = 800;
const AUTOSAVE_SAVED_FEEDBACK_MS = 1200;
const LIST_STATE_STORAGE_KEY = "certi_nt.quality_evaluation_list_state.v1";
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

function textValue(value) {
  return String(value ?? "");
}

function cellKey(rowId, field) {
  return `${rowId}:${field}`;
}

function composeLega(row) {
  return [row.lega_base, row.variante_lega || row.lega_designazione].filter(Boolean).join(" ") || "-";
}

function isRowChanged(row, draft) {
  return EDITABLE_FIELDS.some((field) => textValue(row[field]) !== textValue(draft[field]));
}

function fieldClass({ changed = false, review = false, status = "" } = {}) {
  if (status === "error") {
    return "border-rose-400 bg-rose-50 text-rose-900";
  }
  if (status === "saving") {
    return "border-sky-300 bg-sky-50 text-slate-900";
  }
  if (status === "saved") {
    return "border-emerald-300 bg-emerald-50 text-slate-900";
  }
  if (review) {
    return "border-rose-300 bg-rose-50 text-rose-900";
  }
  if (changed) {
    return "border-amber-300 bg-amber-50 text-ink";
  }
  return "border-slate-200 bg-white text-ink";
}

function buildDraft(row) {
  return Object.fromEntries(EDITABLE_FIELDS.map((field) => [field, row[field] ?? ""]));
}

function payloadValue(value) {
  return value === "" ? null : value;
}

function autosaveTitle(cellState) {
  if (!cellState) {
    return undefined;
  }
  if (cellState.status === "saving") {
    return "Salvataggio automatico...";
  }
  if (cellState.status === "saved") {
    return "Salvato";
  }
  return cellState.message || "Errore salvataggio automatico";
}

function mergeSavedQualityField(row, updatedRow, field) {
  return {
    ...row,
    [field]: updatedRow[field],
    qualita_numero_analisi_da_ricontrollare: updatedRow.qualita_numero_analisi_da_ricontrollare,
    qualita_note_da_ricontrollare: updatedRow.qualita_note_da_ricontrollare,
    updated_at: updatedRow.updated_at,
  };
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

function searchableFieldValues(row, draft) {
  return [
    row.id,
    row.fornitore_nome,
    row.lega_designazione,
    row.lega_base,
    row.variante_lega,
    row.diametro,
    row.cdq,
    row.colata,
    row.ddt,
    row.peso,
    row.ordine,
    draft.qualita_data_ricezione,
    draft.qualita_data_accettazione,
    draft.qualita_data_richiesta,
    draft.qualita_numero_analisi,
    row.qualita_valutazione,
    row.qualita_note,
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

function qualitySortValue(row, draft, field) {
  switch (field) {
    case "id":
      return row.id;
    case "data_ricezione":
      return draft.qualita_data_ricezione || "";
    case "data_accettazione":
      return draft.qualita_data_accettazione || "";
    case "fornitore":
      return row.fornitore_nome || "";
    case "lega":
      return composeLega(row);
    case "diametro":
      return parseSortableNumber(row.diametro);
    case "cdq":
      return row.cdq || "";
    case "colata":
      return row.colata || "";
    case "ddt":
      return row.ddt || "";
    case "peso":
      return parseSortableNumber(row.peso);
    case "ordine":
      return row.ordine || "";
    case "data_richiesta":
      return draft.qualita_data_richiesta || "";
    case "numero_analisi":
      return draft.qualita_numero_analisi || "";
    case "valutazione":
      return EVALUATION_SORT_RANK[row.qualita_valutazione || ""] ?? 99;
    case "note":
      return row.qualita_note || "";
    default:
      return null;
  }
}

function SortableHeader({ field, label, onSort, sortConfig }) {
  const isActive = sortConfig.field === field;
  const indicator = !isActive ? "↕" : sortConfig.direction === "asc" ? "↑" : "↓";
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

function LockedCell({ children, strong = false, wide = false }) {
  return (
    <div
      className={`truncate text-[14px] leading-tight text-slate-950 ${
        strong ? "font-semibold" : "font-medium"
      } ${wide ? "w-36" : "w-20"}`}
    >
      {children || "-"}
    </div>
  );
}

function SupplierCell({ row }) {
  return (
    <div className="w-36">
      <div className="truncate text-[14px] font-semibold leading-tight text-slate-950">{row.fornitore_nome || "-"}</div>
    </div>
  );
}

export default function QualityEvaluationPage() {
  const { token } = useAuth();
  const initialListStateRef = useRef(loadPersistedListState());
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [cellStates, setCellStates] = useState({});
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
  const latestDraftsRef = useRef({});
  const rowsRef = useRef([]);
  const saveTimersRef = useRef({});
  const savedFeedbackTimersRef = useRef({});
  const saveVersionsRef = useRef({});
  const inFlightCellsRef = useRef({});
  const queuedSavesRef = useRef({});

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest("/acquisition/quality-rows", {}, token);
      const nextRows = response.items || [];
      setRows(nextRows);
      setDrafts(Object.fromEntries(nextRows.map((row) => [row.id, buildDraft(row)])));
      setCellStates({});
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
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

  useEffect(() => {
    rowsRef.current = rows;
  }, [rows]);

  useEffect(() => {
    latestDraftsRef.current = drafts;
  }, [drafts]);

  useEffect(
    () => () => {
      Object.values(saveTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
      Object.values(savedFeedbackTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
    },
    [],
  );

  const changedRows = useMemo(
    () => rows.filter((row) => isRowChanged(row, drafts[row.id] || buildDraft(row))).length,
    [drafts, rows],
  );

  const visibleRows = useMemo(() => {
    let nextRows = rows;
    if (queryOne.trim() || queryTwo.trim() || queryThree.trim()) {
      nextRows = nextRows.filter((row) => {
        const draft = drafts[row.id] || buildDraft(row);
        const baseValues = searchableFieldValues(row, draft);
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

    return [...nextRows].sort((left, right) => {
      if (!sortConfig.field) {
        return right.id - left.id;
      }
      const leftDraft = drafts[left.id] || buildDraft(left);
      const rightDraft = drafts[right.id] || buildDraft(right);
      const sorted = compareValues(
        qualitySortValue(left, leftDraft, sortConfig.field),
        qualitySortValue(right, rightDraft, sortConfig.field),
        sortConfig.direction,
      );
      return sorted || right.id - left.id;
    });
  }, [drafts, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rows, sortConfig]);

  const displayedRows = useMemo(() => {
    if (rowLimit === "all") {
      return visibleRows;
    }

    const limit = Number(rowLimit);
    if (!Number.isFinite(limit) || limit <= 0) {
      return visibleRows;
    }

    return visibleRows.slice(0, limit);
  }, [rowLimit, visibleRows]);

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
  }, [displayedRows.length, rows.length]);

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
  }, [loading, displayedRows.length]);

  function setCellState(key, nextState) {
    setCellStates((current) => {
      if (!nextState) {
        const { [key]: _removed, ...rest } = current;
        return rest;
      }
      return {
        ...current,
        [key]: nextState,
      };
    });
  }

  function clearSavedFeedback(key, version) {
    window.clearTimeout(savedFeedbackTimersRef.current[key]);
    savedFeedbackTimersRef.current[key] = window.setTimeout(() => {
      if (saveVersionsRef.current[key] === version) {
        setCellState(key, null);
      }
    }, AUTOSAVE_SAVED_FEEDBACK_MS);
  }

  function updateDraft(rowId, field, value) {
    const next = {
      ...latestDraftsRef.current,
      [rowId]: {
        ...(latestDraftsRef.current[rowId] || {}),
        [field]: value,
      },
    };
    latestDraftsRef.current = next;
    setDrafts(next);
  }

  function queueQualityCellSave(rowId, field, value, delay = AUTOSAVE_DELAY_MS) {
    const key = cellKey(rowId, field);
    window.clearTimeout(saveTimersRef.current[key]);
    window.clearTimeout(savedFeedbackTimersRef.current[key]);

    const version = (saveVersionsRef.current[key] || 0) + 1;
    saveVersionsRef.current[key] = version;

    const currentRow = rowsRef.current.find((item) => item.id === rowId);
    const matchesSavedValue = currentRow && textValue(currentRow[field]) === textValue(value);
    if (matchesSavedValue && !inFlightCellsRef.current[key]) {
      setCellState(key, null);
      return;
    }

    saveTimersRef.current[key] = window.setTimeout(() => {
      void saveQualityCell(rowId, field, value, version, false);
    }, delay);
  }

  async function saveQualityCell(rowId, field, value, version, force) {
    const key = cellKey(rowId, field);
    window.clearTimeout(saveTimersRef.current[key]);
    if (saveVersionsRef.current[key] !== version) {
      return;
    }

    if (inFlightCellsRef.current[key]) {
      queuedSavesRef.current[key] = { rowId, field, value, version };
      return;
    }

    const currentRow = rowsRef.current.find((item) => item.id === rowId);
    if (!force && currentRow && textValue(currentRow[field]) === textValue(value)) {
      setCellState(key, null);
      return;
    }

    inFlightCellsRef.current[key] = true;
    setCellState(key, { status: "saving" });
    setError("");

    try {
      const updatedRow = await apiRequest(
        `/acquisition/quality-rows/${rowId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ [field]: payloadValue(value) }),
        },
        token,
      );

      if (saveVersionsRef.current[key] === version) {
        setRows((current) => {
          const next = current.map((row) => (row.id === rowId ? mergeSavedQualityField(row, updatedRow, field) : row));
          rowsRef.current = next;
          return next;
        });
        setDrafts((current) => {
          const currentDraft = current[rowId] || buildDraft(updatedRow);
          if (textValue(currentDraft[field]) !== textValue(value)) {
            return current;
          }
          const next = {
            ...current,
            [rowId]: {
              ...currentDraft,
              [field]: updatedRow[field] ?? "",
            },
          };
          latestDraftsRef.current = next;
          return next;
        });
        setCellState(key, { status: "saved" });
        clearSavedFeedback(key, version);
      }
    } catch (requestError) {
      if (saveVersionsRef.current[key] === version) {
        const message = requestError.message || "Errore salvataggio automatico";
        setCellState(key, { status: "error", message });
        setError(`Errore autosave riga #${rowId}: ${message}`);
      }
    } finally {
      inFlightCellsRef.current[key] = false;
      const queued = queuedSavesRef.current[key];
      if (queued) {
        delete queuedSavesRef.current[key];
        if (queued.version === saveVersionsRef.current[key]) {
          void saveQualityCell(queued.rowId, queued.field, queued.value, queued.version, true);
        }
      }
    }
  }

  function updateDraftAndAutosave(rowId, field, value, delay = AUTOSAVE_DELAY_MS) {
    updateDraft(rowId, field, value);
    queueQualityCellSave(rowId, field, value, delay);
  }

  function flushQualityCell(rowId, field) {
    const value = latestDraftsRef.current[rowId]?.[field] ?? "";
    queueQualityCellSave(rowId, field, value, 0);
  }

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

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8" ref={sectionRef}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Valutazione qualità</p>
          <h2 className="mt-2 text-2xl font-semibold">Conformità e valutazione qualità</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Registro delle sole righe completamente confermate. I campi di match sono bloccati; date e numero analisi sono gestiti qui. Valutazione e nota arrivano dalla validazione finale Incoming.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{displayedRows.length}</span> righe visibili
          {displayedRows.length !== visibleRows.length ? <span className="ml-2 text-slate-500">su {visibleRows.length}</span> : null}
          {changedRows ? <span className="ml-3 text-amber-700">{changedRows} modificate</span> : null}
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento valutazioni...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-8 flex items-end gap-2 overflow-x-auto pb-1">
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-search-1">
            Filtro 1
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quality-search-1"
            onChange={(event) => setQueryOne(event.target.value)}
            placeholder="Tutti i campi"
            value={queryOne}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-operator-1">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quality-operator-1"
            onChange={(event) => setOperatorOne(event.target.value)}
            value={operatorOne}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-search-2">
            Filtro 2
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quality-search-2"
            onChange={(event) => setQueryTwo(event.target.value)}
            placeholder="Campi non presi dal 1"
            value={queryTwo}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-operator-2">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quality-operator-2"
            onChange={(event) => setOperatorTwo(event.target.value)}
            value={operatorTwo}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-search-3">
            Filtro 3
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="quality-search-3"
            onChange={(event) => setQueryThree(event.target.value)}
            placeholder="Campi non presi da 1 e 2"
            value={queryThree}
          />
        </div>
        <div className="ml-auto min-w-[88px] max-w-[88px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quality-row-limit">
            Righe
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="quality-row-limit"
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

      <div className="mt-8 sticky top-0 z-20 rounded-xl border border-border bg-slate-50 px-3 py-2 shadow-sm">
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

      <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div
          className="incoming-grid-scroll overflow-x-hidden overflow-y-visible"
          onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
          ref={tableViewportRef}
        >
        <table className="min-w-[1360px] w-full border-collapse text-sm" ref={tableRef}>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-[0.16em] text-slate-500">
              <SortableHeader field="id" label="N°" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="data_ricezione" label="Data ricezione" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="data_accettazione" label="Data accettazione" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="fornitore" label="Fornitore" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="lega" label="Lega" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="diametro" label="Ø" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="cdq" label="Cdq" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="colata" label="Colata" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="ddt" label="Ddt" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="peso" label="Peso Kg" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="ordine" label="Vs. Odv" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="data_richiesta" label="Data richiesta" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="numero_analisi" label="N° analisi" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="valutazione" label="Valutazione" onSort={toggleSort} sortConfig={sortConfig} />
              <SortableHeader field="note" label="Note" onSort={toggleSort} sortConfig={sortConfig} />
            </tr>
          </thead>
          <tbody>
            {displayedRows.map((row) => {
              const draft = drafts[row.id] || buildDraft(row);
              return (
                <tr key={row.id} className="border-b border-slate-100 align-middle hover:bg-slate-50/70 last:border-0">
                  <td className="px-2 py-2 font-semibold text-slate-900">{row.id}</td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_data_ricezione) !== textValue(draft.qualita_data_ricezione),
                        status: cellStates[cellKey(row.id, "qualita_data_ricezione")]?.status,
                      })}`}
                      onBlur={() => flushQualityCell(row.id, "qualita_data_ricezione")}
                      onChange={(event) => updateDraftAndAutosave(row.id, "qualita_data_ricezione", event.target.value, 300)}
                      title={autosaveTitle(cellStates[cellKey(row.id, "qualita_data_ricezione")])}
                      type="date"
                      value={draft.qualita_data_ricezione || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_data_accettazione) !== textValue(draft.qualita_data_accettazione),
                        status: cellStates[cellKey(row.id, "qualita_data_accettazione")]?.status,
                      })}`}
                      onBlur={() => flushQualityCell(row.id, "qualita_data_accettazione")}
                      onChange={(event) => updateDraftAndAutosave(row.id, "qualita_data_accettazione", event.target.value, 300)}
                      title={autosaveTitle(cellStates[cellKey(row.id, "qualita_data_accettazione")])}
                      type="date"
                      value={draft.qualita_data_accettazione || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <SupplierCell row={row} />
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{composeLega(row)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{formatRowFieldDisplay("diametro", row.diametro)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell strong>{formatRowFieldDisplay("cdq", row.cdq)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{formatRowFieldDisplay("colata", row.colata)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{formatRowFieldDisplay("ddt", row.ddt)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{formatRowFieldDisplay("peso", row.peso)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell>{formatRowFieldDisplay("ordine", row.ordine)}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_data_richiesta) !== textValue(draft.qualita_data_richiesta),
                        status: cellStates[cellKey(row.id, "qualita_data_richiesta")]?.status,
                      })}`}
                      onBlur={() => flushQualityCell(row.id, "qualita_data_richiesta")}
                      onChange={(event) => updateDraftAndAutosave(row.id, "qualita_data_richiesta", event.target.value, 300)}
                      title={autosaveTitle(cellStates[cellKey(row.id, "qualita_data_richiesta")])}
                      type="date"
                      value={draft.qualita_data_richiesta || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-24 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_numero_analisi) !== textValue(draft.qualita_numero_analisi),
                        review: row.qualita_numero_analisi_da_ricontrollare,
                        status: cellStates[cellKey(row.id, "qualita_numero_analisi")]?.status,
                      })}`}
                      onBlur={() => flushQualityCell(row.id, "qualita_numero_analisi")}
                      onChange={(event) => updateDraftAndAutosave(row.id, "qualita_numero_analisi", event.target.value)}
                      title={autosaveTitle(cellStates[cellKey(row.id, "qualita_numero_analisi")])}
                      value={draft.qualita_numero_analisi || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell wide>{EVALUATION_OPTIONS.find((option) => option.value === row.qualita_valutazione)?.label || "Da valutare"}</LockedCell>
                  </td>
                  <td className="px-2 py-2">
                    <LockedCell wide>{row.qualita_note}</LockedCell>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
        {!loading && rows.length === 0 ? (
          <p className="px-5 py-8 text-sm text-slate-500">Nessuna riga completamente confermata disponibile per la valutazione qualità.</p>
        ) : null}
      </div>
    </section>
  );
}
