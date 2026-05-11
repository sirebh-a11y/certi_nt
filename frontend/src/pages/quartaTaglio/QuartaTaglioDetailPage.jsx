import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const STATUS_CLASSES = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  missing: "border-amber-200 bg-amber-50 text-amber-800",
  missing_from_supplier: "border-rose-200 bg-rose-50 text-rose-800",
  different: "border-amber-200 bg-amber-50 text-amber-800",
  out_of_range: "border-rose-200 bg-rose-50 text-rose-800",
  not_in_standard: "border-rose-200 bg-rose-50 text-rose-800",
  not_checked: "border-slate-200 bg-slate-50 text-slate-700",
};

const STATUS_LABELS = {
  green: "Pronto",
  yellow: "Da completare",
  red: "Bloccato",
  ok: "OK",
  missing: "Manca",
  missing_from_supplier: "Manca da fornitore",
  different: "Diverso",
  out_of_range: "Fuori standard",
  not_in_standard: "Non previsto",
  not_checked: "Non verificato",
};

const METHOD_LABELS = {
  weighted: "media pesata",
  average: "media",
  single: "singolo",
  missing: "-",
};

function statusClass(status) {
  return STATUS_CLASSES[status] || STATUS_CLASSES.not_checked;
}

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("it-IT", { maximumFractionDigits: digits });
}

function formatLimit(min, max) {
  if (min === null && max === null) {
    return "-";
  }
  if (min !== null && max !== null) {
    return `${formatNumber(min)} - ${formatNumber(max)}`;
  }
  if (min !== null) {
    return `>= ${formatNumber(min)}`;
  }
  return `<= ${formatNumber(max)}`;
}

