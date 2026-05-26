import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { formatRowFieldDisplay } from "./fieldFormatting";

const BLOCK_LABELS = {
  match: "Match",
  chimica: "Chim.",
  proprieta: "Prop.",
  note: "Note",
};
const QUALITY_EVALUATION_LABELS = {
  accettato: "Accettato",
  accettato_con_riserva: "Accettato con riserva",
  respinto: "Respinto",
};

const LIST_STATE_STORAGE_KEY = "certi_nt.acquisition_list_state.v1";
const DEFAULT_LIST_STATE = {
  queryOne: "",
  queryTwo: "",
  queryThree: "",
  operatorOne: "and",
  operatorTwo: "and",
  rowLimit: "50",
  showConfirmedOnly: false,
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
      showConfirmedOnly: Boolean(parsed?.showConfirmedOnly),
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

function activityLabelFromState(state) {
  if (state === "verde") {
    return "pronto";
  }
  if (state === "giallo") {
    return "quasi";
  }
  return "da fare";
}

  function blockActivityLabel(block, state) {
    if ((block === "chimica" || block === "proprieta") && state === "verde") {
      return "confermato";
    }
    return activityLabelFromState(state);
  }

function blockDisplayLabel(row, block) {
  if (
    (block === "chimica" || block === "proprieta") &&
    row.block_states?.[block] === "verde" &&
    row.quick_confirmed_blocks?.[block]
  ) {
    return "Conf. da Cert.";
  }
  return blockActivityLabel(block, row.block_states?.[block] || "rosso");
}

function parseCertificationIncomingScope(search) {
  const params = new URLSearchParams(search || "");
  if (params.get("scope") !== "certificazione") {
    return null;
  }
  const rowIds = (params.get("row_ids") || "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
  if (!rowIds.length) {
    return null;
  }
  return {
    rowIds: Array.from(new Set(rowIds)),
    ol: params.get("ol") || "",
    mode: params.get("mode") || "",
    cdq: params.get("cdq") || "",
    colata: params.get("colata") || "",
    qta: params.get("qta") || "",
    returnTo: params.get("returnTo") || "/quarta-taglio",
  };
}

function compactMatchReference(row) {
  const hasDdt = Boolean(row.document_ddt_id);
  const hasCertificate = Boolean(row.document_certificato_id);

  if (hasDdt && !hasCertificate) {
    return "";
  }
  if (hasCertificate && !hasDdt) {
    return "";
  }
  if (row.match_state === "confermato") {
    return "";
  }
  if (!row.certificate_file_name) {
    return activityLabelFromState(row.block_states?.match || "rosso");
  }
  const numericMatch = row.certificate_file_name.match(/\d{4,}/);
  if (numericMatch) {
    return numericMatch[0];
  }
  return row.certificate_file_name.replace(/\.pdf$/i, "").slice(0, 12);
}

function matchCellLabel(row) {
  const hasDdt = Boolean(row.document_ddt_id);
  const hasCertificate = Boolean(row.document_certificato_id);

  if (hasDdt && !hasCertificate) {
    return "Solo DDT";
  }
  if (hasCertificate && !hasDdt) {
    return "Solo Certificato";
  }
  if (row.match_state === "confermato") {
    return "Match Confermato";
  }
  return BLOCK_LABELS.match;
}

function matchSortValue(row) {
  const label = matchCellLabel(row);
  const priority =
    label === "Solo DDT"
      ? 1
      : label === "Solo Certificato"
        ? 2
        : label === "Match"
          ? 3
          : 4;
  return `${priority}-${label}-${compactMatchReference(row)}-${row.id}`;
}

function composeLega(row) {
  return row.lega_designazione || row.lega_base || row.variante_lega || "-";
}

function displaySupplierName(row) {
  return row.fornitore_nome || row.fornitore_raw || "-";
}

function formatUploadDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function stateSurfaceClasses(state) {
  if (state === "documento_chiuso") {
    return "border-transparent bg-transparent text-slate-950";
  }
  if (state === "neutro") {
    return "border-slate-200 bg-white text-slate-700";
  }
  if (state === "certificato") {
    return "border-sky-200 bg-sky-50 text-sky-800";
  }
  if (state === "ddt") {
    return "border-stone-200 bg-stone-50 text-stone-800";
  }
  if (state === "accettato") {
    return "border-slate-300 bg-slate-100 text-slate-700";
  }
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-rose-200 bg-rose-50 text-rose-800";
}

function qualityEvaluationLabel(value) {
  return QUALITY_EVALUATION_LABELS[value] || "Validata senza valutazione";
}

function qualityEvaluationTone(value) {
  if (value === "respinto") {
    return "rosso";
  }
  if (value === "accettato_con_riserva") {
    return "giallo";
  }
  if (value !== "accettato") {
    return "giallo";
  }
  return "verde";
}

function isQualityEvaluated(row) {
  return Boolean(row.qualita_valutazione);
}

function hasLinkedDdtAndCertificate(row) {
  return Boolean(row.document_ddt_id && row.document_certificato_id);
}

function isQualityBlocksConfirmed(row) {
  return ["chimica", "proprieta", "note"].every((block) => row.block_states?.[block] === "verde");
}

function isConfirmedListRow(row) {
  return Boolean(row.validata_finale || (isQualityEvaluated(row) && isQualityBlocksConfirmed(row) && hasLinkedDdtAndCertificate(row)));
}

function isWaitingForDdt(row) {
  return isQualityEvaluated(row) && !documentMatchingClosed(row);
}

function compactNoteReference(row) {
  const noteValue = row.note_documento?.trim();
  if (noteValue) {
    return noteValue.length > 18 ? `${noteValue.slice(0, 18)}...` : noteValue;
  }
  return activityLabelFromState(row.block_states?.note || "rosso");
}

function searchableFieldValues(row) {
  return [
    row.id,
    row.fornitore_nome,
    row.fornitore_raw,
    row.lega_designazione,
    row.lega_base,
    row.variante_lega,
    row.diametro,
    row.cdq,
    row.colata,
    row.ddt,
    row.peso,
    row.ordine,
    row.qualita_valutazione,
    qualityEvaluationLabel(row.qualita_valutazione),
    isWaitingForDdt(row) ? "attesa ddt attesa match" : null,
    row.qualita_note,
    matchCellLabel(row),
    compactMatchReference(row),
    row.certificate_file_name,
    row.note_documento,
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

function parseSortableNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const raw = String(value).trim();
  const match = raw.match(/-?\d+(?:[.,]\d+)?/);
  if (!match) {
    return null;
  }

  const normalized = match[0].replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function ddtFieldState(row, field) {
  if (row.ddt_confirmed_fields?.includes(field)) {
    return "verde";
  }
  if (row.ddt_missing_fields?.includes(field)) {
    return "rosso";
  }
  return "giallo";
}

function supplierFieldState(row) {
  return displaySupplierName(row) !== "-" ? "verde" : "rosso";
}

function legaFieldState(row) {
  return composeLega(row) && composeLega(row) !== "-" ? "verde" : "rosso";
}

function ddtCoreState(row) {
  const requiredFields = row.ddt_required_fields || [];
  const missingFields = row.ddt_missing_fields || [];
  const pendingFields = row.ddt_pending_fields || [];

  if (requiredFields.some((field) => missingFields.includes(field))) {
    return "rosso";
  }

  return requiredFields.some((field) => pendingFields.includes(field)) ? "giallo" : "verde";
}

function rowActivityState(row) {
  if (isQualityEvaluated(row)) {
    return { tone: qualityEvaluationTone(row.qualita_valutazione), label: qualityEvaluationLabel(row.qualita_valutazione) };
  }

  const ddtState = ddtCoreState(row);
  const matchState = row.block_states?.match || "rosso";
  const chemistryState = row.block_states?.chimica || "rosso";
  const propertiesState = row.block_states?.proprieta || "rosso";
  const notesState = row.block_states?.note || "rosso";

  if (ddtState === "rosso" || matchState === "rosso") {
    return { tone: "rosso", label: "da fare" };
  }

  if ([ddtState, matchState, chemistryState, propertiesState, notesState].some((state) => state !== "verde")) {
    return { tone: "giallo", label: "quasi" };
  }

  return { tone: "verde", label: "pronto" };
}

function documentMatchVisualState(row) {
  const hasDdt = Boolean(row.document_ddt_id);
  const hasCertificate = Boolean(row.document_certificato_id);
  if (hasDdt && hasCertificate && row.match_state === "confermato") {
    return "documento_chiuso";
  }
  if (hasDdt && hasCertificate) {
    return "verde";
  }
  if (hasDdt) {
    return "ddt";
  }
  if (hasCertificate) {
    return "certificato";
  }
  return "rosso";
}

function documentMatchingClosed(row) {
  return ddtCoreState(row) === "verde" && row.block_states?.match === "verde";
}

function activityRank(label) {
  if (label === "Accettato") {
    return 5;
  }
  if (label === "Accettato con riserva") {
    return 4;
  }
  if (label === "Respinto" || label === "Validata senza valutazione") {
    return 3;
  }
  if (label === "pronto") {
    return 2;
  }
  if (label === "quasi") {
    return 1;
  }
  if (label === "Attesa DDT") {
    return 1;
  }
  return 0;
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

  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * multiplier;
  }

  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function rowFieldSortValue(row, field) {
  switch (field) {
    case "id":
      return row.id;
    case "fornitore":
      return displaySupplierName(row);
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
    case "match":
      return matchSortValue(row);
    case "chimica":
      return activityRank(blockActivityLabel("chimica", row.block_states?.chimica || "rosso"));
    case "proprieta":
      return activityRank(blockActivityLabel("proprieta", row.block_states?.proprieta || "rosso"));
    case "note":
      return row.note_documento || blockActivityLabel("note", row.block_states?.note || "rosso");
    case "stato":
      return activityRank(rowActivityState(row).label);
    default:
      return null;
  }
}

function rowSortScore(row) {
  const priorityRank = row.priorita_operativa === "alta" ? 0 : row.priorita_operativa === "media" ? 1 : 2;
  const technicalRank = row.stato_tecnico === "rosso" ? 0 : row.stato_tecnico === "giallo" ? 1 : 2;
  const workflowRank = row.stato_workflow === "riaperta" ? 0 : row.stato_workflow === "in_lavorazione" ? 1 : row.stato_workflow === "nuova" ? 2 : 3;
  const updatedAt = row.updated_at ? new Date(row.updated_at).getTime() : 0;
  return [priorityRank, technicalRank, workflowRank, -updatedAt, -row.id];
}

function CellShell({ children, onClick, onKeyDown, interactive = false }) {
  const Tag = interactive ? "button" : "div";
  return (
    <Tag
      className={`block w-full text-left ${interactive ? "focus:outline-none focus:ring-2 focus:ring-accent/30 rounded-lg" : ""}`}
      onClick={onClick}
      onKeyDown={onKeyDown}
      type={interactive ? "button" : undefined}
    >
      {children}
    </Tag>
  );
}

function documentPlateClasses(state) {
  if (state === "accettato" || state === "documento_chiuso") {
    return "border-transparent bg-transparent";
  }
  if (state === "certificato") {
    return "border-sky-300 bg-sky-100/80";
  }
  if (state === "ddt") {
    return "border-stone-300 bg-stone-100/90";
  }
  if (state === "verde") {
    return "border-emerald-300 bg-emerald-100/90";
  }
  if (state === "giallo") {
    return "border-amber-300 bg-amber-100/90";
  }
  return "border-rose-300 bg-rose-100/90";
}

function displayCellState(row, state) {
  return documentMatchingClosed(row) ? "documento_chiuso" : state;
}

function compactStateLabel(label, hasSecondary) {
  if (!hasSecondary) {
    return label;
  }
  if (label === "Accettato con riserva") {
    return "Acc. riserva";
  }
  return label;
}

function RowStateCell({ row, onClick, onKeyDown }) {
  const activity = rowActivityState(row);
  const secondary = isWaitingForDdt(row) ? "Attesa DDT" : "";
  const label = compactStateLabel(activity.label, Boolean(secondary));
  const title = secondary ? `${activity.label} - ${secondary}` : activity.label;
  const labelClassName = secondary
    ? "block truncate text-[10px] font-semibold leading-none"
    : "block truncate text-xs font-semibold leading-tight";

  return (
    <div className="min-w-[96px] py-1">
      <CellShell interactive onClick={onClick} onKeyDown={onKeyDown}>
        <div
          className={`mx-2 flex h-[46px] w-[calc(100%-1rem)] flex-col justify-center overflow-hidden rounded-lg border px-1.5 pb-1 pt-1 ${stateSurfaceClasses(activity.tone)}`}
          title={title}
        >
          <span className={labelClassName}>{label}</span>
          {secondary ? <span className="mt-1 block truncate text-[9px] font-semibold uppercase leading-none opacity-90">{secondary}</span> : null}
        </div>
      </CellShell>
    </div>
  );
}

function transparentDocumentCellClasses() {
  return "border-slate-300/70 bg-transparent text-slate-950";
}

function DataCell({ value, state, secondary, onClick, onKeyDown, wide = false, boxRef = null }) {
  return (
    <div className={`relative ${wide ? "min-w-[220px]" : "min-w-[92px]"} py-1`}>
      <CellShell interactive onClick={onClick} onKeyDown={onKeyDown}>
        <div
          className={`relative z-10 mx-2 flex h-[46px] w-[calc(100%-1rem)] flex-col justify-start overflow-hidden rounded-lg border px-2.5 pb-1.5 pt-2 ${transparentDocumentCellClasses()}`}
          ref={boxRef}
        >
          <span className="block truncate text-sm font-semibold leading-none">{value || "-"}</span>
          {secondary ? <div className="mt-0.5 truncate text-[10px] leading-none opacity-75">{secondary}</div> : null}
        </div>
      </CellShell>
    </div>
  );
}

function BlockCell({ label, state, secondary, onClick, onKeyDown, boxRef = null }) {
  return (
    <div className="relative min-w-[100px] py-1">
      <CellShell interactive onClick={onClick} onKeyDown={onKeyDown}>
        <div
          className={`relative z-10 mx-2 flex h-[46px] w-[calc(100%-1rem)] flex-col justify-start overflow-hidden rounded-lg border px-2.5 pb-1.5 pt-2 ${stateSurfaceClasses(state)}`}
          ref={boxRef}
        >
          <span className="block text-[11px] font-semibold uppercase tracking-[0.12em] leading-none">{label}</span>
          <div className="mt-0.5 truncate text-[10px] leading-none opacity-75">{secondary}</div>
        </div>
      </CellShell>
    </div>
  );
}

export default function AcquisitionListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const certificationScope = useMemo(() => parseCertificationIncomingScope(location.search), [location.search]);
  const isCertificationScope = Boolean(certificationScope);
  const initialListStateRef = useRef(certificationScope ? DEFAULT_LIST_STATE : loadPersistedListState());
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [queryOne, setQueryOne] = useState(initialListStateRef.current.queryOne);
  const [queryTwo, setQueryTwo] = useState(initialListStateRef.current.queryTwo);
  const [queryThree, setQueryThree] = useState(initialListStateRef.current.queryThree);
  const [operatorOne, setOperatorOne] = useState(initialListStateRef.current.operatorOne);
  const [operatorTwo, setOperatorTwo] = useState(initialListStateRef.current.operatorTwo);
  const [rowLimit, setRowLimit] = useState(initialListStateRef.current.rowLimit);
  const [showConfirmedOnly, setShowConfirmedOnly] = useState(initialListStateRef.current.showConfirmedOnly);
  const [sortConfig, setSortConfig] = useState(initialListStateRef.current.sortConfig);
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 0, viewportWidth: 0 });
  const [documentPlateMetrics, setDocumentPlateMetrics] = useState({});
  const topScrollRef = useRef(null);
  const tableViewportRef = useRef(null);
  const tableRef = useRef(null);
  const syncingScrollRef = useRef(false);
  const restoredScrollRef = useRef(false);
  const sectionRef = useRef(null);
  const firstDocumentAnchorRefs = useRef({});
  const firstDocumentCellRefs = useRef({});
  const lastDocumentCellRefs = useRef({});
  const [resolveCandidate, setResolveCandidate] = useState(null);
  const [resolveError, setResolveError] = useState("");
  const [savingResolve, setSavingResolve] = useState(false);
  const isIncomingResolveScope = certificationScope?.mode === "resolve_row";

  useEffect(() => {
    const nextState = isCertificationScope ? DEFAULT_LIST_STATE : loadPersistedListState();
    initialListStateRef.current = nextState;
    setQueryOne(nextState.queryOne);
    setQueryTwo(nextState.queryTwo);
    setQueryThree(nextState.queryThree);
    setOperatorOne(nextState.operatorOne);
    setOperatorTwo(nextState.operatorTwo);
    setRowLimit(nextState.rowLimit);
    setShowConfirmedOnly(nextState.showConfirmedOnly);
    setSortConfig(nextState.sortConfig);
    setResolveCandidate(null);
    setResolveError("");
  }, [isCertificationScope, location.search]);

  useEffect(() => {
    let ignore = false;

    setLoading(true);
    setError("");

    const endpoint = certificationScope
      ? `/acquisition/rows?row_ids=${encodeURIComponent(certificationScope.rowIds.join(","))}`
      : "/acquisition/rows";

    apiRequest(endpoint, {}, token)
      .then((data) => {
        if (!ignore) {
          setRows(data.items || []);
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
  }, [certificationScope, token]);

  useEffect(() => {
    if (isCertificationScope) {
      return;
    }
    const viewport = tableViewportRef.current;
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    savePersistedListState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      showConfirmedOnly,
      sortConfig,
      scrollLeft: viewport ? viewport.scrollLeft : initialListStateRef.current.scrollLeft,
      scrollTop: viewport ? viewport.scrollTop : initialListStateRef.current.scrollTop,
      windowScrollY: pageScroller?.scrollTop || 0,
    });
  }, [isCertificationScope, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rowLimit, showConfirmedOnly, sortConfig]);

  useEffect(() => {
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    function handlePageScroll() {
      if (isCertificationScope) {
        return;
      }
      const currentState = loadPersistedListState();
      savePersistedListState({
        ...currentState,
        windowScrollY: pageScroller?.scrollTop || 0,
      });
    }

    pageScroller?.addEventListener("scroll", handlePageScroll, { passive: true });
    return () => pageScroller?.removeEventListener("scroll", handlePageScroll);
  }, [isCertificationScope]);

  const visibleRows = useMemo(() => {
    let nextRows = rows;
    if (!isCertificationScope) {
      nextRows = nextRows.filter((row) => (showConfirmedOnly ? isConfirmedListRow(row) : !isConfirmedListRow(row)));
    }

    if (queryOne.trim() || queryTwo.trim() || queryThree.trim()) {
      nextRows = nextRows.filter((row) => {
        const baseValues = searchableFieldValues(row);
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
      if (sortConfig.field) {
        const sorted = compareValues(
          rowFieldSortValue(left, sortConfig.field),
          rowFieldSortValue(right, sortConfig.field),
          sortConfig.direction,
        );
        if (sorted !== 0) {
          return sorted;
        }
      }

      const leftScore = rowSortScore(left);
      const rightScore = rowSortScore(right);
      for (let index = 0; index < leftScore.length; index += 1) {
        if (leftScore[index] !== rightScore[index]) {
          return leftScore[index] - rightScore[index];
        }
      }
      return 0;
    });
  }, [isCertificationScope, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rows, showConfirmedOnly, sortConfig]);

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

  const summary = useMemo(() => {
    const total = rows.length;
    const open = rows.filter((row) => !row.validata_finale).length;
    const waitingDdt = rows.filter((row) => isWaitingForDdt(row)).length;
    return { total, open, waitingDdt };
  }, [rows]);

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
      observer = new ResizeObserver(() => updateScrollMetrics());
      observer.observe(viewport);
      observer.observe(table);
    }

    window.addEventListener("resize", updateScrollMetrics);
    return () => {
      window.removeEventListener("resize", updateScrollMetrics);
      if (observer) {
        observer.disconnect();
      }
    };
  }, [displayedRows.length, rows.length]);

  useEffect(() => {
    function updateDocumentPlateMetrics() {
      const nextMetrics = {};

      displayedRows.forEach((row) => {
        const anchorWrapper = firstDocumentAnchorRefs.current[row.id];
        const anchorElement = firstDocumentCellRefs.current[row.id];
        const lastCell = lastDocumentCellRefs.current[row.id];

        if (!anchorWrapper || !anchorElement || !lastCell) {
          return;
        }

        const wrapperRect = anchorWrapper.getBoundingClientRect();
        const anchorRect = anchorElement.getBoundingClientRect();
        const firstRect = anchorElement.getBoundingClientRect();
        const lastRect = lastCell.getBoundingClientRect();
        const leftInset = -8;
        const width = Math.max(0, lastRect.right - firstRect.left - leftInset);
        const left = firstRect.left - wrapperRect.left + leftInset;
        const panelHeight = 50;
        const top = firstRect.top - wrapperRect.top + (firstRect.height - panelHeight) / 2;

        nextMetrics[row.id] = {
          left,
          top,
          width,
          height: panelHeight,
        };
      });

      setDocumentPlateMetrics(nextMetrics);
    }

    updateDocumentPlateMetrics();
    window.addEventListener("resize", updateDocumentPlateMetrics);
    return () => {
      window.removeEventListener("resize", updateDocumentPlateMetrics);
    };
  }, [displayedRows]);

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

  function syncScroll(target, source) {
    if (!target || !source) {
      return;
    }
    if (syncingScrollRef.current) {
      return;
    }
    syncingScrollRef.current = true;
    target.scrollLeft = source.scrollLeft;
    if (!isCertificationScope) {
      const currentState = loadPersistedListState();
      const pageScroller = getScrollablePageContainer(sectionRef.current);
      savePersistedListState({
        ...currentState,
        scrollLeft: source.scrollLeft,
        scrollTop: tableViewportRef.current ? tableViewportRef.current.scrollTop : currentState.scrollTop,
        windowScrollY: pageScroller?.scrollTop || currentState.windowScrollY || 0,
      });
    }
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  function persistCurrentListState() {
    if (isCertificationScope) {
      return;
    }
    const viewport = tableViewportRef.current;
    const pageScroller = getScrollablePageContainer(sectionRef.current);
    savePersistedListState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      showConfirmedOnly,
      sortConfig,
      scrollLeft: viewport?.scrollLeft || 0,
      scrollTop: viewport?.scrollTop || 0,
      windowScrollY: pageScroller?.scrollTop || 0,
    });
  }

  function openRow(rowId) {
    persistCurrentListState();
    navigate(`/acquisition/${rowId}${isCertificationScope ? location.search : ""}`);
  }

  function openSection(rowId, sectionKey) {
    persistCurrentListState();
    navigate(`/acquisition/${rowId}/${sectionKey}${isCertificationScope ? location.search : ""}`);
  }

  async function confirmIncomingResolveSelection() {
    if (!resolveCandidate || !certificationScope?.ol || !certificationScope?.cdq) {
      return;
    }
    setSavingResolve(true);
    setResolveError("");
    try {
      await apiRequest(
        `/quarta-taglio/${encodeURIComponent(certificationScope.ol)}/incoming-row-override`,
        {
          method: "POST",
          body: JSON.stringify({
            cdq: certificationScope.cdq,
            colata: certificationScope.colata || null,
            acquisition_row_id: resolveCandidate.id,
          }),
        },
        token,
      );
      navigate(certificationScope.returnTo || "/quarta-taglio");
    } catch (requestError) {
      setResolveError(requestError.message);
    } finally {
      setSavingResolve(false);
    }
  }

  function handleRowKeyDown(event, rowId) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openRow(rowId);
    }
  }

  function handleSectionKeyDown(event, rowId, sectionKey) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSection(rowId, sectionKey);
    }
  }

  function toggleSort(field) {
    setSortConfig((current) => {
      if (current.field === field) {
        return {
          field,
          direction: current.direction === "asc" ? "desc" : "asc",
        };
      }

      return { field, direction: "asc" };
    });
  }

  function setFirstDocumentCellRef(rowId, element) {
    if (element) {
      firstDocumentCellRefs.current[rowId] = element;
    } else {
      delete firstDocumentCellRefs.current[rowId];
    }
  }

  function setFirstDocumentAnchorRef(rowId, element) {
    if (element) {
      firstDocumentAnchorRefs.current[rowId] = element;
    } else {
      delete firstDocumentAnchorRefs.current[rowId];
    }
  }

  function setLastDocumentCellRef(rowId, element) {
    if (element) {
      lastDocumentCellRefs.current[rowId] = element;
    } else {
      delete lastDocumentCellRefs.current[rowId];
    }
  }

  return (
    <section className="space-y-2" ref={sectionRef}>
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming materiale</p>
          </div>
        <div className="flex flex-wrap gap-2">
          <Link className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100" to="/acquisition/upload">
            Carica documenti
          </Link>
        </div>
      </div>

        <div className="flex flex-wrap gap-2">
          <SummaryCell label="Righe" value={summary.total} />
          <SummaryCell label="Aperte" value={summary.open} />
          <SummaryCell label="Attesa DDT" value={summary.waitingDdt} />
          <SummaryCell label="Logica attività" value="Placeholder" />
          <SummaryCell label="Masking e nuovo OCR icone" value="Placeholder" />
          <SummaryCell label="Aggiungi nuovo elemento chimico" value="Placeholder" />
          <SummaryCell
            label="Import fornitori DB terzo"
            value="Placeholder"
            note="Tema aperto: vedi docs/modules/supplier_third_party_import_placeholder.md"
          />
        </div>

      {certificationScope ? (
        <div className="flex flex-col gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <span className="font-semibold">
              {isIncomingResolveScope
                ? `Scegli riga Incoming per ${certificationScope.ol || "OL"}`
                : `Righe Incoming collegate${certificationScope.ol ? ` a ${certificationScope.ol}` : ""}`}
            </span>
            <span className="ml-2 text-sky-700">
              {isIncomingResolveScope
                ? `CDQ ${certificationScope.cdq || "-"} · colata ${certificationScope.colata || "-"}${certificationScope.qta ? ` · peso Quarta ${certificationScope.qta}` : ""}. Apri le righe se vuoi controllare i documenti, poi usa il pulsante sulla riga corretta.`
                : "Vista temporanea: i filtri normali di Incoming non vengono modificati."}
            </span>
            {resolveError ? <div className="mt-1 text-xs font-semibold text-rose-700">{resolveError}</div> : null}
          </div>
          <Link className="w-fit rounded-xl border border-sky-300 bg-white px-4 py-2 text-sm font-semibold text-sky-800 hover:bg-sky-100" to={certificationScope.returnTo}>
            Torna al certificato
          </Link>
        </div>
      ) : null}

      <div className="flex items-end gap-2 overflow-x-auto pb-1">
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-search-1">
            Filtro 1
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="incoming-quality-search-1"
            onChange={(event) => setQueryOne(event.target.value)}
            placeholder="Tutti i campi"
            value={queryOne}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-operator-1">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="incoming-quality-operator-1"
            onChange={(event) => setOperatorOne(event.target.value)}
            value={operatorOne}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-search-2">
            Filtro 2
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="incoming-quality-search-2"
            onChange={(event) => setQueryTwo(event.target.value)}
            placeholder="Campi non presi dal 1"
            value={queryTwo}
          />
        </div>
        <div className="min-w-[90px] max-w-[90px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-operator-2">
            Logica
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="incoming-quality-operator-2"
            onChange={(event) => setOperatorTwo(event.target.value)}
            value={operatorTwo}
          >
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        <div className="min-w-[220px] max-w-[220px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-search-3">
            Filtro 3
          </label>
          <input
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
            id="incoming-quality-search-3"
            onChange={(event) => setQueryThree(event.target.value)}
            placeholder="Campi non presi da 1 e 2"
            value={queryThree}
          />
        </div>
        <div className="min-w-[120px] max-w-[120px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-confirmed-toggle">
            Vista
          </label>
          <button
            className={`w-full rounded-xl border px-3 py-2 text-sm font-semibold transition ${
              showConfirmedOnly
                ? "border-slate-300 bg-slate-900 text-white hover:bg-slate-800"
                : "border-border bg-white text-slate-700 hover:bg-slate-100"
            }`}
            id="incoming-quality-confirmed-toggle"
            disabled={isCertificationScope}
            onClick={() => setShowConfirmedOnly((current) => !current)}
            type="button"
          >
            {isCertificationScope ? "Righe OL" : showConfirmedOnly ? "Confermati" : "Aperte"}
          </button>
        </div>
        {!isCertificationScope ? (
          <div className="max-w-[360px] self-end pb-2 text-xs font-semibold text-rose-700">
            {showConfirmedOnly
              ? "Include anche certificati già valutati ma ancora in attesa DDT/match."
              : "Aperte include anche certificati valutati ma non ancora chiusi per DDT/match mancanti."}
          </div>
        ) : null}
        <div className="ml-auto min-w-[88px] max-w-[88px]">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-row-limit">
            Righe
          </label>
          <select
            className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm text-slate-700"
            id="incoming-quality-row-limit"
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

      {loading ? <p className="text-sm text-slate-500">Caricamento righe...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

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
          <table className="min-w-[1480px] divide-y divide-slate-200 text-sm" ref={tableRef}>
              <thead className="sticky-list-head bg-slate-50">
                <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <SortableHeader field="id" label="N°" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="fornitore" label="Fornitore" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="lega" label="Lega" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="diametro" label="Ø" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="cdq" label="Cdq" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="colata" label="Colata" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="ddt" label="Ddt" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="peso" label="Peso Kg" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="ordine" label="Vs. Odv" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="match" label="Match" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="chimica" label="Chim." onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="proprieta" label="Prop." onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="note" label="Note" onSort={toggleSort} sortConfig={sortConfig} />
                  <SortableHeader field="stato" label="Stato" onSort={toggleSort} sortConfig={sortConfig} />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedRows.map((row) => (
                  <tr className="relative align-top hover:bg-slate-50/70 focus-within:bg-slate-50/70" key={row.id}>
                    <td className="whitespace-nowrap px-3 py-2.5 font-semibold text-slate-700">
                      <div>{row.id}</div>
                      {isIncomingResolveScope ? (
                        <button
                          className="mt-2 rounded-lg border border-sky-300 bg-white px-2 py-1 text-[11px] font-semibold text-sky-800 hover:bg-sky-50"
                          onClick={() => setResolveCandidate(row)}
                          type="button"
                        >
                          Usa per OL
                        </button>
                      ) : null}
                    </td>
                    <td className="relative min-w-[220px] max-w-[220px] overflow-visible px-0 py-0" ref={(element) => setFirstDocumentAnchorRef(row.id, element)}>
                      <div
                        className={`pointer-events-none absolute left-3 z-0 rounded-2xl border ${documentPlateClasses(documentMatchVisualState(row))}`}
                        style={{
                          left: `${documentPlateMetrics[row.id]?.left || 0}px`,
                          top: `${documentPlateMetrics[row.id]?.top || 0}px`,
                          width: `${documentPlateMetrics[row.id]?.width || 0}px`,
                          height: `${documentPlateMetrics[row.id]?.height || 0}px`,
                        }}
                      />
                      <DataCell
                        boxRef={(element) => setFirstDocumentCellRef(row.id, element)}
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, supplierFieldState(row))}
                        value={displaySupplierName(row)}
                        secondary={row.ddt_data_upload ? `DDT ${formatUploadDate(row.ddt_data_upload)}` : ""}
                        wide
                      />
                    </td>
                    <td className="max-w-[110px] px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, legaFieldState(row))}
                        value={composeLega(row)}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "diametro"))}
                        value={formatRowFieldDisplay("diametro", row.diametro)}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "cdq"))}
                        value={row.cdq}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "colata"))}
                        value={row.colata}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "ddt"))}
                        value={row.ddt || "-"}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "peso"))}
                        value={formatRowFieldDisplay("peso", row.peso)}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <DataCell
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        state={displayCellState(row, ddtFieldState(row, "ordine"))}
                        value={row.ordine}
                      />
                    </td>
                    <td className="px-0 py-0" ref={(element) => setLastDocumentCellRef(row.id, element)}>
                      <BlockCell
                        boxRef={(element) => setLastDocumentCellRef(row.id, element)}
                        label={matchCellLabel(row)}
                        onClick={() => openSection(row.id, "document-matching")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "document-matching")}
                        secondary={compactMatchReference(row)}
                        state={documentMatchVisualState(row)}
                      />
                    </td>
                      <td className="px-0 py-0">
                        <BlockCell
                          label={BLOCK_LABELS.chimica}
                          onClick={() => openSection(row.id, "chemistry")}
                          onKeyDown={(event) => handleSectionKeyDown(event, row.id, "chemistry")}
                          secondary={blockDisplayLabel(row, "chimica")}
                          state={row.block_states?.chimica || "rosso"}
                        />
                      </td>
                      <td className="px-0 py-0">
                        <BlockCell
                          label={BLOCK_LABELS.proprieta}
                          onClick={() => openSection(row.id, "properties")}
                          onKeyDown={(event) => handleSectionKeyDown(event, row.id, "properties")}
                          secondary={blockDisplayLabel(row, "proprieta")}
                          state={row.block_states?.proprieta || "rosso"}
                        />
                      </td>
                    <td className="px-0 py-0">
                      <BlockCell
                        label={BLOCK_LABELS.note}
                        onClick={() => openSection(row.id, "notes")}
                        onKeyDown={(event) => handleSectionKeyDown(event, row.id, "notes")}
                        secondary={compactNoteReference(row)}
                        state={row.block_states?.note || "rosso"}
                      />
                    </td>
                    <td className="px-0 py-0">
                      <RowStateCell row={row} onClick={() => openRow(row.id)} onKeyDown={(event) => handleRowKeyDown(event, row.id)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        </div>

        {!loading && !visibleRows.length && !error ? (
          <div className="px-4 py-6 text-sm text-slate-500">
            {showConfirmedOnly ? "Nessuna riga confermata disponibile." : "Nessuna riga aperta disponibile."}
          </div>
        ) : null}
      </div>
      {resolveCandidate ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-white p-5 shadow-2xl">
            <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Scelta riga Incoming</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">Conferma questa riga per l'OL</h2>
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
              <div>
                <span className="font-semibold">OL:</span> {certificationScope?.ol || "-"}
              </div>
              <div>
                <span className="font-semibold">CDQ / colata:</span> {certificationScope?.cdq || "-"} / {certificationScope?.colata || "-"}
              </div>
              <div>
                <span className="font-semibold">Riga Incoming:</span> #{resolveCandidate.id} · {displaySupplierName(resolveCandidate)}
              </div>
              <div>
                <span className="font-semibold">Peso riga:</span> {formatRowFieldDisplay("peso", resolveCandidate.peso)}
                {certificationScope?.qta ? ` · peso Quarta ${certificationScope.qta}` : ""}
              </div>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              La scelta non modifica i dati Incoming: collega solo questo OL/CDQ/colata alla riga corretta per sbloccare la certificazione.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                className="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                disabled={savingResolve}
                onClick={() => setResolveCandidate(null)}
                type="button"
              >
                Annulla
              </button>
              <button
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50"
                disabled={savingResolve}
                onClick={confirmIncomingResolveSelection}
                type="button"
              >
                {savingResolve ? "Salvataggio..." : "Conferma scelta"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function SummaryCell({ label, value, note = null }) {
  return (
    <div className="rounded-lg border border-border bg-white px-2.5 py-2">
      <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-0.5 text-base font-semibold text-slate-900">{value}</div>
      {note ? <div className="mt-1 max-w-[240px] text-[10px] leading-4 text-slate-500">{note}</div> : null}
    </div>
  );
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
        <span className="min-w-[10px] text-[10px]">{indicator}</span>
      </button>
    </th>
  );
}
