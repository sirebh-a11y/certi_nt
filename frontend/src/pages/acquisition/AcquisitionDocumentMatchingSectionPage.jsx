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
  const valueKey = field === "lega_base" ? "lega" : field;
  const found = values.find((value) => value.blocco === "ddt" && value.campo === valueKey);
  if (field === "lega_base") {
    return formatRowFieldDisplay("lega", found?.valore_finale || found?.valore_standardizzato || found?.valore_grezzo || row?.lega_base || row?.lega_designazione || row?.variante_lega || "");
  }
  if (found?.valore_finale || found?.valore_standardizzato || found?.valore_grezzo) {
    return formatRowFieldDisplay(field, found.valore_finale || found.valore_standardizzato || found.valore_grezzo || "");
  }
  return formatRowFieldDisplay(field, row?.[field] || "");
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

function PreviewMini({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2 py-1.5">
      <p className="text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-1 text-center text-sm font-medium text-slate-800">{value || "-"}</p>
    </div>
  );
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

      <div className="h-[38vh] overflow-auto rounded-2xl border border-slate-600 bg-slate-700 p-3" ref={viewportRef}>
        {pageImages.length ? (
          <div className="space-y-4">
            {pageImages.map((page) => (
              <div className="w-full" key={page.id}>
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
                  Pagina {page.numero_pagina}
                </p>
                <div className="relative" style={{ width: viewportWidth > 0 ? `${(viewportWidth * zoom) / 100}px` : "100%" }}>
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

function MissingDocumentPanel({ title, subtitle, children }) {
  return (
    <div className="rounded-2xl border border-slate-600 bg-slate-700 p-4">
      <div className="flex h-[38vh] flex-col justify-center rounded-2xl border border-dashed border-slate-500 bg-slate-700 px-6 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">{title}</p>
        <p className="mt-3 text-lg font-semibold text-white">Documento mancante</p>
        <p className="mt-2 text-sm leading-6 text-slate-300">{subtitle}</p>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function StatusBar({ actionLabel, actionState, error, onToggleOverlay, overlayBusy, overlayEnabled }) {
  return (
    <div className="min-h-[32px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5">
      <div className="flex min-h-[18px] flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4">
        <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-sky-700">
          <button
            className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-semibold transition ${
              overlayEnabled
                ? "border-sky-400 bg-sky-100 text-sky-800"
                : "border-sky-200 bg-white text-sky-700 hover:bg-sky-100"
            } disabled:cursor-wait disabled:opacity-60`}
            disabled={overlayBusy}
            onClick={onToggleOverlay}
            type="button"
          >
            {overlayBusy ? "..." : overlayEnabled ? "Overlay off" : "Overlay"}
          </button>
          <span>{actionLabel || <span className="invisible">Stato documento</span>}</span>
        </div>
        <div className="min-w-0 text-sm md:text-right">
          {error ? <span className="text-rose-600">{error}</span> : <span className={`font-medium ${actionState ? "text-slate-600" : "invisible"}`}>{actionState || "placeholder"}</span>}
        </div>
      </div>
    </div>
  );
}

function DocumentControls({
  actionBox,
  fields,
  editable,
  fieldsTitle,
  onChange,
  onReset,
  onConfirm,
  resetDisabled,
  confirmDisabled,
  confirming,
}) {
  return (
    <div className="rounded-2xl border border-slate-300/80 bg-slate-100/95 p-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch xl:justify-between">
        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[230px]">{actionBox}</div>
        <div className="min-w-0 flex-1 overflow-hidden rounded-2xl border border-slate-400 bg-slate-50">
          <div className="overflow-x-auto">
            <div className="grid auto-cols-[96px] grid-flow-col gap-0 border-b border-slate-200">
              {HIGH_LEVEL_FIELDS.map((field) => (
                <div className="border-r border-slate-200 px-1.5 py-1" key={field.key}>
                  <p className="text-center text-[11px] font-semibold leading-none text-slate-600">{field.label}</p>
                  {editable ? (
                    <input
                      className="mt-0.5 w-full rounded-md border border-slate-200 bg-white px-1 py-0.5 text-center text-[13px] text-slate-800 outline-none transition focus:border-accent"
                      onChange={(event) => onChange(field.key, event.target.value)}
                      placeholder="Valore"
                      value={fields[field.key] || ""}
                    />
                  ) : (
                    <div className="mt-0.5 min-h-[28px] rounded-md border border-slate-200 bg-white px-1 py-0.5 text-center text-[13px] text-slate-800">
                      {fields[field.key] || "Valore"}
                    </div>
                  )}
                  <p className="mt-0.5 text-center text-[8px] font-semibold uppercase tracking-[0.03em] text-slate-400">Campo</p>
                  <p className="mt-0 min-h-[20px] text-center text-[10px] font-medium leading-tight text-slate-600">{fieldsTitle}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[230px] xl:self-start">
          <button
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={resetDisabled}
            onClick={onReset}
            type="button"
          >
            Valori iniziali
          </button>
          <button
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={confirmDisabled}
            onClick={onConfirm}
            type="button"
          >
            {confirming ? "Conferma..." : "Conferma"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CandidateBox({ ddtLinkPreview, loadingDdtPreview }) {
  if (loadingDdtPreview) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-sky-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">Ricerca candidati DDT in corso.</p>
      </div>
    );
  }

  if (ddtLinkPreview?.auto_match_row_id) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-emerald-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">Candidato forte: riga #{ddtLinkPreview.auto_match_row_id}.</p>
      </div>
    );
  }

  if (ddtLinkPreview?.items?.length) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-sky-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">{ddtLinkPreview.items.length} candidati DDT trovati.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-700">Accoppiamento</p>
      <p className="mt-1.5 text-[11px] leading-tight text-slate-600">Nessun candidato trovato con le regole attuali.</p>
    </div>
  );
}

function MatchBridgePanel({ row, isCertificateFirstRow, ddtLinkPreview, loadingDdtPreview }) {
  const state = row?.block_states?.match || "rosso";
  return (
    <div className="rounded-2xl border border-slate-300/80 bg-slate-100/95 p-3">
      <div className="flex flex-col items-center gap-3 text-center">
        <button className="flex h-16 w-16 items-center justify-center rounded-full border border-slate-300 bg-white text-3xl font-semibold text-slate-700" type="button">
          ⇄
        </button>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${renderStateTone(state)}`}>{matchStateLabel(row)}</span>
        <p className="max-w-[260px] text-sm leading-6 text-slate-600">
          Qui vivranno collegamento, conferma match e disaccoppio forte tra i due documenti.
        </p>
        {isCertificateFirstRow ? <CandidateBox ddtLinkPreview={ddtLinkPreview} loadingDdtPreview={loadingDdtPreview} /> : null}
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
  const isCertificateFirstRow = useMemo(() => Boolean(row?.document_certificato_id) && !row?.document_ddt_id, [row]);
  const isDdtOnlyRow = useMemo(() => Boolean(row?.document_ddt_id) && !row?.document_certificato_id, [row]);
  const [certificateDraft, setCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [initialCertificateDraft, setInitialCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [refreshingCertificateFirst, setRefreshingCertificateFirst] = useState(false);
  const [savingCertificateFirst, setSavingCertificateFirst] = useState(false);
  const [loadingDdtPreview, setLoadingDdtPreview] = useState(false);
  const [ddtLinkPreview, setDdtLinkPreview] = useState(null);
  const [error, setError] = useState("");
  const [certificateOverlayActive, setCertificateOverlayActive] = useState(false);
  const [ddtOverlayActive, setDdtOverlayActive] = useState(false);

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
    () => Object.fromEntries(HIGH_LEVEL_FIELDS.map((field) => [field.key, readDdtValue(row, field.key)])),
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

  const ddtActionBox = (
    <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-700">DDT</p>
      <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
        {ddtDocument ? "Campi documento DDT pronti per controllo e conferma." : "Qui arriverà la sezione di accoppiamento al posto del PDF mancante."}
      </p>
    </div>
  );

  const certificateActionBox = isCertificateFirstRow ? (
    <div className="space-y-3">
      <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-sky-700">Certificate-first</p>
        <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
          Qui lavoriamo sui 7 campi Excel del certificato, già nel formato utile al match.
        </p>
      </div>
      <CandidateBox ddtLinkPreview={ddtLinkPreview} loadingDdtPreview={loadingDdtPreview} />
    </div>
  ) : (
    <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-700">Certificato</p>
      <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
        {certificateDocument ? "Campi documento certificato pronti per controllo e conferma." : "Qui arriveranno ricerca e collegamento del certificato mancante."}
      </p>
    </div>
  );

  const certificateStatusLabel = isCertificateFirstRow
    ? loadingDdtPreview
      ? "Cerco DDT candidati per il collegamento."
      : ddtLinkPreview?.auto_match_row_id
        ? `Candidato forte trovato: riga #${ddtLinkPreview.auto_match_row_id}.`
        : "Controlla i campi alti del certificato e poi ricarica i candidati."
    : certificateDocument
      ? "Certificato collegato: qui andranno overlay, conferma e controllo match."
      : "Nessun certificato collegato: qui apparirà la sezione di accoppiamento.";

  return (
    <section className="space-y-4">
      {ddtDocument ? (
        <DocumentPdfPanel
          document={ddtDocument}
          footerContent={
            <div className="space-y-2">
              <StatusBar
                actionLabel={ddtDocument ? "PDF DDT collegato. Overlay documentale in arrivo in questa sezione." : "Nessun DDT collegato."}
                actionState={ddtDocument ? "Controllo documento DDT" : ""}
                error={error && !certificateDocument ? error : ""}
                onToggleOverlay={() => setDdtOverlayActive((current) => !current)}
                overlayBusy={false}
                overlayEnabled={ddtOverlayActive}
              />
              <DocumentControls
                actionBox={ddtActionBox}
                confirmDisabled
                confirming={false}
                editable={false}
                fields={ddtFields}
                fieldsTitle="ddt"
                onChange={() => {}}
                onConfirm={() => {}}
                onReset={() => {}}
                resetDisabled
              />
            </div>
          }
          title="DDT"
          token={token}
        />
      ) : (
        <MissingDocumentPanel
          subtitle={
            isCertificateFirstRow
              ? "Qui dobbiamo aiutare l’utente a trovare e collegare il DDT giusto, usando i campi alti e i candidati trovati."
              : "Qui comparirà il DDT una volta collegato o caricato."
          }
          title="DDT"
        >
          <div className="space-y-2">
            <StatusBar
              actionLabel={loadingDdtPreview ? "Ricerca DDT candidati in corso." : "Qui appariranno candidati DDT e collegamento."}
              actionState={ddtLinkPreview?.auto_match_row_id ? `Candidato forte: riga #${ddtLinkPreview.auto_match_row_id}` : ""}
              error={error}
              onToggleOverlay={() => setDdtOverlayActive((current) => !current)}
              overlayBusy={false}
              overlayEnabled={ddtOverlayActive}
            />
            <DocumentControls
              actionBox={ddtActionBox}
              confirmDisabled
              confirming={false}
              editable={false}
              fields={ddtFields}
              fieldsTitle="ddt"
              onChange={() => {}}
              onConfirm={() => {}}
              onReset={() => {}}
              resetDisabled
            />
          </div>
        </MissingDocumentPanel>
      )}

      <MatchBridgePanel
        ddtLinkPreview={ddtLinkPreview}
        isCertificateFirstRow={isCertificateFirstRow}
        loadingDdtPreview={loadingDdtPreview}
        row={row}
      />

      {certificateDocument ? (
        <DocumentPdfPanel
          document={certificateDocument}
          footerContent={
            <div className="space-y-2">
              <StatusBar
                actionLabel={certificateStatusLabel}
                actionState={certificateDocument ? "Controllo documento certificato" : ""}
                error={error && Boolean(certificateDocument) ? error : ""}
                onToggleOverlay={() => setCertificateOverlayActive((current) => !current)}
                overlayBusy={false}
                overlayEnabled={certificateOverlayActive}
              />
              <DocumentControls
                actionBox={certificateActionBox}
                confirmDisabled={savingCertificateFirst || !isCertificateFirstRow}
                confirming={savingCertificateFirst}
                editable={isCertificateFirstRow}
                fields={certificateDraft}
                fieldsTitle="certificato"
                onChange={updateCertificateDraft}
                onConfirm={handleSaveCertificateFirstFields}
                onReset={handleRefreshCertificateFirst}
                resetDisabled={refreshingCertificateFirst || !isCertificateFirstRow}
              />
            </div>
          }
          title="Certificato"
          token={token}
        />
      ) : (
        <MissingDocumentPanel
          subtitle={
            isDdtOnlyRow
              ? "Qui dobbiamo aiutare l’utente a trovare e collegare il certificato giusto, con ricerca assistita e confronto sui campi alti."
              : "Qui comparirà il certificato una volta collegato o caricato."
          }
          title="Certificato"
        >
          <div className="space-y-2">
            <StatusBar
              actionLabel="Qui appariranno ricerca certificato, collegamento e conferma."
              actionState=""
              error={error}
              onToggleOverlay={() => setCertificateOverlayActive((current) => !current)}
              overlayBusy={false}
              overlayEnabled={certificateOverlayActive}
            />
            <DocumentControls
              actionBox={certificateActionBox}
              confirmDisabled
              confirming={false}
              editable={false}
              fields={certificateDraft}
              fieldsTitle="certificato"
              onChange={() => {}}
              onConfirm={() => {}}
              onReset={() => {}}
              resetDisabled
            />
          </div>
        </MissingDocumentPanel>
      )}

      {isCertificateFirstRow && ddtLinkPreview?.items?.length ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">Candidati DDT</p>
          <p className="mt-1 text-xs text-slate-500">Questa lista resterà nella zona centrale finché non agganciamo il collegamento vero.</p>
          <div className="mt-4 space-y-3">
            {ddtLinkPreview.items.map((item) => (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={item.row_id}>
                <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      Riga #{item.row_id} · {item.ddt_file_name || `DDT #${item.document_ddt_id}`}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Score {item.score} · {item.reasons.join(" · ") || "nessun dettaglio"}</p>
                  </div>
                  <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                    DDT {item.ddt || "-"}
                  </div>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-3 xl:grid-cols-7">
                  <PreviewMini label="lega" value={item.lega} />
                  <PreviewMini label="Ø" value={item.diametro} />
                  <PreviewMini label="Cdq" value={item.cdq} />
                  <PreviewMini label="Colata" value={item.colata} />
                  <PreviewMini label="Ddt" value={item.ddt} />
                  <PreviewMini label="peso" value={item.peso} />
                  <PreviewMini label="ordine" value={item.ordine} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
