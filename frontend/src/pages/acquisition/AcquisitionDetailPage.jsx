import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { useAuth } from "../../app/auth";
import AcquisitionRowSummaryCard from "./AcquisitionRowSummaryCard";
import { formatFieldDisplay, formatRowFieldDisplay } from "./fieldFormatting";

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

const CERTIFICATE_FIRST_FIELDS = [
  { key: "lega_base", label: "lega" },
  { key: "diametro", label: "Ø" },
  { key: "cdq", label: "Cdq" },
  { key: "colata", label: "Colata" },
  { key: "ddt", label: "Ddt" },
  { key: "peso", label: "peso" },
  { key: "ordine", label: "ordine" },
];

const NOTE_CORE_FIELDS = [
  "nota_us_control_class_a",
  "nota_us_control_class_b",
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

const PROPERTY_FIELD_ORDER = [
  "HB",
  "Rp0.2",
  "Rm",
  "A%",
  "Rp0.2 / Rm",
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
const QUALITY_EVALUATION_OPTIONS = [
  { value: "accettato", label: "Accettato", state: "verde" },
  { value: "accettato_con_riserva", label: "Accettato con riserva", state: "giallo" },
  { value: "respinto", label: "Respinto", state: "rosso" },
];
const QUALITY_EVALUATION_LABELS = Object.fromEntries(QUALITY_EVALUATION_OPTIONS.map((option) => [option.value, option.label]));

function stateClasses(state) {
  if (state === "verde") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (state === "giallo") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function readValueStateClasses(block, field, value) {
  if (isExplicitNullValue(block, field, value)) {
    return stateClasses("verde");
  }
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

function valueDisplay(block, field, value) {
  const raw = value?.valore_finale || value?.valore_standardizzato || value?.valore_grezzo || "";
  return formatFieldDisplay(block, field, raw);
}

function valueHasPayload(block, field, value) {
  return Boolean(valueDisplay(block, field, value));
}

function isExplicitNullValue(block, field, value) {
  return Boolean(value && !value.__missing && !valueHasPayload(block, field, value));
}

function fieldKey(block, field) {
  return `${block}:${field}`;
}

function safeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function workflowStepState(row, step) {
  if (step === "validazione_finale") {
    if (row?.validata_finale) {
      if (row.qualita_valutazione === "respinto") {
        return "rosso";
      }
      if (row.qualita_valutazione === "accettato_con_riserva") {
        return "giallo";
      }
      return row.qualita_valutazione === "accettato" ? "verde" : "giallo";
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
      return qualityEvaluationLabel(row.qualita_valutazione);
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

function qualityEvaluationLabel(value) {
  return QUALITY_EVALUATION_LABELS[value] || "Da valutare";
}

function readValueStateLabel(block, field, value) {
  if (isExplicitNullValue(block, field, value)) {
    return "null";
  }
  if (value?.__missing) {
    return "non pronto";
  }
  if (value?.stato === "confermato") {
    return "pronto";
  }
  return "da verificare";
}

function sourceDisplayLabel(block, value) {
  if (!value || value.__missing) {
    return "manuale";
  }

  const source = value.fonte_documentale || BLOCK_DEFAULT_SOURCE[block] || "utente";
  const method = value.metodo_lettura || "pdf_text";

  if (method === "utente" || source === "utente") {
    return "manuale";
  }

  if (method === "calcolato" || source === "calcolato") {
    return "calcolato";
  }

  if (method === "chatgpt") {
    if (source === "certificato") {
      return "certificato - AI";
    }
    if (source === "ddt") {
      return "ddt - AI";
    }
    if (source === "ddt_certificato") {
      return "ddt/certificato - AI";
    }
    return "AI";
  }

  if (source === "certificato") {
    return "certificato";
  }
  if (source === "ddt") {
    return "ddt";
  }
  if (source === "ddt_certificato") {
    return "ddt/certificato";
  }
  if (source === "db_esterno") {
    return "db esterno";
  }

  return safeText(source);
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
  const [certificateFirstDraft, setCertificateFirstDraft] = useState({});
  const [refreshingCertificateFirst, setRefreshingCertificateFirst] = useState(false);
  const [savingCertificateFirst, setSavingCertificateFirst] = useState(false);
  const [loadingDdtPreview, setLoadingDdtPreview] = useState(false);
  const [ddtLinkPreview, setDdtLinkPreview] = useState(null);
  const [finalQualityNote, setFinalQualityNote] = useState("");

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

        const requests = [];
        if (rowData.ddt_document?.id) {
          requests.push(apiRequest(`/acquisition/documents/${rowData.ddt_document.id}`, {}, token));
        }
        if (rowData.certificate_document?.id) {
          requests.push(apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token));
        }
        const [ddtData, certificateData] = await Promise.all(requests);
        if (!ignore) {
          setDdtDocument(rowData.ddt_document?.id ? ddtData : null);
          setCertificateDocument(rowData.ddt_document?.id ? certificateData || null : ddtData || null);
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

  const isCertificateFirstRow = useMemo(
    () => Boolean(row?.certificate_document?.id && !row?.ddt_document?.id),
    [row],
  );

  useEffect(() => {
    setFinalQualityNote(row?.qualita_note || "");
  }, [row?.id, row?.qualita_note]);

  async function refreshRow(includeDocuments = false) {
    const rowData = await apiRequest(`/acquisition/rows/${rowId}`, {}, token);
    setRow(rowData);
    setMatchDraft({
      documentId: String(rowData.certificate_match?.document_certificato_id || rowData.certificate_document?.id || ""),
      motivo: rowData.certificate_match?.motivo_breve || "",
    });

    if (includeDocuments) {
      const requests = [];
      if (rowData.ddt_document?.id) {
        requests.push(apiRequest(`/acquisition/documents/${rowData.ddt_document.id}`, {}, token));
      }
      if (rowData.certificate_document?.id) {
        requests.push(apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token));
      }
      const [ddtData, certificateData] = await Promise.all(requests);
      setDdtDocument(rowData.ddt_document?.id ? ddtData : null);
      setCertificateDocument(rowData.ddt_document?.id ? certificateData || null : ddtData || null);
    }
  }

  useEffect(() => {
    if (!isCertificateFirstRow) {
      setCertificateFirstDraft({});
      setDdtLinkPreview(null);
      return;
    }

    setCertificateFirstDraft({
      lega_base: formatRowFieldDisplay("lega", row?.lega_base || row?.lega_designazione || row?.variante_lega || ""),
      diametro: formatRowFieldDisplay("diametro", row?.diametro || ""),
      cdq: formatRowFieldDisplay("cdq", row?.cdq || ""),
      colata: formatRowFieldDisplay("colata", row?.colata || ""),
      ddt: formatRowFieldDisplay("ddt", row?.ddt || ""),
      peso: formatRowFieldDisplay("peso", row?.peso || ""),
      ordine: formatRowFieldDisplay("ordine", row?.ordine || ""),
    });
  }, [isCertificateFirstRow, row]);

  useEffect(() => {
    let ignore = false;

    async function loadPreview() {
      if (!isCertificateFirstRow) {
        return;
      }
      setLoadingDdtPreview(true);
      try {
        const preview = await apiRequest(`/acquisition/rows/${rowId}/ddt-link-preview`, {}, token);
        if (!ignore) {
          setDdtLinkPreview(preview);
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

    loadPreview();

    return () => {
      ignore = true;
    };
  }, [isCertificateFirstRow, rowId, token]);

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

  function updateCertificateFirstDraft(field, value) {
    setCertificateFirstDraft((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleRefreshCertificateFirst() {
    setRefreshingCertificateFirst(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/refresh-certificate-first`,
        { method: "POST" },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRefreshingCertificateFirst(false);
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

  async function handleSaveCertificateFirstFields() {
    setSavingCertificateFirst(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            lega_base: safeText(certificateFirstDraft.lega_base).trim() || null,
            diametro: safeText(certificateFirstDraft.diametro).trim() || null,
            cdq: safeText(certificateFirstDraft.cdq).trim() || null,
            colata: safeText(certificateFirstDraft.colata).trim() || null,
            ddt: safeText(certificateFirstDraft.ddt).trim() || null,
            peso: safeText(certificateFirstDraft.peso).trim() || null,
            ordine: safeText(certificateFirstDraft.ordine).trim() || null,
          }),
        },
        token,
      );
      await refreshRow(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingCertificateFirst(false);
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
    const currentDisplay = valueDisplay(block, field, value);
    const nextValue = safeText(getDraft(block, field, currentDisplay)).trim();

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
    const cleanedValue = safeText(nextValue).trim();
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
    const display = valueDisplay(block, field, value);

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

  async function handleSetNullValue(block, field, value) {
    const key = fieldKey(block, field);

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
            valore_grezzo: null,
            valore_standardizzato: null,
            valore_finale: null,
            stato: "confermato",
            document_evidence_id: value?.document_evidence_id || null,
            metodo_lettura: "utente",
            fonte_documentale: value?.fonte_documentale || BLOCK_DEFAULT_SOURCE[block] || "utente",
            confidenza: null,
          }),
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

  async function handleValidateFinal(qualityEvaluation) {
    const cleanedNote = safeText(finalQualityNote).trim();
    if ((qualityEvaluation === "accettato_con_riserva" || qualityEvaluation === "respinto") && !cleanedNote) {
      window.alert("Per accettare con riserva o respingere la riga devi indicare una motivazione nella nota valutazione.");
      return;
    }

    setProcessingFinalValidation(true);
    setError("");
    try {
      await apiRequest(
        `/acquisition/rows/${rowId}/validate-final`,
        {
          method: "POST",
          body: JSON.stringify({
            qualita_valutazione: qualityEvaluation,
            qualita_note: cleanedNote || null,
          }),
        },
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
    <section className="space-y-4">
      <div className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <button className="text-sm font-medium text-accent hover:underline" onClick={() => navigate("/acquisition")} type="button">
              Torna alla griglia
            </button>
            <p className="mt-3 text-sm uppercase tracking-[0.3em] text-slate-500">Dettaglio acquisition</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Riga #{rowId}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={processingVision || !row?.ddt_document} onClick={handleProcessDdtVision} type="button">
              {processingVision ? "Vision..." : "Vision DDT"}
            </button>
            <button className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={processingChemistry || !row?.certificate_document} onClick={handleDetectChemistry} type="button">
              {processingChemistry ? "Chimica..." : "Rileva chimica"}
            </button>
            <button className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={processingProperties || !row?.certificate_document} onClick={handleDetectProperties} type="button">
              {processingProperties ? "Proprietà..." : "Rileva proprietà"}
            </button>
            <button className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={processingNotes || !row?.certificate_document} onClick={handleDetectNotes} type="button">
              {processingNotes ? "Note..." : "Rileva note"}
            </button>
            <button className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60" disabled={processing || !row?.ddt_document} onClick={handleProcessMinimal} type="button">
              {processing ? "Processo..." : "Processo minimo"}
            </button>
          </div>
        </div>

        {loading ? <p className="mt-4 text-sm text-slate-500">Caricamento riga...</p> : null}
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

        {row ? (
          <div className="mt-4 space-y-4">
            <AcquisitionRowSummaryCard canValidateFinal={canValidateFinal} row={row} rowId={rowId} showStatus showTitle={false} />

            <div className="rounded-2xl border border-border bg-white p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Percorso operativo</div>
              <div className="grid gap-2 xl:grid-cols-6">
                {[...ORDERED_BLOCKS, "validazione_finale"].map((step) => {
                  const state = workflowStepState(row, step);
                  return (
                    <div className={`rounded-xl border px-3 py-2 ${stateClasses(state)}`} key={step}>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em]">{workflowStepLabel(step)}</div>
                      <div className="mt-1 text-xs">{workflowStepAction(row, step)}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-white p-4">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="max-w-2xl">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Valutazione finale qualità</div>
                  <p className="mt-2 text-sm text-slate-600">
                    I dati tecnici restano confermati. Qui scegli solo l'esito qualità finale che manda la riga nella vista Confermati.
                  </p>
                  {row.validata_finale ? (
                    <span className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(row.qualita_valutazione === "respinto" ? "rosso" : row.qualita_valutazione === "accettato" ? "verde" : "giallo")}`}>
                      {qualityEvaluationLabel(row.qualita_valutazione)}
                    </span>
                  ) : null}
                </div>
                <div className="min-w-[320px] flex-1 xl:max-w-xl">
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="final-quality-note">
                    Nota valutazione
                  </label>
                  <textarea
                    className="min-h-20 w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700 disabled:bg-slate-50 disabled:text-slate-500"
                    disabled={row.validata_finale || processingFinalValidation}
                    id="final-quality-note"
                    onChange={(event) => setFinalQualityNote(event.target.value)}
                    placeholder="Obbligatoria per accettato con riserva o respinto."
                    value={finalQualityNote}
                  />
                </div>
              </div>
              {!row.validata_finale ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {QUALITY_EVALUATION_OPTIONS.map((option) => (
                    <button
                      className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 ${
                        option.state === "verde"
                          ? "bg-emerald-700 hover:bg-emerald-800"
                          : option.state === "giallo"
                            ? "bg-amber-600 hover:bg-amber-700"
                            : "bg-rose-700 hover:bg-rose-800"
                      }`}
                      disabled={processingFinalValidation || !canValidateFinal}
                      key={option.value}
                      onClick={() => handleValidateFinal(option.value)}
                      type="button"
                    >
                      {processingFinalValidation ? "Validazione..." : option.label}
                    </button>
                  ))}
                </div>
              ) : null}
              {!canValidateFinal ? (
                <p className="mt-3 text-sm text-rose-600">La valutazione finale si abilita solo quando DDT, match, chimica, proprietà e note sono verdi.</p>
              ) : null}
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
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
              certificateFirstDraft={certificateFirstDraft}
              availableCertificates={availableCertificates}
              certificateDocument={certificateDocument}
              ddtLinkPreview={ddtLinkPreview}
              isCertificateFirstRow={isCertificateFirstRow}
              loadingDdtPreview={loadingDdtPreview}
              match={row.certificate_match}
              matchDraft={matchDraft}
              onConfirmMatch={() => handleUpsertMatch("confermato")}
              onRefreshCertificateFirst={handleRefreshCertificateFirst}
              onReloadDdtPreview={handleReloadDdtPreview}
              onDraftChange={setMatchDraft}
              onSaveCertificateFirstFields={handleSaveCertificateFirstFields}
              onSaveMatch={() => handleUpsertMatch(row.certificate_match ? "cambiato" : "proposto")}
              onUpdateCertificateFirstDraft={updateCertificateFirstDraft}
              processingMatch={processingMatch}
              refreshingCertificateFirst={refreshingCertificateFirst}
              savingCertificateFirst={savingCertificateFirst}
            />

            <div className="space-y-4">
              {ORDERED_BLOCKS.map((block) => (
                <BlockPanel
                  key={block}
                  block={block}
                  label={BLOCK_LABELS[block] || block}
                  values={valuesByBlock[block] || []}
                  expectedFields={
                    block === "ddt"
                      ? DDT_CORE_FIELDS
                      : block === "note"
                        ? NOTE_CORE_FIELDS
                        : block === "chimica"
                          ? CHEMISTRY_FIELD_ORDER
                          : []
                  }
                  chemistryFieldOrder={CHEMISTRY_FIELD_ORDER}
                  propertyFieldOrder={PROPERTY_FIELD_ORDER}
                  draftValues={draftValues}
                  onCreateManualValue={handleCreateManualValue}
                  onDraftChange={updateDraft}
                  onSaveValue={handleSaveValue}
                  onSetNullValue={handleSetNullValue}
                  onConfirmValue={handleConfirmValue}
                  savingFieldKey={savingFieldKey}
                />
              ))}
            </div>

            <div className="rounded-2xl border border-border bg-white p-4">
              <div className="mb-3 text-base font-semibold text-slate-900">Storico recente</div>
              <div className="overflow-hidden rounded-2xl border border-border">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50">
                    <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      <th className="px-3 py-2">Blocco</th>
                      <th className="px-3 py-2">Azione</th>
                      <th className="px-3 py-2">Quando</th>
                      <th className="px-3 py-2">Nota</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {(row.history_events || []).slice(0, 8).map((event) => (
                      <tr key={event.id}>
                        <td className="px-3 py-2 text-slate-800">{event.blocco}</td>
                        <td className="px-3 py-2 text-slate-800">{event.azione}</td>
                        <td className="px-3 py-2 text-slate-600">{new Date(event.timestamp).toLocaleString()}</td>
                        <td className="px-3 py-2 text-slate-600">{event.nota_breve || "-"}</td>
                      </tr>
                    ))}
                    {!row.history_events?.length ? (
                      <tr>
                        <td className="px-3 py-4 text-sm text-slate-500" colSpan={4}>
                          Nessun evento disponibile.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
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
    <div className="rounded-xl border border-border bg-slate-50 px-3 py-2">
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
  onSetNullValue,
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
    <div className="rounded-2xl border border-border bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900">{label}</h3>
        <span className="text-xs text-slate-500">{renderedValues.length} campi</span>
      </div>
      <div className="space-y-3">
        {block === "proprieta" ? (
          <PropertyAdder onCreateValue={onCreateManualValue} propertyFieldOrder={propertyFieldOrder} />
        ) : null}
        <div className="overflow-hidden rounded-2xl border border-border">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-3 py-2">Campo</th>
                <th className="px-3 py-2">Valore</th>
                <th className="px-3 py-2">Stato</th>
                <th className="px-3 py-2">Fonte</th>
                <th className="px-3 py-2">Azioni</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {renderedValues.map((value) => {
          const key = fieldKey(block, value.campo);
          const currentDisplay = valueDisplay(block, value.campo, value);
          const draftValue = safeText(Object.prototype.hasOwnProperty.call(draftValues, key) ? draftValues[key] : currentDisplay);
          const isSaving = savingFieldKey === key;
          const isMissing = Boolean(value.__missing);
          const isExplicitNull = isExplicitNullValue(block, value.campo, value);
          const saveLabel = isMissing ? "Aggiungi" : "Salva";

          return (
            <tr key={key}>
              <td className="px-3 py-3 font-medium text-slate-900">{value.campo}</td>
              <td className="px-3 py-3">
                <input
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-accent"
                  onChange={(event) => onDraftChange(block, value.campo, event.target.value)}
                  placeholder={isMissing ? "Inserisci valore" : "Correggi valore"}
                  value={draftValue}
                />
              </td>
              <td className="px-3 py-3">
                <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${readValueStateClasses(block, value.campo, value)}`}>
                  {readValueStateLabel(block, value.campo, value)}
                </span>
              </td>
              <td className="px-3 py-3 text-xs text-slate-500">
                {sourceDisplayLabel(block, value)}
              </td>
              <td className="px-3 py-3">
                <div className="flex flex-wrap gap-2">
                  <button
                    className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    disabled={isSaving}
                    onClick={() => onSaveValue(block, value.campo, isMissing ? null : value)}
                    type="button"
                  >
                    {isSaving ? "Salvataggio..." : saveLabel}
                  </button>
                  {!isMissing ? (
                    <button
                      className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
                      disabled={isSaving || !currentDisplay}
                      onClick={() => onConfirmValue(value)}
                      type="button"
                    >
                      {value.stato === "confermato" ? "Riconferma" : "Conferma"}
                    </button>
                  ) : null}
                  {block === "chimica" ? (
                    <button
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                      disabled={isSaving}
                      onClick={() => onSetNullValue(block, value.campo, isMissing || isExplicitNull ? null : value)}
                      type="button"
                    >
                      Null
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          );
        })}
              {!renderedValues.length ? (
                <tr>
                  <td className="px-3 py-4 text-sm text-slate-500" colSpan={5}>
                    Nessun valore presente.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MatchPanel({
  certificateFirstDraft,
  availableCertificates,
  certificateDocument,
  ddtLinkPreview,
  isCertificateFirstRow,
  loadingDdtPreview,
  match,
  matchDraft,
  onConfirmMatch,
  onDraftChange,
  onRefreshCertificateFirst,
  onReloadDdtPreview,
  onSaveCertificateFirstFields,
  onSaveMatch,
  onUpdateCertificateFirstDraft,
  processingMatch,
  refreshingCertificateFirst,
  savingCertificateFirst,
}) {
  const certificateOptions = useMemo(() => {
    const items = [...availableCertificates];
    if (certificateDocument && !items.some((item) => item.id === certificateDocument.id)) {
      items.unshift(certificateDocument);
    }
    return items;
  }, [availableCertificates, certificateDocument]);

  return (
    <div className="rounded-2xl border border-border bg-white p-4">
      {isCertificateFirstRow ? (
        <div className="mb-6 rounded-2xl border border-sky-200 bg-sky-50/70 p-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Certificate-first</h3>
              <p className="mt-1 text-sm text-slate-600">
                Qui lavoriamo solo sui 7 campi Excel del certificato, già nel formato utile al match.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                disabled={refreshingCertificateFirst}
                onClick={onRefreshCertificateFirst}
                type="button"
              >
                {refreshingCertificateFirst ? "Aggiorno..." : "Aggiorna da certificato"}
              </button>
              <button
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                disabled={savingCertificateFirst}
                onClick={onSaveCertificateFirstFields}
                type="button"
              >
                {savingCertificateFirst ? "Salvo..." : "Salva campi"}
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {CERTIFICATE_FIRST_FIELDS.map((field) => (
              <div className="rounded-xl border border-sky-100 bg-white p-3" key={field.key}>
                <label className="text-xs uppercase tracking-[0.18em] text-slate-500" htmlFor={`cf-${field.key}`}>
                  {field.label}
                </label>
                <input
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
                  id={`cf-${field.key}`}
                  onChange={(event) => onUpdateCertificateFirstDraft(field.key, event.target.value)}
                  value={safeText(certificateFirstDraft[field.key])}
                />
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900">DDT candidati per il match</p>
                <p className="mt-1 text-xs text-slate-500">
                  Il sistema confronta questi campi alti con i DDT liberi dello stesso fornitore.
                </p>
              </div>
              <button
                className="rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                disabled={loadingDdtPreview}
                onClick={onReloadDdtPreview}
                type="button"
              >
                {loadingDdtPreview ? "Cerco..." : "Ricarica candidati"}
              </button>
            </div>

            {ddtLinkPreview?.auto_match_row_id ? (
              <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
                Candidato forte trovato sulla riga #{safeText(ddtLinkPreview.auto_match_row_id)}.
              </div>
            ) : null}

            <div className="mt-4 space-y-3">
              {ddtLinkPreview?.items?.length ? (
                ddtLinkPreview.items.map((item) => (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={safeText(item.row_id)}>
                    <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">
                          Riga #{safeText(item.row_id)} · {safeText(item.ddt_file_name) || `DDT #${safeText(item.document_ddt_id)}`}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Score {safeText(item.score)} · {(Array.isArray(item.reasons) ? item.reasons : []).join(" · ") || "nessun dettaglio"}
                        </p>
                      </div>
                      <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                        DDT {safeText(item.ddt) || "-"}
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
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-sm text-slate-500">
                  Nessun DDT candidato trovato con le regole attuali.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Match certificato</h3>
          <p className="mt-1 text-sm text-slate-500">Seleziona il certificato corretto e conferma il match.</p>
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
        <div className="rounded-2xl border border-border bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Certificato attuale</p>
          <p className="mt-2 text-sm font-medium text-slate-800">
            {safeText(certificateDocument?.nome_file_originale) || "Nessun certificato collegato"}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateClasses(match?.stato === "confermato" ? "verde" : certificateDocument ? "giallo" : "rosso")}`}>
              {safeText(match?.stato) || (certificateDocument ? "proposto" : "nessun match")}
            </span>
            {match?.fonte_proposta ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                Fonte {safeText(match.fonte_proposta)}
              </span>
            ) : null}
          </div>
          {match?.motivo_breve ? <p className="mt-3 text-xs text-slate-500">{safeText(match.motivo_breve)}</p> : null}
        </div>

        <div className="space-y-3 rounded-2xl border border-border bg-white p-4">
          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-slate-500" htmlFor="match-document">
              Certificato da collegare
            </label>
            <select
              className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-accent"
              id="match-document"
              onChange={(event) => onDraftChange((current) => ({ ...current, documentId: event.target.value }))}
              value={safeText(matchDraft.documentId)}
            >
              <option value="">Seleziona certificato</option>
              {certificateOptions.map((document) => (
                <option key={document.id} value={document.id}>
                  #{document.id} · {safeText(document.nome_file_originale)}
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
              value={safeText(matchDraft.motivo)}
            />
          </div>
        </div>
      </div>

      {match?.candidates?.length ? (
        <div className="mt-4 space-y-3">
          <p className="text-sm font-medium text-slate-700">Candidati registrati</p>
          {match.candidates.map((candidate) => (
            <div className="rounded-xl border border-border bg-slate-50 p-4" key={candidate.id}>
              <p className="text-sm font-medium text-slate-800">
                Certificato #{safeText(candidate.document_certificato_id)} · rank {safeText(candidate.rank)}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {safeText(candidate.stato)} · {safeText(candidate.fonte_proposta)} {candidate.motivo_breve ? `· ${safeText(candidate.motivo_breve)}` : ""}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PreviewMini({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2 py-2">
      <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-800">{safeText(value) || "-"}</div>
    </div>
  );
}

function ChemistryAdder({ chemistryFieldOrder, onCreateValue }) {
  const [field, setField] = useState(chemistryFieldOrder[0] || "");
  const [value, setValue] = useState("");

  async function handleAdd() {
    if (!field || !safeText(value).trim()) {
      return;
    }
    await onCreateValue("chimica", field, value);
    setValue("");
  }

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
      <p className="text-sm font-medium text-slate-800">Aggiungi elemento chimico presente nel certificato</p>
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
          value={safeText(value)}
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
    if (!field || !safeText(value).trim()) {
      return;
    }
    await onCreateValue("proprieta", field, value);
    setValue("");
  }

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
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
          value={safeText(value)}
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
    <div className="rounded-2xl border border-border bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <p className="mt-2 text-sm text-slate-500">
            {document ? `${safeText(document.nome_file_originale)} · ${safeText(document.numero_pagine || 0)} pagine` : "Documento non collegato"}
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
        <div className="mt-4 overflow-hidden rounded-2xl border border-border">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-3 py-2">Pagina</th>
                <th className="px-3 py-2">Stato</th>
                <th className="px-3 py-2">Contenuto</th>
                <th className="px-3 py-2 text-right">Apri</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {document.pages.map((page) => (
                <tr key={page.id}>
                  <td className="px-3 py-2 text-slate-800">{page.numero_pagina}</td>
                  <td className="px-3 py-2 text-slate-600">{safeText(page.stato_estrazione)}</td>
                  <td className="px-3 py-2 text-slate-600">{page.testo_estratto ? "testo disponibile" : "immagine disponibile"}</td>
                  <td className="px-3 py-2 text-right">
                    {page.image_url ? (
                      <button
                        className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
                        disabled={openingAsset === page.image_url}
                        onClick={() => onOpenAsset(page.image_url, `pagina-${page.numero_pagina}.png`)}
                        type="button"
                      >
                        {openingAsset === page.image_url ? "Apertura..." : "Apri immagine"}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
