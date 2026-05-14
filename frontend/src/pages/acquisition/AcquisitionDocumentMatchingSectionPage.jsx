import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload, useNavigate } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { documentTone } from "./documentTone";
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

const DDT_VALUE_FIELDS = {
  lega_base: ["lega"],
  diametro: ["diametro"],
  cdq: ["cdq", "numero_certificato_ddt"],
  colata: ["colata"],
  ddt: ["ddt"],
  peso: ["peso"],
  ordine: ["ordine", "customer_order_no"],
};

const CERTIFICATE_VALUE_FIELDS = {
  lega_base: ["lega_certificato"],
  diametro: ["diametro_certificato"],
  cdq: ["numero_certificato_certificato"],
  colata: ["colata_certificato"],
  ddt: ["ddt_certificato"],
  peso: ["peso_certificato"],
  ordine: ["ordine_cliente_certificato"],
};

function readValuePayload(value) {
  return value?.valore_finale || value?.valore_standardizzato || value?.valore_grezzo || "";
}

function safeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function readRowFallbackValue(row, field) {
  if (field === "lega_base") {
    return formatRowFieldDisplay("lega", row?.lega_base || row?.lega_designazione || row?.variante_lega || "");
  }
  return formatRowFieldDisplay(field, row?.[field] || "");
}

function findSideValue(row, side, field) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const block = side === "ddt" ? "ddt" : "match";
  const fields = side === "ddt" ? DDT_VALUE_FIELDS[field] : CERTIFICATE_VALUE_FIELDS[field];
  const candidates = values.filter((value) => value.blocco === block && fields.includes(value.campo));
  return candidates.find((value) => readValuePayload(value)) || candidates[0] || null;
}

function sideAllowsRowFallback(row, side) {
  if (side === "ddt") {
    return Boolean(row?.document_ddt_id) && !row?.document_certificato_id;
  }
  return Boolean(row?.document_certificato_id) && !row?.document_ddt_id;
}

function readDocumentSideValue(row, side, field) {
  const found = findSideValue(row, side, field);
  const payload = readValuePayload(found);
  if (payload) {
    return formatRowFieldDisplay(field === "lega_base" ? "lega" : field, payload);
  }
  if (sideAllowsRowFallback(row, side)) {
    return readRowFallbackValue(row, field);
  }
  return "";
}

function sourceTextForSide(row, side, field, override) {
  const label = side === "ddt" ? "ddt" : "certificato";
  if (override === "utente") {
    return `${label} - utente`;
  }
  const found = findSideValue(row, side, field);
  if (found?.metodo_lettura === "utente" || found?.fonte_documentale === "utente") {
    return `${label} - utente`;
  }
  if (readValuePayload(found) || (sideAllowsRowFallback(row, side) && readRowFallbackValue(row, field))) {
    return `${label} - AI`;
  }
  return `${label} - mancante`;
}

function stateForSide(row, side, field, override) {
  if (override === "utente") {
    return "giallo";
  }
  const found = findSideValue(row, side, field);
  if (readValuePayload(found)) {
    return found.stato === "confermato" ? "verde" : "giallo";
  }
  if (sideAllowsRowFallback(row, side) && readRowFallbackValue(row, field)) {
    return "giallo";
  }
  return "rosso";
}

function buildSourceMap(row, side, overrides = {}) {
  return Object.fromEntries(HIGH_LEVEL_FIELDS.map(({ key }) => [key, sourceTextForSide(row, side, key, overrides[key])]));
}

function buildStateMap(row, side, overrides = {}) {
  return Object.fromEntries(HIGH_LEVEL_FIELDS.map(({ key }) => [key, stateForSide(row, side, key, overrides[key])]));
}

function documentSideConfirmed(row, side) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const block = side === "ddt" ? "ddt" : "match";
  const fieldMap = side === "ddt" ? DDT_VALUE_FIELDS : CERTIFICATE_VALUE_FIELDS;
  const fields = new Set(Object.values(fieldMap).flat());
  const sideValues = values.filter((value) => value.blocco === block && fields.has(value.campo) && readValuePayload(value));
  return sideValues.length > 0 && sideValues.every((value) => value.stato === "confermato");
}

function ddtBlockConfirmed(row) {
  return row?.block_states?.ddt === "verde" || documentSideConfirmed(row, "ddt");
}

function matchBlockConfirmed(row) {
  return row?.block_states?.match === "verde" || row?.certificate_match?.stato === "confermato";
}

