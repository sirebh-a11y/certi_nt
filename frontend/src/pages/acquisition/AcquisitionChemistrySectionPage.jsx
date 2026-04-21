import { useEffect, useMemo, useState } from "react";
import { useBeforeUnload } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";

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
  const calculatedValue = calculatedValueForField(field, draft);
  if (calculatedValue && normalizeDisplayValue(draft[field]) === normalizeDisplayValue(calculatedValue)) {
    return "calcolato";
  }
  if (sessionSourceOverrides[field] === "manuale") {
    return "manuale";
  }
  if (!value) {
    return "certificato - AI";
  }
  if (value.metodo_lettura === "utente") {
    return "manuale";
  }
  if (value.metodo_lettura === "calcolato" || value.fonte_documentale === "calcolato") {
    return "calcolato";
  }
  if ((value.fonte_documentale || "certificato") === "certificato" || !chemistryDisplayValue(value)) {
    return "certificato - AI";
  }
  return value.fonte_documentale || "manuale";
}

function ChemistryPdfPanel({
  captureField,
  certificateDocument,
  onCaptureError,
  onCaptureValue,
  onTableCaptureProposal,
  tableCaptureActive,
  token,
}) {
  const [pageImages, setPageImages] = useState([]);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
  const [captureBusyPageId, setCaptureBusyPageId] = useState(null);
  const [selection, setSelection] = useState(null);

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

      onCaptureValue(captureField, capture.value);
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

  return (
    <div className="rounded-2xl border border-border bg-white p-4">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Certificato</p>
          <p className="mt-1 text-sm text-slate-600">
            {certificateDocument?.nome_file_originale || "Nessun certificato collegato"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => setZoom((current) => Math.max(50, current - 10))}
            type="button"
          >
            -
          </button>
          <span className="min-w-[64px] text-center text-sm font-semibold text-slate-700">{zoom}%</span>
          <button
            className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => setZoom((current) => Math.min(250, current + 10))}
            type="button"
          >
            +
          </button>
        </div>
      </div>

      <div className="h-[43vh] overflow-auto rounded-2xl border border-border bg-slate-50 p-3">
        {pageImages.length ? (
          <div className="space-y-4">
            {pageImages.map((page) => (
              <div className="relative mx-auto w-fit" key={page.id}>
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Pagina {page.numero_pagina}
                </p>
                <img
                  alt={`Certificato pagina ${page.numero_pagina}`}
                  className="block rounded-xl border border-slate-200 bg-white shadow-sm"
                  draggable={false}
                  src={page.src}
                  style={{ width: `${zoom}%`, minWidth: "100%", userSelect: "none" }}
                />
                <div
                  className={`${captureField || tableCaptureActive ? "cursor-crosshair" : "cursor-default"} absolute inset-0`}
                  onClick={(event) => handlePageClick(page, event)}
                  onMouseDown={(event) => handleSelectionStart(page, event)}
                  onMouseMove={(event) => handleSelectionMove(page, event)}
                  onMouseUp={() => void handleSelectionEnd(page)}
                />
                {selection && selection.pageId === page.id && selectionStyle ? (
                  <div
                    className="pointer-events-none absolute rounded-lg border-2 border-sky-400 bg-sky-200/20"
                    style={selectionStyle}
                  />
                ) : null}
                {captureBusyPageId === page.id ? (
                  <p className="mt-2 text-center text-xs font-medium text-sky-700">Cattura in corso...</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-500">
            {error || "Immagini pagina non disponibili."}
          </div>
        )}
      </div>
      {captureField ? (
        <div className="sr-only">Modalità cattura attiva su {formatChemistryFieldLabel(captureField)}</div>
      ) : null}
    </div>
  );
}

export default function AcquisitionChemistrySectionPage({ certificateDocument, row, rowId, token, onRefreshRow }) {
  const chemistryValues = useMemo(() => (row?.values || []).filter((value) => value.blocco === "chimica"), [row]);
  const fieldList = useMemo(() => buildFieldList(chemistryValues), [chemistryValues]);
  const persistedInitialDraft = useMemo(() => buildInitialDraft(chemistryValues), [chemistryValues]);
  const valueMap = useMemo(() => new Map(chemistryValues.map((value) => [value.campo, value])), [chemistryValues]);
  const [sessionInitialDraft, setSessionInitialDraft] = useState(() => ({ ...persistedInitialDraft }));
  const [draft, setDraft] = useState(() => ({ ...persistedInitialDraft }));
  const [sessionSourceOverrides, setSessionSourceOverrides] = useState(() => ({}));
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [captureField, setCaptureField] = useState("");
  const [tableCaptureActive, setTableCaptureActive] = useState(false);
  const [tableCaptureProposal, setTableCaptureProposal] = useState(null);

  useEffect(() => {
    const nextInitial = { ...persistedInitialDraft };
    setSessionInitialDraft(nextInitial);
    setDraft(nextInitial);
    setSessionSourceOverrides({});
  }, [persistedInitialDraft]);

  const effectiveDraft = useMemo(() => buildEffectiveDraft(sessionInitialDraft, draft), [sessionInitialDraft, draft]);
  const hasUnsavedChanges = useMemo(
    () => !draftsEqual(sessionInitialDraft, effectiveDraft, fieldList),
    [effectiveDraft, fieldList, sessionInitialDraft],
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

  function updateField(field, value, options = {}) {
    const { markTouched = true } = options;
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
  }

  function handleCaptureValue(field, value) {
    updateField(field, value, { markTouched: true });
    setCaptureField("");
    setError("");
  }

  function handleTableCaptureProposal(proposal) {
    setTableCaptureProposal(proposal);
    setError("");
  }

  async function persistDraft() {
    const changedFields = fieldList.filter(
      (field) => normalizeDisplayValue(sessionInitialDraft[field]) !== normalizeDisplayValue(effectiveDraft[field]),
    );

    if (!changedFields.length) {
      return true;
    }

    setSubmitting(true);
    setError("");
    try {
      for (const field of changedFields) {
        const existingValue = valueMap.get(field);
        const nextValue = normalizeDisplayValue(effectiveDraft[field]);
        const persistedValue = formatChemistryDisplayValue(nextValue);
        const calculatedValue = calculatedValueForField(field, effectiveDraft);
        const isCalculated = Boolean(calculatedValue) && persistedValue === formatChemistryDisplayValue(calculatedValue);
        const sourceType = isCalculated ? "calcolato" : "utente";
        const readMethod = isCalculated ? "calcolato" : "utente";

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
                document_evidence_id: existingValue?.document_evidence_id || null,
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
              document_evidence_id: existingValue?.document_evidence_id || null,
              metodo_lettura: readMethod,
              fonte_documentale: sourceType,
              confidenza: existingValue?.confidenza || null,
            }),
          },
          token,
        );
      }

      await onRefreshRow();
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm() {
    await persistDraft();
  }

  function handleDiscard() {
    resetToInitialValues();
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
    setTableCaptureActive(false);
    setTableCaptureProposal(null);
    setError("");
  }

  return (
    <div className="space-y-4">
      <ChemistryPdfPanel
        captureField={captureField}
        certificateDocument={certificateDocument}
        onCaptureError={setError}
        onCaptureValue={handleCaptureValue}
        onTableCaptureProposal={handleTableCaptureProposal}
        tableCaptureActive={tableCaptureActive}
        token={token}
      />

      <div className="rounded-2xl border border-border bg-white p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch xl:justify-between">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch">
            <div className="flex min-h-[72px] min-w-[178px] flex-col justify-center rounded-xl border border-sky-200 bg-sky-50 px-3 py-2">
              <p className="text-[11px] font-semibold text-sky-700">Tabella</p>
              <p className="mt-1.5 min-h-[28px] text-[11px] leading-tight text-sky-700">
                Cattura un rettangolo sopra la tabella chimica completa.
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
            <div className="flex min-h-[72px] flex-col justify-center rounded-xl border border-slate-200 bg-white px-3 py-2">
              <h3 className="text-base font-semibold text-slate-900">Workspace Chimica</h3>
              <p className="mt-1 text-sm text-slate-500">
                Modifichi tutta la pagina in bozza e confermi solo alla fine. I valori iniziali sono quelli persistiti quando entri.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 xl:self-center">
            <button
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={!hasUnsavedChanges || submitting}
              onClick={resetToInitialValues}
              type="button"
            >
              Valori iniziali
            </button>
            <button
              className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60"
              disabled={!hasUnsavedChanges || submitting}
              onClick={handleDiscard}
              type="button"
            >
              Non salvare
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
        <div className="mt-3 min-h-[44px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="flex min-h-[28px] flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4">
            <div className="min-w-0 text-sm font-medium text-sky-700">
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
        {tableCaptureProposal ? (
          <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-sky-800">
                  Proposta tabella:{" "}
                  {tableCaptureProposal.orientation === "horizontal"
                    ? "orizzontale"
                    : tableCaptureProposal.orientation === "vertical"
                      ? "verticale"
                      : "incerta"}
                </p>
                <p className="mt-1 text-xs text-sky-700">
                  Campi trovati:{" "}
                  {Object.entries(tableCaptureProposal.values)
                    .map(([field, value]) => `${field} ${value}`)
                    .join(" · ")}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  className="rounded-xl border border-sky-200 bg-white px-3 py-2 text-sm font-semibold text-sky-700 hover:bg-sky-100"
                  onClick={() => setTableCaptureProposal(null)}
                  type="button"
                >
                  Scarta proposta
                </button>
                <button
                  className="rounded-xl bg-sky-700 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-800"
                  onClick={applyTableCaptureProposal}
                  type="button"
                >
                  Applica proposta
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-border bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Elementi chimici</p>
            <p className="mt-1 text-sm text-slate-500">Griglia compatta. I campi derivati vengono completati solo se mancanti e se i campi base ci sono.</p>
          </div>
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${hasUnsavedChanges ? "border-amber-200 bg-amber-50 text-amber-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
            {hasUnsavedChanges ? "Modifiche non confermate" : "Allineato ai valori persistiti"}
          </span>
        </div>

        <div className="overflow-hidden rounded-2xl border border-border">
          <div className="overflow-x-auto">
            <div className="grid auto-cols-[112px] grid-flow-col gap-2 p-2">
              {fieldList.map((field) => {
                const existingValue = valueMap.get(field);
                const currentValue = effectiveDraft[field] || "";

                return (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-2" key={field}>
                    <p className="text-[11px] font-semibold text-slate-600">{formatChemistryFieldLabel(field)}</p>
                    <input
                      className="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none transition focus:border-accent"
                      onChange={(event) => updateField(field, event.target.value)}
                      placeholder="Valore"
                      value={currentValue}
                    />
                    <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Origine</p>
                    <p className="mt-0.5 text-[11px] font-medium leading-tight text-slate-600">
                      {sourceLabel(existingValue, field, effectiveDraft, sessionSourceOverrides)}
                    </p>
                    <button
                      className={`mt-2 w-full rounded-md border px-2 py-1 text-[11px] font-semibold transition ${
                        captureField === field
                          ? "border-sky-300 bg-sky-100 text-sky-700"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
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
      </div>
    </div>
  );
}
