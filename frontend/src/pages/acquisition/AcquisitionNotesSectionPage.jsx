import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload, useNavigate } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { documentTone } from "./documentTone";
import { focusFirstOverlayItemInViewport } from "./overlayScroll";

const SYSTEM_NOTE_ORDER = [
  "us_control_class_a",
  "us_control_class_b",
  "rohs",
  "radioactive_free",
];

const SYSTEM_NOTE_LABELS = {
  us_control_class_a: "Class A",
  us_control_class_b: "Class B",
  rohs: "RoHS",
  radioactive_free: "Material free from radioactive contamination",
};

const CHECKBOX_CLASSNAME =
  "mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20";

function renderOverlayBox({ item, imageHeight, imageWidth, key, title }) {
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
  return (
    <div
      className="pointer-events-none absolute rounded border border-sky-500 bg-sky-400/20 shadow-[0_0_0_1px_rgba(14,165,233,0.2)]"
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

function NotePdfPanel({ certificateDocument, footerContent, overlayPreviewItems, token }) {
  const tone = documentTone("certificato");
  const [pageImages, setPageImages] = useState([]);
  const [pageImageSizes, setPageImageSizes] = useState({});
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
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
    <div className={`rounded-2xl border p-4 ${tone.panel}`}>
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Certificato</p>
          <p className="mt-1 text-sm text-slate-900">
            {certificateDocument?.nome_file_originale || "Nessun certificato collegato"}
          </p>
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

      <div className={`h-[43vh] overflow-auto rounded-2xl border p-3 ${tone.viewport}`} ref={viewportRef}>
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
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
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
                  {(previewItemsByPage.get(page.id) || []).map((item, index) =>
                    renderOverlayBox({
                      item,
                      imageWidth: Number(item.image_width || pageImageSizes[page.id]?.width || 0),
                      imageHeight: Number(item.image_height || pageImageSizes[page.id]?.height || 0),
                      title: `${item.field} evidenza`,
                      key: `${page.id}-${item.field}-${index}`,
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

function buildInitialDraft(row) {
  const values = row?.values || [];
  const byField = Object.fromEntries(values.filter((value) => value.blocco === "note").map((value) => [value.campo, value]));
  const legacyUsClass = (byField.nota_us_control_classe?.valore_finale || byField.nota_us_control_classe?.valore_standardizzato || "").trim().toUpperCase();
  const usClassARaw =
    (byField.nota_us_control_class_a?.valore_finale || byField.nota_us_control_class_a?.valore_standardizzato || "").trim().toLowerCase();
  const usClassBRaw =
    (byField.nota_us_control_class_b?.valore_finale || byField.nota_us_control_class_b?.valore_standardizzato || "").trim().toLowerCase();
  const hasNewUsFields = Boolean(byField.nota_us_control_class_a || byField.nota_us_control_class_b);
  const rohsRaw = (byField.nota_rohs?.valore_finale || byField.nota_rohs?.valore_standardizzato || "").trim().toLowerCase();
  const radioactiveRaw =
    (byField.nota_radioactive_free?.valore_finale || byField.nota_radioactive_free?.valore_standardizzato || "").trim().toLowerCase();
  const customIds = (row?.custom_note_templates || []).map((item) => item.id).sort((left, right) => left - right);

  return {
    usClassA: hasNewUsFields ? usClassARaw === "true" : legacyUsClass === "A",
    usClassB: hasNewUsFields ? usClassBRaw === "true" : legacyUsClass === "B",
    rohs: rohsRaw === "true",
    radioactiveFree: radioactiveRaw === "true",
    customIds,
  };
}

function draftsEqual(left, right) {
  return (
    left.usClassA === right.usClassA &&
    left.usClassB === right.usClassB &&
    left.rohs === right.rohs &&
    left.radioactiveFree === right.radioactiveFree &&
    JSON.stringify([...left.customIds].sort((a, b) => a - b)) === JSON.stringify([...right.customIds].sort((a, b) => a - b))
  );
}

export default function AcquisitionNotesSectionPage({ certificateDocument, row, rowId, token, onRefreshRow, onDirtyChange }) {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState([]);
  const [sessionInitialDraft, setSessionInitialDraft] = useState(() => buildInitialDraft(row));
  const [draft, setDraft] = useState(() => buildInitialDraft(row));
  const [selectedCustomId, setSelectedCustomId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [overlayPreviewItems, setOverlayPreviewItems] = useState([]);
  const [overlayBusy, setOverlayBusy] = useState(false);
  const workspaceRef = useRef(null);

  useEffect(() => {
    let ignore = false;
    apiRequest("/notes", {}, token)
      .then((data) => {
        if (!ignore) {
          setCatalog(data.items || []);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
        }
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  useEffect(() => {
    const nextInitial = buildInitialDraft(row);
    setSessionInitialDraft(nextInitial);
    setDraft(nextInitial);
    setSelectedCustomId("");
    setOverlayPreviewItems([]);
    onDirtyChange?.(false);
  }, [row]);

  const hasUnsavedChanges = useMemo(() => !draftsEqual(sessionInitialDraft, draft), [draft, sessionInitialDraft]);

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

  const systemNotesByCode = useMemo(() => Object.fromEntries(catalog.filter((item) => item.is_system).map((item) => [item.code, item])), [catalog]);
  const customNoteOptions = useMemo(
    () =>
      catalog
        .filter((item) => !item.is_system && item.is_active && !draft.customIds.includes(item.id))
        .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id),
    [catalog, draft.customIds],
  );
  const selectedCustomNotes = useMemo(
    () =>
      catalog
        .filter((item) => !item.is_system && draft.customIds.includes(item.id))
        .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id),
    [catalog, draft.customIds],
  );

  function handleWorkspaceError(message) {
    setError(message);
    requestAnimationFrame(() => {
      workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function handleToggleOverlayPreview() {
    if (overlayBusy) {
      return;
    }
    if (overlayPreviewItems.length) {
      setOverlayPreviewItems([]);
      return;
    }
    setOverlayBusy(true);
    try {
      const response = await apiRequest(`/acquisition/rows/${rowId}/notes-overlay-preview`, {}, token);
      setOverlayPreviewItems(Array.isArray(response?.items) ? response.items : []);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
      setOverlayPreviewItems([]);
    } finally {
      setOverlayBusy(false);
    }
  }

  function setBooleanField(field, value) {
    setDraft((current) => ({
      ...current,
      [field]: value,
    }));
    setError("");
  }

  function addCustomNote() {
    const noteId = Number.parseInt(selectedCustomId, 10);
    if (!Number.isInteger(noteId)) {
      return;
    }
    setDraft((current) => ({
      ...current,
      customIds: [...current.customIds, noteId].sort((left, right) => left - right),
    }));
    setSelectedCustomId("");
    setError("");
  }

  function removeCustomNote(noteId) {
    setDraft((current) => ({
      ...current,
      customIds: current.customIds.filter((item) => item !== noteId),
    }));
    setError("");
  }

  function resetToInitialValues() {
    setDraft(sessionInitialDraft);
    setSelectedCustomId("");
    setError("");
    onDirtyChange?.(false);
  }

  async function persistDraft() {
    setSubmitting(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/notes-section`,
        {
          method: "PUT",
          body: JSON.stringify({
            nota_us_control_class_a: draft.usClassA,
            nota_us_control_class_b: draft.usClassB,
            nota_rohs: draft.rohs,
            nota_radioactive_free: draft.radioactiveFree,
            custom_note_template_ids: draft.customIds,
          }),
        },
        token,
      );

      const confirmedDraft = {
        ...draft,
        customIds: [...draft.customIds].sort((left, right) => left - right),
      };
      setSessionInitialDraft(confirmedDraft);
      setDraft(confirmedDraft);
      setSelectedCustomId("");
      setError("");
      onDirtyChange?.(false);
      await onRefreshRow();
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmAccepted() {
    setConfirmDialogOpen(false);
    const saved = await persistDraft();
    if (!saved) {
      setConfirmDialogOpen(true);
      return;
    }
    onDirtyChange?.(false);
    navigate("/acquisition");
  }

  const workspaceStatusBar = (
    <div className="min-h-[32px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5">
      <div className="flex min-h-[18px] flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4">
        <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-sky-700">
          <button
            className={`shrink-0 rounded-lg border px-3 py-1 text-xs font-semibold transition ${
              overlayPreviewItems.length
                ? "border-sky-400 bg-sky-100 text-sky-700"
                : "border-sky-200 bg-white text-sky-700 hover:bg-sky-100"
            }`}
            disabled={overlayBusy}
            onClick={() => void handleToggleOverlayPreview()}
            type="button"
          >
            {overlayBusy ? "..." : overlayPreviewItems.length ? "Overlay off" : "Overlay"}
          </button>
          <span>Le spunte aggiornano solo la bozza locale. La sezione Note diventa definitiva con Conferma.</span>
        </div>
        <div className="min-w-0 text-sm text-rose-600 md:text-right">
          {error ? <span>{error}</span> : <span className="invisible">Nessun errore</span>}
        </div>
      </div>
    </div>
  );

  const notesControls = (
    <div className="rounded-2xl border border-slate-300/80 bg-slate-100/95 p-3 sm:p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1 overflow-hidden rounded-2xl border border-slate-300 bg-white p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-1 border-b border-slate-200 pb-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Note</p>
            <p className="text-sm text-slate-600">
              Conferma le note di sistema e aggiungi eventuali note custom senza modificare il flusso AI.
            </p>
          </div>

          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-800">U.S. control</p>
                <p className="mt-1 text-xs text-slate-500">Spunta le classi trovate nel certificato. Se sono presenti entrambe, lascia entrambe selezionate.</p>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {["us_control_class_a", "us_control_class_b"].map((code) => {
                  const template = systemNotesByCode[code];
                  const field = code.endsWith("_a") ? "usClassA" : "usClassB";
                  const checked = draft[field];
                  return (
                    <label
                      className={`flex gap-3 rounded-xl border px-4 py-3 transition ${
                        checked
                          ? "border-accent/30 bg-accent/5 shadow-sm"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                      key={code}
                    >
                      <input
                        checked={checked}
                        className={CHECKBOX_CLASSNAME}
                        onChange={(event) => setBooleanField(field, event.target.checked)}
                        type="checkbox"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-800">{SYSTEM_NOTE_LABELS[code]}</p>
                        <p className="mt-1 text-sm leading-6 text-slate-600">{template?.text || "-"}</p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-3">
              {["rohs", "radioactive_free"].map((code) => {
                const template = systemNotesByCode[code];
                const field = code === "rohs" ? "rohs" : "radioactiveFree";
                return (
                  <label
                    className={`flex gap-3 rounded-xl border px-4 py-3 transition ${
                      draft[field]
                        ? "border-accent/30 bg-accent/5 shadow-sm"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                    key={code}
                  >
                    <input
                      checked={draft[field]}
                      className={CHECKBOX_CLASSNAME}
                      onChange={(event) => setBooleanField(field, event.target.checked)}
                      type="checkbox"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-800">{SYSTEM_NOTE_LABELS[code]}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{template?.text || "-"}</p>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-800">Note aggiuntive</p>
                <p className="mt-1 text-xs text-slate-500">Aggiungi altre note dal catalogo disponibile.</p>
              </div>
              <div className="flex flex-col gap-3 md:flex-row">
                <select
                  className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-ink"
                  onChange={(event) => setSelectedCustomId(event.target.value)}
                  value={selectedCustomId}
                >
                  <option value="">Seleziona una nota custom</option>
                  {customNoteOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.text}
                    </option>
                  ))}
                </select>
                <button
                  className="rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-60"
                  disabled={!selectedCustomId}
                  onClick={addCustomNote}
                  type="button"
                >
                  Aggiungi
                </button>
              </div>

              <div className="mt-4 space-y-2">
                {selectedCustomNotes.length ? (
                  selectedCustomNotes.map((item) => (
                    <div
                      className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-start sm:justify-between"
                      key={item.id}
                    >
                      <label className="flex items-start gap-3">
                        <input checked className={CHECKBOX_CLASSNAME} readOnly type="checkbox" />
                        <span className="text-sm leading-6 text-slate-700">{item.text}</span>
                      </label>
                      <button
                        className="self-start rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                        onClick={() => removeCustomNote(item.id)}
                        type="button"
                      >
                        Rimuovi
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Nessuna nota aggiuntiva selezionata.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[220px] xl:self-start">
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
            onClick={() => setConfirmDialogOpen(true)}
            type="button"
          >
            {submitting ? "Conferma..." : "Conferma"}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <NotePdfPanel
        certificateDocument={certificateDocument}
        footerContent={
          <div className="space-y-2" ref={workspaceRef}>
            {workspaceStatusBar}
            {notesControls}
          </div>
        }
        overlayPreviewItems={overlayPreviewItems}
        token={token}
      />

      {confirmDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-slate-900">Stai confermando le Note</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Stai confermando questa pagina. Le spunte correnti verranno salvate e i valori iniziali di questa sessione andranno persi.
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
              Se continui perderai le modifiche non confermate di questa sessione e la pagina Note tornerà ai valori persistiti presenti quando sei entrato.
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
