import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { formatRowFieldDisplay } from "./fieldFormatting";

const HIGH_LEVEL_FIELDS = [
  { key: "lega_base", label: "lega" },
  { key: "diametro", label: "Ø" },
  { key: "cdq", label: "Cdq" },
  { key: "colata", label: "Colata" },
  { key: "ddt", label: "Ddt" },
  { key: "peso", label: "peso" },
  { key: "ordine", label: "ordine" },
];

function buildCertificateDraft(row) {
  return {
    lega_base: formatRowFieldDisplay("lega", row?.lega_base || row?.lega_designazione || row?.variante_lega || ""),
    diametro: formatRowFieldDisplay("diametro", row?.diametro || ""),
    cdq: formatRowFieldDisplay("cdq", row?.cdq || ""),
    colata: formatRowFieldDisplay("colata", row?.colata || ""),
    ddt: formatRowFieldDisplay("ddt", row?.ddt || ""),
    peso: formatRowFieldDisplay("peso", row?.peso || ""),
    ordine: formatRowFieldDisplay("ordine", row?.ordine || ""),
  };
}

function draftsEqual(left, right) {
  return HIGH_LEVEL_FIELDS.every(({ key }) => (left?.[key] || "").trim() === (right?.[key] || "").trim());
}

function renderStateTone(state) {
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function readDdtValue(row, field) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const found = values.find((value) => value.blocco === "ddt" && value.campo === field);
  if (field === "lega_base") {
    return formatRowFieldDisplay("lega", row?.lega_base || row?.lega_designazione || row?.variante_lega || "");
  }
  if (found?.valore_finale || found?.valore_standardizzato || found?.valore_grezzo) {
    return formatRowFieldDisplay(field === "lega_base" ? "lega" : field, found.valore_finale || found.valore_standardizzato || found.valore_grezzo || "");
  }
  return formatRowFieldDisplay(field === "lega_base" ? "lega" : field, row?.[field] || "");
}

function matchStateLabel(row) {
  if (row?.certificate_match?.stato === "confermato") {
    return "Match confermato";
  }
  if (row?.certificate_match) {
    return "Match proposto";
  }
  if (row?.document_ddt_id && row?.document_certificato_id) {
    return "Documenti presenti";
  }
  if (row?.document_certificato_id) {
    return "Solo certificato";
  }
  if (row?.document_ddt_id) {
    return "Solo DDT";
  }
  return "Nessun documento";
}

