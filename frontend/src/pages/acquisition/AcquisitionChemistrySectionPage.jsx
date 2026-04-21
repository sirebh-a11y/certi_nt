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

const BASE_CHEMISTRY_FIELDS = CHEMISTRY_FIELD_ORDER.filter((field) => !Object.prototype.hasOwnProperty.call(DERIVED_FIELDS, field));

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

function sourceLabel(value, field, draft) {
  const calculatedValue = calculatedValueForField(field, draft);
  if (calculatedValue && normalizeDisplayValue(draft[field]) === normalizeDisplayValue(calculatedValue)) {
    return "calcolato";
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

function ChemistryPdfPanel({ certificateDocument, token }) {
  const [pdfUrl, setPdfUrl] = useState("");
  const [zoom, setZoom] = useState(125);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    let objectUrl = "";

    async function loadPdf() {
      if (!certificateDocument?.file_url) {
        setPdfUrl("");
        return;
      }
      try {
        const blob = await fetchApiBlob(certificateDocument.file_url, token);
        objectUrl = URL.createObjectURL(blob);
        if (!ignore) {
          setPdfUrl(objectUrl);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError.message);
        }
      }
    }

    loadPdf();

    return () => {
      ignore = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [certificateDocument, token]);

  const pdfSrc = pdfUrl ? `${pdfUrl}#view=FitH&zoom=${zoom}` : "";

  return (
    <div className="rounded-2xl border border-border bg-white p-4">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Certificato PDF</p>
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

      <div className="h-[50vh] overflow-hidden rounded-2xl border border-border bg-slate-50">
        {pdfSrc ? (
          <iframe className="h-full w-full" src={pdfSrc} title="Certificato PDF chimica" />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-500">
            {error || "PDF non disponibile."}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AcquisitionChemistrySectionPage({ certificateDocument, row, rowId, token, onRefreshRow }) {
  const chemistryValues = useMemo(() => (row?.values || []).filter((value) => value.blocco === "chimica"), [row]);
  const fieldList = useMemo(() => buildFieldList(chemistryValues), [chemistryValues]);
  const initialDraft = useMemo(() => buildInitialDraft(chemistryValues), [chemistryValues]);
  const valueMap = useMemo(() => new Map(chemistryValues.map((value) => [value.campo, value])), [chemistryValues]);
  const [draft, setDraft] = useState(initialDraft);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [captureField, setCaptureField] = useState("");

  useEffect(() => {
    setDraft(initialDraft);
  }, [initialDraft]);

  const effectiveDraft = useMemo(() => buildEffectiveDraft(initialDraft, draft), [initialDraft, draft]);
  const hasUnsavedChanges = useMemo(() => !draftsEqual(initialDraft, effectiveDraft, fieldList), [effectiveDraft, fieldList, initialDraft]);

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

  function updateField(field, value) {
    setDraft((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function resetToInitialValues() {
    setDraft(initialDraft);
    setError("");
    setCaptureField("");
  }

  async function persistDraft() {
    const changedFields = fieldList.filter(
      (field) => normalizeDisplayValue(initialDraft[field]) !== normalizeDisplayValue(effectiveDraft[field]),
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
    setCaptureField((current) => (current === field ? "" : field));
  }

  return (
    <div className="space-y-4">
      <ChemistryPdfPanel certificateDocument={certificateDocument} token={token} />

      <div className="rounded-2xl border border-border bg-white p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Workspace Chimica</h3>
            <p className="mt-1 text-sm text-slate-500">
              Modifichi tutta la pagina in bozza e confermi solo alla fine. I valori iniziali sono quelli persistiti quando entri.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
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
        {captureField ? (
          <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700">
            Cattura attiva: {formatChemistryFieldLabel(captureField)}. Il click sul PDF compilerà questo campo nella bozza, senza confermare.
          </div>
        ) : null}
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
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
                    <p className="mt-0.5 text-[11px] font-medium leading-tight text-slate-600">{sourceLabel(existingValue, field, effectiveDraft)}</p>
                    {BASE_CHEMISTRY_FIELDS.includes(field) ? (
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
                    ) : null}
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
