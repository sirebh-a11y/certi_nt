import { formatRowFieldDisplay } from "./fieldFormatting";

function stateClasses(state) {
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function workflowLabel(value) {
  if (value === "in_lavorazione") {
    return "In lavorazione";
  }
  if (value === "validata_quality") {
    return "Validata";
  }
  if (value === "riaperta") {
    return "Riaperta";
  }
  if (value === "nuova") {
    return "Nuova";
  }
  return value || "-";
}

function displaySupplierName(row) {
  return row?.fornitore_nome || row?.fornitore_raw || "-";
}

function composeLega(row) {
  return row?.lega_designazione || row?.lega_base || row?.variante_lega || "-";
}

export default function AcquisitionRowSummaryCard({ canValidateFinal = false, row, rowId, showStatus = false, showTitle = true }) {
  if (!row) {
    return null;
  }

  return (
    <div className="space-y-4">
      {showTitle ? (
        <div>
          <h2 className="mt-2 text-2xl font-semibold text-ink">Riga #{rowId}</h2>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-border bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-3 py-2">Fornitore</th>
                <th className="px-3 py-2">Lega</th>
                <th className="px-3 py-2">Ø</th>
                <th className="px-3 py-2">Cdq</th>
                <th className="px-3 py-2">Colata</th>
                <th className="px-3 py-2">Ddt</th>
                <th className="px-3 py-2">Peso Kg</th>
                <th className="px-3 py-2">Vs. Odv</th>
                {showStatus ? <th className="px-3 py-2">Stato</th> : null}
              </tr>
            </thead>
            <tbody className="bg-white">
              <tr>
                <td className="px-3 py-3 text-slate-900">{displaySupplierName(row)}</td>
                <td className="px-3 py-3 text-slate-800">{composeLega(row)}</td>
                <td className="px-3 py-3 text-slate-800">{formatRowFieldDisplay("diametro", row.diametro) || "-"}</td>
                <td className="px-3 py-3 text-slate-800">{row.cdq || "-"}</td>
                <td className="px-3 py-3 text-slate-800">{row.colata || "-"}</td>
                <td className="px-3 py-3 text-slate-800">{row.ddt || `#${row.document_ddt_id}`}</td>
                <td className="px-3 py-3 text-slate-800">{formatRowFieldDisplay("peso", row.peso) || "-"}</td>
                <td className="px-3 py-3 text-slate-800">{row.ordine || "-"}</td>
                {showStatus ? (
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${stateClasses(row.stato_tecnico)}`}>Tecnico {row.stato_tecnico}</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-700">{workflowLabel(row.stato_workflow)}</span>
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${row.validata_finale ? stateClasses("verde") : stateClasses(canValidateFinal ? "giallo" : "rosso")}`}>
                        {row.validata_finale ? "Validata" : canValidateFinal ? "Pronta da validare" : "Non pronta"}
                      </span>
                    </div>
                  </td>
                ) : null}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
