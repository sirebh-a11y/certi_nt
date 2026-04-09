import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const BLOCK_LABELS = {
  ddt: "DDT",
  match: "Match",
  chimica: "Chim.",
  proprieta: "Prop.",
  note: "Note",
};

function stateClasses(state) {
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function priorityClasses(priority) {
  if (priority === "alta") {
    return "bg-rose-100 text-rose-700";
  }
  if (priority === "media") {
    return "bg-amber-100 text-amber-700";
  }
  return "bg-slate-200 text-slate-700";
}

const TECHNICAL_FILTERS = [
  { value: "", label: "Tutti gli stati tecnici" },
  { value: "rosso", label: "Tecnico rosso" },
  { value: "giallo", label: "Tecnico giallo" },
  { value: "verde", label: "Tecnico verde" },
];

const WORKFLOW_FILTERS = [
  { value: "", label: "Tutti i workflow" },
  { value: "nuova", label: "Nuova" },
  { value: "in_lavorazione", label: "In lavorazione" },
  { value: "riaperta", label: "Riaperta" },
  { value: "validata_quality", label: "Validata" },
];

const PRIORITY_FILTERS = [
  { value: "", label: "Tutte le priorità" },
  { value: "alta", label: "Alta" },
  { value: "media", label: "Media" },
  { value: "bassa", label: "Bassa" },
];

const CERTIFICATE_FILTERS = [
  { value: "", label: "DDT con e senza certificato" },
  { value: "yes", label: "Con certificato" },
  { value: "no", label: "Senza certificato" },
];

const ATTENTION_FILTERS = [
  { value: "", label: "Tutte le righe" },
  { value: "attention", label: "Solo con attenzione" },
  { value: "validated", label: "Solo validate" },
];

const DDT_FIELD_LABELS = {
  numero_certificato_ddt: "Cert.",
  cdq: "CDQ",
  colata: "Colata",
  diametro: "Diametro",
  peso: "Peso",
  ordine: "Ordine",
};

const TECHNICAL_BLOCK_KEYS = ["chimica", "proprieta", "note"];

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

function matchLabel(row) {
  if (row.match_state === "confermato") {
    return "Pronto";
  }
  if (row.match_state === "proposto" || row.match_state === "cambiato") {
    return "Da verificare";
  }
  return "Non pronto";
}

function matchSecondaryLabel(row) {
  if (row.certificate_file_name) {
    return row.certificate_file_name;
  }
  if (row.document_certificato_id) {
    return `Certificato ${row.document_certificato_id}`;
  }
  return "Nessun certificato";
}

function ddtFieldLabel(field) {
  return DDT_FIELD_LABELS[field] || field;
}

function ddtSummaryLabel(row) {
  const state = row.block_states?.ddt || "rosso";
  if (state === "verde") {
    return "Pronto";
  }
  if (row.ddt_pending_fields?.length) {
    return "Da verificare";
  }
  if (row.ddt_missing_fields?.length) {
    return "Non pronto";
  }
  return "Da verificare";
}

function technicalOpenBlocks(row) {
  return TECHNICAL_BLOCK_KEYS.filter((key) => (row.block_states?.[key] || "rosso") !== "verde");
}

function technicalCriticalBlocks(row) {
  return TECHNICAL_BLOCK_KEYS.filter((key) => (row.block_states?.[key] || "rosso") === "rosso");
}

function technicalSummaryLabel(row) {
  const critical = technicalCriticalBlocks(row);
  const open = technicalOpenBlocks(row);
  if (!open.length) {
    return "Pronti";
  }
  if (critical.length) {
    return "Non pronti";
  }
  return "Da verificare";
}

function technicalSummaryTone(row) {
  if (technicalCriticalBlocks(row).length) {
    return "rosso";
  }
  if (technicalOpenBlocks(row).length) {
    return "giallo";
  }
  return "verde";
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

export default function AcquisitionListPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [technicalFilter, setTechnicalFilter] = useState("");
  const [workflowFilter, setWorkflowFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [certificateFilter, setCertificateFilter] = useState("");
  const [attentionFilter, setAttentionFilter] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let ignore = false;
    const queryParams = new URLSearchParams();
    if (technicalFilter) {
      queryParams.set("stato_tecnico", technicalFilter);
    }
    if (workflowFilter) {
      queryParams.set("stato_workflow", workflowFilter);
    }
    if (priorityFilter) {
      queryParams.set("priorita_operativa", priorityFilter);
    }
    if (certificateFilter === "yes") {
      queryParams.set("has_certificate", "true");
    } else if (certificateFilter === "no") {
      queryParams.set("has_certificate", "false");
    }
    const path = queryParams.toString() ? `/acquisition/rows?${queryParams.toString()}` : "/acquisition/rows";

    setLoading(true);
    setError("");

    apiRequest(path, {}, token)
      .then((data) => {
        if (!ignore) {
          setRows(data.items);
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
  }, [certificateFilter, priorityFilter, technicalFilter, token, workflowFilter]);

  const visibleRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    let nextRows = rows;

    if (onlyOpen) {
      nextRows = nextRows.filter((row) => row.stato_workflow !== "validata_quality");
    }

    if (attentionFilter === "attention") {
      nextRows = nextRows.filter((row) => hasAttention(row));
    } else if (attentionFilter === "validated") {
      nextRows = nextRows.filter((row) => row.validata_finale);
    }

    if (normalizedQuery) {
      nextRows = nextRows.filter((row) => {
        const haystack = [
          row.cdq,
          row.colata,
          row.ordine,
          row.peso,
          row.diametro,
          row.fornitore_raw,
          row.fornitore_id,
          row.id,
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
  }, [attentionFilter, onlyOpen, query, rows]);

  const summary = useMemo(() => {
    const total = rows.length;
    const open = rows.filter((row) => row.stato_workflow !== "validata_quality").length;
    const highPriority = rows.filter((row) => row.priorita_operativa === "alta").length;
    const validated = rows.filter((row) => row.validata_finale).length;
    return { total, open, highPriority, validated };
  }, [rows]);

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
            <h2 className="mt-2 text-2xl font-semibold">Righe acquisition</h2>
            <p className="mt-2 text-sm text-slate-500">
              Cruscotto minimo per DDT, certificato, blocchi tecnici e note del pilota reader-acquisition.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className={`rounded-xl border px-4 py-3 text-sm font-medium ${
                onlyOpen ? "border-accent bg-accent/10 text-accent" : "border-border bg-white text-slate-600"
              }`}
              onClick={() => setOnlyOpen((value) => !value)}
              type="button"
            >
              {onlyOpen ? "Mostra tutte" : "Solo aperte"}
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SummaryTile label="Totali" value={summary.total} tone="slate" />
          <SummaryTile label="Aperte" value={summary.open} tone="amber" />
          <SummaryTile label="Priorità alta" value={summary.highPriority} tone="rose" />
          <SummaryTile label="Validate" value={summary.validated} tone="emerald" />
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-3 xl:grid-cols-6">
          <select
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setTechnicalFilter(event.target.value)}
            value={technicalFilter}
          >
            {TECHNICAL_FILTERS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setWorkflowFilter(event.target.value)}
            value={workflowFilter}
          >
            {WORKFLOW_FILTERS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setPriorityFilter(event.target.value)}
            value={priorityFilter}
          >
            {PRIORITY_FILTERS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setCertificateFilter(event.target.value)}
            value={certificateFilter}
          >
            {CERTIFICATE_FILTERS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setAttentionFilter(event.target.value)}
            value={attentionFilter}
          >
            {ATTENTION_FILTERS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            className="rounded-2xl border border-border bg-white px-4 py-3 text-sm text-slate-700"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Cerca CDQ, colata, ordine..."
            value={query}
          />
        </div>

        {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento righe...</p> : null}
        {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

        <div className="mt-6 space-y-4">
          {visibleRows.map((row) => (
            <article
              className="rounded-3xl border border-border bg-white p-5 shadow-sm shadow-slate-200/40"
              key={row.id}
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white">
                      CDQ {row.cdq || "n/d"}
                    </span>
                    <span className="text-sm font-medium text-slate-700">Colata {row.colata || "-"}</span>
                    <span className="text-sm text-slate-500">Riga #{row.id}</span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <InfoTile label="Fornitore" value={row.fornitore_raw || row.fornitore_id || "-"} />
                    <InfoTile label="Diametro" value={row.diametro || "-"} />
                    <InfoTile label="Peso" value={row.peso || "-"} />
                    <InfoTile label="Ordine" value={row.ordine || "-"} />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 xl:max-w-sm xl:justify-end">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${priorityClasses(row.priorita_operativa)}`}>
                    {row.priorita_operativa}
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${stateClasses(row.stato_tecnico)}`}>
                    {row.stato_tecnico}
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase text-slate-700">
                    {workflowLabel(row.stato_workflow)}
                  </span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${row.validata_finale ? stateClasses("verde") : stateClasses(hasAttention(row) ? "giallo" : "rosso")}`}>
                    {row.validata_finale ? "Validata" : "Da validare"}
                  </span>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                {Object.entries(row.block_states || {}).map(([key, state]) => (
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(state)}`} key={key}>
                    {BLOCK_LABELS[key] || key} · {state}
                  </span>
                ))}
              </div>

              <div className="mt-5 grid gap-3 xl:grid-cols-3">
                <div className={`rounded-2xl border p-4 ${stateClasses(row.block_states?.ddt || "rosso")}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em]">DDT Core</p>
                      <p className="mt-2 text-sm font-semibold">{ddtSummaryLabel(row)}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(row.block_states?.ddt || "rosso")}`}>
                      {row.block_states?.ddt || "rosso"}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <MiniValueTile label="CDQ" value={row.cdq || "-"} />
                    <MiniValueTile label="Colata" value={row.colata || "-"} />
                    <MiniValueTile label="Peso" value={row.peso || "-"} />
                  </div>

                  {row.ddt_pending_fields?.length ? (
                    <p className="mt-3 text-xs font-medium text-amber-800">
                      Da confermare: {row.ddt_pending_fields.map(ddtFieldLabel).join(", ")}
                    </p>
                  ) : null}
                  {row.ddt_missing_fields?.length ? (
                    <p className="mt-2 text-xs font-medium text-rose-800">
                      Mancanti: {row.ddt_missing_fields.map(ddtFieldLabel).join(", ")}
                    </p>
                  ) : null}
                </div>

                <div className={`rounded-2xl border p-4 ${stateClasses(row.block_states?.match || "rosso")}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em]">Match Certificato</p>
                      <p className="mt-2 text-sm font-semibold">{matchLabel(row)}</p>
                      <p className="mt-1 text-xs opacity-80">{matchSecondaryLabel(row)}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(row.block_states?.match || "rosso")}`}>
                      {row.block_states?.match || "rosso"}
                    </span>
                  </div>
                </div>

                <div className={`rounded-2xl border p-4 ${stateClasses(technicalSummaryTone(row))}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em]">Blocchi Tecnici</p>
                      <p className="mt-2 text-sm font-semibold">{technicalSummaryLabel(row)}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(technicalSummaryTone(row))}`}>
                      {technicalOpenBlocks(row).length ? `${technicalOpenBlocks(row).length} aperti` : "ok"}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {TECHNICAL_BLOCK_KEYS.map((key) => (
                      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(row.block_states?.[key] || "rosso")}`} key={key}>
                        {BLOCK_LABELS[key] || key} · {row.block_states?.[key] || "rosso"}
                      </span>
                    ))}
                  </div>

                  {technicalOpenBlocks(row).length ? (
                    <p className="mt-3 text-xs font-medium opacity-90">
                      Aperti: {technicalOpenBlocks(row).map((key) => BLOCK_LABELS[key] || key).join(", ")}
                    </p>
                  ) : (
                    <p className="mt-3 text-xs font-medium opacity-90">Chimica, proprietà e note sono già pronte.</p>
                  )}
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between gap-3">
                <p className="text-sm text-slate-500">
                  DDT {row.document_ddt_id} {row.document_certificato_id ? `· Certificato ${row.document_certificato_id}` : "· Nessun certificato"} ·
                  {" "}
                  {hasAttention(row) ? "Richiede attenzione" : "Pronta o validata"}
                </p>
                <Link className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700" to={`/acquisition/${row.id}`}>
                  Apri riga
                </Link>
              </div>
            </article>
          ))}
        </div>

        {!loading && !visibleRows.length && !error ? (
          <p className="mt-6 text-sm text-slate-500">Nessuna riga acquisition disponibile.</p>
        ) : null}
      </div>
    </section>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-slate-800">{value}</p>
    </div>
  );
}

function SummaryTile({ label, value, tone }) {
  const toneClasses =
    tone === "emerald"
      ? "bg-emerald-50 text-emerald-700"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700"
        : tone === "rose"
          ? "bg-rose-50 text-rose-700"
          : "bg-slate-50 text-slate-700";

  return (
    <div className={`rounded-2xl p-4 ${toneClasses}`}>
      <p className="text-xs uppercase tracking-[0.2em] opacity-80">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function MiniValueTile({ label, value }) {
  return (
    <div className="rounded-xl bg-white/70 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}
