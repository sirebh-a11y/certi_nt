import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { useAuth } from "../../app/auth";

const BLOCK_LABELS = {
  ddt: "DDT",
  match: "Match Certificato",
  chimica: "Chimica",
  proprieta: "Proprietà",
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

export default function AcquisitionDetailPage() {
  const { token } = useAuth();
  const { rowId } = useParams();
  const navigate = useNavigate();
  const [row, setRow] = useState(null);
  const [ddtDocument, setDdtDocument] = useState(null);
  const [certificateDocument, setCertificateDocument] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [processingVision, setProcessingVision] = useState(false);
  const [openingAsset, setOpeningAsset] = useState("");

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const rowData = await apiRequest(`/acquisition/rows/${rowId}`, {}, token);
        if (ignore) {
          return;
        }
        setRow(rowData);

        const requests = [apiRequest(`/acquisition/documents/${rowData.ddt_document.id}`, {}, token)];
        if (rowData.certificate_document?.id) {
          requests.push(apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token));
        }
        const [ddtData, certificateData] = await Promise.all(requests);
        if (!ignore) {
          setDdtDocument(ddtData);
          setCertificateDocument(certificateData || null);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError.message);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, [rowId, token]);

  const valuesByBlock = useMemo(() => {
    const groups = { ddt: [], match: [], chimica: [], proprieta: [], note: [] };
    (row?.values || []).forEach((value) => {
      if (!groups[value.blocco]) {
        groups[value.blocco] = [];
      }
      groups[value.blocco].push(value);
    });
    return groups;
  }, [row]);

  async function handleProcessMinimal() {
    setProcessing(true);
    setError("");
    try {
      const updatedRow = await apiRequest(
        `/acquisition/rows/${rowId}/process-minimal`,
        { method: "POST" },
        token,
      );
      setRow(updatedRow);

      const [ddtData, certificateData] = await Promise.all([
        apiRequest(`/acquisition/documents/${updatedRow.ddt_document.id}`, {}, token),
        updatedRow.certificate_document?.id
          ? apiRequest(`/acquisition/documents/${updatedRow.certificate_document.id}`, {}, token)
          : Promise.resolve(null),
      ]);
      setDdtDocument(ddtData);
      setCertificateDocument(certificateData);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessing(false);
    }
  }

  async function handleProcessDdtVision() {
    setProcessingVision(true);
    setError("");
    try {
      const updatedRow = await apiRequest(
        `/acquisition/rows/${rowId}/extract-ddt-vision`,
        { method: "POST" },
        token,
      );
      setRow(updatedRow);
      const ddtData = await apiRequest(`/acquisition/documents/${updatedRow.ddt_document.id}`, {}, token);
      setDdtDocument(ddtData);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingVision(false);
    }
  }

  async function handleOpenAsset(path, fileName) {
    setOpeningAsset(path);
    setError("");
    try {
      const blob = await fetchApiBlob(path, token);
      const objectUrl = URL.createObjectURL(blob);
      const popup = window.open(objectUrl, "_blank", "noopener,noreferrer");
      if (!popup) {
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = fileName || "document";
        anchor.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setOpeningAsset("");
    }
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <button className="text-sm font-medium text-accent hover:underline" onClick={() => navigate("/acquisition")} type="button">
              Torna alle righe
            </button>
            <p className="mt-4 text-sm uppercase tracking-[0.3em] text-slate-500">Dettaglio acquisition</p>
            <h2 className="mt-2 text-2xl font-semibold">Riga #{rowId}</h2>
            <p className="mt-2 text-sm text-slate-500">
              Vista minima per DDT, certificato, blocchi tecnici, note ed evidenze del pilota.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={processingVision}
              onClick={handleProcessDdtVision}
              type="button"
            >
              {processingVision ? "Vision DDT..." : "Vision DDT"}
            </button>
            <button
              className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              disabled={processing}
              onClick={handleProcessMinimal}
              type="button"
            >
              {processing ? "Processo in corso..." : "Processo minimo"}
            </button>
          </div>
        </div>

        {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento riga...</p> : null}
        {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

        {row ? (
          <div className="mt-6 space-y-6">
            <div className="grid gap-4 md:grid-cols-4">
              <InfoTile label="CDQ" value={row.cdq || "-"} />
              <InfoTile label="Colata" value={row.colata || "-"} />
              <InfoTile label="Peso" value={row.peso || "-"} />
              <InfoTile label="Ordine" value={row.ordine || "-"} />
            </div>

            <div className="flex flex-wrap gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${stateClasses(row.stato_tecnico)}`}>
                Tecnico · {row.stato_tecnico}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase text-slate-700">
                Workflow · {row.stato_workflow}
              </span>
              {Object.entries(row.block_states || {}).map(([key, state]) => (
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(state)}`} key={key}>
                  {BLOCK_LABELS[key] || key} · {state}
                </span>
              ))}
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <DocumentPanel
                document={ddtDocument}
                onOpenAsset={handleOpenAsset}
                openingAsset={openingAsset}
                title="DDT sorgente"
              />
              <DocumentPanel
                document={certificateDocument}
                onOpenAsset={handleOpenAsset}
                openingAsset={openingAsset}
                title="Certificato sorgente"
              />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              {Object.entries(valuesByBlock).map(([block, values]) => (
                <BlockPanel key={block} label={BLOCK_LABELS[block] || block} values={values} />
              ))}
            </div>

            <div className="rounded-2xl border border-border p-5">
              <h3 className="text-lg font-semibold">Storico recente</h3>
              <div className="mt-4 space-y-3">
                {(row.history_events || []).slice(0, 8).map((event) => (
                  <div className="rounded-2xl bg-slate-50 p-4" key={event.id}>
                    <p className="text-sm font-medium text-slate-800">
                      {event.blocco} · {event.azione}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {new Date(event.timestamp).toLocaleString()} {event.nota_breve ? `· ${event.nota_breve}` : ""}
                    </p>
                  </div>
                ))}
                {!row.history_events?.length ? <p className="text-sm text-slate-500">Nessun evento disponibile.</p> : null}
              </div>
            </div>
          </div>
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

function BlockPanel({ label, values }) {
  return (
    <div className="rounded-2xl border border-border p-5">
      <h3 className="text-lg font-semibold">{label}</h3>
      <div className="mt-4 space-y-3">
        {values.map((value) => (
          <div className="rounded-2xl bg-slate-50 p-4" key={value.id}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white">
                {value.campo}
              </span>
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(value.stato === "confermato" ? "verde" : "giallo")}`}>
                {value.stato}
              </span>
            </div>
            <p className="mt-3 text-sm text-slate-800">{value.valore_finale || value.valore_standardizzato || value.valore_grezzo || "-"}</p>
            <p className="mt-2 text-xs text-slate-500">
              Fonte {value.fonte_documentale} · Metodo {value.metodo_lettura}
            </p>
          </div>
        ))}
        {!values.length ? <p className="text-sm text-slate-500">Nessun valore presente.</p> : null}
      </div>
    </div>
  );
}

function DocumentPanel({ title, document, onOpenAsset, openingAsset }) {
  return (
    <div className="rounded-2xl border border-border p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="mt-2 text-sm text-slate-500">
            {document ? `${document.nome_file_originale} · ${document.numero_pagine || 0} pagine` : "Documento non collegato"}
          </p>
        </div>
        {document?.file_url ? (
          <button
            className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={openingAsset === document.file_url}
            onClick={() => onOpenAsset(document.file_url, document.nome_file_originale)}
            type="button"
          >
            {openingAsset === document.file_url ? "Apertura..." : "Apri PDF"}
          </button>
        ) : null}
      </div>

      {document?.pages?.length ? (
        <div className="mt-4 grid gap-3">
          {document.pages.map((page) => (
            <div className="rounded-2xl bg-slate-50 p-4" key={page.id}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800">Pagina {page.numero_pagina}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {page.stato_estrazione} {page.testo_estratto ? "· testo disponibile" : "· immagine disponibile"}
                  </p>
                </div>
                {page.image_url ? (
                  <button
                    className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
                    disabled={openingAsset === page.image_url}
                    onClick={() => onOpenAsset(page.image_url, `pagina-${page.numero_pagina}.png`)}
                    type="button"
                  >
                    {openingAsset === page.image_url ? "Apertura..." : "Apri immagine"}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
