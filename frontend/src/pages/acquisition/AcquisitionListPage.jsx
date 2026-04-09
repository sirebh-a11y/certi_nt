import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const BLOCK_LABELS = {
  match: "Match",
  chimica: "Chim.",
  proprieta: "Prop.",
  note: "Note",
};

function activityLabelFromState(state) {
  if (state === "verde") {
    return "verifica";
  }
  if (state === "giallo") {
    return "quasi";
  }
  return "da fare";
}

function finalActivityLabel(row) {
  if (row.validata_finale) {
    return "confermata";
  }
  if (row.stato_tecnico === "verde") {
    return "verifica";
  }
  if (row.stato_tecnico === "giallo") {
    return "quasi";
  }
  return "da fare";
}

function finalActivityClasses(row) {
  if (row.validata_finale) {
    return "border-slate-300 bg-slate-100 text-slate-700";
  }
  return stateBadgeClasses(row.stato_tecnico);
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

function stateTone(state) {
  if (state === "verde") {
    return "bg-emerald-500";
  }
  if (state === "giallo") {
    return "bg-amber-500";
  }
  return "bg-rose-500";
}

function stateBadgeClasses(state) {
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

function composeLega(row) {
  return row.lega_designazione || row.lega_base || row.variante_lega || "-";
}

function matchLabel(row) {
  if (row.match_state === "confermato") {
    return "Pronto";
  }
  if (row.match_state === "proposto" || row.match_state === "cambiato") {
    return "Da verificare";
  }
  return "Non pronto";
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

function hasAttention(row) {
  return Object.values(row.block_states || {}).some((state) => state !== "verde");
}

function rowSortScore(row) {
  const priorityRank = row.priorita_operativa === "alta" ? 0 : row.priorita_operativa === "media" ? 1 : 2;
  const technicalRank = row.stato_tecnico === "rosso" ? 0 : row.stato_tecnico === "giallo" ? 1 : 2;
  const workflowRank = row.stato_workflow === "riaperta" ? 0 : row.stato_workflow === "in_lavorazione" ? 1 : row.stato_workflow === "nuova" ? 2 : 3;
  const updatedAt = row.updated_at ? new Date(row.updated_at).getTime() : 0;
  return [priorityRank, technicalRank, workflowRank, -updatedAt, -row.id];
}

function RowStateCell({ row }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <StateDot state={row.stato_tecnico} />
        <span className="text-xs font-semibold text-slate-700">{activityLabelFromState(row.stato_tecnico)}</span>
      </div>
      <div className="text-[11px] text-slate-500">{workflowLabel(row.stato_workflow)}</div>
      <div className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${finalActivityClasses(row)}`}>
        {finalActivityLabel(row)}
      </div>
    </div>
  );
}

function StateDot({ state }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${stateTone(state)}`} />;
}

function DataCell({ value, state, secondary }) {
  return (
    <div className="min-w-[90px]">
      <div className="flex items-center gap-2">
        <StateDot state={state} />
        <span className="truncate text-sm font-medium text-slate-800">{value || "-"}</span>
      </div>
      {secondary ? <div className="mt-1 truncate text-[11px] text-slate-500">{secondary}</div> : null}
    </div>
  );
}

function BlockCell({ label, state, secondary }) {
  return (
    <div className="min-w-[88px]">
      <div className="flex items-center gap-2">
        <StateDot state={state} />
        <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">{label}</span>
      </div>
      <div className="mt-1 truncate text-[11px] text-slate-500">{secondary}</div>
    </div>
  );
}

export default function AcquisitionListPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
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
    const normalizedQuery = query.trim().toLowerCase();
    let nextRows = rows;

    if (normalizedQuery) {
      nextRows = nextRows.filter((row) => {
        const haystack = [
          row.id,
          row.fornitore_raw,
          row.lega_designazione,
          row.lega_base,
          row.diametro,
          row.cdq,
          row.colata,
          row.ddt,
          row.peso,
          row.ordine,
          row.certificate_file_name,
          row.note_documento,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(normalizedQuery);
      });
    }

    return [...nextRows].sort((left, right) => {
      const leftScore = rowSortScore(left);
      const rightScore = rowSortScore(right);
      for (let index = 0; index < leftScore.length; index += 1) {
        if (leftScore[index] !== rightScore[index]) {
          return leftScore[index] - rightScore[index];
        }
      }
      return 0;
    });
  }, [query, rows]);

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

      <div className="grid gap-2 xl:max-w-xl">
        <div className="min-w-0">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="incoming-quality-search">
            Ricerca
          </label>
          <input
          className="rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700"
          id="incoming-quality-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Fornitore, cdq, colata, ddt..."
          value={query}
        />
        </div>
      </div>

      {loading ? <p className="text-sm text-slate-500">Caricamento righe...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="overflow-hidden rounded-2xl border border-border bg-white">
        <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
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
        <div
          className="incoming-grid-scroll h-[calc(100vh-250px)] min-h-[520px] overflow-y-auto overflow-x-hidden"
          onScroll={(event) => syncScroll(topScrollRef.current, event.currentTarget)}
          ref={tableViewportRef}
        >
          <table className="min-w-[1480px] divide-y divide-slate-200 text-sm" ref={tableRef}>
              <thead className="sticky top-0 z-10 bg-slate-50 shadow-sm">
                <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <th className="px-3 py-3">N°</th>
                  <th className="px-3 py-3">Fornitore</th>
                  <th className="px-3 py-3">Lega</th>
                  <th className="px-3 py-3">Ø</th>
                  <th className="px-3 py-3">Cdq</th>
                  <th className="px-3 py-3">Colata</th>
                  <th className="px-3 py-3">Ddt</th>
                  <th className="px-3 py-3">Peso Kg</th>
                  <th className="px-3 py-3">Ordine</th>
                  <th className="px-3 py-3">Match</th>
                  <th className="px-3 py-3">Chim.</th>
                  <th className="px-3 py-3">Prop.</th>
                  <th className="px-3 py-3">Note</th>
                  <th className="px-3 py-3">Stato</th>
                  <th className="px-3 py-3 text-right">Apri</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleRows.map((row) => (
                  <tr className="align-top hover:bg-slate-50/70" key={row.id}>
                    <td className="whitespace-nowrap px-3 py-3 font-semibold text-slate-700">{row.id}</td>
                    <td className="min-w-[220px] max-w-[220px] px-3 py-3">
                      <div className="truncate font-medium text-slate-900" title={row.fornitore_raw || "-"}>
                        {row.fornitore_raw || "-"}
                      </div>
                    </td>
                    <td className="max-w-[110px] px-3 py-3">
                      <div className="truncate font-medium text-slate-800" title={composeLega(row)}>
                        {composeLega(row)}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={ddtFieldState(row, "diametro")} value={row.diametro} />
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={ddtFieldState(row, "cdq")} value={row.cdq} />
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={ddtFieldState(row, "colata")} value={row.colata} />
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={row.ddt ? "verde" : "rosso"} value={row.ddt || `#${row.document_ddt_id}`} />
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={ddtFieldState(row, "peso")} value={row.peso} />
                    </td>
                    <td className="px-3 py-3">
                      <DataCell state={ddtFieldState(row, "ordine")} value={row.ordine} />
                    </td>
                    <td className="px-3 py-3">
                      <BlockCell
                        label={BLOCK_LABELS.match}
                        secondary={compactMatchReference(row)}
                        state={row.block_states?.match || "rosso"}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <BlockCell
                        label={BLOCK_LABELS.chimica}
                        secondary={activityLabelFromState(row.block_states?.chimica || "rosso")}
                        state={row.block_states?.chimica || "rosso"}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <BlockCell
                        label={BLOCK_LABELS.proprieta}
                        secondary={activityLabelFromState(row.block_states?.proprieta || "rosso")}
                        state={row.block_states?.proprieta || "rosso"}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <div className="min-w-[140px]">
                        <div className="flex items-center gap-2">
                          <StateDot state={row.block_states?.note || "rosso"} />
                          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">Note</span>
                        </div>
                        <div className="mt-1 truncate text-[11px] text-slate-500" title={row.note_documento || activityLabelFromState(row.block_states?.note || "rosso")}>
                          {row.note_documento || activityLabelFromState(row.block_states?.note || "rosso")}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <RowStateCell row={row} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-right">
                      <Link className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-slate-700 hover:bg-white" to={`/acquisition/${row.id}`}>
                        Apri
                      </Link>
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
