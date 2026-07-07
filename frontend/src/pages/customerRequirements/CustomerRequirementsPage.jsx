import { useEffect, useMemo, useRef, useState } from "react";

import { canEditQualitySetup } from "../../app/access";
import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const TABLE_STATE_STORAGE_KEY = "certi_nt.customer_requirements_list_state.v1";

const BOOLEAN_COLUMNS = [
  { field: "requires_chemical_analysis", label: "Analisi chimica" },
  { field: "requires_mechanical_mp", label: "Caratt. Mecc. MP" },
  { field: "requires_mechanical_forged", label: "Caratt. Mecc. Forgiato" },
  { field: "requires_hardness_hb", label: "Durezza HB" },
  { field: "requires_lot_traceability_text", label: "Tracciabilità Lotto (datario) Indicazione" },
  { field: "requires_lot_traceability_photo", label: "Tracciabilità Lotto (datario) Foto" },
  { field: "requires_dimensional", label: "Dimensionale (Dimensioni concordate con cliente)" },
  { field: "requires_electrical_conductivity_forged", label: "Conducibilità elettrica (sul forgiato)" },
  { field: "requires_marking", label: "Marcature (Tracciabilità aggiuntive)" },
  { field: "requires_macro_micro", label: "Macrografie e/o Micrografie" },
  { field: "requires_ndt", label: "Tracciabilità Controllo NDT" },
];

const TEXT_FIELDS = ["cod_f3", "cliente", "specific_requirements", "note"];
const EDITABLE_FIELDS = [...TEXT_FIELDS, ...BOOLEAN_COLUMNS.map((column) => column.field)];
const DEFAULT_DRAFT = {
  cod_f3: "",
  cliente: "",
  specific_requirements: "",
  note: "",
  requires_chemical_analysis: false,
  requires_mechanical_mp: false,
  requires_mechanical_forged: false,
  requires_hardness_hb: false,
  requires_lot_traceability_text: false,
  requires_lot_traceability_photo: false,
  requires_dimensional: false,
  requires_electrical_conductivity_forged: false,
  requires_marking: false,
  requires_macro_micro: false,
  requires_ndt: false,
};

const DEFAULT_TABLE_STATE = {
  queryOne: "",
  queryTwo: "",
  queryThree: "",
  operatorOne: "and",
  operatorTwo: "and",
  rowLimit: "25",
  sortConfig: { field: "cliente", direction: "asc" },
  scrollLeft: 0,
};

function loadPersistedTableState() {
  if (typeof window === "undefined") {
    return DEFAULT_TABLE_STATE;
  }
  try {
    const raw = window.sessionStorage.getItem(TABLE_STATE_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_TABLE_STATE;
    }
    const parsed = JSON.parse(raw);
    return {
      queryOne: typeof parsed?.queryOne === "string" ? parsed.queryOne : "",
      queryTwo: typeof parsed?.queryTwo === "string" ? parsed.queryTwo : "",
      queryThree: typeof parsed?.queryThree === "string" ? parsed.queryThree : "",
      operatorOne: parsed?.operatorOne === "or" ? "or" : "and",
      operatorTwo: parsed?.operatorTwo === "or" ? "or" : "and",
      rowLimit: ["25", "50", "75", "100", "all"].includes(parsed?.rowLimit) ? parsed.rowLimit : "25",
      sortConfig:
        parsed?.sortConfig && typeof parsed.sortConfig === "object"
          ? {
              field: typeof parsed.sortConfig.field === "string" ? parsed.sortConfig.field : "cliente",
              direction: parsed.sortConfig.direction === "desc" ? "desc" : "asc",
            }
          : DEFAULT_TABLE_STATE.sortConfig,
      scrollLeft: Number.isFinite(Number(parsed?.scrollLeft)) ? Number(parsed.scrollLeft) : 0,
    };
  } catch {
    return DEFAULT_TABLE_STATE;
  }
}

function savePersistedTableState(nextState) {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(TABLE_STATE_STORAGE_KEY, JSON.stringify(nextState));
}

