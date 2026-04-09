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

export default function AcquisitionListPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [onlyOpen, setOnlyOpen] = useState(false);

  useEffect(() => {
    let ignore = false;

    apiRequest("/acquisition/rows", {}, token)
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
  }, [token]);

  const visibleRows = useMemo(() => {
    if (!onlyOpen) {
      return rows;
    }
    return rows.filter((row) => row.stato_workflow !== "validata_quality");
  }, [onlyOpen, rows]);

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
                    {row.stato_workflow}
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

              <div className="mt-5 flex items-center justify-between gap-3">
                <p className="text-sm text-slate-500">
                  DDT {row.document_ddt_id} {row.document_certificato_id ? `· Certificato ${row.document_certificato_id}` : "· Nessun certificato"}
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
