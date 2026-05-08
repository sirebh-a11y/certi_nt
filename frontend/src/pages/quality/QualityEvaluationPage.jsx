import { useEffect, useMemo, useState } from "react";

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

export default function QualityEvaluationPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

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
          <span className="font-semibold text-ink">{rows.length}</span> righe confermate
          {changedRows ? <span className="ml-3 text-amber-700">{changedRows} modificate</span> : null}
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento valutazioni...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
      {statusMessage ? <p className="mt-6 text-sm text-slate-600">{statusMessage}</p> : null}

      <div className="mt-8 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-[1500px] w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-[0.16em] text-slate-500">
              <th className="px-3 py-3 text-left">Riga</th>
              <th className="px-3 py-3 text-left">Data ricezione</th>
              <th className="px-3 py-3 text-left">Data accettazione</th>
              <th className="px-3 py-3 text-left">Lega</th>
              <th className="px-3 py-3 text-left">Ø</th>
              <th className="px-3 py-3 text-left">Cdq</th>
              <th className="px-3 py-3 text-left">Colata</th>
              <th className="px-3 py-3 text-left">Ddt</th>
              <th className="px-3 py-3 text-left">Peso Kg</th>
              <th className="px-3 py-3 text-left">Ordine</th>
              <th className="px-3 py-3 text-left">Data richiesta</th>
              <th className="px-3 py-3 text-left">N° analisi</th>
              <th className="px-3 py-3 text-left">Valutazione</th>
              <th className="px-3 py-3 text-left">Note</th>
              <th className="px-3 py-3 text-left">Azione</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const draft = drafts[row.id] || buildDraft(row);
              const changed = isRowChanged(row, draft);
              return (
                <tr key={row.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-3 py-3 font-semibold text-slate-700">#{row.id}</td>
                  <td className="px-3 py-3">
                    <input
                      className={`w-36 rounded-lg border px-2 py-2 ${fieldClass({ changed: textValue(row.qualita_data_ricezione) !== textValue(draft.qualita_data_ricezione) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_ricezione", event.target.value)}
                      type="date"
                      value={draft.qualita_data_ricezione || ""}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <input
                      className={`w-36 rounded-lg border px-2 py-2 ${fieldClass({ changed: textValue(row.qualita_data_accettazione) !== textValue(draft.qualita_data_accettazione) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_accettazione", event.target.value)}
                      type="date"
                      value={draft.qualita_data_accettazione || ""}
                    />
                  </td>
                  <td className="px-3 py-3 text-slate-700">{composeLega(row)}</td>
                  <td className="px-3 py-3 text-slate-700">{formatRowFieldDisplay("diametro", row.diametro)}</td>
                  <td className="px-3 py-3 font-semibold text-slate-900">{formatRowFieldDisplay("cdq", row.cdq)}</td>
                  <td className="px-3 py-3 text-slate-700">{formatRowFieldDisplay("colata", row.colata)}</td>
                  <td className="px-3 py-3 text-slate-700">{formatRowFieldDisplay("ddt", row.ddt)}</td>
                  <td className="px-3 py-3 text-slate-700">{formatRowFieldDisplay("peso", row.peso)}</td>
                  <td className="px-3 py-3 text-slate-700">{formatRowFieldDisplay("ordine", row.ordine)}</td>
                  <td className="px-3 py-3">
                    <input
                      className={`w-36 rounded-lg border px-2 py-2 ${fieldClass({ changed: textValue(row.qualita_data_richiesta) !== textValue(draft.qualita_data_richiesta) })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_data_richiesta", event.target.value)}
                      type="date"
                      value={draft.qualita_data_richiesta || ""}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <input
                      className={`w-32 rounded-lg border px-2 py-2 ${fieldClass({
                        changed: textValue(row.qualita_numero_analisi) !== textValue(draft.qualita_numero_analisi),
                        review: row.qualita_numero_analisi_da_ricontrollare,
                      })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_numero_analisi", event.target.value)}
                      value={draft.qualita_numero_analisi || ""}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <select
                      className={`w-52 rounded-lg border px-2 py-2 ${fieldClass({ changed: textValue(row.qualita_valutazione) !== textValue(draft.qualita_valutazione) })}`}
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
                  <td className="px-3 py-3">
                    <textarea
                      className={`min-h-10 w-56 rounded-lg border px-2 py-2 ${fieldClass({
                        changed: textValue(row.qualita_note) !== textValue(draft.qualita_note),
                        review: row.qualita_note_da_ricontrollare,
                      })}`}
                      onChange={(event) => updateDraft(row.id, "qualita_note", event.target.value)}
                      value={draft.qualita_note || ""}
                    />
                  </td>
                  <td className="px-3 py-3">
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
        {!loading && rows.length === 0 ? (
          <p className="px-5 py-8 text-sm text-slate-500">Nessuna riga completamente confermata disponibile per la valutazione qualità.</p>
        ) : null}
      </div>
    </section>
  );
}
