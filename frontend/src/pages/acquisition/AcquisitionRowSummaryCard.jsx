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

export default function AcquisitionRowSummaryCard({
  canValidateFinal = false,
  compact = false,
  containerClassName = "",
  row,
  rowId,
  showStatus = false,
  showTitle = true,
}) {
  if (!row) {
    return null;
  }

  const headCellClass = compact
    ? "px-3 py-2"
    : "px-3 py-2";
  const bodyCellClass = compact
    ? "px-3 py-3 text-slate-800"
    : "px-3 py-3 text-slate-800";
  const wrapperClasses = "overflow-hidden rounded-2xl border border-border bg-white h-full";
  const tableClasses = compact ? "min-w-full divide-y divide-slate-200 text-[18px]" : "min-w-full divide-y divide-slate-200 text-sm";
  const theadClasses = "bg-slate-50";
  const trHeadClasses = compact
    ? "text-left font-semibold uppercase tracking-[0.16em] text-slate-500 text-[12px]"
    : "text-left font-semibold uppercase tracking-[0.16em] text-slate-500 text-[11px]";

  return (
    <div className="space-y-4">
      {showTitle ? (
        <div>
          <h2 className="mt-2 text-2xl font-semibold text-ink">Riga #{rowId}</h2>
        </div>
      ) : null}

      <div className={`${wrapperClasses} ${containerClassName}`.trim()}>
        <div className="overflow-x-auto">
          <table className={tableClasses}>
            <thead className={theadClasses}>
              <tr className={trHeadClasses}>
                <th className={headCellClass}>Fornitore</th>
                <th className={headCellClass}>Lega</th>
                <th className={headCellClass}>Ø</th>
                <th className={headCellClass}>Cdq</th>
                <th className={headCellClass}>Colata</th>
                <th className={headCellClass}>Ddt</th>
                <th className={headCellClass}>Peso Kg</th>
                <th className={headCellClass}>Vs. Odv</th>
                {showStatus ? <th className={headCellClass}>Stato</th> : null}
              </tr>
            </thead>
            <tbody className="bg-white">
              <tr>
                <td className={bodyCellClass.replace("text-slate-800", "text-slate-900")}>{displaySupplierName(row)}</td>
                <td className={bodyCellClass}>{composeLega(row)}</td>
                <td className={bodyCellClass}>{formatRowFieldDisplay("diametro", row.diametro) || "-"}</td>
                <td className={bodyCellClass}>{row.cdq || "-"}</td>
                <td className={bodyCellClass}>{row.colata || "-"}</td>
                <td className={bodyCellClass}>{row.ddt || `#${row.document_ddt_id}`}</td>
                <td className={bodyCellClass}>{formatRowFieldDisplay("peso", row.peso) || "-"}</td>
                <td className={bodyCellClass}>{row.ordine || "-"}</td>
                {showStatus ? (
                  <td className={bodyCellClass}>
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