function documentPairConfirmed(row) {
  return Boolean(
    row?.document_ddt_id &&
      row?.document_certificato_id &&
      ddtBlockConfirmed(row) &&
      matchBlockConfirmed(row),
  );
}

function readDdtValue(row, field) {
  return readDocumentSideValue(row, "ddt", field);
}

function readCertificateValue(row, field) {
  return readDocumentSideValue(row, "certificato", field);
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
  return HIGH_LEVEL_FIELDS.every(({ key }) => safeText(left?.[key]).trim() === safeText(right?.[key]).trim());
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
      <p className="mt-1 text-center text-sm font-medium text-slate-800">{safeText(value) || "-"}</p>
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
          : "border-sky-500 bg-sky-400/40 shadow-[0_0_0_1px_rgba(14,165,233,0.25)]";
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
        <span className="h-2.5 w-2.5 rounded-sm border border-sky-500 bg-sky-400/40" />
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

function DocumentPdfPanel({ document, title, footerContent, token, overlayPreviewItems, kind }) {
  const tone = documentTone(kind);
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
    <div className={`rounded-2xl border p-4 ${tone.panel}`}>
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-lg font-bold text-slate-950">{title}</p>
          <p className="mt-1 text-sm text-slate-900">{document?.nome_file_originale || "Documento non collegato"}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={`rounded-lg border px-3 py-2 text-sm font-semibold ${tone.button}`}
            onClick={() => setZoom((current) => Math.max(50, current - 10))}
            type="button"
          >
            -
          </button>
          <span className="min-w-[64px] text-center text-sm font-semibold text-slate-700">{zoom}%</span>
          <button
            className={`rounded-lg border px-3 py-2 text-sm font-semibold ${tone.button}`}
            onClick={() => setZoom((current) => Math.min(250, current + 10))}
            type="button"
          >
            +
          </button>
        </div>
      </div>

      <div className={`h-[38vh] overflow-auto rounded-2xl border p-3 ${tone.viewport}`} ref={viewportRef}>
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
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
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
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-600">
            {error || "Immagini pagina non disponibili."}
          </div>
        )}
      </div>

      {footerContent ? <div className="mt-3">{footerContent}</div> : null}
    </div>
  );
}

function MissingDocumentPanel({ title, subtitle, previewContent, children, kind }) {
  const tone = documentTone(kind);
  return (
    <div className={`rounded-2xl border p-4 ${tone.panel}`}>
      <div className={`h-[38vh] overflow-auto rounded-2xl border border-dashed p-4 ${tone.dashedViewport}`}>
        <div className="text-center">
          <p className="text-lg font-bold text-slate-950">{title}</p>
          <p className="mt-3 text-lg font-semibold text-slate-900">Documento mancante</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{subtitle}</p>
        </div>
        {previewContent ? <div className="mt-4 text-left">{previewContent}</div> : null}
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
  fieldSources,
  fieldStates,
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
                      value={safeText(fields?.[field.key])}
                    />
                  ) : (
                    <div className="mt-0.5 min-h-[28px] rounded-md border border-slate-200 bg-white px-1 py-0.5 text-center text-[13px] text-slate-800">
                      {safeText(fields?.[field.key]) || "Valore"}
                    </div>
                  )}
                  <p
                    className={`mt-0.5 text-center text-[8px] font-semibold uppercase tracking-[0.03em] ${
                      fieldStates?.[field.key] === "verde"
                        ? "text-emerald-600"
                        : fieldStates?.[field.key] === "giallo"
                          ? "text-amber-600"
                          : "text-rose-500"
                    }`}
                  >
                    Origine
                  </p>
                  <p className="mt-0 min-h-[20px] text-center text-[10px] font-medium leading-tight text-slate-600">
                    {fieldSources?.[field.key] || "dato mancante"}
                  </p>
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

function CandidateBox({ label = "candidati", loadingPreview, preview }) {
  if (loadingPreview) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-sky-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">Ricerca {label} in corso.</p>
      </div>
    );
  }

  if (preview?.auto_match_row_id) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-emerald-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">Candidato forte: riga #{safeText(preview.auto_match_row_id)}.</p>
      </div>
    );
  }

  if (preview?.items?.length) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
        <p className="text-[11px] font-semibold text-sky-700">Accoppiamento</p>
        <p className="mt-1.5 text-[11px] leading-tight text-slate-600">{safeText(preview.items.length)} {label} trovati.</p>
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