function buildDraft(row) {
  return EDITABLE_FIELDS.reduce(
    (draft, field) => ({
      ...draft,
      [field]: field in DEFAULT_DRAFT && typeof DEFAULT_DRAFT[field] === "boolean" ? Boolean(row[field]) : row[field] ?? "",
    }),
    {},
  );
}

function textValue(value) {
  return String(value ?? "");
}

function normalizeForSearch(value) {
  return textValue(value).toLowerCase();
}

function rowSearchText(row, draft = null) {
  const source = draft || row;
  const flagText = BOOLEAN_COLUMNS.filter((column) => source[column.field])
    .map((column) => column.label)
    .join(" ");
  return normalizeForSearch([source.cod_f3, source.cliente, source.specific_requirements, source.note, flagText].join(" "));
}

function matchesQuery(row, draft, query) {
  const cleaned = query.trim().toLowerCase();
  if (!cleaned) {
    return true;
  }
  return rowSearchText(row, draft).includes(cleaned);
}

function combineMatches(first, operator, second) {
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
  if (typeof left === "boolean" || typeof right === "boolean") {
    return (Number(Boolean(left)) - Number(Boolean(right))) * multiplier;
  }
  return String(left).localeCompare(String(right), "it", { numeric: true, sensitivity: "base" }) * multiplier;
}

function sortValue(row, draft, field) {
  const source = draft || row;
  if (field in source) {
    return source[field];
  }
  return "";
}

function payloadFromDraft(draft) {
  return {
    ...DEFAULT_DRAFT,
    ...draft,
    cod_f3: textValue(draft.cod_f3).trim(),
    cliente: textValue(draft.cliente).trim(),
    specific_requirements: textValue(draft.specific_requirements).trim() || null,
    note: textValue(draft.note).trim() || null,
  };
}

function isRowChanged(row, draft) {
  return EDITABLE_FIELDS.some((field) => textValue(row[field]) !== textValue(draft[field]));
}

function rowClass(row, draft) {
  return isRowChanged(row, draft) ? "bg-amber-50" : "bg-white";
}

function inputClass(changed = false) {
  return [
    "w-full rounded-lg border px-3 py-2 text-sm outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100",
    changed ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white",
  ].join(" ");
}

function SortableHeader({ field, label, onSort, sortConfig, className = "", vertical = false }) {
  const isActive = sortConfig.field === field;
  const indicator = !isActive ? "↕" : sortConfig.direction === "asc" ? "↑" : "↓";
  if (vertical) {
    return (
      <th className={`px-1 py-2 text-center align-bottom ${className}`}>
        <button
          className="inline-flex h-24 w-full items-center justify-center gap-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500 hover:text-slate-800"
          type="button"
          onClick={() => onSort(field)}
        >
          <span className="leading-none" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
            {label}
          </span>
          <span className={isActive ? "text-slate-800" : "text-slate-400"}>{indicator}</span>
        </button>
      </th>
    );
  }
  return (
    <th className={`px-3 py-3 text-left align-middle ${className}`}>
      <button
        className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 hover:text-slate-800"
        type="button"
        onClick={() => onSort(field)}
      >
        <span>{label}</span>
        <span className={isActive ? "text-slate-800" : "text-slate-400"}>{indicator}</span>
      </button>
    </th>
  );
}

