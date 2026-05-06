import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { focusFirstOverlayItemInViewport } from "./overlayScroll";

const CHEMISTRY_FIELD_ORDER = [
  "Si",
  "Fe",
  "Cu",
  "Mn",
  "Mg",
  "Cr",
  "Ni",
  "Zn",
  "Ti",
  "Cd",
  "Hg",
  "Pb",
  "V",
  "Bi",
  "Sn",
  "Zr",
  "Be",
  "Zr+Ti",
  "Mn+Cr",
  "Bi+Pb",
];

const DERIVED_FIELDS = {
  "Zr+Ti": ["Zr", "Ti"],
  "Mn+Cr": ["Mn", "Cr"],
  "Bi+Pb": ["Bi", "Pb"],
};

function normalizeDisplayValue(value) {
  return (value || "").trim();
}

function formatChemistryDisplayValue(value) {
  const raw = normalizeDisplayValue(value);
  if (!raw) {
    return "";
  }

  const simpleNumeric = raw.match(/^([<>]=?\s*)?(\d+)([.,](\d+))?$/);
  if (simpleNumeric) {
    const prefix = simpleNumeric[1] || "";
    const integerPart = simpleNumeric[2] || "";
    const decimalPart = simpleNumeric[4] || "";
    return decimalPart ? `${prefix}${integerPart},${decimalPart}` : `${prefix}${integerPart}`;
  }

  return raw.replace(/(\d)\.(\d)/g, "$1,$2");
}

function chemistryDisplayValue(value) {
  return formatChemistryDisplayValue(value?.valore_finale || value?.valore_standardizzato || value?.valore_grezzo || "");
}

