import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest, resolveApiAssetUrl } from "../../app/api";
import { canGenerateFinalCertificatePdf, canReopenQualityFlow } from "../../app/access";
import { useAuth } from "../../app/auth";

const STATUS_LABELS = {
  draft: "Word aperto",
  pdf_final: "PDF chiuso",
};

const CONFORMITY_LABELS = {
  conforme: "Conforme",
  non_conforme: "Non conforme",
  da_verificare: "Da verificare",
};

const LIST_STATE_STORAGE_KEY = "certi_nt.quarta_taglio_certificate_register_state.v1";
const VISIBLE_REFRESH_CHUNK_SIZE = 50;
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
  const statusLabel = registerStatusLabel(item);
  return [
    item.certificate_number,
    item.cdq,
    item.cod_odp,
    item.lega_cod_f3,
    item.cod_f3,
    item.ddt,
    item.ordine_cliente,
    item.cdo_lega,
    item.fornitore_cliente,
    item.status,
    statusLabel,
    item.word_source_label,
    item.conformity_status,
    CONFORMITY_LABELS[item.conformity_status],
    ...(item.conformity_issues || []).map((issue) => `${issue.block} ${issue.field} ${issue.message || ""}`),
  ]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());
}

function hasInheritedWord(item) {
  return item.has_word && item.word_source === "inherited";
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
    return direction === "asc" ? -1 : 1;
  }
  if (rightEmpty) {
    return direction === "asc" ? 1 : -1;
  }
  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function registerStatusSortValue(item) {
  if (item.status === "pdf_final" && item.has_pdf) {
    return 10;
  }
  if (item.ddt && hasInheritedWord(item) && !item.has_pdf) {
    return 30;
  }
  if (item.ddt && item.has_word && !item.has_pdf) {
    return 20;
  }
  if (!item.ddt) {
    return 40;
  }
  return 90;
}

