import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { formatRowFieldDisplay } from "./fieldFormatting";

const BLOCK_LABELS = {
  match: "Match",
  chimica: "Chim.",
  proprieta: "Prop.",
  note: "Note",
};

function activityLabelFromState(state) {
  if (state === "verde") {
    return "pronto";
  }
  if (state === "giallo") {
    return "quasi";
  }
  return "da fare";
}

function compactMatchReference(row) {
  if (!row.certificate_file_name) {
    return activityLabelFromState(row.block_states?.match || "rosso");
  }
  const numericMatch = row.certificate_file_name.match(/\d{4,}/);
  if (numericMatch) {
    return numericMatch[0];
  }
  return row.certificate_file_name.replace(/\.pdf$/i, "").slice(0, 12);
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
  const hasMissingCore =
    !row.diametro ||
    !row.cdq ||
    !row.colata ||
    !row.peso ||
    !row.ddt;

  if (hasMissingCore) {
    return "rosso";
  }

  const hasPendingCore =
    ddtFieldState(row, "diametro") === "giallo" ||
    ddtFieldState(row, "cdq") === "giallo" ||
    ddtFieldState(row, "colata") === "giallo" ||
    ddtFieldState(row, "peso") === "giallo" ||
    ddtFieldState(row, "ordine") === "giallo";

  return hasPendingCore ? "giallo" : "verde";
}

function rowActivityState(row) {
  if (row.validata_finale) {
    return { tone: "accettato", label: "confermata" };
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

function activityRank(label) {
  if (label === "confermata") {
    return 3;
  }
  if (label === "pronto") {
    return 2;
  }
  if (label === "quasi") {
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
      return compactMatchReference(row);
    case "chimica":
      return activityRank(activityLabelFromState(row.block_states?.chimica || "rosso"));
    case "proprieta":
      return activityRank(activityLabelFromState(row.block_states?.proprieta || "rosso"));
    case "note":
      return row.note_documento || activityLabelFromState(row.block_states?.note || "rosso");
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

function RowStateCell({ row }) {
  const activity = rowActivityState(row);

  return (
    <div className="min-w-[96px]">
      <div className={`flex min-h-[54px] w-full flex-col justify-center rounded-lg border px-2.5 py-2 ${stateSurfaceClasses(activity.tone)}`}>
        <span className="block text-xs font-semibold">{activity.label}</span>
      </div>
    </div>
  );
}

function DataCell({ value, state, secondary }) {
  return (
    <div className="min-w-[92px]">
      <div className={`flex min-h-[54px] w-full flex-col justify-center rounded-lg border px-2.5 py-2 ${stateSurfaceClasses(state)}`}>
        <span className="block truncate text-sm font-semibold">{value || "-"}</span>
        {secondary ? <div className="mt-0.5 truncate text-[10px] opacity-75">{secondary}</div> : null}
      </div>
    </div>
  );
}

function BlockCell({ label, state, secondary }) {
  return (
    <div className="min-w-[100px]">
      <div className={`flex min-h-[54px] w-full flex-col justify-center rounded-lg border px-2.5 py-2 ${stateSurfaceClasses(state)}`}>
        <span className="block text-[11px] font-semibold uppercase tracking-[0.12em]">{label}</span>
        <div className="mt-0.5 truncate text-[10px] opacity-75">{secondary}</div>
      </div>
    </div>
  );
}

export default function AcquisitionListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [queryOne, setQueryOne] = useState("");
  const [queryTwo, setQueryTwo] = useState("");
  const [queryThree, setQueryThree] = useState("");
  const [operatorOne, setOperatorOne] = useState("and");
  const [operatorTwo, setOperatorTwo] = useState("and");
  const [sortConfig, setSortConfig] = useState({ field: null, direction: "asc" });
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 0, viewportWidth: 0 });
  const topScrollRef = useRef(null);
  const tableViewportRef = useRef(null);
  const tableRef = useRef(null);
  const syncingScrollRef = useRef(false);

  useEffect(() => {
    let ignore = false;

    setLoading(true);
    setError("");

    apiRequest("/acquisition/rows", {}, token)
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
  }, [token]);

  const visibleRows = useMemo(() => {
    let nextRows = rows;

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
  }, [operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rows, sortConfig]);

  const summary = useMemo(() => {
    const total = rows.length;
    const open = rows.filter((row) => row.stato_workflow !== "validata_quality").length;
    return { total, open };
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
  }, [visibleRows.length, rows.length]);

  function syncScroll(target, source) {
    if (!target || !source) {
      return;
    }
    if (syncingScrollRef.current) {
      return;
    }
    syncingScrollRef.current = true;
    target.scrollLeft = source.scrollLeft;
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  function openRow(rowId) {
    navigate(`/acquisition/${rowId}`);
  }

  function handleRowKeyDown(event, rowId) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openRow(rowId);
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

  return (
    <section className="space-y-2">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
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
        <SummaryCell label="Logica attività" value="Placeholder" />
      </div>

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
              <thead className="bg-slate-50">
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
                {visibleRows.map((row) => (
                  <tr
                    className="cursor-pointer align-top hover:bg-slate-50/70 focus-within:bg-slate-50/70"
                    key={row.id}
                    onClick={() => openRow(row.id)}
                    onKeyDown={(event) => handleRowKeyDown(event, row.id)}
                    tabIndex={0}
                  >
                    <td className="whitespace-nowrap px-3 py-3 font-semibold text-slate-700">{row.id}</td>
                    <td className="min-w-[220px] max-w-[220px] px-2 py-2">
                      <DataCell
                        state={supplierFieldState(row)}
                        value={displaySupplierName(row)}
                        secondary={row.ddt_data_upload ? `DDT ${formatUploadDate(row.ddt_data_upload)}` : ""}
                      />
                    </td>
                    <td className="max-w-[110px] px-2 py-2">
                      <DataCell state={legaFieldState(row)} value={composeLega(row)} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={ddtFieldState(row, "diametro")} value={formatRowFieldDisplay("diametro", row.diametro)} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={ddtFieldState(row, "cdq")} value={row.cdq} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={ddtFieldState(row, "colata")} value={row.colata} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={row.ddt ? "verde" : "rosso"} value={row.ddt || "-"} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={ddtFieldState(row, "peso")} value={formatRowFieldDisplay("peso", row.peso)} />
                    </td>
                    <td className="px-2 py-2">
                      <DataCell state={ddtFieldState(row, "ordine")} value={row.ordine} />
                    </td>
                    <td className="px-2 py-2">
                      <BlockCell
                        label={BLOCK_LABELS.match}
                        secondary={compactMatchReference(row)}
                        state={row.block_states?.match || "rosso"}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <BlockCell
                        label={BLOCK_LABELS.chimica}
                        secondary={activityLabelFromState(row.block_states?.chimica || "rosso")}
                        state={row.block_states?.chimica || "rosso"}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <BlockCell
                        label={BLOCK_LABELS.proprieta}
                        secondary={activityLabelFromState(row.block_states?.proprieta || "rosso")}
                        state={row.block_states?.proprieta || "rosso"}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <BlockCell
                        label={BLOCK_LABELS.note}
                        secondary={compactNoteReference(row)}
                        state={row.block_states?.note || "rosso"}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <RowStateCell row={row} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        </div>

        {!loading && !visibleRows.length && !error ? (
          <div className="px-4 py-6 text-sm text-slate-500">Nessuna riga acquisition disponibile.</div>
        ) : null}
      </div>
    </section>
  );
}

function SummaryCell({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-white px-2.5 py-2">
      <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-0.5 text-base font-semibold text-slate-900">{value}</div>
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