function parseLocalizedNumber(value) {
  if (!value) {
    return null;
  }
  const normalized = String(value).trim().replace(/\s+/g, "").replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDerivedNumber(value) {
  return value
    .toFixed(4)
    .replace(/\.?0+$/, "")
    .replace(".", ",");
}

function formatChemistryFieldLabel(field) {
  return String(field)
    .split("+")
    .map((part) => {
      const trimmed = part.trim();
      if (!trimmed) {
        return trimmed;
      }
      return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
    })
    .join("+");
}

function buildFieldList(values) {
  const extras = values
    .map((value) => value.campo)
    .filter((field) => !CHEMISTRY_FIELD_ORDER.includes(field))
    .sort((left, right) => left.localeCompare(right));

  return [...CHEMISTRY_FIELD_ORDER, ...extras];
}

function buildInitialDraft(values) {
  const draft = {};
  values.forEach((value) => {
    draft[value.campo] = chemistryDisplayValue(value);
  });
  return draft;
}

function buildChemistryPersistedSignature(values) {
  return JSON.stringify(
    (values || [])
      .filter((value) => value.blocco === "chimica")
      .map((value) => ({
        campo: value.campo,
        grezzo: value.valore_grezzo || "",
        standardizzato: value.valore_standardizzato || "",
        finale: value.valore_finale || "",
        metodo: value.metodo_lettura || "",
        fonte: value.fonte_documentale || "",
        evidence: value.document_evidence_id || null,
      }))
      .sort((left, right) => String(left.campo).localeCompare(String(right.campo))),
  );
}

function buildEffectiveDraft(initialDraft, draft) {
  const next = { ...draft };
  Object.entries(DERIVED_FIELDS).forEach(([target, parts]) => {
    if (normalizeDisplayValue(next[target])) {
      return;
    }
    const numbers = parts.map((field) => parseLocalizedNumber(next[field]));
    if (numbers.some((value) => value === null)) {
      return;
    }
    next[target] = formatDerivedNumber(numbers[0] + numbers[1]);
  });
  return next;
}

function draftsEqual(left, right, fields) {
  return fields.every((field) => normalizeDisplayValue(left[field]) === normalizeDisplayValue(right[field]));
}

function calculatedValueForField(field, draft) {
  const parts = DERIVED_FIELDS[field];
  if (!parts) {
    return "";
  }
  const numbers = parts.map((item) => parseLocalizedNumber(draft[item]));
  if (numbers.some((value) => value === null)) {
    return "";
  }
  return formatDerivedNumber(numbers[0] + numbers[1]);
}

function sourceLabel(value, field, draft, sessionSourceOverrides) {
  if (sessionSourceOverrides[field] === "manuale") {
    return "manuale";
  }
  if (!value) {
    const calculatedValue = calculatedValueForField(field, draft);
    if (calculatedValue && normalizeDisplayValue(draft[field]) === normalizeDisplayValue(calculatedValue)) {
      return "calcolato";
    }
    return "certificato - AI";
  }
  if (value.metodo_lettura === "utente") {
    return "manuale";
  }
  if (value.metodo_lettura === "calcolato" || value.fonte_documentale === "calcolato") {
    return "calcolato";
  }
  if (value && chemistryDisplayValue(value)) {
    if ((value.fonte_documentale || "certificato") === "certificato") {
      return "certificato - AI";
    }
    return value.fonte_documentale || "manuale";
  }
  const calculatedValue = calculatedValueForField(field, draft);
  if (calculatedValue && normalizeDisplayValue(draft[field]) === normalizeDisplayValue(calculatedValue)) {
    return "calcolato";
  }
  if ((value.fonte_documentale || "certificato") === "certificato") {
    return "certificato - AI";
  }
  return value.fonte_documentale || "manuale";
}

function renderOverlayBox({ item, color, imageWidth, imageHeight, title, key }) {
  const [left, top, right, bottom] = String(item?.bbox || "")
    .split(",")
    .map((part) => Number.parseFloat(part));
  if (
    !Number.isFinite(left) ||
    !Number.isFinite(top) ||
    !Number.isFinite(right) ||
    !Number.isFinite(bottom) ||
    imageWidth <= 0 ||
    imageHeight <= 0
  ) {
    return null;
  }
  const palette =
    color === "green"
      ? "border-emerald-500 bg-emerald-400/50 shadow-[0_0_0_1px_rgba(16,185,129,0.3)]"
      : "border-sky-500 bg-sky-400/20 shadow-[0_0_0_1px_rgba(14,165,233,0.2)]";
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

function buildPersistedUserOverlayItems(row) {
  const evidences = Array.isArray(row?.evidences) ? row.evidences : [];
  const evidenceMap = new Map(evidences.map((evidence) => [evidence.id, evidence]));
  return (Array.isArray(row?.values) ? row.values : [])
    .filter((value) => value?.blocco === "chimica" && value?.metodo_lettura === "utente" && value?.document_evidence_id)
    .map((value) => {
      const evidence = evidenceMap.get(value.document_evidence_id);
      if (!evidence?.bbox || !evidence?.document_page_id) {
        return null;
      }
      return {
        field: value.campo,
        page_id: evidence.document_page_id,
        bbox: evidence.bbox,
        image_width: 0,
        image_height: 0,
      };
    })
    .filter(Boolean);
}

function mergeOverlayItems(primaryItems, secondaryItems) {
  const merged = [];
  const seenFields = new Set();
  [...(primaryItems || []), ...(secondaryItems || [])].forEach((item) => {
    if (!item?.field || seenFields.has(item.field)) {
      return;
    }
    seenFields.add(item.field);
    merged.push(item);
  });
  return merged;
}

function ChemistryPdfPanel({
  captureField,
  certificateDocument,
  draftOverlayItems,
  footerContent,
  onCaptureError,
  onCaptureValue,
  overlayPreviewItems,
  onTableCaptureProposal,
  tableCaptureActive,
  token,
}) {
  const [pageImages, setPageImages] = useState([]);
  const [pageImageSizes, setPageImageSizes] = useState({});
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
  const [captureBusyPageId, setCaptureBusyPageId] = useState(null);
  const [selection, setSelection] = useState(null);
  const viewportRef = useRef(null);
  const pageElementRefs = useRef({});
  const [viewportWidth, setViewportWidth] = useState(0);
  useEffect(() => {
    let ignore = false;
    const objectUrls = [];

    async function loadPageImages() {
      const pages = (certificateDocument?.pages || []).filter((page) => page.image_url);
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
            return {
              id: page.id,
              numero_pagina: page.numero_pagina,
              src: objectUrl,
            };
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

    loadPageImages();

    return () => {
      ignore = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [certificateDocument, token]);

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

  async function handlePageClick(page, event) {
    if (!captureField) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }
    const xRatio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
    const yRatio = Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1);

    setCaptureBusyPageId(page.id);
    try {
      const capture = await apiRequest(
        `/acquisition/document-pages/${page.id}/chemistry-capture`,
        {
          method: "POST",
          body: JSON.stringify({
            x_ratio: xRatio,
            y_ratio: yRatio,
          }),
        },
        token,
      );

      if (!capture?.value) {
        const message = "Nessun valore chimico leggibile vicino al punto cliccato.";
        onCaptureError?.(message);
        return;
      }

      onCaptureValue(captureField, capture.value, capture);
    } catch (requestError) {
      onCaptureError?.(requestError.message);
    } finally {
      setCaptureBusyPageId(null);
    }
  }

  function handleSelectionStart(page, event) {
    if (!tableCaptureActive || captureField) {
      return;
    }
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
    const y = Math.min(Math.max(event.clientY - rect.top, 0), rect.height);
    setSelection({
      pageId: page.id,
      pageNumber: page.numero_pagina,
      originX: x,
      originY: y,
      currentX: x,
      currentY: y,
      rectWidth: rect.width,
      rectHeight: rect.height,
    });
  }

  function handleSelectionMove(page, event) {
    if (!selection || selection.pageId !== page.id) {
      return;
    }
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
    const y = Math.min(Math.max(event.clientY - rect.top, 0), rect.height);
    setSelection((current) =>
      current && current.pageId === page.id
        ? {
            ...current,
            currentX: x,
            currentY: y,
            rectWidth: rect.width,
            rectHeight: rect.height,
          }
        : current,
    );
  }

  async function handleSelectionEnd(page) {
    if (!selection || selection.pageId !== page.id) {
      return;
    }

    const x1 = Math.min(selection.originX, selection.currentX);
    const x2 = Math.max(selection.originX, selection.currentX);
    const y1 = Math.min(selection.originY, selection.currentY);
    const y2 = Math.max(selection.originY, selection.currentY);
    const width = x2 - x1;
    const height = y2 - y1;
    const rectWidth = selection.rectWidth || 1;
    const rectHeight = selection.rectHeight || 1;
    setSelection(null);

    if (width < 12 || height < 12) {
      return;
    }

    setCaptureBusyPageId(page.id);
    try {
      const proposal = await apiRequest(
        `/acquisition/document-pages/${page.id}/chemistry-table-capture`,
        {
          method: "POST",
          body: JSON.stringify({
            x1_ratio: x1 / rectWidth,
            y1_ratio: y1 / rectHeight,
            x2_ratio: x2 / rectWidth,
            y2_ratio: y2 / rectHeight,
          }),
        },
        token,
      );

      if (!proposal?.values || !Object.keys(proposal.values).length) {
        const message = "Nessun valore chimico leggibile nel rettangolo selezionato.";
        onCaptureError?.(message);
        return;
      }

      onTableCaptureProposal?.(proposal);
    } catch (requestError) {
      onCaptureError?.(requestError.message);
    } finally {
      setCaptureBusyPageId(null);
    }
  }

  const selectionStyle =
    selection && selection.pageId
      ? {
          left: `${Math.min(selection.originX, selection.currentX)}px`,
          top: `${Math.min(selection.originY, selection.currentY)}px`,
          width: `${Math.abs(selection.currentX - selection.originX)}px`,
          height: `${Math.abs(selection.currentY - selection.originY)}px`,
        }
      : null;

  const previewItemsByPage = useMemo(() => {
    const grouped = new Map();
    (overlayPreviewItems || []).forEach((item) => {
      const key = item.page_id;
      const items = grouped.get(key) || [];
      items.push(item);
      grouped.set(key, items);
    });
    return grouped;
  }, [overlayPreviewItems]);

  const draftItemsByPage = useMemo(() => {
    const grouped = new Map();
    (draftOverlayItems || []).forEach((item) => {
      const key = item.page_id;
      const items = grouped.get(key) || [];
      items.push(item);
      grouped.set(key, items);
    });
    return grouped;
  }, [draftOverlayItems]);

  useEffect(() => {
    if (!overlayPreviewItems.length) {
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

  return (
    <div className="rounded-2xl border border-slate-600 bg-slate-700 p-4">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">Certificato</p>
          <p className="mt-1 text-sm text-white">
            {certificateDocument?.nome_file_originale || "Nessun certificato collegato"}
          </p>
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

      <div className="h-[43vh] overflow-auto rounded-2xl border border-slate-600 bg-slate-700 p-3" ref={viewportRef}>
        {pageImages.length ? (
          <div className="space-y-4">
            {pageImages.map((page) => (
              <div
                className="w-full"
                key={page.id}
                ref={(element) => {
                  if (element) {
                    pageElementRefs.current[page.id] = element;
                  } else {
                    delete pageElementRefs.current[page.id];
                  }
                }}
              >
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
                    alt={`Certificato pagina ${page.numero_pagina}`}
                    className="block w-full rounded-xl border border-slate-200 bg-white shadow-sm"
                    draggable={false}
                    onLoad={(event) => {
                      const target = event.currentTarget;
                      const nextWidth = Number(target.naturalWidth || 0);
                      const nextHeight = Number(target.naturalHeight || 0);
                      if (nextWidth <= 0 || nextHeight <= 0) {
                        return;
                      }
                      setPageImageSizes((current) => {
                        const existing = current[page.id];
                        if (existing && existing.width === nextWidth && existing.height === nextHeight) {
                          return current;
                        }
                        return {
                          ...current,
                          [page.id]: { width: nextWidth, height: nextHeight },
                        };
                      });
                    }}
                    src={page.src}
                    style={{ userSelect: "none" }}
                  />
                  <div
                    className={`${captureField || tableCaptureActive ? "cursor-crosshair" : "cursor-default"} absolute inset-0`}
                    onClick={(event) => handlePageClick(page, event)}
                    onMouseDown={(event) => handleSelectionStart(page, event)}
                    onMouseMove={(event) => handleSelectionMove(page, event)}
                    onMouseUp={() => void handleSelectionEnd(page)}
                  />
                  {(previewItemsByPage.get(page.id) || []).map((item, index) =>
                    renderOverlayBox({
                      item,
                      color: "blue",
                      imageWidth: Number(item.image_width || pageImageSizes[page.id]?.width || 0),
                      imageHeight: Number(item.image_height || pageImageSizes[page.id]?.height || 0),
                      title: `${formatChemistryFieldLabel(item.field)} evidenza preview`,
                      key: `${page.id}-${item.field}-${index}`,
                    }),
                  )}
                  {(draftItemsByPage.get(page.id) || []).map((item, index) =>
                    renderOverlayBox({
                      item,
                      color: "green",
                      imageWidth: Number(pageImageSizes[page.id]?.width || 0),
                      imageHeight: Number(pageImageSizes[page.id]?.height || 0),
                      title:
                        item.field === "__table__"
                          ? "Cattura tabella in bozza"
                          : `${formatChemistryFieldLabel(item.field)} catturato nella bozza`,
                      key: `draft-${page.id}-${item.field}-${index}`,
                    }),
                  )}
                  {selection && selection.pageId === page.id && selectionStyle ? (
                    <div
                      className="pointer-events-none absolute rounded-lg border-2 border-sky-400 bg-sky-200/20"
                      style={selectionStyle}
                    />
                  ) : null}
                </div>
                {captureBusyPageId === page.id ? (
                  <p className="mt-2 text-center text-xs font-medium text-sky-300">Cattura in corso...</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-200">
            {error || "Immagini pagina non disponibili."}
          </div>
        )}
      </div>
      {captureField ? (
        <div className="sr-only">Modalità cattura attiva su {formatChemistryFieldLabel(captureField)}</div>
      ) : null}
      {footerContent ? <div className="mt-3">{footerContent}</div> : null}
    </div>
  );
}

export default function AcquisitionChemistrySectionPage({ certificateDocument, row, rowId, token, onRefreshRow, onDirtyChange }) {
  const chemistryValues = useMemo(() => (row?.values || []).filter((value) => value.blocco === "chimica"), [row]);
  const fieldList = useMemo(() => buildFieldList(chemistryValues), [chemistryValues]);
  const persistedInitialDraft = useMemo(() => buildInitialDraft(chemistryValues), [chemistryValues]);
  const persistedSignature = useMemo(() => buildChemistryPersistedSignature(chemistryValues), [chemistryValues]);
  const valueMap = useMemo(() => new Map(chemistryValues.map((value) => [value.campo, value])), [chemistryValues]);
  const [sessionInitialDraft, setSessionInitialDraft] = useState(() => ({ ...persistedInitialDraft }));
  const [draft, setDraft] = useState(() => ({ ...persistedInitialDraft }));
  const [sessionSourceOverrides, setSessionSourceOverrides] = useState(() => ({}));
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [captureField, setCaptureField] = useState("");
  const [tableCaptureActive, setTableCaptureActive] = useState(false);
  const [tableCaptureProposal, setTableCaptureProposal] = useState(null);
  const [draftOverlayItems, setDraftOverlayItems] = useState([]);
  const [overlayPreviewItems, setOverlayPreviewItems] = useState([]);
  const [overlayBusy, setOverlayBusy] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const workspaceRef = useRef(null);
  const persistedUserOverlayItems = useMemo(() => buildPersistedUserOverlayItems(row), [row]);

  useEffect(() => {
    const nextInitial = { ...persistedInitialDraft };
    setSessionInitialDraft(nextInitial);
    setDraft(nextInitial);
    setSessionSourceOverrides({});
    setDraftOverlayItems([]);
    setOverlayPreviewItems([]);
    onDirtyChange?.(false);
  }, [persistedInitialDraft, persistedSignature]);

  const effectiveDraft = useMemo(() => buildEffectiveDraft(sessionInitialDraft, draft), [sessionInitialDraft, draft]);
  const initialSources = useMemo(
    () =>
      Object.fromEntries(
        fieldList.map((field) => [field, sourceLabel(valueMap.get(field), field, sessionInitialDraft, {})]),
      ),
    [fieldList, sessionInitialDraft, valueMap],
  );
  const currentSources = useMemo(
    () =>
      Object.fromEntries(
        fieldList.map((field) => [field, sourceLabel(valueMap.get(field), field, effectiveDraft, sessionSourceOverrides)]),
      ),
    [effectiveDraft, fieldList, sessionSourceOverrides, valueMap],
  );
  const hasUnsavedChanges = useMemo(() => {
    const valuesChanged = !draftsEqual(sessionInitialDraft, effectiveDraft, fieldList);
    if (valuesChanged) {
      return true;
    }
    return fieldList.some((field) => initialSources[field] !== currentSources[field]);
  }, [currentSources, effectiveDraft, fieldList, initialSources, sessionInitialDraft]);

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
    return () => onDirtyChange?.(false);
  }, [hasUnsavedChanges, onDirtyChange]);

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

  function updateField(field, value, options = {}) {
    const { markTouched = true } = options;
    onDirtyChange?.(true);
    setDraft((current) => ({
      ...current,
      [field]: value,
    }));
    if (markTouched) {
      setSessionSourceOverrides((current) => ({
        ...current,
        [field]: "manuale",
      }));
    }
  }

  function refreshSessionSourceOverrides(nextDraft) {
    setSessionSourceOverrides((current) => {
      const next = {};
      Object.entries(current).forEach(([field, source]) => {
        if (normalizeDisplayValue(nextDraft[field]) !== normalizeDisplayValue(sessionInitialDraft[field])) {
          next[field] = source;
        }
      });
      return next;
    });
  }

  function resetToInitialValues() {
    const nextDraft = { ...sessionInitialDraft };
    setDraft(nextDraft);
    setSessionSourceOverrides({});
    setError("");
    setCaptureField("");
    setTableCaptureActive(false);
    setTableCaptureProposal(null);
    setDraftOverlayItems([]);
    onDirtyChange?.(false);
  }

  function handleWorkspaceError(message) {
    setError(message);
    requestAnimationFrame(() => {
      workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function handleCaptureValue(field, value, capture) {
    onDirtyChange?.(true);
    updateField(field, value, { markTouched: true });
    if (capture?.bbox && capture?.page_id) {
      setDraftOverlayItems((current) => [
        ...current.filter((item) => item.field !== field),
        {
          field,
          page_id: capture.page_id,
          bbox: capture.bbox,
        },
      ]);
    }
    setCaptureField("");
    setError("");
  }

  function handleTableCaptureProposal(proposal) {
    setTableCaptureActive(false);
    setTableCaptureProposal(proposal);
    setError("");
    requestAnimationFrame(() => {
      workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function fetchOverlayPreview() {
    setOverlayBusy(true);
    try {
      const response = await apiRequest(`/acquisition/rows/${rowId}/chemistry-overlay-preview`, {}, token);
      const backendItems = Array.isArray(response?.items) ? response.items : [];
      const nextItems = mergeOverlayItems(persistedUserOverlayItems, backendItems);
      setOverlayPreviewItems(nextItems);
      if (!nextItems.length) {
        setError("Nessun overlay disponibile per questo certificato.");
      } else {
        setError("");
      }
    } catch (requestError) {
      setError(requestError.message);
      setOverlayPreviewItems([]);
    } finally {
      setOverlayBusy(false);
    }
  }

  async function handleToggleOverlayPreview() {
    if (overlayBusy) {
      return;
    }
    if (overlayPreviewItems.length) {
      setOverlayPreviewItems([]);
      return;
    }
    await fetchOverlayPreview();
  }

  async function persistDraft() {
    const overlayWasActive = overlayPreviewItems.length > 0;
    const draftOverlaySnapshot = draftOverlayItems.map((item) => ({ ...item }));
    const evidenceIdByField = {};
    const tableOverlay = draftOverlaySnapshot.find((item) => item.field === "__table__");

    async function ensureUserEvidenceForField(field, persistedValue) {
      if (evidenceIdByField[field]) {
        return evidenceIdByField[field];
      }
      const directOverlay = draftOverlaySnapshot.find((item) => item.field === field);
      const sharedOverlay = tableOverlay;
      const overlayItem = directOverlay || sharedOverlay;
      if (!overlayItem?.bbox || !overlayItem?.page_id || !certificateDocument?.id) {
        return null;
      }
      if (sharedOverlay && Array.isArray(sharedOverlay.fields) && !sharedOverlay.fields.includes(field) && !directOverlay) {
        return null;
      }
      const evidence = await apiRequest(
        `/acquisition/rows/${rowId}/evidences`,
        {
          method: "POST",
          body: JSON.stringify({
            document_id: certificateDocument.id,
            document_page_id: overlayItem.page_id,
            blocco: "chimica",
            tipo_evidenza: directOverlay ? "cella" : "tabella",
            bbox: overlayItem.bbox,
            testo_grezzo: persistedValue || null,
            metodo_estrazione: "utente",
            mascherato: false,
          }),
        },
        token,
      );
      const evidenceId = evidence?.id || null;
      if (evidenceId) {
        if (directOverlay) {
          evidenceIdByField[field] = evidenceId;
        } else if (Array.isArray(sharedOverlay?.fields)) {
          sharedOverlay.fields.forEach((sharedField) => {
            evidenceIdByField[sharedField] = evidenceId;
          });
        }
      }
      return evidenceId;
    }
    const fieldsToPersist = fieldList.filter((field) => {
      const existingValue = valueMap.get(field);
      const initialValue = normalizeDisplayValue(sessionInitialDraft[field]);
      const currentValue = normalizeDisplayValue(effectiveDraft[field]);
      const valueChanged = initialValue !== currentValue;
      const sourceChanged = initialSources[field] !== currentSources[field];
      const hasExistingPayload = Boolean(existingValue && chemistryDisplayValue(existingValue));
      const hasCurrentPayload = Boolean(currentValue);
      return valueChanged || sourceChanged || hasExistingPayload || hasCurrentPayload;
    });

    if (!fieldsToPersist.length) {
      return true;
    }

    setSubmitting(true);
    setError("");
    try {
      for (const field of fieldsToPersist) {
        const existingValue = valueMap.get(field);
        const nextValue = normalizeDisplayValue(effectiveDraft[field]);
        const persistedValue = formatChemistryDisplayValue(nextValue);
        const calculatedValue = calculatedValueForField(field, effectiveDraft);
        const isCalculated = Boolean(calculatedValue) && persistedValue === formatChemistryDisplayValue(calculatedValue);
        const sourceChangedToManual = sessionSourceOverrides[field] === "manuale";
        const sourceType = isCalculated
          ? "calcolato"
          : sourceChangedToManual
            ? "utente"
            : existingValue?.fonte_documentale || "certificato";
        const readMethod = isCalculated
          ? "sistema"
          : sourceChangedToManual
            ? "utente"
            : existingValue?.metodo_lettura || "pdf_text";
        const userEvidenceId =
          sourceChangedToManual && !isCalculated ? await ensureUserEvidenceForField(field, persistedValue) : null;

        if (!persistedValue) {
          await apiRequest(
            `/acquisition/rows/${rowId}/values`,
            {
              method: "PUT",
              body: JSON.stringify({
                blocco: "chimica",
                campo: field,
                valore_grezzo: null,
                valore_standardizzato: null,
                valore_finale: null,
                stato: "confermato",
                document_evidence_id: userEvidenceId,
                metodo_lettura: readMethod,
                fonte_documentale: sourceType,
                confidenza: null,
              }),
            },
            token,
          );
          continue;
        }

        await apiRequest(
          `/acquisition/rows/${rowId}/values`,
          {
            method: "PUT",
            body: JSON.stringify({
              blocco: "chimica",
              campo: field,
              valore_grezzo: existingValue?.valore_grezzo || persistedValue,
              valore_standardizzato: persistedValue,
              valore_finale: persistedValue,
              stato: "confermato",
              document_evidence_id: userEvidenceId,
              metodo_lettura: readMethod,
              fonte_documentale: sourceType,
              confidenza: existingValue?.confidenza || null,
            }),
          },
          token,
        );
      }

      const confirmedDraft = { ...effectiveDraft };
      setSessionInitialDraft(confirmedDraft);
      setDraft(confirmedDraft);
      setSessionSourceOverrides({});
      setCaptureField("");
      setTableCaptureActive(false);
      setTableCaptureProposal(null);
      if (draftOverlaySnapshot.length) {
        setOverlayPreviewItems((current) => {
          const preserved = (current || []).filter(
            (item) =>
              !draftOverlaySnapshot.some(
                (draftItem) =>
                  draftItem.field === item.field ||
                  (draftItem.field === "__table__" && Array.isArray(draftItem.fields) && draftItem.fields.includes(item.field)),
              ),
          );
          const promoted = draftOverlaySnapshot.flatMap((item) => {
            if (item.field !== "__table__") {
              return [item];
            }
            if (!Array.isArray(item.fields)) {
              return [];
            }
            return item.fields.map((field) => ({
              field,
              page_id: item.page_id,
              bbox: item.bbox,
            }));
          });
          return [...preserved, ...promoted];
        });
      }
      setDraftOverlayItems([]);
      setError("");
      onDirtyChange?.(false);

      await onRefreshRow();
      if (overlayWasActive && !draftOverlaySnapshot.length) {
        await fetchOverlayPreview();
      }
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm() {
    if (submitting || confirmDialogOpen) {
      return;
    }
    setConfirmDialogOpen(true);
  }

  async function handleConfirmAccepted() {
    setConfirmDialogOpen(false);
    const saved = await persistDraft();
    if (!saved) {
      setConfirmDialogOpen(true);
    }
  }

  function handleToggleCapture(field) {
    setTableCaptureActive(false);
    setTableCaptureProposal(null);
    setError("");
    setCaptureField((current) => (current === field ? "" : field));
  }

  function handleToggleTableCapture() {
    setCaptureField("");
    setTableCaptureProposal(null);
    setError("");
    setTableCaptureActive((current) => !current);
  }

  function applyTableCaptureProposal() {
    if (!tableCaptureProposal?.values) {
      return;
    }
    onDirtyChange?.(true);
    const nextDraft = {
      ...draft,
      ...tableCaptureProposal.values,
    };
    setDraft(nextDraft);
    setSessionSourceOverrides((current) => {
      const next = { ...current };
      Object.keys(tableCaptureProposal.values || {}).forEach((field) => {
        next[field] = "manuale";
      });
      return next;
    });
    if (Array.isArray(tableCaptureProposal?.items) && tableCaptureProposal.items.length) {
      setDraftOverlayItems((current) => {
        const next = current.filter(
          (item) => !Object.prototype.hasOwnProperty.call(tableCaptureProposal.values || {}, item.field),
        );
        return [...next, ...tableCaptureProposal.items];
      });
    } else if (tableCaptureProposal?.bbox && tableCaptureProposal?.page_id) {
      setDraftOverlayItems((current) => [
        ...current.filter((item) => item.field !== "__table__"),
        {
          field: "__table__",
          page_id: tableCaptureProposal.page_id,
          bbox: tableCaptureProposal.bbox,
          fields: Object.keys(tableCaptureProposal.values || {}),
        },
      ]);
    }
    setTableCaptureActive(false);
    setTableCaptureProposal(null);
    setError("");
  }

  const chemistryControls = (
    <div className="rounded-2xl border border-slate-300/80 bg-slate-100/95 p-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch xl:justify-between">
        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[230px]">
          <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
            <p className="text-[11px] font-semibold text-sky-700">Tabella</p>
            <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-slate-600">
              Cattura un rettangolo sopra la tabella chimica completa.
            </p>
            <p className="mt-1 text-[11px] leading-tight text-slate-500">
              Per almeno tre elementi.
            </p>
            <button
              className={`mt-2 w-full rounded-md border px-2 py-2 text-xs font-semibold transition ${
                tableCaptureActive
                  ? "border-sky-400 bg-sky-200 text-sky-800"
                  : "border-sky-200 bg-white text-sky-700 hover:bg-sky-100"
              }`}
              onClick={handleToggleTableCapture}
              type="button"
            >
              {tableCaptureActive ? "Cattura tabella attiva" : "Cattura tabella"}
            </button>
          </div>
        </div>
        <div className="min-w-0 flex-1 overflow-hidden rounded-2xl border border-slate-400 bg-slate-50">
          <div className="overflow-x-auto">
            <div className="grid auto-cols-[82px] grid-flow-col gap-0 border-b border-slate-200">
              {fieldList.map((field) => {
                const existingValue = valueMap.get(field);
                const currentValue = effectiveDraft[field] || "";

                return (
                  <div className="border-r border-slate-200 px-1.5 py-1" key={field}>
                    <p className="text-center text-[11px] font-semibold leading-none text-slate-600">{formatChemistryFieldLabel(field)}</p>
                    <input
                      className="mt-0.5 w-full rounded-md border border-slate-200 bg-white px-1 py-0.5 text-center text-[13px] text-slate-800 outline-none transition focus:border-accent"
                      onChange={(event) => updateField(field, event.target.value)}
                      placeholder="Valore"
                      value={currentValue}
                    />
                    <p className="mt-0.5 text-center text-[8px] font-semibold uppercase tracking-[0.03em] text-slate-400">Origine</p>
                    <p className="mt-0 min-h-[20px] text-center text-[10px] font-medium leading-tight text-slate-600">
                      {sourceLabel(existingValue, field, effectiveDraft, sessionSourceOverrides)}
                    </p>
                    <button
                      className={`mt-0.5 w-full rounded-md border px-1 py-0.5 text-[10px] font-semibold transition ${
                        captureField === field
                          ? "border-sky-300 bg-sky-100 text-sky-700"
                          : "border-slate-200 bg-slate-100 text-slate-600 hover:bg-sky-50 hover:text-sky-700"
                      }`}
                      onClick={() => handleToggleCapture(field)}
                      type="button"
                    >
                      {captureField === field ? "Cattura attiva" : "Cattura"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[230px] xl:self-start">
          <button
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={!hasUnsavedChanges || submitting}
            onClick={() => setResetDialogOpen(true)}
            type="button"
          >
            Valori iniziali
          </button>
          <button
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={submitting}
            onClick={handleConfirm}
            type="button"
          >
            {submitting ? "Conferma..." : "Conferma"}
          </button>
        </div>
      </div>
    </div>
  );

  const workspaceStatusBar = (
    <div className="min-h-[32px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5">
      <div className="flex min-h-[18px] flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4">
        <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-sky-700">
          <button
            className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-semibold transition ${
              overlayPreviewItems.length
                ? "border-sky-400 bg-sky-100 text-sky-800"
                : "border-sky-200 bg-white text-sky-700 hover:bg-sky-100"
            } disabled:cursor-wait disabled:opacity-60`}
            disabled={overlayBusy}
            onClick={() => void handleToggleOverlayPreview()}
            type="button"
          >
            {overlayBusy ? "..." : overlayPreviewItems.length ? "Overlay off" : "Overlay"}
          </button>
          {tableCaptureActive ? (
            <span>Cattura tabella attiva: seleziona un rettangolo sopra la tabella chimica.</span>
          ) : captureField ? (
            <span>Cattura attiva: {formatChemistryFieldLabel(captureField)}. Il click sul PDF compilerà questo campo nella bozza, senza confermare.</span>
          ) : (
            <span className="invisible">Cattura attiva: spazio riservato.</span>
          )}
        </div>
        <div className="min-w-0 text-sm text-rose-600 md:text-right">
          {error ? <span>{error}</span> : <span className="invisible">Nessun errore</span>}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <ChemistryPdfPanel
        captureField={captureField}
        certificateDocument={certificateDocument}
        draftOverlayItems={draftOverlayItems}
        footerContent={
          <div className="space-y-2" ref={workspaceRef}>
            {workspaceStatusBar}
            {chemistryControls}
          </div>
        }
      onCaptureError={handleWorkspaceError}
      onCaptureValue={handleCaptureValue}
      overlayPreviewItems={overlayPreviewItems}
      onTableCaptureProposal={handleTableCaptureProposal}
      tableCaptureActive={tableCaptureActive}
      token={token}
      />

      {tableCaptureProposal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-2xl rounded-2xl border border-sky-200 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-slate-900">
              Proposta tabella{" "}
              <span className="text-sky-700">
                {tableCaptureProposal.orientation === "horizontal"
                  ? "orizzontale"
                  : tableCaptureProposal.orientation === "vertical"
                    ? "verticale"
                    : "incerta"}
              </span>
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Ho raccolto questi valori dalla tabella chimica. Puoi applicarli alla bozza oppure scartare la proposta.
            </p>
            <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">Campi trovati</p>
              <p className="mt-2 text-sm leading-6 text-sky-800">
                {Object.entries(tableCaptureProposal.values)
                  .map(([field, value]) => `${field} ${value}`)
                  .join(" · ")}
              </p>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                className="rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-semibold text-sky-700 hover:bg-sky-100"
                onClick={() => setTableCaptureProposal(null)}
                type="button"
              >
                Scarta proposta
              </button>
              <button
                className="rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800"
                onClick={applyTableCaptureProposal}
                type="button"
              >
                Applica proposta
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirmDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-slate-900">Stai confermando la Chimica</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Stai confermando questa pagina. I valori correnti verranno salvati e i valori iniziali di questa sessione andranno persi.
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => setConfirmDialogOpen(false)}
                type="button"
              >
                Continua a modificare
              </button>
              <button
                className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                disabled={submitting}
                onClick={handleConfirmAccepted}
                type="button"
              >
                {submitting ? "Conferma..." : "Conferma"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {resetDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-slate-900">Tornerai ai valori iniziali</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Se continui perderai le modifiche non confermate di questa sessione e la Chimica tornerà ai valori persistiti presenti quando sei entrato nella pagina.
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => setResetDialogOpen(false)}
                type="button"
              >
                Continua a modificare
              </button>
              <button
                className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-700 hover:bg-amber-100"
                onClick={() => {
                  setResetDialogOpen(false);
                  resetToInitialValues();
                }}
                type="button"
              >
                Valori iniziali
              </button>
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}