function MatchBridgePanel({ canDetach, detaching, ddtLinkPreview, isCertificateFirstRow, loadingDdtPreview, onDetach, row }) {
  const state = row?.block_states?.match || "rosso";
  return (
    <div className="rounded-2xl border border-slate-300/80 bg-slate-200/90 p-3 shadow-inner shadow-slate-300/40">
      <div className="flex flex-col items-center gap-3 text-center">
        <button
          className={`flex h-16 w-16 items-center justify-center rounded-full border text-3xl font-semibold transition ${
            canDetach
              ? "border-amber-300 bg-white text-amber-700 hover:border-amber-500 hover:bg-amber-50"
              : "border-slate-300 bg-white text-slate-700"
          } disabled:cursor-not-allowed disabled:opacity-60`}
          disabled={!canDetach || detaching}
          onClick={canDetach ? onDetach : undefined}
          title={canDetach ? "Disaccoppia DDT e certificato" : "Collegamento documenti"}
          type="button"
        >
          ⇄
        </button>
        {canDetach ? (
          <button
            className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-60"
            disabled={detaching}
            onClick={onDetach}
            type="button"
          >
            {detaching ? "Disaccoppio..." : "Disaccoppia documenti"}
          </button>
        ) : null}
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${renderStateTone(state)}`}>{matchStateLabel(row)}</span>
        <p className="max-w-[260px] text-sm leading-6 text-slate-600">
          Qui vivranno collegamento, conferma match e disaccoppio forte tra i due documenti.
        </p>
        {isCertificateFirstRow ? <CandidateBox label="candidati DDT" loadingPreview={loadingDdtPreview} preview={ddtLinkPreview} /> : null}
      </div>
    </div>
  );
}

function LinkCandidateList({ emptyLabel, items, linkingKey, loading, onLinkCandidate, title, type }) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4">
        <p className="text-sm font-semibold text-sky-800">{title}</p>
        <p className="mt-1 text-xs text-slate-600">Sto cercando candidati usando i campi ponte Excel.</p>
      </div>
    );
  }
  if (!items?.length) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className="mt-1 text-xs text-slate-500">{emptyLabel}</p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="mt-1 text-xs text-slate-500">Scegli un candidato solo se i campi ponte sono coerenti con la riga.</p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">{items.length} trovati</span>
      </div>
      <div className="mt-4 space-y-3">
        {items.map((item) => {
          const fileName = type === "ddt" ? safeText(item.ddt_file_name) || `DDT #${safeText(item.document_ddt_id)}` : safeText(item.certificate_file_name) || `Certificato #${safeText(item.document_certificato_id)}`;
          return (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={`${type}-${safeText(item.row_id)}`}>
              <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Riga #{safeText(item.row_id)} · {fileName}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Score {safeText(item.score)} · {(Array.isArray(item.reasons) ? item.reasons : []).join(" · ") || "nessun dettaglio"}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.manual_blocked ? (
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">
                      Bloccato da disaccoppio
                    </span>
                  ) : null}
                  {item.already_linked ? (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
                      Gia agganciata a riga #{safeText(item.linked_row_id)}
                    </span>
                  ) : null}
                  <button
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                      item.manual_blocked
                        ? "border-rose-300 bg-white text-rose-700 hover:bg-rose-50"
                        : item.already_linked
                          ? "border-amber-300 bg-white text-amber-800 hover:bg-amber-50"
                          : "border-emerald-300 bg-white text-emerald-700 hover:bg-emerald-50"
                    } disabled:opacity-60`}
                    disabled={linkingKey === `${type}-${safeText(item.row_id)}`}
                    onClick={() => onLinkCandidate?.(type, item)}
                    type="button"
                  >
                    {linkingKey === `${type}-${safeText(item.row_id)}`
                      ? "Collego..."
                      : item.recommended_action === "collega_anche_qui"
                        ? "Collega anche qui"
                        : item.recommended_action === "riaggancio_bloccato"
                          ? "Riaggancia comunque"
                          : "Aggancia"}
                  </button>
                </div>
              </div>
              {item.manual_blocked ? (
                <p className="mt-2 text-xs text-rose-700">
                  Questa coppia è stata separata manualmente: il rematch automatico resta bloccato, ma puoi riagganciarla con conferma esplicita.
                </p>
              ) : null}
              {item.already_linked && item.linked_file_name ? (
                <p className="mt-2 text-xs text-amber-800">
                  Documento gia collegato: {safeText(item.linked_file_name)}. Se confermi, non lo sposto: creo un aggancio aggiuntivo.
                </p>
              ) : null}
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
          );
        })}
      </div>
    </div>
  );
}

function DetachConfirmDialog({ certificateDraft, ddtDraft, detaching, onCancel, onConfirm }) {
  const equalFields = HIGH_LEVEL_FIELDS.filter(
    ({ key }) => safeText(ddtDraft?.[key]).trim() && safeText(ddtDraft?.[key]).trim() === safeText(certificateDraft?.[key]).trim(),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-8">
      <div className="w-full max-w-3xl rounded-2xl border border-amber-200 bg-white p-5 shadow-2xl">
        <p className="text-lg font-semibold text-slate-950">Disaccoppiare DDT e certificato?</p>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Verranno create due righe: una resterà con il DDT, una nuova con il certificato. Questa stessa coppia non verrà riagganciata
          automaticamente dal rematch: potrai riagganciarla solo con una scelta esplicita.
        </p>
        {equalFields.length ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Attenzione: alcuni campi sono ancora uguali ({equalFields.map((field) => field.label).join(", ")}). Senza blocco manuale il
            sistema li considererebbe ancora matchabili.
          </div>
        ) : null}
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <DetachPreview title="Riga DDT" values={ddtDraft} />
          <DetachPreview title="Nuova riga certificato" values={certificateDraft} />
        </div>
        <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={detaching}
            onClick={onCancel}
            type="button"
          >
            Annulla
          </button>
          <button
            className="rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
            disabled={detaching}
            onClick={onConfirm}
            type="button"
          >
            {detaching ? "Disaccoppio..." : "Conferma disaccoppio"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DetachPreview({ title, values }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {HIGH_LEVEL_FIELDS.map((field) => (
          <div className="rounded-lg border border-slate-200 bg-white px-2 py-1.5" key={field.key}>
            <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">{field.label}</p>
            <p className="mt-0.5 truncate text-sm font-medium text-slate-800">{safeText(values?.[field.key]) || "-"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LinkCandidateConfirmDialog({ candidate, confirming, onCancel, onConfirm }) {
  if (!candidate) {
    return null;
  }
  const typeLabel = candidate.type === "ddt" ? "DDT" : "certificato";
  const isManualBlocked = Boolean(candidate.item.manual_blocked);
  const fileName =
    candidate.type === "ddt"
      ? safeText(candidate.item.ddt_file_name) || `DDT #${safeText(candidate.item.document_ddt_id)}`
      : safeText(candidate.item.certificate_file_name) || `Certificato #${safeText(candidate.item.document_certificato_id)}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-8">
      <div className="w-full max-w-2xl rounded-2xl border border-amber-200 bg-white p-5 shadow-2xl">
        <p className="text-lg font-semibold text-slate-950">
          {isManualBlocked ? "Riagganciare una coppia separata?" : "Collegare un documento gia agganciato?"}
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {isManualBlocked
            ? `Il candidato ${typeLabel} sulla riga #${safeText(candidate.item.row_id)} era stato separato manualmente. Confermando togliamo il blocco solo per questa coppia e la riagganciamo.`
            : `Il candidato ${typeLabel} sulla riga #${safeText(candidate.item.row_id)} è gia collegato. Confermando non lo spostiamo dalla riga attuale: creiamo un aggancio aggiuntivo o una riga gemella quando serve.`}
        </p>
        <div className={`mt-4 rounded-xl border px-3 py-2 text-sm ${isManualBlocked ? "border-rose-200 bg-rose-50 text-rose-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
          {isManualBlocked
            ? "Azione forte: usala solo se lo sgancio era sbagliato o vuoi ricreare consapevolmente questo match."
            : "Controlla che i campi ponte siano davvero dello stesso materiale prima di proseguire."}
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <PreviewMini label="Riga" value={`#${safeText(candidate.item.row_id)}`} />
          <PreviewMini label="Documento" value={fileName} />
          <PreviewMini label="Score" value={candidate.item.score} />
          <PreviewMini label={isManualBlocked ? "Stato" : "Gia collegato"} value={isManualBlocked ? "Bloccato da disaccoppio" : safeText(candidate.item.linked_file_name) || "-"} />
        </div>
        <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={confirming}
            onClick={onCancel}
            type="button"
          >
            Annulla
          </button>
          <button
            className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 ${isManualBlocked ? "bg-rose-600 hover:bg-rose-700" : "bg-amber-600 hover:bg-amber-700"}`}
            disabled={confirming}
            onClick={onConfirm}
            type="button"
          >
            {confirming ? "Collego..." : isManualBlocked ? "Conferma riaggancio" : "Conferma collega anche qui"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DocumentConfirmGuidanceDialog({ dialog, onClose }) {
  if (!dialog) {
    return null;
  }
  const isFinal = dialog.kind === "final";
  const title =
    dialog.kind === "final"
      ? "DDT e certificato confermati"
      : dialog.kind === "conflict"
        ? "Campi confermati, match da controllare"
        : dialog.nextSide === "certificato"
          ? "Ora conferma anche il certificato"
          : "Ora conferma anche il DDT";
  const detail =
    dialog.kind === "final"
      ? "La coppia documentale è confermata. Torno a Incoming materiale."
      : dialog.kind === "conflict"
        ? "I due lati sono salvati, ma il match non risulta confermato. Controlla i campi oppure disaccoppia o matcha secondo finalità."
        : "Oppure disaccoppia o matcha secondo finalità.";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <p className="text-lg font-semibold text-slate-950">{title}</p>
        <p className="mt-3 text-sm leading-6 text-slate-600">{detail}</p>
        {!isFinal ? (
          <div className="mt-6 flex justify-end">
            <button
              className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-700"
              onClick={onClose}
              type="button"
            >
              Ho capito
            </button>
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
  onRowRelocated,
  row,
  rowId,
  token,
  onRefreshRow,
}) {
  const navigate = useNavigate();
  const isCertificateFirstRow = useMemo(() => Boolean(row?.document_certificato_id) && !row?.document_ddt_id, [row]);
  const isDdtOnlyRow = useMemo(() => Boolean(row?.document_ddt_id) && !row?.document_certificato_id, [row]);
  const [ddtDraft, setDdtDraft] = useState(() => buildDdtDraft(row));
  const [initialDdtDraft, setInitialDdtDraft] = useState(() => buildDdtDraft(row));
  const [certificateDraft, setCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [initialCertificateDraft, setInitialCertificateDraft] = useState(() => buildCertificateDraft(row));
  const [ddtSourceOverrides, setDdtSourceOverrides] = useState({});
  const [certificateSourceOverrides, setCertificateSourceOverrides] = useState({});
  const [savingDdtFields, setSavingDdtFields] = useState(false);
  const [refreshingCertificateFirst, setRefreshingCertificateFirst] = useState(false);
  const [savingCertificateFirst, setSavingCertificateFirst] = useState(false);
  const [loadingDdtPreview, setLoadingDdtPreview] = useState(false);
  const [ddtLinkPreview, setDdtLinkPreview] = useState(null);
  const [loadingCertificatePreview, setLoadingCertificatePreview] = useState(false);
  const [certificateLinkPreview, setCertificateLinkPreview] = useState(null);
  const [error, setError] = useState("");
  const [certificateOverlayActive, setCertificateOverlayActive] = useState(false);
  const [ddtOverlayActive, setDdtOverlayActive] = useState(false);
  const [certificateOverlayBusy, setCertificateOverlayBusy] = useState(false);
  const [ddtOverlayBusy, setDdtOverlayBusy] = useState(false);
  const [certificateOverlayItems, setCertificateOverlayItems] = useState([]);
  const [ddtOverlayItems, setDdtOverlayItems] = useState([]);
  const [detachDialogOpen, setDetachDialogOpen] = useState(false);
  const [detachingMatch, setDetachingMatch] = useState(false);
  const [linkingCandidateKey, setLinkingCandidateKey] = useState("");
  const [pendingLinkCandidate, setPendingLinkCandidate] = useState(null);
  const [confirmGuidanceDialog, setConfirmGuidanceDialog] = useState(null);

  useEffect(() => {
    const nextDraft = buildDdtDraft(row);
    setDdtDraft(nextDraft);
    setInitialDdtDraft(nextDraft);
    setDdtSourceOverrides({});
  }, [row]);

  useEffect(() => {
    const nextDraft = buildCertificateDraft(row);
    setCertificateDraft(nextDraft);
    setInitialCertificateDraft(nextDraft);
    setCertificateSourceOverrides({});
  }, [row]);

  useEffect(() => {
    onDirtyChange?.(
      (Boolean(certificateDocument) && !draftsEqual(certificateDraft, initialCertificateDraft)) ||
        (Boolean(ddtDocument) && !draftsEqual(ddtDraft, initialDdtDraft)),
    );
  }, [certificateDocument, certificateDraft, ddtDocument, ddtDraft, initialCertificateDraft, initialDdtDraft, onDirtyChange]);

  const hasUnsavedChanges = useMemo(
    () =>
      (Boolean(certificateDocument) && !draftsEqual(certificateDraft, initialCertificateDraft)) ||
      (Boolean(ddtDocument) && !draftsEqual(ddtDraft, initialDdtDraft)),
    [certificateDocument, certificateDraft, ddtDocument, ddtDraft, initialCertificateDraft, initialDdtDraft],
  );

  useBeforeUnload(
    (event) => {
      if (!hasUnsavedChanges) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    },
    { capture: true },
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

  useEffect(() => {
    let ignore = false;

    async function loadPreview() {
      if (!isDdtOnlyRow) {
        setCertificateLinkPreview(null);
        return;
      }
      setLoadingCertificatePreview(true);
      try {
        const preview = await apiRequest(`/acquisition/rows/${rowId}/certificate-link-preview`, {}, token);
        if (!ignore) {
          setCertificateLinkPreview(preview);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setCertificateLinkPreview(null);
          setError(requestError.message);
        }
      } finally {
        if (!ignore) {
          setLoadingCertificatePreview(false);
        }
      }
    }

    void loadPreview();
    return () => {
      ignore = true;
    };
  }, [isDdtOnlyRow, rowId, token]);

  useEffect(() => {
    if (confirmGuidanceDialog?.kind !== "final") {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      onDirtyChange?.(false);
      navigate("/acquisition");
    }, 3500);
    return () => window.clearTimeout(timer);
  }, [confirmGuidanceDialog, navigate, onDirtyChange]);

  function showPostDocumentConfirmDialog(refreshedRow, savedSide) {
    if (documentPairConfirmed(refreshedRow)) {
      setConfirmGuidanceDialog({ kind: "final" });
      return;
    }
    const ddtConfirmed = ddtBlockConfirmed(refreshedRow);
    const certificateFieldsConfirmed = documentSideConfirmed(refreshedRow, "certificato");
    const matchConfirmed = matchBlockConfirmed(refreshedRow);
    if (ddtConfirmed && certificateFieldsConfirmed && !matchConfirmed) {
      setConfirmGuidanceDialog({ kind: "conflict" });
      return;
    }
    if (savedSide === "ddt" && !certificateFieldsConfirmed && !matchConfirmed) {
      setConfirmGuidanceDialog({ kind: "next", nextSide: "certificato" });
      return;
    }
    if (savedSide === "certificato" && !ddtConfirmed) {
      setConfirmGuidanceDialog({ kind: "next", nextSide: "ddt" });
    }
  }

  const ddtFields = useMemo(() => ddtDraft, [ddtDraft]);
  const ddtFieldSources = useMemo(() => buildSourceMap(row, "ddt", ddtSourceOverrides), [ddtSourceOverrides, row]);
  const certificateFieldSources = useMemo(() => buildSourceMap(row, "certificato", certificateSourceOverrides), [certificateSourceOverrides, row]);
  const ddtFieldStates = useMemo(() => buildStateMap(row, "ddt", ddtSourceOverrides), [ddtSourceOverrides, row]);
  const certificateFieldStates = useMemo(() => buildStateMap(row, "certificato", certificateSourceOverrides), [certificateSourceOverrides, row]);

  function updateCertificateDraft(field, value) {
    setCertificateDraft((current) => ({ ...current, [field]: value }));
    setCertificateSourceOverrides((current) => ({ ...current, [field]: "utente" }));
  }

  function updateDdtDraft(field, value) {
    setDdtDraft((current) => ({ ...current, [field]: value }));
    setDdtSourceOverrides((current) => ({ ...current, [field]: "utente" }));
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
    setDdtSourceOverrides({});
  }

  async function handleResetCertificateDraft() {
    const nextDraft = buildCertificateDraft(row);
    setCertificateDraft(nextDraft);
    setInitialCertificateDraft(nextDraft);
    setCertificateSourceOverrides({});
  }

  async function handleSaveDdtFields() {
    setSavingDdtFields(true);
    setError("");
    try {
      const refreshedRow = await apiRequest(
        `/acquisition/rows/${rowId}/document-side-fields`,
        {
          method: "PUT",
          body: JSON.stringify({
            side: "ddt",
            fields: ddtDraft,
          }),
        },
        token,
      );
      setDdtSourceOverrides({});
      onDirtyChange?.(false);
      await onRefreshRow?.();
      showPostDocumentConfirmDialog(refreshedRow, "ddt");
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
      const refreshedRow = await apiRequest(
        `/acquisition/rows/${rowId}/document-side-fields`,
        {
          method: "PUT",
          body: JSON.stringify({
            side: "certificato",
            fields: certificateDraft,
          }),
        },
        token,
      );
      setCertificateSourceOverrides({});
      onDirtyChange?.(false);
      await onRefreshRow?.();
      showPostDocumentConfirmDialog(refreshedRow, "certificato");
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

  async function handleDetachMatch() {
    setDetachingMatch(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/detach-match`,
        {
          method: "POST",
          body: JSON.stringify({
            motivo_breve: "Disaccoppiato manualmente dalla pagina match",
          }),
        },
        token,
      );
      setDetachDialogOpen(false);
      setDdtOverlayActive(false);
      setCertificateOverlayActive(false);
      setDdtOverlayItems([]);
      setCertificateOverlayItems([]);
      await onRefreshRow?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setDetachingMatch(false);
    }
  }

  async function handleLinkCandidate(type, item) {
    if (item.already_linked || item.manual_blocked) {
      setPendingLinkCandidate({ type, item });
      return;
    }
    await executeLinkCandidate(type, item);
  }

  async function executeLinkCandidate(type, item) {
    const key = `${type}-${safeText(item.row_id)}`;
    setLinkingCandidateKey(key);
    setError("");
    try {
      const response = await apiRequest(
        `/acquisition/rows/${rowId}/link-candidate`,
        {
          method: "POST",
          body: JSON.stringify({
            candidate_row_id: item.row_id,
            allow_already_linked: Boolean(item.already_linked),
            allow_manual_blocked: Boolean(item.manual_blocked),
            motivo_breve: null,
          }),
        },
        token,
      );
      setDdtOverlayActive(false);
      setCertificateOverlayActive(false);
      setDdtOverlayItems([]);
      setCertificateOverlayItems([]);
      setDdtLinkPreview(null);
      setCertificateLinkPreview(null);
      setPendingLinkCandidate(null);
      const targetRowId = response?.target_row_id;
      if (targetRowId && String(targetRowId) !== String(rowId)) {
        onRowRelocated?.(targetRowId);
        return;
      }
      await onRefreshRow?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLinkingCandidateKey("");
    }
  }

  const ddtActionBox = (
    <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-700">DDT</p>
      <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
        {ddtDocument
          ? "Controlla i campi letti dal DDT come documento autonomo."
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
      <CandidateBox label="candidati DDT" loadingPreview={loadingDdtPreview} preview={ddtLinkPreview} />
    </div>
  ) : (
    <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-700">Certificato</p>
      <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
        {certificateDocument ? "Controlla i campi letti dal certificato come certificate-first." : "Qui arriveranno ricerca e collegamento del certificato mancante."}
      </p>
    </div>
  );

  const certificateStatusLabel = isCertificateFirstRow
    ? loadingDdtPreview
      ? "Cerco DDT candidati per il collegamento."
      : ddtLinkPreview?.auto_match_row_id
        ? `Candidato forte trovato: riga #${safeText(ddtLinkPreview.auto_match_row_id)}.`
        : "Controlla i campi alti del certificato e poi ricarica i candidati."
    : certificateDocument
      ? "Controlla e conferma il lato certificato. Il DDT resta separato."
      : "Nessun certificato collegato: qui apparirà la sezione di accoppiamento.";

  const ddtStatusLabel = ddtDocument
    ? "Controlla e conferma il lato DDT. Il certificato resta separato."
    : "Nessun DDT collegato.";

  return (
    <section className="space-y-4">
      {ddtDocument ? (
        <DocumentPdfPanel
          document={ddtDocument}
          kind="ddt"
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
                confirmDisabled={!ddtDocument || savingDdtFields}
                confirming={savingDdtFields}
                editable={Boolean(ddtDocument)}
                fields={ddtFields}
                fieldSources={ddtFieldSources}
                fieldStates={ddtFieldStates}
                onChange={updateDdtDraft}
                onConfirm={() => void handleSaveDdtFields()}
                onReset={() => void handleResetDdtDraft()}
                resetDisabled={!ddtDocument}
              />
            </div>
          }
          title="DDT"
          token={token}
        />
      ) : (
        <MissingDocumentPanel
          kind="ddt"
          previewContent={
            isCertificateFirstRow ? (
              <LinkCandidateList
                emptyLabel="Nessun DDT candidato trovato con i campi ponte attuali."
                items={ddtLinkPreview?.items || []}
                linkingKey={linkingCandidateKey}
                loading={loadingDdtPreview}
                onLinkCandidate={handleLinkCandidate}
                title="Candidati DDT da collegare"
                type="ddt"
              />
            ) : null
          }
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
              actionState={ddtLinkPreview?.auto_match_row_id ? `Candidato forte: riga #${safeText(ddtLinkPreview.auto_match_row_id)}` : ""}
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
              fieldSources={ddtFieldSources}
              fieldStates={ddtFieldStates}
              onChange={() => {}}
              onConfirm={() => {}}
              onReset={() => {}}
              resetDisabled
            />
          </div>
        </MissingDocumentPanel>
      )}

      <MatchBridgePanel
        canDetach={Boolean(ddtDocument && certificateDocument)}
        detaching={detachingMatch}
        ddtLinkPreview={ddtLinkPreview}
        isCertificateFirstRow={isCertificateFirstRow}
        loadingDdtPreview={loadingDdtPreview}
        onDetach={() => setDetachDialogOpen(true)}
        row={row}
      />

      {certificateDocument ? (
        <DocumentPdfPanel
          document={certificateDocument}
          kind="certificato"
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
                confirmDisabled={savingCertificateFirst || !certificateDocument}
                confirming={savingCertificateFirst}
                editable={Boolean(certificateDocument)}
                fields={certificateDraft}
                fieldSources={certificateFieldSources}
                fieldStates={certificateFieldStates}
                onChange={updateCertificateDraft}
                onConfirm={handleSaveCertificateFirstFields}
                onReset={isCertificateFirstRow ? handleRefreshCertificateFirst : handleResetCertificateDraft}
                resetDisabled={refreshingCertificateFirst || !certificateDocument}
              />
            </div>
          }
          title="Certificato"
          token={token}
        />
      ) : (
        <MissingDocumentPanel
          kind="certificato"
          previewContent={
            isDdtOnlyRow ? (
              <LinkCandidateList
                emptyLabel="Nessun certificato candidato trovato con i campi ponte attuali."
                items={certificateLinkPreview?.items || []}
                linkingKey={linkingCandidateKey}
                loading={loadingCertificatePreview}
                onLinkCandidate={handleLinkCandidate}
                title="Candidati certificato da collegare"
                type="certificato"
              />
            ) : null
          }
          subtitle={
            isDdtOnlyRow
              ? "Qui dobbiamo aiutare l’utente a trovare e collegare il certificato giusto, con ricerca assistita e confronto sui campi alti."
              : "Qui comparirà il certificato una volta collegato o caricato."
          }
          title="Certificato"
        >
          <div className="space-y-2">
            <StatusBar
              actionLabel={loadingCertificatePreview ? "Ricerca certificati candidati in corso." : "Qui appariranno candidati certificato e collegamento."}
              actionState={certificateLinkPreview?.auto_match_row_id ? `Candidato forte: riga #${safeText(certificateLinkPreview.auto_match_row_id)}` : ""}
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
              fieldSources={certificateFieldSources}
              fieldStates={certificateFieldStates}
              onChange={() => {}}
              onConfirm={() => {}}
              onReset={() => {}}
              resetDisabled
            />
          </div>
        </MissingDocumentPanel>
      )}
      {detachDialogOpen ? (
        <DetachConfirmDialog
          certificateDraft={certificateDraft}
          ddtDraft={ddtDraft}
          detaching={detachingMatch}
          onCancel={() => setDetachDialogOpen(false)}
          onConfirm={() => void handleDetachMatch()}
        />
      ) : null}
      {pendingLinkCandidate ? (
        <LinkCandidateConfirmDialog
          candidate={pendingLinkCandidate}
          confirming={linkingCandidateKey === `${pendingLinkCandidate.type}-${safeText(pendingLinkCandidate.item.row_id)}`}
          onCancel={() => setPendingLinkCandidate(null)}
          onConfirm={() => void executeLinkCandidate(pendingLinkCandidate.type, pendingLinkCandidate.item)}
        />
      ) : null}
      <DocumentConfirmGuidanceDialog dialog={confirmGuidanceDialog} onClose={() => setConfirmGuidanceDialog(null)} />
    </section>
  );
}
