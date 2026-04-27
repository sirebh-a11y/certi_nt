import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { formatRowFieldDisplay } from "./fieldFormatting";
import { focusFirstOverlayItemInViewport } from "./overlayScroll";

const HIGH_LEVEL_FIELDS = [
  { key: "lega_base", label: "lega" },
  { key: "diametro", label: "Ø" },
  { key: "cdq", label: "Cdq" },
  { key: "colata", label: "Colata" },
  { key: "ddt", label: "Ddt" },
  { key: "peso", label: "peso" },
  { key: "ordine", label: "ordine" },
];

function readValuePayload(value) {
  return value?.valore_finale || value?.valore_standardizzato || value?.valore_grezzo || "";
}

function readDdtValue(row, field) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const valueKey = field === "lega_base" ? "lega" : field;
  const found = values.find((value) => value.blocco === "ddt" && value.campo === valueKey);
  if (field === "lega_base") {
    return formatRowFieldDisplay("lega", readValuePayload(found) || row?.lega_base || row?.lega_designazione || row?.variante_lega || "");
  }
  if (readValuePayload(found)) {
    return formatRowFieldDisplay(field, readValuePayload(found));
  }
  return formatRowFieldDisplay(field, row?.[field] || "");
}

function readCertificateValue(row, field) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const matchFieldMap = {
    lega_base: "lega_certificato",
    diametro: "diametro_certificato",
    cdq: "numero_certificato_certificato",
    colata: "colata_certificato",
    ddt: "ddt_certificato",
    peso: "peso_certificato",
    ordine: "ordine_cliente_certificato",
  };
  const found = values.find((value) => value.blocco === "match" && value.campo === matchFieldMap[field]);
  if (field === "lega_base") {
    return formatRowFieldDisplay("lega", readValuePayload(found) || row?.lega_base || row?.lega_designazione || row?.variante_lega || "");
  }
  if (readValuePayload(found)) {
    return formatRowFieldDisplay(field, readValuePayload(found));
  }
  return formatRowFieldDisplay(field, row?.[field] || "");
}

function buildCertificateDraft(row) {
  return {
    lega_base: readCertificateValue(row, "lega_base"),
    diametro: readCertificateValue(row, "diametro"),
    cdq: readCertificateValue(row, "cdq"),
    colata: readCertificateValue(row, "colata"),
    ddt: readCertificateValue(row, "ddt"),
    peso: readCertificateValue(row, "peso"),
    ordine: readCertificateValue(row, "ordine"),
  };
}

