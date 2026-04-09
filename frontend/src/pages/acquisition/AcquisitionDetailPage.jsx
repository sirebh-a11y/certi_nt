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

const DDT_CORE_FIELDS = [
  "numero_certificato_ddt",
  "cdq",
  "colata",
  "diametro",
  "peso",
  "ordine",
];

const NOTE_CORE_FIELDS = [
  "nota_us_control_classe",
  "nota_rohs",
  "nota_radioactive_free",
  "nota_libera_utente",
];

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

const PROPERTY_FIELD_ORDER = [
  "HB",
  "Rp0.2",
  "Rm",
  "A%",
  "Rp0.2 / Rm",
  "IACS%",
];

const BLOCK_DEFAULT_SOURCE = {
  ddt: "ddt",
  match: "ddt_certificato",
  chimica: "certificato",
  proprieta: "certificato",
  note: "certificato",
};

const FINAL_REQUIRED_BLOCKS = ["ddt", "match", "chimica", "proprieta", "note"];
const ORDERED_BLOCKS = ["ddt", "match", "chimica", "proprieta", "note"];

function stateClasses(state) {
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function readValueStateClasses(value) {
  if (value?.stato === "confermato") {
    return stateClasses("verde");
  }
  if (value?.stato === "corretto") {
    return stateClasses("giallo");
  }
  if (value?.__missing) {
    return stateClasses("rosso");
  }
  return stateClasses("giallo");
}

function valueDisplay(value) {
  return value?.valore_finale || value?.valore_standardizzato || value?.valore_grezzo || "";
}

function fieldKey(block, field) {
  return `${block}:${field}`;
}

function workflowStepState(row, step) {
  if (step === "validazione_finale") {
    if (row?.validata_finale) {
      return "verde";
    }
    return FINAL_REQUIRED_BLOCKS.every((block) => row?.block_states?.[block] === "verde") ? "giallo" : "rosso";
  }
  return row?.block_states?.[step] || "rosso";
}

function workflowStepLabel(step) {
  if (step === "validazione_finale") {
    return "Validazione finale";
  }
  return BLOCK_LABELS[step] || step;
}

function workflowStepAction(row, step) {
  const state = workflowStepState(row, step);
  if (step === "validazione_finale") {
    if (row?.validata_finale) {
      return "Validata";
    }
    return state === "giallo" ? "Pronta da validare" : "Non pronta";
  }
  if (state === "verde") {
    return "Pronto";
  }
  if (state === "giallo") {
    return "Da verificare";
  }
  return "Non pronto";
}

function readValueStateLabel(value) {
  if (value?.__missing) {
    return "non pronto";
  }
  if (value?.stato === "confermato") {
    return "pronto";
  }
  return "da verificare";
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
  const [processingNotes, setProcessingNotes] = useState(false);
  const [processingChemistry, setProcessingChemistry] = useState(false);
  const [processingProperties, setProcessingProperties] = useState(false);
  const [processingMatch, setProcessingMatch] = useState(false);
  const [processingFinalValidation, setProcessingFinalValidation] = useState(false);
  const [openingAsset, setOpeningAsset] = useState("");
  const [draftValues, setDraftValues] = useState({});
  const [savingFieldKey, setSavingFieldKey] = useState("");
  const [availableCertificates, setAvailableCertificates] = useState([]);
  const [matchDraft, setMatchDraft] = useState({ documentId: "", motivo: "" });

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

        const certificatesData = await apiRequest("/acquisition/documents?tipo_documento=certificato", {}, token);
        if (!ignore) {
          setAvailableCertificates(certificatesData.items || []);
          setMatchDraft({
            documentId: String(rowData.certificate_match?.document_certificato_id || rowData.certificate_document?.id || ""),
            motivo: rowData.certificate_match?.motivo_breve || "",
          });
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

  const canValidateFinal = useMemo(() => {
    if (!row?.block_states) {
      return false;
    }
    return FINAL_REQUIRED_BLOCKS.every((block) => row.block_states?.[block] === "verde");
  }, [row]);

  async function refreshRow(includeDocuments = false) {
    const rowData = await apiRequest(`/acquisition/rows/${rowId}`, {}, token);
    setRow(rowData);
    setMatchDraft({
      documentId: String(rowData.certificate_match?.document_certificato_id || rowData.certificate_document?.id || ""),
      motivo: rowData.certificate_match?.motivo_breve || "",
    });

    if (includeDocuments) {
      const requests = [apiRequest(`/acquisition/documents/${rowData.ddt_document.id}`, {}, token)];
      if (rowData.certificate_document?.id) {
        requests.push(apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token));
      }
      const [ddtData, certificateData] = await Promise.all(requests);
      setDdtDocument(ddtData);
      setCertificateDocument(certificateData || null);
    }
  }

  async function handleUpsertMatch(targetState) {
    const selectedDocumentId = Number(matchDraft.documentId);
    if (!selectedDocumentId) {
      setError("Seleziona un certificato per il match.");
      return;
    }

    setProcessingMatch(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/match`,
        {
          method: "PUT",
          body: JSON.stringify({
            document_certificato_id: selectedDocumentId,
            stato: targetState,
            motivo_breve: matchDraft.motivo || null,
            fonte_proposta: "utente",
            candidates: [],
          }),
        },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingMatch(false);
    }
  }

  function updateDraft(block, field, nextValue) {
    const key = fieldKey(block, field);
    setDraftValues((current) => ({
      ...current,
      [key]: nextValue,
    }));
  }

  function getDraft(block, field, fallbackValue = "") {
    const key = fieldKey(block, field);
    if (Object.prototype.hasOwnProperty.call(draftValues, key)) {
      return draftValues[key];
    }
    return fallbackValue;
  }

  async function handleProcessMinimal() {
    setProcessing(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/process-minimal`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
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
      await apiRequest(
        `/acquisition/rows/${rowId}/extract-ddt-vision`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingVision(false);
    }
  }

  async function handleDetectNotes() {
    setProcessingNotes(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/detect-notes`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingNotes(false);
    }
  }

  async function handleDetectChemistry() {
    setProcessingChemistry(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/detect-chemistry`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingChemistry(false);
    }
  }

  async function handleDetectProperties() {
    setProcessingProperties(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/detect-properties`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingProperties(false);
    }
  }

  async function handleSaveValue(block, field, value) {
    const key = fieldKey(block, field);
    const currentDisplay = valueDisplay(value);
    const nextValue = (getDraft(block, field, currentDisplay) || "").trim();

    if (!nextValue) {
      setError(`Inserisci un valore per ${field}.`);
      return;
    }

    setSavingFieldKey(key);
    setError("");
    try {
      const payload = value
        ? {
            blocco: block,
            campo: field,
            valore_grezzo: value.valore_grezzo || currentDisplay || nextValue,
            valore_standardizzato: nextValue,
            valore_finale: nextValue,
            stato: "corretto",
            document_evidence_id: value.document_evidence_id,
            metodo_lettura: "utente",
            fonte_documentale: value.fonte_documentale || BLOCK_DEFAULT_SOURCE[block] || "utente",
            confidenza: value.confidenza,
          }
        : {
            blocco: block,
            campo: field,
            valore_grezzo: nextValue,
            valore_standardizzato: nextValue,
            valore_finale: nextValue,
            stato: "corretto",
            document_evidence_id: null,
            metodo_lettura: "utente",
            fonte_documentale: BLOCK_DEFAULT_SOURCE[block] || "utente",
            confidenza: null,
          };

      await apiRequest(
        `/acquisition/rows/${rowId}/values`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
        token,
      );
      setDraftValues((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await refreshRow(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingFieldKey("");
    }
  }

  async function handleCreateManualValue(block, field, nextValue) {
    const key = fieldKey(block, field);
    const cleanedValue = (nextValue || "").trim();
    if (!cleanedValue) {
      setError(`Inserisci un valore per ${field}.`);
      return;
    }

    setSavingFieldKey(key);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/values`,
        {
          method: "PUT",
          body: JSON.stringify({
            blocco: block,
            campo: field,
            valore_grezzo: cleanedValue,
            valore_standardizzato: cleanedValue,
            valore_finale: cleanedValue,
            stato: "corretto",
            document_evidence_id: null,
            metodo_lettura: "utente",
            fonte_documentale: BLOCK_DEFAULT_SOURCE[block] || "utente",
            confidenza: null,
          }),
        },
        token,
      );
      await refreshRow(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingFieldKey("");
    }
  }

  async function handleConfirmValue(value) {
    const block = value.blocco;
    const field = value.campo;
    const key = fieldKey(block, field);
    const display = valueDisplay(value);

    if (!display) {
      setError(`Nessun valore da confermare per ${field}.`);
      return;
    }

    setSavingFieldKey(key);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/values`,
        {
          method: "PUT",
          body: JSON.stringify({
            blocco: block,
            campo: field,
            valore_grezzo: value.valore_grezzo,
            valore_standardizzato: value.valore_standardizzato || display,
            valore_finale: value.valore_finale || value.valore_standardizzato || value.valore_grezzo,
            stato: "confermato",
            document_evidence_id: value.document_evidence_id,
            metodo_lettura: value.metodo_lettura,
            fonte_documentale: value.fonte_documentale || BLOCK_DEFAULT_SOURCE[block] || "utente",
            confidenza: value.confidenza,
          }),
        },
        token,
      );
      await refreshRow(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingFieldKey("");
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

  async function handleValidateFinal() {
    setProcessingFinalValidation(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/validate-final`,
        { method: "POST" },
        token,
      );
      await refreshRow(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessingFinalValidation(false);
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
              disabled={processingNotes || !row?.certificate_document}
              onClick={handleDetectNotes}
              type="button"
            >
              {processingNotes ? "Rilevo note..." : "Rileva note"}
            </button>
            <button
              className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={processingChemistry || !row?.certificate_document}
              onClick={handleDetectChemistry}
              type="button"
            >
              {processingChemistry ? "Rilevo chimica..." : "Rileva chimica"}
            </button>
            <button
              className="rounded-xl border border-border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={processingProperties || !row?.certificate_document}
              onClick={handleDetectProperties}
              type="button"
            >
              {processingProperties ? "Rilevo proprietà..." : "Rileva proprietà"}
            </button>
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
            <button
              className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={processingFinalValidation || !canValidateFinal}
              onClick={handleValidateFinal}
              type="button"
            >
              {processingFinalValidation ? "Validazione..." : row?.validata_finale ? "Riga validata" : "Valida riga"}
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
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${row.validata_finale ? stateClasses("verde") : stateClasses(canValidateFinal ? "giallo" : "rosso")}`}>
                Validazione finale · {row.validata_finale ? "validata" : canValidateFinal ? "pronta da validare" : "non pronta"}
              </span>
              {Object.entries(row.block_states || {}).map(([key, state]) => (
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(state)}`} key={key}>
                  {BLOCK_LABELS[key] || key} · {state}
                </span>
              ))}
            </div>

            <div className="rounded-2xl border border-border p-5">
              <h3 className="text-lg font-semibold">Percorso operativo</h3>
              <p className="mt-2 text-sm text-slate-500">
                Ordine consigliato per il lavoro quality: DDT, match certificato, blocchi tecnici e chiusura finale.
              </p>
              <div className="mt-4 grid gap-3 xl:grid-cols-3">
                {[...ORDERED_BLOCKS, "validazione_finale"].map((step, index) => {
                  const state = workflowStepState(row, step);
                  return (
                    <div className={`rounded-2xl border p-4 ${stateClasses(state)}`} key={step}>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em]">
                        Step {index + 1}
                      </p>
                      <p className="mt-2 text-sm font-semibold">{workflowStepLabel(step)}</p>
                      <p className="mt-1 text-xs opacity-80">{workflowStepAction(row, step)}</p>
                    </div>
                  );
                })}
              </div>
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

            <MatchPanel
              availableCertificates={availableCertificates}
              certificateDocument={certificateDocument}
              match={row.certificate_match}
              matchDraft={matchDraft}
              onConfirmMatch={() => handleUpsertMatch("confermato")}
              onDraftChange={setMatchDraft}
              onSaveMatch={() => handleUpsertMatch(row.certificate_match ? "cambiato" : "proposto")}
              processingMatch={processingMatch}
            />

            <div className="grid gap-6 xl:grid-cols-2">
              {ORDERED_BLOCKS.map((block) => (
                <BlockPanel
                  key={block}
                  block={block}
                  label={BLOCK_LABELS[block] || block}
                  values={valuesByBlock[block] || []}
                  expectedFields={block === "ddt" ? DDT_CORE_FIELDS : block === "note" ? NOTE_CORE_FIELDS : []}
                  chemistryFieldOrder={CHEMISTRY_FIELD_ORDER}
                  propertyFieldOrder={PROPERTY_FIELD_ORDER}
                  draftValues={draftValues}
                  onCreateManualValue={handleCreateManualValue}
                  onDraftChange={updateDraft}
                  onSaveValue={handleSaveValue}
                  onConfirmValue={handleConfirmValue}
                  savingFieldKey={savingFieldKey}
                />
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

function BlockPanel({
  block,
  label,
  values,
  expectedFields,
  chemistryFieldOrder,
  propertyFieldOrder,
  draftValues,
  onCreateManualValue,
  onDraftChange,
  onSaveValue,
  onConfirmValue,
  savingFieldKey,
}) {
  const valueMap = new Map(values.map((value) => [value.campo, value]));
  const effectiveExpectedFields =
    expectedFields.length > 0 ? expectedFields : block === "proprieta" ? propertyFieldOrder : [];
  const chemistryRank = (field) => {
    const index = chemistryFieldOrder.indexOf(field);
    return index >= 0 ? index : Number.MAX_SAFE_INTEGER;
  };
  const propertyRank = (field) => {
    const index = propertyFieldOrder.indexOf(field);
    return index >= 0 ? index : Number.MAX_SAFE_INTEGER;
  };
  const extraValues = values
    .filter((value) => !effectiveExpectedFields.includes(value.campo))
    .sort((left, right) => {
      if (block === "chimica") {
        return chemistryRank(left.campo) - chemistryRank(right.campo) || left.campo.localeCompare(right.campo);
      }
      if (block === "proprieta") {
        return propertyRank(left.campo) - propertyRank(right.campo) || left.campo.localeCompare(right.campo);
      }
      return left.campo.localeCompare(right.campo);
    });
  const orderedValues = effectiveExpectedFields.map((field) => valueMap.get(field) || { blocco: block, campo: field, __missing: true });
  const renderedValues = [...orderedValues, ...extraValues];

  return (
    <div className="rounded-2xl border border-border p-5">
      <h3 className="text-lg font-semibold">{label}</h3>
      <div className="mt-4 space-y-3">
        {block === "chimica" ? (
          <ChemistryAdder chemistryFieldOrder={chemistryFieldOrder} onCreateValue={onCreateManualValue} />
        ) : null}
        {block === "proprieta" ? (
          <PropertyAdder onCreateValue={onCreateManualValue} propertyFieldOrder={propertyFieldOrder} />
        ) : null}
        {renderedValues.map((value) => {
          const key = fieldKey(block, value.campo);
          const currentDisplay = valueDisplay(value);
          const draftValue = Object.prototype.hasOwnProperty.call(draftValues, key) ? draftValues[key] : currentDisplay;
          const isSaving = savingFieldKey === key;
          const isMissing = Boolean(value.__missing);
          const saveLabel = isMissing ? "Aggiungi" : "Salva";

          return (
            <div className="rounded-2xl bg-slate-50 p-4" key={key}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white">
                  {value.campo}
                </span>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${readValueStateClasses(value)}`}>
                  {readValueStateLabel(value)}
                </span>
              </div>

              <div className="mt-3 space-y-3">
                <input
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none ring-0 transition focus:border-accent"
                  onChange={(event) => onDraftChange(block, value.campo, event.target.value)}
                  placeholder={isMissing ? "Inserisci valore" : "Correggi valore"}
                  value={draftValue}
                />

                <div className="flex flex-wrap gap-2">
                  <button
                    className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    disabled={isSaving}
                    onClick={() => onSaveValue(block, value.campo, isMissing ? null : value)}
                    type="button"
                  >
                    {isSaving ? "Salvataggio..." : saveLabel}
                  </button>
                  {!isMissing ? (
                    <button
                      className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
                      disabled={isSaving || !currentDisplay}
                      onClick={() => onConfirmValue(value)}
                      type="button"
                    >
                      {value.stato === "confermato" ? "Riconferma" : "Conferma"}
                    </button>
                  ) : null}
                </div>
              </div>

              {!isMissing ? (
                <p className="mt-3 text-xs text-slate-500">
                  Fonte {value.fonte_documentale} · Metodo {value.metodo_lettura}
                </p>
              ) : (
                <p className="mt-3 text-xs text-slate-500">Campo non ancora valorizzato per questo blocco.</p>
              )}
            </div>
          );
        })}
        {!renderedValues.length ? <p className="text-sm text-slate-500">Nessun valore presente.</p> : null}
      </div>
    </div>
  );
}

function MatchPanel({
  availableCertificates,
  certificateDocument,
  match,
  matchDraft,
  onConfirmMatch,
  onDraftChange,
  onSaveMatch,
  processingMatch,
}) {
  const certificateOptions = useMemo(() => {
    const items = [...availableCertificates];
    if (certificateDocument && !items.some((item) => item.id === certificateDocument.id)) {
      items.unshift(certificateDocument);
    }
    return items;
  }, [availableCertificates, certificateDocument]);

  return (
    <div className="rounded-2xl border border-border p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h3 className="text-lg font-semibold">Match Certificato</h3>
          <p className="mt-2 text-sm text-slate-500">
            Seleziona il certificato corretto e conferma il match dal blocco quality.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
            disabled={processingMatch}
            onClick={onSaveMatch}
            type="button"
          >
            {processingMatch ? "Salvataggio..." : "Salva match"}
          </button>
          <button
            className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={processingMatch}
            onClick={onConfirmMatch}
            type="button"
          >
            {processingMatch ? "Confermo..." : "Conferma match"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Certificato attuale</p>
          <p className="mt-2 text-sm font-medium text-slate-800">
            {certificateDocument?.nome_file_originale || "Nessun certificato collegato"}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(match?.stato === "confermato" ? "verde" : certificateDocument ? "giallo" : "rosso")}`}>
              {match?.stato || (certificateDocument ? "proposto" : "nessun match")}
            </span>
            {match?.fonte_proposta ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                Fonte {match.fonte_proposta}
              </span>
            ) : null}
          </div>
          {match?.motivo_breve ? <p className="mt-3 text-xs text-slate-500">{match.motivo_breve}</p> : null}
        </div>

        <div className="space-y-3 rounded-2xl bg-slate-50 p-4">
          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-slate-500" htmlFor="match-document">
              Certificato da collegare
            </label>
            <select
              className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
              id="match-document"
              onChange={(event) => onDraftChange((current) => ({ ...current, documentId: event.target.value }))}
              value={matchDraft.documentId}
            >
              <option value="">Seleziona certificato</option>
              {certificateOptions.map((document) => (
                <option key={document.id} value={document.id}>
                  #{document.id} · {document.nome_file_originale}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-slate-500" htmlFor="match-motivo">
              Motivo breve
            </label>
            <input
              className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
              id="match-motivo"
              onChange={(event) => onDraftChange((current) => ({ ...current, motivo: event.target.value }))}
              placeholder="CDQ e colata coerenti"
              value={matchDraft.motivo}
            />
          </div>
        </div>
      </div>

      {match?.candidates?.length ? (
        <div className="mt-4 space-y-3">
          <p className="text-sm font-medium text-slate-700">Candidati registrati</p>
          {match.candidates.map((candidate) => (
            <div className="rounded-2xl bg-slate-50 p-4" key={candidate.id}>
              <p className="text-sm font-medium text-slate-800">
                Certificato #{candidate.document_certificato_id} · rank {candidate.rank}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {candidate.stato} · {candidate.fonte_proposta} {candidate.motivo_breve ? `· ${candidate.motivo_breve}` : ""}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ChemistryAdder({ chemistryFieldOrder, onCreateValue }) {
  const [field, setField] = useState(chemistryFieldOrder[0] || "");
  const [value, setValue] = useState("");

  async function handleAdd() {
    if (!field || !value.trim()) {
      return;
    }
    await onCreateValue("chimica", field, value);
    setValue("");
  }

  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
      <p className="text-sm font-medium text-slate-800">Aggiungi elemento chimico</p>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr,1fr,auto]">
        <select
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
          onChange={(event) => setField(event.target.value)}
          value={field}
        >
          {chemistryFieldOrder.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <input
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
          onChange={(event) => setValue(event.target.value)}
          placeholder="0.07"
          value={value}
        />
        <button
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          onClick={handleAdd}
          type="button"
        >
          Aggiungi
        </button>
      </div>
    </div>
  );
}

function PropertyAdder({ onCreateValue, propertyFieldOrder }) {
  const [field, setField] = useState(propertyFieldOrder[0] || "");
  const [value, setValue] = useState("");

  async function handleAdd() {
    if (!field || !value.trim()) {
      return;
    }
    await onCreateValue("proprieta", field, value);
    setValue("");
  }

  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
      <p className="text-sm font-medium text-slate-800">Aggiungi proprietà</p>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr,1fr,auto]">
        <select
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
          onChange={(event) => setField(event.target.value)}
          value={field}
        >
          {propertyFieldOrder.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <input
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
          onChange={(event) => setValue(event.target.value)}
          placeholder="528"
          value={value}
        />
        <button
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          onClick={handleAdd}
          type="button"
        >
          Aggiungi
        </button>
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
