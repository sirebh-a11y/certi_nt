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

const EDITABLE_FIELDS = [
  "qualita_data_ricezione",
  "qualita_data_accettazione",
  "qualita_data_richiesta",
  "qualita_numero_analisi",
  "qualita_valutazione",
  "qualita_note",
];

function textValue(value) {
  return String(value ?? "");
}

function composeLega(row) {
  return [row.lega_base, row.variante_lega || row.lega_designazione].filter(Boolean).join(" ") || "-";
}

function isRowChanged(row, draft) {
  return EDITABLE_FIELDS.some((field) => textValue(row[field]) !== textValue(draft[field]));
}

function fieldClass({ changed = false, review = false } = {}) {
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
    draft.qualita_valutazione,
    draft.qualita_note,
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
      return draft.qualita_valutazione || "";
    case "note":
      return draft.qualita_note || "";
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
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
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

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest("/acquisition/quality-rows", {}, token);
      const nextRows = response.items || [];
      setRows(nextRows);
      setDrafts(Object.fromEntries(nextRows.map((row) => [row.id, buildDraft(row)])));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [token]);

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
  }, [rows.length]);

  function updateDraft(rowId, field, value) {
    setDrafts((current) => ({
      ...current,
      [rowId]: {
        ...(current[rowId] || {}),
        [field]: value,
      },
    }));
    setStatusMessage("");
  }

  function toggleSort(field) {
    setSortConfig((current) => {
      if (current.field !== field) {
        return { field, direction: "asc" };
      }
      return { field, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  }

  async function saveRow(row) {
    const draft = drafts[row.id] || buildDraft(row);
    setSavingId(row.id);
    setError("");
    try {
      const payload = Object.fromEntries(EDITABLE_FIELDS.map((field) => [field, draft[field] || null]));
      await apiRequest(
        `/acquisition/quality-rows/${row.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
        token,
      );
      setStatusMessage(`Riga #${row.id} aggiornata`);
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  function syncScroll(target, source) {
    if (!target || !source || syncingScrollRef.current) {
      return;
    }
    syncingScrollRef.current = true;
    target.scrollLeft = source.scrollLeft;
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Valutazione qualità</p>
          <h2 className="mt-2 text-2xl font-semibold">Conformità e valutazione qualità</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Registro delle sole righe completamente confermate. I campi di match sono bloccati; date, numero analisi, valutazione e note sono gestiti qui.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{visibleRows.length}</span> righe visibili
          {changedRows ? <span className="ml-3 text-amber-700">{changedRows} modificate</span> : null}
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento valutazioni...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
      {statusMessage ? <p className="mt-6 text-sm text-slate-600">{statusMessage}</p> : null}

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
              <th className="px-3 py-3 text-left">Azione</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const draft = drafts[row.id] || buildDraft(row);
              const changed = isRowChanged(row, draft);
              return (
                <tr key={row.id} className="border-b border-slate-100 align-middle hover:bg-slate-50/70 last:border-0">
                  <td className="px-2 py-2 font-semibold text-slate-900">{row.id}</td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({ changed: textValue(row.qualita_data_ricezione) !== textValue(draft.qualita_data_ricezione) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_ricezione", event.target.value)}
                      type="date"
                      value={draft.qualita_data_ricezione || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({ changed: textValue(row.qualita_data_accettazione) !== textValue(draft.qualita_data_accettazione) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_accettazione", event.target.value)}
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
                      className={`w-28 rounded-lg border px-2 py-1.5 ${fieldClass({ changed: textValue(row.qualita_data_richiesta) !== textValue(draft.qualita_data_richiesta) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_richiesta", event.target.value)}
                      type="date"
                      value={draft.qualita_data_richiesta || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className={`w-24 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_numero_analisi) !== textValue(draft.qualita_numero_analisi),
                        review: row.qualita_numero_analisi_da_ricontrollare,
                      })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_numero_analisi", event.target.value)}
                      value={draft.qualita_numero_analisi || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <select
                      className={`w-40 rounded-lg border px-2 py-1.5 ${fieldClass({ changed: textValue(row.qualita_valutazione) !== textValue(draft.qualita_valutazione) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_valutazione", event.target.value)}
                      value={draft.qualita_valutazione || ""}
                    >
                      {EVALUATION_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2">
                    <textarea
                      className={`min-h-8 w-40 rounded-lg border px-2 py-1.5 ${fieldClass({
                        changed: textValue(row.qualita_note) !== textValue(draft.qualita_note),
                        review: row.qualita_note_da_ricontrollare,
                      })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_note", event.target.value)}
                      value={draft.qualita_note || ""}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <button
                      className="rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
                      disabled={!changed || savingId === row.id}
                      onClick={() => void saveRow(row)}
                      type="button"
                    >
                      {savingId === row.id ? "Salvo..." : "Salva"}
                    </button>
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