function registerFileSortValue(item) {
  if (item.has_word && item.has_pdf && item.status === "pdf_final") {
    return 10;
  }
  if (item.has_word && item.ddt && !item.has_pdf && !hasInheritedWord(item)) {
    return 20;
  }
  if (hasInheritedWord(item)) {
    return 30;
  }
  if (item.has_word) {
    return 40;
  }
  return 90;
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
    case "ddt":
      return item.ddt || "";
    case "ordine_cliente":
      return item.ordine_cliente || "";
    case "cdo_lega":
      return item.cdo_lega || "";
    case "quantita":
      return item.quantita || "";
    case "fornitore_cliente":
      return item.fornitore_cliente || "";
    case "status":
      return registerStatusSortValue(item);
    case "conformity":
      return normalizedConformityStatus(item.conformity_status);
    case "file":
      return registerFileSortValue(item);
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

function registerStatusLabel(item) {
  if (item.status === "pdf_final") {
    return STATUS_LABELS.pdf_final;
  }
  if (item.ddt && hasInheritedWord(item) && !item.has_pdf) {
    return "PDF da generare - Word ereditato";
  }
  if (!item.ddt && hasInheritedWord(item)) {
    return "Word ereditato - attesa DDT";
  }
  if (item.ddt && item.has_word && !item.has_pdf) {
    return "PDF da generare";
  }
  if (!item.ddt) {
    return "In attesa DDT";
  }
  return STATUS_LABELS[item.status] || item.status;
}

function statusClass(item) {
  if (item.status === "pdf_final") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (hasInheritedWord(item)) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (item.ddt && item.has_word && !item.has_pdf) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (!item.ddt) {
    return "border-sky-200 bg-sky-50 text-sky-800";
  }
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function conformityClass(status) {
  const normalizedStatus = normalizedConformityStatus(status);
  if (normalizedStatus === "conforme") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (normalizedStatus === "non_conforme") {
    return "border-rose-300 bg-rose-50 text-rose-800";
  }
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function normalizedConformityStatus(status) {
  return status === "conforme" || status === "non_conforme" ? status : "da_verificare";
}

function conformityTitle(item) {
  const issues = item.conformity_issues || [];
  if (!issues.length) {
    return CONFORMITY_LABELS[normalizedConformityStatus(item.conformity_status)];
  }
  return issues.map((issue) => `${issue.block}: ${issue.field} ${issue.message || ""}`).join(" | ");
}

export default function QuartaTaglioCertificatesRegisterPage() {
  const { token, user } = useAuth();
  const initialListStateRef = useRef(loadPersistedListState());
  const [items, setItems] = useState([]);
  const [queryOne, setQueryOne] = useState(initialListStateRef.current.queryOne);
  const [queryTwo, setQueryTwo] = useState(initialListStateRef.current.queryTwo);
  const [queryThree, setQueryThree] = useState(initialListStateRef.current.queryThree);
  const [operatorOne, setOperatorOne] = useState(initialListStateRef.current.operatorOne);
  const [operatorTwo, setOperatorTwo] = useState(initialListStateRef.current.operatorTwo);
  const [rowLimit, setRowLimit] = useState(initialListStateRef.current.rowLimit);
  const [sortConfig, setSortConfig] = useState(initialListStateRef.current.sortConfig);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [visibleRefreshState, setVisibleRefreshState] = useState({ status: "idle", done: 0, total: 0, message: "" });
  const [pdfDialogItem, setPdfDialogItem] = useState(null);
  const [reopenDialogItem, setReopenDialogItem] = useState(null);
  const [reopenReason, setReopenReason] = useState("");
  const [actionState, setActionState] = useState({ status: "idle", message: "" });
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 0, viewportWidth: 0 });
  const sectionRef = useRef(null);
  const topScrollRef = useRef(null);
  const tableViewportRef = useRef(null);
  const tableRef = useRef(null);
  const syncingScrollRef = useRef(false);
  const restoredScrollRef = useRef(false);
  const lastVisibleRefreshSignatureRef = useRef("");

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

  const visibleRefreshIds = useMemo(
    () =>
      displayedItems
        .filter((item) => item.has_word && !item.has_pdf && item.status !== "pdf_final")
        .map((item) => item.id),
    [displayedItems],
  );

  useEffect(() => {
    if (loading || !token || !visibleRefreshIds.length) {
      return undefined;
    }
    const signature = visibleRefreshIds.join("|");
    if (signature === lastVisibleRefreshSignatureRef.current) {
      return undefined;
    }
    lastVisibleRefreshSignatureRef.current = signature;
    let ignore = false;

    async function refreshVisibleItems() {
      const chunks = [];
      for (let index = 0; index < visibleRefreshIds.length; index += VISIBLE_REFRESH_CHUNK_SIZE) {
        chunks.push(visibleRefreshIds.slice(index, index + VISIBLE_REFRESH_CHUNK_SIZE));
      }
      setVisibleRefreshState({ status: "refreshing", done: 0, total: visibleRefreshIds.length, message: "" });
      let done = 0;
      try {
        for (const chunk of chunks) {
          const response = await apiRequest(
            "/quarta-taglio/certificates/register/refresh-visible",
            {
              method: "POST",
              body: JSON.stringify(chunk),
            },
            token,
          );
          if (ignore) {
            return;
          }
          const updatedItems = response.items || [];
          if (updatedItems.length) {
            setItems((currentItems) => {
              const updatedById = new Map(updatedItems.map((item) => [item.id, item]));
              return currentItems.map((item) => updatedById.get(item.id) || item);
            });
          }
          done += chunk.length;
          setVisibleRefreshState({
            status: "refreshing",
            done: Math.min(done, visibleRefreshIds.length),
            total: visibleRefreshIds.length,
            message: "",
          });
        }
        if (!ignore) {
          setVisibleRefreshState({
            status: "done",
            done: visibleRefreshIds.length,
            total: visibleRefreshIds.length,
            message: "Dati visibili aggiornati.",
          });
        }
      } catch (requestError) {
        if (!ignore) {
          setVisibleRefreshState({
            status: "error",
            done,
            total: visibleRefreshIds.length,
            message: requestError.message,
          });
        }
      }
    }

    refreshVisibleItems();
    return () => {
      ignore = true;
    };
  }, [loading, token, visibleRefreshIds]);

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

  function updateRegisterItem(updatedItem) {
    setItems((currentItems) => currentItems.map((item) => (item.id === updatedItem.id ? updatedItem : item)));
  }

  async function handleGeneratePdf(item) {
    setActionState({ status: "saving", message: "" });
    setActionMessage("");
    try {
      const updatedItem = await apiRequest(`/quarta-taglio/certificates/${item.id}/pdf`, { method: "POST" }, token);
      updateRegisterItem(updatedItem);
      setPdfDialogItem(null);
      setActionMessage(`PDF generato per il certificato ${updatedItem.certificate_number}.`);
    } catch (requestError) {
      setActionState({ status: "error", message: requestError.message });
      return;
    }
    setActionState({ status: "idle", message: "" });
  }

  async function handleReopenPdf(item) {
    const reason = reopenReason.trim();
    if (!reason) {
      setActionState({ status: "error", message: "Inserisci il motivo della riapertura." });
      return;
    }
    setActionState({ status: "saving", message: "" });
    setActionMessage("");
    try {
      const updatedItem = await apiRequest(
        `/quarta-taglio/certificates/${item.id}/reopen`,
        {
          method: "POST",
          body: JSON.stringify({ reason }),
        },
        token,
      );
      updateRegisterItem(updatedItem);
      setReopenDialogItem(null);
      setReopenReason("");
      setActionMessage(`Certificato ${updatedItem.certificate_number} riaperto.`);
    } catch (requestError) {
      setActionState({ status: "error", message: requestError.message });
      return;
    }
    setActionState({ status: "idle", message: "" });
  }

  const canGeneratePdf = canGenerateFinalCertificatePdf(user);
  const canReopenPdf = canReopenQualityFlow(user);

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8" ref={sectionRef}>
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

      {visibleRefreshState.status === "refreshing" ? (
        <p className="mt-3 text-sm text-slate-500">
          Aggiornamento dati eSolver/Quarta visibili: {visibleRefreshState.done} / {visibleRefreshState.total} righe.
        </p>
      ) : null}
      {visibleRefreshState.status === "error" ? (
        <p className="mt-3 text-sm text-amber-700">
          Aggiornamento dati visibili non completato: {visibleRefreshState.message}
        </p>
      ) : null}

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento registro certificati...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

      <div className="sticky top-0 z-20 mt-8 rounded-xl border border-border bg-slate-50 px-3 py-2 shadow-sm">
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

      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div
          className="incoming-grid-scroll overflow-x-auto"
          onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
          ref={tableViewportRef}
        >
          <table className="min-w-[1540px] w-full border-collapse text-sm" ref={tableRef}>
            <thead className="sticky-list-head">
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
                <SortableHeader field="certificate_number" label="Cert. Nr." onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cert_date" label="Data" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cdq" label="CDQ" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cod_odp" label="OL" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="lega_cod_f3" label="Cod. F3" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="ddt" label="DDT" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="ordine_cliente" label="Ordine" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cdo_lega" label="C.d.O." onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="quantita" label="Quantità" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="fornitore_cliente" label="Cliente" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="conformity" label="Conformità" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="status" label="Stato" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="file" label="File" onSort={toggleSort} sortConfig={sortConfig} />
                <th className="px-4 py-3">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {displayedItems.map((item) => (
                <tr className="border-b border-slate-100 align-middle hover:bg-slate-50/70 last:border-0" key={item.id}>
                  <td className="px-4 py-3 font-semibold text-slate-950">{item.certificate_number}</td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(item.cert_date || item.created_at)}</td>
                  <td className="px-4 py-3 font-semibold text-slate-800">{item.cdq || "-"}</td>
                  <td className="px-4 py-3">
                    <Link
                      className="font-semibold text-accent hover:underline"
                      onClick={persistCurrentListState}
                      to={`/quarta-taglio/${encodeURIComponent(item.cod_odp)}?certificateId=${encodeURIComponent(item.id)}`}
                    >
                      {item.cod_odp}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.lega_cod_f3 || "-"}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.ddt || "-"}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.ordine_cliente || "-"}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.cdo_lega || "-"}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{item.quantita ? Number(item.quantita).toLocaleString("it-IT") : "-"}</td>
                  <td className="px-4 py-3 text-slate-700">{item.fornitore_cliente || "-"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-semibold ${conformityClass(item.conformity_status)}`}
                      title={conformityTitle(item)}
                    >
                      {normalizedConformityStatus(item.conformity_status) === "non_conforme" ? "! " : ""}
                      {CONFORMITY_LABELS[normalizedConformityStatus(item.conformity_status)]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-semibold ${statusClass(item)}`}>
                      {registerStatusLabel(item)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {item.word_download_url ? (
                      <a
                        className="font-semibold text-accent hover:underline"
                        href={resolveApiAssetUrl(item.word_download_url)}
                        onClick={persistCurrentListState}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Word
                      </a>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                    {item.pdf_download_url ? (
                      <a
                        className="ml-3 font-semibold text-emerald-700 hover:underline"
                        href={resolveApiAssetUrl(item.pdf_download_url)}
                        onClick={persistCurrentListState}
                        rel="noreferrer"
                        target="_blank"
                      >
                        PDF
                      </a>
                    ) : canGeneratePdf && item.ddt && item.has_word && !item.has_pdf ? (
                      <button
                        className="ml-3 font-semibold text-accent hover:underline"
                        onClick={() => {
                          persistCurrentListState();
                          setActionState({ status: "idle", message: "" });
                          setPdfDialogItem(item);
                        }}
                        type="button"
                      >
                        PDF
                      </button>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    {canReopenPdf && item.status === "pdf_final" && item.has_pdf ? (
                      <button
                        className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 transition hover:border-amber-300"
                        onClick={() => {
                          persistCurrentListState();
                          setActionState({ status: "idle", message: "" });
                          setReopenReason("");
                          setReopenDialogItem(item);
                        }}
                        type="button"
                      >
                        Riapri
                      </button>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !visibleItems.length && !error ? <p className="px-5 py-8 text-sm text-slate-500">Nessun certificato numerato trovato.</p> : null}
      </div>
      {actionMessage ? <p className="mt-4 text-sm font-semibold text-emerald-700">{actionMessage}</p> : null}

      {pdfDialogItem ? (
        <ConfirmPdfDialog
          busy={actionState.status === "saving"}
          error={actionState.status === "error" ? actionState.message : ""}
          item={pdfDialogItem}
          onCancel={() => {
            setPdfDialogItem(null);
            setActionState({ status: "idle", message: "" });
          }}
          onConfirm={() => handleGeneratePdf(pdfDialogItem)}
        />
      ) : null}

      {reopenDialogItem ? (
        <ReopenPdfDialog
          busy={actionState.status === "saving"}
          error={actionState.status === "error" ? actionState.message : ""}
          item={reopenDialogItem}
          onCancel={() => {
            setReopenDialogItem(null);
            setReopenReason("");
            setActionState({ status: "idle", message: "" });
          }}
          onChangeReason={setReopenReason}
          onConfirm={() => handleReopenPdf(reopenDialogItem)}
          reason={reopenReason}
        />
      ) : null}
    </section>
  );
}

function ConfirmPdfDialog({ busy, error, item, onCancel, onConfirm }) {
  const inheritedWord = hasInheritedWord(item);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
      <div className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xl font-black text-amber-700">
            !
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-950">Generare PDF finale?</h3>
            {inheritedWord ? (
              <p className="mt-2 text-sm leading-6 text-slate-700">
                Il certificato <span className="font-semibold text-slate-900">{item.certificate_number}</span> usa un Word ereditato, creato
                automaticamente senza conferma definitiva della Qualità per questa lavorazione. Puoi generare il PDF, ma consigliamo di contattare
                la Qualità prima di chiudere il certificato.
              </p>
            ) : (
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Il PDF finale chiude il certificato{" "}
                <span className="font-semibold text-slate-900">{item.certificate_number}</span> e sarà il documento usabile da amministrazione e qualità.
                Se hai dubbi sul contenuto, o se servono modifiche amministrative da riportare nel documento, scarica prima il Word e confrontati con
                l'ufficio qualità.
              </p>
            )}
            {error ? <p className="mt-3 text-sm font-semibold text-rose-600">{error}</p> : null}
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
            disabled={busy}
            onClick={onCancel}
            type="button"
          >
            Esci senza generare
          </button>
          <button
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={busy}
            onClick={onConfirm}
            type="button"
          >
            {busy ? "Generazione..." : "Genera PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ReopenPdfDialog({ busy, error, item, onCancel, onChangeReason, onConfirm, reason }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
      <div className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xl font-black text-amber-700">
            !
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-lg font-bold text-slate-950">Riaprire certificato PDF?</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Il PDF finale del certificato <span className="font-semibold text-slate-900">{item.certificate_number}</span> verrà mantenuto nello storico
              come riaperto e il certificato tornerà modificabile. Dopo la correzione dovrà essere generato un nuovo PDF.
            </p>
            <label className="mt-4 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="pdf-reopen-reason">
              Motivo riapertura
            </label>
            <textarea
              className="mt-1 min-h-[90px] w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
              id="pdf-reopen-reason"
              onChange={(event) => onChangeReason(event.target.value)}
              placeholder="Descrivi la correzione richiesta da qualità."
              value={reason}
            />
            {error ? <p className="mt-3 text-sm font-semibold text-rose-600">{error}</p> : null}
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
            disabled={busy}
            onClick={onCancel}
            type="button"
          >
            Annulla
          </button>
          <button
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={busy}
            onClick={onConfirm}
            type="button"
          >
            {busy ? "Riapertura..." : "Riapri certificato"}
          </button>
        </div>
      </div>
    </div>
  );
}