function DocumentPdfPanel({ document, title, footerContent, token }) {
  const [pageImages, setPageImages] = useState([]);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
  const viewportRef = useRef(null);
  const [viewportWidth, setViewportWidth] = useState(0);

  useEffect(() => {
    let ignore = false;
    const objectUrls = [];

    async function loadPageImages() {
      const pages = (document?.pages || []).filter((page) => page.image_url);
      if (!pages.length) {
        setPageImages([]);
        return;
      }
      try {
        const loadedPages = await Promise.all(
          pages.map(async (page) => {
            const blob = await fetchApiBlob(page.image_url, token);
            const objectUrl = URL.createObjectURL(blob);
            objectUrls.push(objectUrl);
            return { id: page.id, numero_pagina: page.numero_pagina, src: objectUrl };
          }),
        );
        if (!ignore) {
          setPageImages(loadedPages);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setPageImages([]);
          setError(requestError.message);
        }
      }
    }

    void loadPageImages();

    return () => {
      ignore = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [document, token]);

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) {
      return undefined;
    }

    function updateViewportWidth() {
      const nextWidth = Math.max(node.clientWidth - 24, 0);
      setViewportWidth(nextWidth);
    }

    updateViewportWidth();
    const observer = new ResizeObserver(updateViewportWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="rounded-2xl border border-slate-600 bg-slate-700 p-4">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">{title}</p>
          <p className="mt-1 text-sm text-white">{document?.nome_file_originale || "Documento non collegato"}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-600"
            onClick={() => setZoom((current) => Math.max(50, current - 10))}
            type="button"
          >
            -
          </button>
          <span className="min-w-[64px] text-center text-sm font-semibold text-white">{zoom}%</span>
          <button
            className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-600"
            onClick={() => setZoom((current) => Math.min(250, current + 10))}
            type="button"
          >
            +
          </button>
        </div>
      </div>

      <div className="h-[34vh] overflow-auto rounded-2xl border border-slate-600 bg-slate-700 p-3" ref={viewportRef}>
        {pageImages.length ? (
          <div className="space-y-4">
            {pageImages.map((page) => (
              <div className="w-full" key={page.id}>
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
                  Pagina {page.numero_pagina}
                </p>
                <div
                  className="relative"
                  style={{
                    width: viewportWidth > 0 ? `${(viewportWidth * zoom) / 100}px` : "100%",
                  }}
                >
                  <img
                    alt={`${title} pagina ${page.numero_pagina}`}
                    className="block w-full rounded-xl border border-slate-200 bg-white shadow-sm"
                    draggable={false}
                    src={page.src}
                    style={{ userSelect: "none" }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-200">
            {error || "Immagini pagina non disponibili."}
          </div>
        )}
      </div>

      {footerContent ? <div className="mt-3">{footerContent}</div> : null}
    </div>
  );
}

function DocumentFieldGrid({ fields, editable = false, onChange, title, tone = "rosso" }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="mt-1 text-xs text-slate-500">Campi alti Excel usati dall’utente per il match.</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${renderStateTone(tone)}`}>{tone}</span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {HIGH_LEVEL_FIELDS.map((field) => (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={field.key}>
            <label className="text-xs uppercase tracking-[0.18em] text-slate-500">{field.label}</label>
            {editable ? (
              <input
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
                onChange={(event) => onChange(field.key, event.target.value)}
                value={fields[field.key] || ""}
              />
            ) : (
              <div className="mt-2 min-h-[42px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800">
                {fields[field.key] || "-"}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MatchBridgeCard({ row, isCertificateFirstRow, ddtLinkPreview, loadingDdtPreview }) {
  const state = row?.block_states?.match || "rosso";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col items-center gap-4 text-center">
        <button
          className="flex h-16 w-16 items-center justify-center rounded-full border border-slate-300 bg-slate-50 text-3xl font-semibold text-slate-700"
          type="button"
        >
          ⇄
        </button>
        <div>
          <p className="text-sm font-semibold text-slate-900">{matchStateLabel(row)}</p>
          <p className="mt-1 text-xs text-slate-500">
            Qui andrà il collegamento forte tra DDT e certificato, e poi il disaccoppio con warning.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${renderStateTone(state)}`}>{state}</span>
        {isCertificateFirstRow ? (
          <div className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-left">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Candidati DDT</p>
            <p className="mt-2 text-sm text-slate-700">
              {loadingDdtPreview
                ? "Ricerca candidati in corso..."
                : ddtLinkPreview?.auto_match_row_id
                  ? `Candidato forte trovato: riga #${ddtLinkPreview.auto_match_row_id}`
                  : ddtLinkPreview?.items?.length
                    ? `${ddtLinkPreview.items.length} candidati trovati`
                    : "Nessun candidato trovato con le regole attuali."}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function AcquisitionDocumentMatchingSectionPage({
  certificateDocument,
  ddtDocument,
  onDirtyChange,
  row,
  rowId,
  token,
  onRefreshRow,
}) {
  const isCertificateFirstRow = useMemo(
    () => Boolean(row?.document_certificato_id) && !row?.document_ddt_id,
    [row],
  );
  const [certificateDraft, setCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [initialCertificateDraft, setInitialCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [refreshingCertificateFirst, setRefreshingCertificateFirst] = useState(false);
  const [savingCertificateFirst, setSavingCertificateFirst] = useState(false);
  const [loadingDdtPreview, setLoadingDdtPreview] = useState(false);
  const [ddtLinkPreview, setDdtLinkPreview] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const nextDraft = buildCertificateDraft(row);
    setCertificateDraft(nextDraft);
    setInitialCertificateDraft(nextDraft);
  }, [row]);

  useEffect(() => {
    onDirtyChange?.(isCertificateFirstRow && !draftsEqual(certificateDraft, initialCertificateDraft));
  }, [certificateDraft, initialCertificateDraft, isCertificateFirstRow, onDirtyChange]);

  useBeforeUnload(
    useMemo(
      () => (isCertificateFirstRow && !draftsEqual(certificateDraft, initialCertificateDraft) ? "Hai modifiche certificate-first non confermate." : undefined),
      [certificateDraft, initialCertificateDraft, isCertificateFirstRow],
    ),
  );

  useEffect(() => {
    let ignore = false;

    async function loadPreview() {
      if (!isCertificateFirstRow) {
        setDdtLinkPreview(null);
        return;
      }
      setLoadingDdtPreview(true);
      try {
        const preview = await apiRequest(`/acquisition/rows/${rowId}/ddt-link-preview`, {}, token);
        if (!ignore) {
          setDdtLinkPreview(preview);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setDdtLinkPreview(null);
          setError(requestError.message);
        }
      } finally {
        if (!ignore) {
          setLoadingDdtPreview(false);
        }
      }
    }

    void loadPreview();
    return () => {
      ignore = true;
    };
  }, [isCertificateFirstRow, rowId, token]);

  const ddtFields = useMemo(
    () =>
      Object.fromEntries(
        HIGH_LEVEL_FIELDS.map((field) => [field.key, readDdtValue(row, field.key)]),
      ),
    [row],
  );

  function updateCertificateDraft(field, value) {
    setCertificateDraft((current) => ({ ...current, [field]: value }));
  }

  async function handleRefreshCertificateFirst() {
    setRefreshingCertificateFirst(true);
    setError("");
    try {
      await apiRequest(`/acquisition/rows/${rowId}/refresh-certificate-first`, { method: "POST" }, token);
      await onRefreshRow?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRefreshingCertificateFirst(false);
    }
  }

  async function handleSaveCertificateFirstFields() {
    setSavingCertificateFirst(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            lega_base: (certificateDraft.lega_base || "").trim() || null,
            diametro: (certificateDraft.diametro || "").trim() || null,
            cdq: (certificateDraft.cdq || "").trim() || null,
            colata: (certificateDraft.colata || "").trim() || null,
            ddt: (certificateDraft.ddt || "").trim() || null,
            peso: (certificateDraft.peso || "").trim() || null,
            ordine: (certificateDraft.ordine || "").trim() || null,
          }),
        },
        token,
      );
      await onRefreshRow?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingCertificateFirst(false);
    }
  }

  async function handleReloadDdtPreview() {
    setLoadingDdtPreview(true);
    setError("");
    try {
      const preview = await apiRequest(`/acquisition/rows/${rowId}/ddt-link-preview`, {}, token);
      setDdtLinkPreview(preview);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoadingDdtPreview(false);
    }
  }

  return (
    <section className="space-y-4">
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px]">
        <DocumentPdfPanel
          document={ddtDocument}
          footerContent={<DocumentFieldGrid fields={ddtFields} title="Documento DDT" tone={row?.block_states?.ddt || "rosso"} />}
          title="DDT"
          token={token}
        />
        <MatchBridgeCard
          ddtLinkPreview={ddtLinkPreview}
          isCertificateFirstRow={isCertificateFirstRow}
          loadingDdtPreview={loadingDdtPreview}
          row={row}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px]">
        <DocumentPdfPanel
          document={certificateDocument}
          footerContent={
            <div className="space-y-3">
              <DocumentFieldGrid
                editable={isCertificateFirstRow}
                fields={certificateDraft}
                onChange={updateCertificateDraft}
                title="Documento Certificato"
                tone={row?.document_certificato_id ? (row?.certificate_match?.stato === "confermato" ? "verde" : "giallo") : "rosso"}
              />
              {isCertificateFirstRow ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    className="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    disabled={refreshingCertificateFirst}
                    onClick={handleRefreshCertificateFirst}
                    type="button"
                  >
                    {refreshingCertificateFirst ? "Aggiorno..." : "Aggiorna da certificato"}
                  </button>
                  <button
                    className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    disabled={savingCertificateFirst}
                    onClick={handleSaveCertificateFirstFields}
                    type="button"
                  >
                    {savingCertificateFirst ? "Salvo..." : "Salva campi"}
                  </button>
                  <button
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    disabled={loadingDdtPreview}
                    onClick={handleReloadDdtPreview}
                    type="button"
                  >
                    {loadingDdtPreview ? "Cerco..." : "Ricarica candidati"}
                  </button>
                </div>
              ) : null}
            </div>
          }
          title="Certificato"
          token={token}
        />
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">Passi successivi</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Qui andranno: collega DDT, disaccoppia con warning forte, conferma DDT, conferma certificato,
            conferma match e conferma totale.
          </p>
        </div>
      </div>

      {isCertificateFirstRow && ddtLinkPreview?.items?.length ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">Anteprima candidati DDT</p>
          <div className="mt-4 space-y-3">
            {ddtLinkPreview.items.map((item) => (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={item.row_id}>
                <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      Riga #{item.row_id} · {item.ddt_file_name || `DDT #${item.document_ddt_id}`}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Score {item.score} · {item.reasons.join(" · ") || "nessun dettaglio"}
                    </p>
                  </div>
                  <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                    DDT {item.ddt || "-"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