function buildDdtDraft(row) {
  return {
    lega_base: readDdtValue(row, "lega_base"),
    diametro: readDdtValue(row, "diametro"),
    cdq: readDdtValue(row, "cdq"),
    colata: readDdtValue(row, "colata"),
    ddt: readDdtValue(row, "ddt"),
    peso: readDdtValue(row, "peso"),
    ordine: readDdtValue(row, "ordine"),
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

function renderOverlayBox({ item, color, imageWidth, imageHeight, title, key }) {
  const [left, top, right, bottom] = String(item?.bbox || "")
    .split(",")
    .map((part) => Number.parseFloat(part));
  if (!Number.isFinite(left) || !Number.isFinite(top) || !Number.isFinite(right) || !Number.isFinite(bottom) || imageWidth <= 0 || imageHeight <= 0) {
    return null;
  }
  const palette =
    color === "green"
      ? "border-emerald-500 bg-emerald-400/45 shadow-[0_0_0_1px_rgba(16,185,129,0.3)]"
      : color === "orange"
        ? "border-orange-500 bg-orange-400/35 shadow-[0_0_0_1px_rgba(249,115,22,0.25)]"
        : color === "indigo"
          ? "border-indigo-500 bg-indigo-400/30 shadow-[0_0_0_1px_rgba(99,102,241,0.22)]"
          : "border-sky-500 bg-sky-400/22 shadow-[0_0_0_1px_rgba(14,165,233,0.2)]";
  return (
    <div
      className={`pointer-events-none absolute rounded border ${palette}`}
      key={key}
      title={title}
      style={{
        left: `${(left / imageWidth) * 100}%`,
        top: `${(top / imageHeight) * 100}%`,
        width: `${((right - left) / imageWidth) * 100}%`,
        height: `${((bottom - top) / imageHeight) * 100}%`,
      }}
    />
  );
}

function overlayTitle(field) {
  if (field === "material_block") {
    return "Lega / Ø / Colata / Peso";
  }
  if (field === "cdq") {
    return "CDQ / certificato";
  }
  if (field === "ddt") {
    return "DDT";
  }
  if (field === "ordine") {
    return "Ordine";
  }
  return field;
}

function overlayColor(field) {
  if (field === "material_block") {
    return "green";
  }
  if (field === "ordine") {
    return "orange";
  }
  if (field === "ddt") {
    return "indigo";
  }
  return "blue";
}

function OverlayLegend({ visible }) {
  if (!visible) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold text-slate-500">
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm border border-emerald-500 bg-emerald-400/45" />
        materiale
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm border border-sky-500 bg-sky-400/25" />
        cdq
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm border border-orange-500 bg-orange-400/35" />
        ordine
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm border border-indigo-500 bg-indigo-400/30" />
        ddt
      </span>
    </div>
  );
}

function DocumentPdfPanel({ document, title, footerContent, token, overlayPreviewItems }) {
  const [pageImages, setPageImages] = useState([]);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
  const viewportRef = useRef(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  const pageElementRefs = useRef({});
  const [pageImageSizes, setPageImageSizes] = useState({});

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
    const nextSizes = {};
    (overlayPreviewItems || []).forEach((item) => {
      if (!item?.page_id) {
        return;
      }
      nextSizes[item.page_id] = {
        width: Number(item.image_width || 0),
        height: Number(item.image_height || 0),
      };
    });
    setPageImageSizes((current) => ({ ...current, ...nextSizes }));
  }, [overlayPreviewItems]);

  useEffect(() => {
    if (!overlayPreviewItems?.length) {
      return;
    }
    focusFirstOverlayItemInViewport({
      overlayItems: overlayPreviewItems,
      pageImages,
      pageImageSizes,
      pageElementRefs,
      viewportElement: viewportRef.current,
      viewportWidth,
      zoom,
    });
  }, [overlayPreviewItems, pageImages, pageImageSizes, viewportWidth, zoom]);

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
              <div
                className="w-full"
                key={page.id}
                ref={(node) => {
                  pageElementRefs.current[page.id] = node;
                }}
              >
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
                  Pagina {page.numero_pagina}
                </p>
                <div className="relative" style={{ width: viewportWidth > 0 ? `${(viewportWidth * zoom) / 100}px` : "100%" }}>
                  <img
                    alt={`${title} pagina ${page.numero_pagina}`}
                    className="block w-full rounded-xl border border-slate-200 bg-white shadow-sm"
                    draggable={false}
                    onLoad={(event) => {
                      const image = event.currentTarget;
                      setPageImageSizes((current) => ({
                        ...current,
                        [page.id]: {
                          width: image.naturalWidth || current[page.id]?.width || 0,
                          height: image.naturalHeight || current[page.id]?.height || 0,
                        },
                      }));
                    }}
                    src={page.src}
                    style={{ userSelect: "none" }}
                  />
                  {(overlayPreviewItems || [])
                    .filter((item) => item.page_id === page.id)
                    .map((item) =>
                      renderOverlayBox({
                        item,
                        color: overlayColor(item.field),
                        imageWidth: Number(item.image_width || pageImageSizes[page.id]?.width || 0),
                        imageHeight: Number(item.image_height || pageImageSizes[page.id]?.height || 0),
                        title: overlayTitle(item.field),
                        key: `${page.id}-${item.field}-${item.bbox}`,
                      }),
                    )}
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
          <OverlayLegend visible={overlayEnabled} />
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
  const [ddtDraft, setDdtDraft] = useState(() => buildDdtDraft(row));
  const [initialDdtDraft, setInitialDdtDraft] = useState(() => buildDdtDraft(row));
  const [certificateDraft, setCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [initialCertificateDraft, setInitialCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [savingDdtFields, setSavingDdtFields] = useState(false);
  const [refreshingCertificateFirst, setRefreshingCertificateFirst] = useState(false);
  const [savingCertificateFirst, setSavingCertificateFirst] = useState(false);
  const [loadingDdtPreview, setLoadingDdtPreview] = useState(false);
  const [ddtLinkPreview, setDdtLinkPreview] = useState(null);
  const [error, setError] = useState("");
  const [certificateOverlayActive, setCertificateOverlayActive] = useState(false);
  const [ddtOverlayActive, setDdtOverlayActive] = useState(false);
  const [certificateOverlayBusy, setCertificateOverlayBusy] = useState(false);
  const [ddtOverlayBusy, setDdtOverlayBusy] = useState(false);
  const [certificateOverlayItems, setCertificateOverlayItems] = useState([]);
  const [ddtOverlayItems, setDdtOverlayItems] = useState([]);

  useEffect(() => {
    const nextDraft = buildDdtDraft(row);
    setDdtDraft(nextDraft);
    setInitialDdtDraft(nextDraft);
  }, [row]);

  useEffect(() => {
    const nextDraft = buildCertificateDraft(row);
    setCertificateDraft(nextDraft);
    setInitialCertificateDraft(nextDraft);
  }, [row]);

  useEffect(() => {
    onDirtyChange?.(
      (isCertificateFirstRow && !draftsEqual(certificateDraft, initialCertificateDraft)) ||
        (isDdtOnlyRow && !draftsEqual(ddtDraft, initialDdtDraft)),
    );
  }, [certificateDraft, ddtDraft, initialCertificateDraft, initialDdtDraft, isCertificateFirstRow, isDdtOnlyRow, onDirtyChange]);

  useBeforeUnload(
    useMemo(
      () =>
        isCertificateFirstRow && !draftsEqual(certificateDraft, initialCertificateDraft)
          ? "Hai modifiche certificate-first non confermate."
          : isDdtOnlyRow && !draftsEqual(ddtDraft, initialDdtDraft)
            ? "Hai modifiche DDT non confermate."
            : undefined,
      [certificateDraft, ddtDraft, initialCertificateDraft, initialDdtDraft, isCertificateFirstRow, isDdtOnlyRow],
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

  const ddtFields = useMemo(() => ddtDraft, [ddtDraft]);

  function updateCertificateDraft(field, value) {
    setCertificateDraft((current) => ({ ...current, [field]: value }));
  }

  function updateDdtDraft(field, value) {
    setDdtDraft((current) => ({ ...current, [field]: value }));
  }

  async function fetchDocumentCoreOverlay(source) {
    const response = await apiRequest(`/acquisition/rows/${rowId}/document-core-overlay-preview?source=${source}`, {}, token);
    return Array.isArray(response?.items) ? response.items : [];
  }

  async function handleToggleDdtOverlay() {
    if (!ddtDocument || ddtOverlayBusy) {
      return;
    }
    if (ddtOverlayActive) {
      setDdtOverlayActive(false);
      setDdtOverlayItems([]);
      return;
    }
    setDdtOverlayBusy(true);
    setError("");
    try {
      const items = await fetchDocumentCoreOverlay("ddt");
      setDdtOverlayItems(items);
      setDdtOverlayActive(items.length > 0);
      if (!items.length) {
        setError("Nessun overlay disponibile per il DDT.");
      }
    } catch (requestError) {
      setError(requestError.message);
      setDdtOverlayItems([]);
      setDdtOverlayActive(false);
    } finally {
      setDdtOverlayBusy(false);
    }
  }

  async function handleToggleCertificateOverlay() {
    if (!certificateDocument || certificateOverlayBusy) {
      return;
    }
    if (certificateOverlayActive) {
      setCertificateOverlayActive(false);
      setCertificateOverlayItems([]);
      return;
    }
    setCertificateOverlayBusy(true);
    setError("");
    try {
      const items = await fetchDocumentCoreOverlay("certificato");
      setCertificateOverlayItems(items);
      setCertificateOverlayActive(items.length > 0);
      if (!items.length) {
        setError("Nessun overlay disponibile per il certificato.");
      }
    } catch (requestError) {
      setError(requestError.message);
      setCertificateOverlayItems([]);
      setCertificateOverlayActive(false);
    } finally {
      setCertificateOverlayBusy(false);
    }
  }

  async function handleResetDdtDraft() {
    const nextDraft = buildDdtDraft(row);
    setDdtDraft(nextDraft);
    setInitialDdtDraft(nextDraft);
  }

  async function handleSaveDdtFields() {
    setSavingDdtFields(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            lega_base: (ddtDraft.lega_base || "").trim() || null,
            diametro: (ddtDraft.diametro || "").trim() || null,
            cdq: (ddtDraft.cdq || "").trim() || null,
            colata: (ddtDraft.colata || "").trim() || null,
            ddt: (ddtDraft.ddt || "").trim() || null,
            peso: (ddtDraft.peso || "").trim() || null,
            ordine: (ddtDraft.ordine || "").trim() || null,
          }),
        },
        token,
      );
      await onRefreshRow?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingDdtFields(false);
    }
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
        {ddtDocument
          ? isDdtOnlyRow
            ? "Qui lavoriamo sui 7 campi Excel del DDT."
            : "Campi DDT in sola lettura finché non chiudiamo la conferma separata a due documenti."
          : "Qui arriverà la sezione di accoppiamento al posto del PDF mancante."}
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

  const ddtStatusLabel = ddtDocument
    ? isDdtOnlyRow
      ? "Controlla i campi alti del DDT e conferma il documento."
      : "DDT collegato: confronto in sola lettura finché non chiudiamo la conferma separata."
    : "Nessun DDT collegato.";

  return (
    <section className="space-y-4">
      {ddtDocument ? (
        <DocumentPdfPanel
          document={ddtDocument}
          overlayPreviewItems={ddtOverlayItems}
          footerContent={
            <div className="space-y-2">
              <StatusBar
                actionLabel={ddtStatusLabel}
                actionState={ddtDocument ? "Controllo documento DDT" : ""}
                error={error && !certificateDocument ? error : ""}
                onToggleOverlay={() => void handleToggleDdtOverlay()}
                overlayBusy={ddtOverlayBusy}
                overlayEnabled={ddtOverlayActive}
              />
              <DocumentControls
                actionBox={ddtActionBox}
                confirmDisabled={!isDdtOnlyRow || savingDdtFields}
                confirming={savingDdtFields}
                editable={isDdtOnlyRow}
                fields={ddtFields}
                fieldsTitle="ddt"
                onChange={updateDdtDraft}
                onConfirm={() => void handleSaveDdtFields()}
                onReset={() => void handleResetDdtDraft()}
                resetDisabled={!isDdtOnlyRow}
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
              onToggleOverlay={() => void handleToggleDdtOverlay()}
              overlayBusy={ddtOverlayBusy}
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
          overlayPreviewItems={certificateOverlayItems}
          footerContent={
            <div className="space-y-2">
              <StatusBar
                actionLabel={certificateStatusLabel}
                actionState={certificateDocument ? "Controllo documento certificato" : ""}
                error={error && Boolean(certificateDocument) ? error : ""}
                onToggleOverlay={() => void handleToggleCertificateOverlay()}
                overlayBusy={certificateOverlayBusy}
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