function FilterInput({ label, value, onChange, placeholder }) {
  return (
    <label className="block" htmlFor={`customer-requirements-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</span>
      <input
        id={`customer-requirements-${label.toLowerCase().replace(/\s+/g, "-")}`}
        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function LogicSelect({ value, onChange }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Logica</span>
      <select
        className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="and">AND</option>
        <option value="or">OR</option>
      </select>
    </label>
  );
}

function DeleteModal({ item, onCancel, onConfirm, saving }) {
  if (!item) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <p className="text-lg font-semibold text-slate-900">Eliminare requisito cliente?</p>
        <p className="mt-2 text-sm text-slate-500">
          La riga <strong>{item.cod_f3}</strong> verra rimossa dalla tabella requisiti cliente.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
            type="button"
            disabled={saving}
            onClick={onCancel}
          >
            Annulla
          </button>
          <button
            className="rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
            type="button"
            disabled={saving}
            onClick={onConfirm}
          >
            Elimina
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CustomerRequirementsPage() {
  const { token, user } = useAuth();
  const canEdit = canEditQualitySetup(user);
  const initialStateRef = useRef(loadPersistedTableState());
  const tableScrollRef = useRef(null);
  const tableRef = useRef(null);
  const topScrollRef = useRef(null);
  const syncingScrollRef = useRef(false);
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [newDraft, setNewDraft] = useState(DEFAULT_DRAFT);
  const [showNewRow, setShowNewRow] = useState(false);
  const [queryOne, setQueryOne] = useState(initialStateRef.current.queryOne);
  const [queryTwo, setQueryTwo] = useState(initialStateRef.current.queryTwo);
  const [queryThree, setQueryThree] = useState(initialStateRef.current.queryThree);
  const [operatorOne, setOperatorOne] = useState(initialStateRef.current.operatorOne);
  const [operatorTwo, setOperatorTwo] = useState(initialStateRef.current.operatorTwo);
  const [rowLimit, setRowLimit] = useState(initialStateRef.current.rowLimit);
  const [sortConfig, setSortConfig] = useState(initialStateRef.current.sortConfig);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scrollMetrics, setScrollMetrics] = useState({ contentWidth: 1780, viewportWidth: 0 });

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    apiRequest("/customer-requirements", {}, token)
      .then((response) => {
        if (ignore) {
          return;
        }
        const items = response.items || [];
        setRows(items);
        setDrafts(Object.fromEntries(items.map((row) => [row.id, buildDraft(row)])));
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
    savePersistedTableState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      sortConfig,
      scrollLeft: tableScrollRef.current?.scrollLeft || 0,
    });
  }, [operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rowLimit, sortConfig]);

  const filteredRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      const draft = drafts[row.id] || buildDraft(row);
      const first = matchesQuery(row, draft, queryOne);
      const second = matchesQuery(row, draft, queryTwo);
      const third = matchesQuery(row, draft, queryThree);
      return combineMatches(combineMatches(first, operatorOne, second), operatorTwo, third);
    });

    if (sortConfig.field) {
      filtered.sort((left, right) =>
        compareValues(
          sortValue(left, drafts[left.id], sortConfig.field),
          sortValue(right, drafts[right.id], sortConfig.field),
          sortConfig.direction,
        ),
      );
    }
    return filtered;
  }, [drafts, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, rows, sortConfig]);

  const visibleRows = useMemo(() => {
    if (rowLimit === "all") {
      return filteredRows;
    }
    return filteredRows.slice(0, Number(rowLimit));
  }, [filteredRows, rowLimit]);

  useEffect(() => {
    function updateScrollMetrics() {
      const table = tableRef.current;
      const viewport = tableScrollRef.current;
      setScrollMetrics({
        contentWidth: Math.max(table?.scrollWidth || 0, 1780),
        viewportWidth: viewport?.clientWidth || 0,
      });
    }

    updateScrollMetrics();
    window.addEventListener("resize", updateScrollMetrics);
    return () => window.removeEventListener("resize", updateScrollMetrics);
  }, [showNewRow, visibleRows.length]);

  useEffect(() => {
    const left = initialStateRef.current.scrollLeft || 0;
    if (topScrollRef.current) {
      topScrollRef.current.scrollLeft = left;
    }
    if (tableScrollRef.current) {
      tableScrollRef.current.scrollLeft = left;
    }
  }, [scrollMetrics.contentWidth]);

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
    savePersistedTableState({
      queryOne,
      queryTwo,
      queryThree,
      operatorOne,
      operatorTwo,
      rowLimit,
      sortConfig,
      scrollLeft: source.scrollLeft,
    });
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  }

  function updateDraft(rowId, field, value) {
    setMessage("");
    setError("");
    setDrafts((current) => ({
      ...current,
      [rowId]: {
        ...(current[rowId] || {}),
        [field]: value,
      },
    }));
  }

  function updateNewDraft(field, value) {
    setMessage("");
    setError("");
    setNewDraft((current) => ({ ...current, [field]: value }));
  }

  async function saveRow(row) {
    if (!canEdit) {
      setError("Solo admin IT/Qualità possono modificare i requisiti cliente.");
      return;
    }
    const draft = drafts[row.id] || buildDraft(row);
    const payload = payloadFromDraft(draft);
    if (!payload.cod_f3 || !payload.cliente) {
      setError("Cod. F3 e Cliente sono obbligatori.");
      return;
    }
    setSavingId(row.id);
    setError("");
    try {
      const updated = await apiRequest(
        `/customer-requirements/${row.id}`,
        { method: "PUT", body: JSON.stringify(payload) },
        token,
      );
      setRows((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDrafts((current) => ({ ...current, [updated.id]: buildDraft(updated) }));
      setMessage(`Requisito ${updated.cod_f3} salvato.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  async function createRow() {
    if (!canEdit) {
      setError("Solo admin IT/Qualità possono creare requisiti cliente.");
      return;
    }
    const payload = payloadFromDraft(newDraft);
    if (!payload.cod_f3 || !payload.cliente) {
      setError("Cod. F3 e Cliente sono obbligatori.");
      return;
    }
    setSavingId("new");
    setError("");
    try {
      const created = await apiRequest("/customer-requirements", { method: "POST", body: JSON.stringify(payload) }, token);
      setRows((current) => [...current, created]);
      setDrafts((current) => ({ ...current, [created.id]: buildDraft(created) }));
      setNewDraft(DEFAULT_DRAFT);
      setShowNewRow(false);
      setMessage(`Requisito ${created.cod_f3} aggiunto.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingId(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) {
      return;
    }
    if (!canEdit) {
      setError("Solo admin IT/Qualità possono eliminare requisiti cliente.");
      setDeleteTarget(null);
      return;
    }
    setDeleting(true);
    setError("");
    try {
      await apiRequest(`/customer-requirements/${deleteTarget.id}`, { method: "DELETE" }, token);
      setRows((current) => current.filter((item) => item.id !== deleteTarget.id));
      setDrafts((current) => {
        const next = { ...current };
        delete next[deleteTarget.id];
        return next;
      });
      setMessage(`Requisito ${deleteTarget.cod_f3} eliminato.`);
      setDeleteTarget(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="w-full max-w-none space-y-6">
      <section className="w-full rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Strumenti qualità</p>
            <h1 className="mt-2 text-2xl font-semibold text-ink">Requisiti Cliente</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
              {filteredRows.length} righe visibili
            </span>
            <button
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
              disabled={!canEdit}
              type="button"
              onClick={() => setShowNewRow((current) => !current)}
            >
              {showNewRow ? "Chiudi nuova riga" : "Aggiungi riga"}
            </button>
          </div>
        </div>

        {(message || error) && (
          <div className={`mt-5 rounded-2xl px-4 py-3 text-sm font-semibold ${error ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>
            {error || message}
          </div>
        )}
        {!canEdit ? <p className="mt-4 text-sm text-slate-500">Solo admin IT/Qualità possono modificare i requisiti cliente.</p> : null}

        {showNewRow && (
          <div className="mt-6 rounded-2xl border border-sky-200 bg-sky-50/60 p-4">
            <p className="text-sm font-semibold text-slate-900">Nuovo requisito cliente</p>
            <div className="mt-4 grid gap-3 xl:grid-cols-[150px_220px_1fr_1fr_auto]">
              <input
                className={inputClass()}
                disabled={!canEdit}
                placeholder="Cod. F3"
                value={newDraft.cod_f3}
                onChange={(event) => updateNewDraft("cod_f3", event.target.value)}
              />
              <input
                className={inputClass()}
                disabled={!canEdit}
                placeholder="Cliente"
                value={newDraft.cliente}
                onChange={(event) => updateNewDraft("cliente", event.target.value)}
              />
              <input
                className={inputClass()}
                disabled={!canEdit}
                placeholder="Requisiti specifici"
                value={newDraft.specific_requirements}
                onChange={(event) => updateNewDraft("specific_requirements", event.target.value)}
              />
              <input
                className={inputClass()}
                disabled={!canEdit}
                placeholder="Note"
                value={newDraft.note}
                onChange={(event) => updateNewDraft("note", event.target.value)}
              />
              <button
                className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
                type="button"
                disabled={!canEdit || savingId === "new"}
                onClick={createRow}
              >
                Aggiungi
              </button>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
              {BOOLEAN_COLUMNS.map((column) => (
                <label key={column.field} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                  <input
                    disabled={!canEdit}
                    type="checkbox"
                    checked={Boolean(newDraft[column.field])}
                    onChange={(event) => updateNewDraft(column.field, event.target.checked)}
                  />
                  {column.label}
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 flex items-end gap-2 overflow-x-auto pb-1">
          <div className="min-w-[220px] max-w-[220px]">
          <FilterInput label="Filtro 1" placeholder="Tutti i campi" value={queryOne} onChange={setQueryOne} />
          </div>
          <div className="min-w-[90px] max-w-[90px]">
          <LogicSelect value={operatorOne} onChange={setOperatorOne} />
          </div>
          <div className="min-w-[220px] max-w-[220px]">
          <FilterInput label="Filtro 2" placeholder="Campi non presi dal 1" value={queryTwo} onChange={setQueryTwo} />
          </div>
          <div className="min-w-[90px] max-w-[90px]">
          <LogicSelect value={operatorTwo} onChange={setOperatorTwo} />
          </div>
          <div className="min-w-[220px] max-w-[220px]">
          <FilterInput label="Filtro 3" placeholder="Campi non presi da 1 e 2" value={queryThree} onChange={setQueryThree} />
          </div>
          <label className="ml-auto block min-w-[88px] max-w-[88px]">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Righe</span>
            <select
              className="w-full rounded-xl border border-border bg-white px-2 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
              value={rowLimit}
              onChange={(event) => setRowLimit(event.target.value)}
            >
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="75">75</option>
              <option value="100">100</option>
              <option value="all">Tutte</option>
            </select>
          </label>
        </div>
      </section>

      <section className="w-full">
        <div className="sticky top-0 z-20 rounded-xl border border-border bg-slate-50 px-3 py-2 shadow-sm">
          <div
            ref={topScrollRef}
            className="incoming-top-scroll overflow-x-auto overflow-y-hidden"
            onScroll={(event) => syncScroll(tableScrollRef.current, event.currentTarget)}
          >
            <div
              className="h-4 min-w-full"
              style={{ width: Math.max(scrollMetrics.contentWidth, scrollMetrics.viewportWidth) }}
            />
          </div>
        </div>
        <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div
            ref={tableScrollRef}
            className="incoming-grid-scroll overflow-x-hidden overflow-y-visible"
            onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
          >
          <table ref={tableRef} className="min-w-[2420px] table-fixed border-collapse text-sm">
            <colgroup>
              <col className="w-[180px]" />
              <col className="w-[164px]" />
              {BOOLEAN_COLUMNS.map((column) => (
                <col key={column.field} className="w-[54px]" />
              ))}
              <col className="w-[450px]" />
              <col className="w-[560px]" />
              <col className="w-[260px]" />
            </colgroup>
            <thead className="sticky-list-head">
              <tr className="border-b border-slate-200 bg-slate-50">
                <SortableHeader field="cod_f3" label="Cod. F3" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="cliente" label="Cliente" onSort={toggleSort} sortConfig={sortConfig} />
                {BOOLEAN_COLUMNS.map((column) => (
                  <SortableHeader
                    key={column.field}
                    field={column.field}
                    label={column.label}
                    onSort={toggleSort}
                    sortConfig={sortConfig}
                    vertical
                  />
                ))}
                <SortableHeader field="specific_requirements" label="Requisiti specifici" onSort={toggleSort} sortConfig={sortConfig} />
                <SortableHeader field="note" label="Note" onSort={toggleSort} sortConfig={sortConfig} />
                <th className="px-3 py-3 text-right text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td className="px-3 py-10 text-center text-slate-500" colSpan={BOOLEAN_COLUMNS.length + 5}>
                    Caricamento requisiti cliente...
                  </td>
                </tr>
              )}
              {!loading &&
                visibleRows.map((row) => {
                  const draft = drafts[row.id] || buildDraft(row);
                  const changed = isRowChanged(row, draft);
                  return (
                    <tr key={row.id} className={`border-b border-slate-100 ${rowClass(row, draft)}`}>
                      <td className="px-3 py-3 align-top">
                        <input
                          className={inputClass(textValue(row.cod_f3) !== textValue(draft.cod_f3))}
                          disabled={!canEdit}
                          value={draft.cod_f3}
                          onChange={(event) => updateDraft(row.id, "cod_f3", event.target.value)}
                        />
                      </td>
                      <td className="px-3 py-3 align-top">
                        <input
                          className={inputClass(textValue(row.cliente) !== textValue(draft.cliente))}
                          disabled={!canEdit}
                          value={draft.cliente}
                          onChange={(event) => updateDraft(row.id, "cliente", event.target.value)}
                        />
                      </td>
                      {BOOLEAN_COLUMNS.map((column) => (
                        <td key={column.field} className="px-1 py-3 text-center align-top">
                          <input
                            className="h-4 w-4 accent-teal-700"
                            disabled={!canEdit}
                            type="checkbox"
                            checked={Boolean(draft[column.field])}
                            onChange={(event) => updateDraft(row.id, column.field, event.target.checked)}
                          />
                        </td>
                      ))}
                      <td className="px-3 py-3 align-top">
                        <textarea
                          className={`${inputClass(textValue(row.specific_requirements) !== textValue(draft.specific_requirements))} min-h-10 resize-y`}
                          disabled={!canEdit}
                          value={draft.specific_requirements || ""}
                          onChange={(event) => updateDraft(row.id, "specific_requirements", event.target.value)}
                        />
                      </td>
                      <td className="px-3 py-3 align-top">
                        <textarea
                          className={`${inputClass(textValue(row.note) !== textValue(draft.note))} min-h-10 resize-y`}
                          disabled={!canEdit}
                          value={draft.note || ""}
                          onChange={(event) => updateDraft(row.id, "note", event.target.value)}
                        />
                      </td>
                      <td className="px-3 py-3 text-right align-top">
                        <div className="flex min-w-[236px] justify-end gap-2 whitespace-nowrap">
                          {changed ? (
                            <button
                              className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                              type="button"
                              disabled={!canEdit || savingId === row.id}
                              onClick={() => setDrafts((current) => ({ ...current, [row.id]: buildDraft(row) }))}
                            >
                              Annulla modifiche
                            </button>
                          ) : null}
                          <button
                            className="rounded-xl bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
                            type="button"
                            disabled={!canEdit || !changed || savingId === row.id}
                            onClick={() => saveRow(row)}
                          >
                            Salva
                          </button>
                          <button
                            className="rounded-xl border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                            disabled={!canEdit}
                            type="button"
                            onClick={() => setDeleteTarget(row)}
                          >
                            Elimina
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              {!loading && visibleRows.length === 0 && (
                <tr>
                  <td className="px-3 py-10 text-center text-slate-500" colSpan={BOOLEAN_COLUMNS.length + 5}>
                    Nessun requisito cliente trovato con i filtri attuali.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      </section>
      <DeleteModal item={deleteTarget} saving={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={confirmDelete} />
    </div>
  );
}