function standardLabel(standard) {
  return [
    standard.lega_base,
    standard.norma,
    standard.trattamento_termico,
    standard.tipo_prodotto,
    standard.misura_tipo,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function QuartaTaglioDetailPage() {
  const { codOdp } = useParams();
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingStandardId, setSavingStandardId] = useState(null);
  const [standardError, setStandardError] = useState("");
  const [standards, setStandards] = useState([]);
  const [manualStandardId, setManualStandardId] = useState("");

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    apiRequest(`/quarta-taglio/${encodeURIComponent(codOdp)}`, {}, token)
      .then((response) => {
        if (!ignore) {
          setData(response);
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
  }, [codOdp, token]);

  useEffect(() => {
    let ignore = false;
    apiRequest("/standards?stato=attivo", {}, token)
      .then((response) => {
        if (!ignore) {
          setStandards(response.items || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setStandards([]);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  function confirmStandard(standardId) {
    setSavingStandardId(standardId);
    setStandardError("");
    apiRequest(
      `/quarta-taglio/${encodeURIComponent(codOdp)}/standard`,
      {
        method: "POST",
        body: JSON.stringify({ standard_id: standardId }),
      },
      token,
    )
      .then((response) => {
        setData(response);
      })
      .catch((requestError) => {
        setStandardError(requestError.message);
      })
      .finally(() => {
        setSavingStandardId(null);
      });
  }

  const headerRows = useMemo(() => {
    const header = data?.header || {};
    return [
      ["Certificato", header.numero_certificato || "Da assegnare"],
      ["Cliente", header.cliente || "Da eSolver"],
      ["Ordine cliente", header.ordine_cliente || "Da eSolver"],
      ["DDT", header.ddt || "Da eSolver"],
      ["Codice F3", header.codice_f3 || "-"],
      ["Descrizione", header.descrizione || "Da completare con dati articolo/eSolver"],
      ["Colata", header.colata || "-"],
      ["Quantità", header.quantita ? formatNumber(header.quantita, 2) : "-"],
    ];
  }, [data]);

  if (loading) {
    return <p className="text-sm text-slate-500">Caricamento certificato...</p>;
  }

  if (error) {
    return (
      <section className="space-y-3">
        <Link className="text-sm font-semibold text-accent hover:underline" to="/quarta-taglio">
          Torna a Certificazione
        </Link>
        <p className="text-sm text-rose-600">{error}</p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <Link className="text-sm font-semibold text-accent hover:underline" to="/quarta-taglio">
            Torna a Certificazione
          </Link>
          <p className="mt-3 text-sm uppercase tracking-[0.3em] text-slate-500">Certificato materiale</p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-950">OL {data.cod_odp}</h2>
          <p className="mt-1 text-sm text-slate-500">{data.status_message}</p>
        </div>
        <span className={`inline-flex w-fit rounded-lg border px-3 py-1.5 text-sm font-semibold ${statusClass(data.status_color)}`}>
          {STATUS_LABELS[data.status_color] || data.status_color}
        </span>
      </div>

      {!data.ready ? (
        <Panel title="Dati ancora mancanti">
          <Table
            columns={["CDQ", "Colata", "Stato", "Cosa manca"]}
            rows={(data.missing_items || []).map((item) => [
              item.cdq,
              item.colata || "-",
              <StatusPill key="status" status={item.status_color} />,
              <div className="space-y-1" key="details">
                <div className="font-medium">{item.message}</div>
                {(item.details || []).map((detail) => (
                  <div className="text-xs text-slate-500" key={detail}>
                    {detail}
                  </div>
                ))}
              </div>,
            ])}
            emptyText="Nessun blocco tecnico rilevato."
          />
        </Panel>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="Dati certificato">
          <div className="grid gap-2 md:grid-cols-2">
            {headerRows.map(([label, value]) => (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" key={label}>
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
                <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Standard">
          {data.selected_standard ? (
            <div
              className={`rounded-lg border px-3 py-2 text-sm ${
                data.selected_standard_confirmed
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              <div className="font-semibold">{data.selected_standard.label}</div>
              <div className="mt-1 text-xs">
                {data.selected_standard_confirmed ? "Standard confermato per questo OL." : "Scelta proposta: confermare prima della generazione."}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Standard non scelto automaticamente: serve conferma utente.
            </div>
          )}
          {standardError ? <div className="mt-2 text-sm text-rose-600">{standardError}</div> : null}
          <div className="mt-3 space-y-2">
            {(data.standard_candidates || []).map((candidate) => (
              <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm" key={candidate.id}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-slate-900">{candidate.label}</span>
                  <span className="text-xs font-semibold uppercase text-slate-500">{candidate.confidence}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{candidate.reasons.join(" · ") || candidate.code}</div>
                <button
                  className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={savingStandardId !== null || (data.selected_standard_confirmed && data.selected_standard?.id === candidate.id)}
                  onClick={() => confirmStandard(candidate.id)}
                  type="button"
                >
                  {data.selected_standard_confirmed && data.selected_standard?.id === candidate.id
                    ? "Confermato"
                    : savingStandardId === candidate.id
                      ? "Salvataggio..."
                      : "Conferma standard"}
                </button>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="manual-standard">
              Conferma manuale
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                className="min-w-0 flex-1 rounded-lg border border-border bg-white px-3 py-2 text-sm text-slate-700"
                id="manual-standard"
                onChange={(event) => setManualStandardId(event.target.value)}
                value={manualStandardId}
              >
                <option value="">Scegli standard</option>
                {standards.map((standard) => (
                  <option key={standard.id} value={standard.id}>
                    {standardLabel(standard)}
                  </option>
                ))}
              </select>
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!manualStandardId || savingStandardId !== null}
                onClick={() => confirmStandard(Number(manualStandardId))}
                type="button"
              >
                {savingStandardId === Number(manualStandardId) ? "Salvataggio..." : "Conferma"}
              </button>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Materiali collegati">
        <Table
          columns={["CDQ", "Colata", "Articolo", "Quantità", "Lotti", "Righe app"]}
          rows={(data.materials || []).map((item) => [
            item.cdq,
            item.colata || "-",
            item.cod_art || "-",
            formatNumber(item.qta_totale, 2),
            (item.cod_lotti || []).join(", ") || "-",
            item.matching_row_ids?.length
              ? item.matching_row_ids.map((rowId) => (
                  <Link className="mr-2 font-semibold text-accent hover:underline" key={rowId} to={`/acquisition/${rowId}`}>
                    #{rowId}
                  </Link>
                ))
              : "-",
          ])}
        />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Chimica">
          <ValueTable values={data.chemistry || []} />
        </Panel>
        <Panel title="Proprietà">
          <ValueTable values={data.properties || []} />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Note">
          <Table
            columns={["Nota", "Valore", "Stato", "Messaggio"]}
            rows={(data.notes || []).map((item) => [item.label, item.value || "-", <StatusPill key="status" status={item.status} />, item.message])}
          />
        </Panel>
        <Panel title="Seconda pagina">
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
            Placeholder per la seconda pagina del certificato. La compileremo quando saranno definite le regole finali.
          </div>
        </Panel>
      </div>
    </section>
  );
}

function Panel({ title, children }) {
  return (
    <div className="rounded-xl border border-border bg-white p-4">
      <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Table({ columns, rows, emptyText = "Nessun dato." }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {columns.map((column) => (
              <th className="px-3 py-2.5" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length ? (
            rows.map((row, index) => (
              <tr className="align-top" key={index}>
                {row.map((cell, cellIndex) => (
                  <td className="px-3 py-2.5 text-slate-700" key={cellIndex}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td className="px-3 py-4 text-slate-500" colSpan={columns.length}>
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ValueTable({ values }) {
  return (
    <Table
      columns={["Campo", "Valore", "Metodo", "Standard", "Stato", "Messaggio"]}
      rows={values.map((item) => [
        item.field,
        formatNumber(item.value),
        METHOD_LABELS[item.method] || item.method,
        formatLimit(item.standard_min, item.standard_max),
        <StatusPill key="status" status={item.status} />,
        item.message || "-",
      ])}
    />
  );
}

function StatusPill({ status }) {
  return <span className={`inline-flex rounded-lg border px-2 py-1 text-xs font-semibold ${statusClass(status)}`}>{STATUS_LABELS[status] || status}</span>;
}
