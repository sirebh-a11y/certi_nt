import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiRequest, fetchApiBlob, resolveApiAssetUrl } from "../../app/api";
import { useAuth } from "../../app/auth";

const STATUS_CLASSES = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  missing: "border-amber-200 bg-amber-50 text-amber-800",
  missing_from_supplier: "border-slate-200 bg-slate-50 text-slate-700",
  different: "border-amber-200 bg-amber-50 text-amber-800",
  out_of_range: "border-rose-200 bg-rose-50 text-rose-800",
  not_in_standard: "border-slate-200 bg-slate-50 text-slate-700",
  not_checked: "border-slate-200 bg-slate-50 text-slate-700",
  missing_diameter: "border-amber-200 bg-amber-50 text-amber-800",
  range_not_found: "border-rose-200 bg-rose-50 text-rose-800",
  mismatch: "border-rose-200 bg-rose-50 text-rose-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

const STATUS_LABELS = {
  green: "Pronto",
  yellow: "Da completare",
  red: "Bloccato",
  ok: "OK",
  missing: "Manca",
  missing_from_supplier: "Manca da fornitore",
  different: "Diverso",
  out_of_range: "Fuori standard",
  not_in_standard: "Non previsto",
  not_checked: "Non verificato",
  missing_diameter: "Diametro mancante",
  range_not_found: "Range mancante",
  mismatch: "Non coerente",
  error: "Errore",
};

const METHOD_LABELS = {
  weighted: "media pesata",
  average: "media",
  minimum: "minimo",
  single: "singolo",
  missing: "-",
};

const CONFORMITY_LABELS = {
  conforme: "Conforme",
  non_conforme: "Non conforme",
  da_verificare: "Da verificare",
};

const CONFORMITY_CLASSES = {
  conforme: "border-emerald-200 bg-emerald-50 text-emerald-800",
  non_conforme: "border-rose-300 bg-rose-50 text-rose-800",
  da_verificare: "border-amber-200 bg-amber-50 text-amber-800",
};

const CUSTOMER_REQUIREMENT_FIELDS = [
  { field: "requires_chemical_analysis", label: "Analisi Chimica" },
  { field: "requires_mechanical_mp", label: "Caratt. Mecc. MP" },
  { field: "requires_mechanical_forged", label: "Caratt. Mecc. Forgiato" },
  { field: "requires_hardness_hb", label: "Durezza HB" },
  { field: "requires_lot_traceability_text", label: "Tracciabilita Lotto (datario) Indicazione" },
  { field: "requires_lot_traceability_photo", label: "Tracciabilita Lotto (datario) Foto" },
  { field: "requires_dimensional", label: "Dimensionale (Dimensioni concordate con cliente)" },
  { field: "requires_marking", label: "Marcature (Tracciabilita aggiuntive)" },
  { field: "requires_macro_micro", label: "Macrografie e/o Micrografie" },
  { field: "requires_ndt", label: "Tracciabilita Controllo NDT" },
];

const ARTICLE_AUTOSAVE_DELAY_MS = 800;
const ARTICLE_SAVED_FEEDBACK_MS = 1200;
const QUICK_INCOMING_CONFIRM_STORAGE_KEY = "certi_nt.quarta_taglio_quick_incoming_confirm.v1";

function statusClass(status) {
  return STATUS_CLASSES[status] || STATUS_CLASSES.not_checked;
}

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("it-IT", { maximumFractionDigits: digits });
}

function formatQuantity(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return String(value).replace(".", ",");
  }
  return Math.round(numericValue).toLocaleString("it-IT", { maximumFractionDigits: 0 });
}

function formatLimit(min, max, digits = 4) {
  if (min === null && max === null) {
    return "-";
  }
  if (min !== null && max !== null) {
    return `${formatNumber(min, digits)} - ${formatNumber(max, digits)}`;
  }
  if (min !== null) {
    return `>= ${formatNumber(min, digits)}`;
  }
  return `<= ${formatNumber(max, digits)}`;
}

function conformityClass(status) {
  return CONFORMITY_CLASSES[normalizedConformityStatus(status)];
}

function conformityLabel(status) {
  return CONFORMITY_LABELS[normalizedConformityStatus(status)];
}

function normalizedConformityStatus(status) {
  return status === "conforme" || status === "non_conforme" ? status : "da_verificare";
}

function formatConformityIssue(issue) {
  const blockLabel = issue.block === "chimica" ? "Chimica" : "Proprietà";
  const digits = issue.block === "chimica" ? 3 : 4;
  const value = formatNumber(issue.value, digits);
  const limit = formatLimit(issue.standard_min ?? null, issue.standard_max ?? null, digits);
  return `${blockLabel}: ${issue.field} ${value} fuori limite ${limit}${issue.message ? ` (${issue.message})` : ""}`;
}

function articleFieldClass(status) {
  if (status === "error") {
    return "border-rose-400 bg-rose-50 text-rose-900";
  }
  if (status === "saving") {
    return "border-sky-300 bg-sky-50 text-slate-900";
  }
  if (status === "saved") {
    return "border-emerald-300 bg-emerald-50 text-slate-900";
  }
  return "border-slate-200 bg-white text-slate-900";
}

function articleAutosaveTitle(cellState) {
  if (!cellState) {
    return undefined;
  }
  if (cellState.status === "saving") {
    return "Salvataggio automatico...";
  }
  if (cellState.status === "saved") {
    return "Salvato";
  }
  return cellState.message || "Errore salvataggio automatico";
}

function standardLabel(standard) {
  const designation = String(standard.lega_designazione || "").trim();
  const base = String(standard.lega_base || "").trim();
  const variant = String(standard.variante_lega || "").trim();
  let alloy = designation || base;
  if (variant && !alloy.toLowerCase().includes(variant.toLowerCase())) {
    alloy = `${alloy} ${variant}`.trim();
  }
  return [
    alloy,
    standard.norma,
    standard.trattamento_termico,
    standard.tipo_prodotto,
    standard.misura_tipo,
  ]
    .filter(Boolean)
    .join(" · ");
}

function quartaDetailApiPath(codOdp, params = {}) {
  const basePath = `/quarta-taglio/${encodeURIComponent(codOdp)}`;
  const query = new URLSearchParams();
  if (params.certificateId) {
    query.set("certificate_id", params.certificateId);
  } else if (params.candidateCodF3) {
    query.set("candidate_cod_f3", params.candidateCodF3);
  }
  const queryString = query.toString();
  return queryString ? `${basePath}?${queryString}` : basePath;
}

function quartaDetailUiPath(codOdp, params = {}) {
  const basePath = `/quarta-taglio/${encodeURIComponent(codOdp)}`;
  const query = new URLSearchParams();
  if (params.certificateId) {
    query.set("certificateId", params.certificateId);
  } else if (params.candidateCodF3) {
    query.set("candidateCodF3", params.candidateCodF3);
  }
  const queryString = query.toString();
  return queryString ? `${basePath}?${queryString}` : basePath;
}

function codF3CandidateClass(confidence) {
  if (confidence === "ddt" || confidence === "raw" || confidence === "ready") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (confidence === "medium") {
    return "border-sky-200 bg-sky-50 text-sky-800";
  }
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function codF3CandidateStatusClass(candidate) {
  if (candidate.has_word && candidate.word_source === "inherited") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (candidate.has_word && ["generated", "user_uploaded", "fields_updated"].includes(candidate.word_source)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (candidate.has_word) {
    return "border-slate-200 bg-slate-50 text-slate-700";
  }
  return codF3CandidateClass(candidate.confidence);
}

function codF3CandidateLabel(candidate) {
  if (candidate.has_word) {
    return candidate.word_source_label || "Word aperto";
  }
  if (candidate.confidence === "ddt") {
    return "Candidato";
  }
  if (candidate.confidence === "raw") {
    return "Raw";
  }
  if (candidate.confidence === "ready") {
    return "Candidato";
  }
  if (candidate.confidence === "medium") {
    return "Candidato";
  }
  return "Da verificare";
}

function wordInfoPanelClass(wordInfo) {
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function wordSourceBadgeClass(source) {
  if (source === "inherited") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (["generated", "user_uploaded", "fields_updated"].includes(source)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function codF3CandidateCardClass(candidate, isActive) {
  const activeClass = isActive ? "ring-2 ring-sky-300" : "";
  if (candidate.has_word && candidate.word_source === "inherited") {
    return `border-amber-300 bg-amber-50 ${activeClass}`;
  }
  if (candidate.has_word && ["generated", "user_uploaded", "fields_updated"].includes(candidate.word_source)) {
    return `border-emerald-300 bg-emerald-50 ${activeClass}`;
  }
  if (isActive) {
    return "border-sky-300 bg-sky-50/70";
  }
  return "border-slate-200 bg-white";
}

function quickIncomingConfirmEnabled() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(QUICK_INCOMING_CONFIRM_STORAGE_KEY) === "true";
}

function codF3MatchKey(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length <= 2) {
    return "";
  }
  return digits.slice(0, -2);
}

function codF3ExactKey(value) {
  return String(value || "").replace(/\D/g, "");
}

function findCustomerRequirementForCodF3(requirements, codF3) {
  const targetKey = codF3MatchKey(codF3);
  if (!targetKey) {
    return null;
  }
  const targetDigits = String(codF3 || "").replace(/\D/g, "");
  const exact = requirements.find((item) => String(item.cod_f3 || "").replace(/\D/g, "") === targetDigits);
  if (exact) {
    return exact;
  }
  return requirements.find((item) => codF3MatchKey(item.cod_f3) === targetKey) || null;
}

export default function QuartaTaglioDetailPage() {
  const { codOdp } = useParams();
  const [searchParams] = useSearchParams();
  const certificateId = searchParams.get("certificateId");
  const selectedCandidateCodF3 = searchParams.get("candidateCodF3");
  const navigate = useNavigate();
  const location = useLocation();
  const { clearAuth, token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingStandardId, setSavingStandardId] = useState(null);
  const [standardError, setStandardError] = useState("");
  const [standards, setStandards] = useState([]);
  const [customerRequirements, setCustomerRequirements] = useState([]);
  const [manualStandardId, setManualStandardId] = useState("");
  const [articleDraft, setArticleDraft] = useState({ descrizione: "", disegno: "" });
  const [articleStates, setArticleStates] = useState({});
  const [wordDraftState, setWordDraftState] = useState({ status: "idle", message: "" });
  const [wordUploadFile, setWordUploadFile] = useState(null);
  const [wordUploadState, setWordUploadState] = useState({ status: "idle", message: "" });
  const [additionalPagesFile, setAdditionalPagesFile] = useState(null);
  const [additionalPagesState, setAdditionalPagesState] = useState({ status: "idle", message: "" });
  const [pdfAttachmentFile, setPdfAttachmentFile] = useState(null);
  const [pdfAttachmentState, setPdfAttachmentState] = useState({ status: "idle", message: "" });
  const [wordConformityDialogOpen, setWordConformityDialogOpen] = useState(false);
  const [standardConformityDialogOpen, setStandardConformityDialogOpen] = useState(false);
  const [wordRegenerateDialogOpen, setWordRegenerateDialogOpen] = useState(false);
  const [pendingWordCandidateCodF3, setPendingWordCandidateCodF3] = useState(null);
  const [quickConfirmState, setQuickConfirmState] = useState({ status: "idle", message: "" });
  const [incomingRefreshNonce, setIncomingRefreshNonce] = useState("");
  const articleTimersRef = useRef({});
  const articleSavedTimersRef = useRef({});
  const articleVersionsRef = useRef({});
  const latestArticleDraftRef = useRef({ descrizione: "", disegno: "" });
  const autoQuickConfirmAttemptRef = useRef("");

  function handleRequestError(requestError, fallbackMessage = "Errore richiesta") {
    const message = requestError.message || fallbackMessage;
    if (requestError.status === 401 || /invalid token/i.test(message)) {
      clearAuth();
      return "Sessione scaduta: effettua nuovamente il login.";
    }
    return message;
  }

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    apiRequest(quartaDetailApiPath(codOdp, { certificateId, candidateCodF3: selectedCandidateCodF3 }), {}, token)
      .then((response) => {
        if (!ignore) {
          setData(response);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(handleRequestError(requestError, "Errore caricamento certificato"));
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [codOdp, certificateId, selectedCandidateCodF3, token]);

  useEffect(() => {
    let ignore = false;
    apiRequest("/standards?stato=attivo", {}, token)
      .then((response) => {
        if (!ignore) {
          setStandards(response.items || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setStandards([]);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  useEffect(() => {
    let ignore = false;
    apiRequest("/customer-requirements", {}, token)
      .then((response) => {
        if (!ignore) {
          setCustomerRequirements(response.items || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setCustomerRequirements([]);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  useEffect(() => {
    if (!data?.cod_odp) {
      return;
    }
    const nextDraft = {
      descrizione: data.header?.descrizione || "",
      disegno: data.header?.disegno || "",
    };
    latestArticleDraftRef.current = nextDraft;
    setArticleDraft(nextDraft);
    setArticleStates({});
  }, [data?.cod_odp]);

  useEffect(
    () => () => {
      Object.values(articleTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
      Object.values(articleSavedTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
    },
    [],
  );

  useEffect(() => {
    if (!data?.cod_odp || !quickIncomingConfirmEnabled()) {
      return;
    }
    if (!data.quick_incoming_confirm_available || data.quick_incoming_confirm_applied) {
      return;
    }
    const signature = [
      data.cod_odp,
      data.header?.certificate_id || "",
      data.selected_standard?.id || "",
      data.conformity_status || "",
    ].join("|");
    if (autoQuickConfirmAttemptRef.current === signature) {
      return;
    }
    autoQuickConfirmAttemptRef.current = signature;
    void applyQuickIncomingConfirmation();
  }, [
    data?.cod_odp,
    data?.header?.certificate_id,
    data?.selected_standard?.id,
    data?.conformity_status,
    data?.quick_incoming_confirm_available,
    data?.quick_incoming_confirm_applied,
  ]);

  function confirmStandard(standardId) {
    setSavingStandardId(standardId);
    setStandardError("");
    apiRequest(
      `/quarta-taglio/${encodeURIComponent(codOdp)}/standard`,
      {
        method: "POST",
        body: JSON.stringify({ standard_id: standardId }),
      },
      token,
    )
      .then(async (response) => {
        let nextResponse =
          certificateId || selectedCandidateCodF3
            ? await apiRequest(quartaDetailApiPath(codOdp, { certificateId, candidateCodF3: selectedCandidateCodF3 }), {}, token)
            : response;
        if (
          quickIncomingConfirmEnabled() &&
          nextResponse.quick_incoming_confirm_available &&
          !nextResponse.quick_incoming_confirm_applied
        ) {
          setQuickConfirmState({ status: "saving", message: "Aggiornamento Incoming in corso..." });
          nextResponse = await applyQuickIncomingConfirmationRequest(nextResponse.header?.certificate_id || activeCertificateId);
          setQuickConfirmState({
            status: "saved",
            message: "Incoming aggiornato: chimica, proprietà e note confermate.",
          });
        }
        setData(nextResponse);
        if ((response.conformity_issues || []).length > 0) {
          setStandardConformityDialogOpen(true);
        }
      })
      .catch((requestError) => {
        setStandardError(handleRequestError(requestError, "Errore conferma standard"));
      })
      .finally(() => {
        setSavingStandardId(null);
      });
  }

  function setArticleState(field, nextState) {
    setArticleStates((current) => {
      if (!nextState) {
        const { [field]: _removed, ...rest } = current;
        return rest;
      }
      return { ...current, [field]: nextState };
    });
  }

  function clearArticleSavedFeedback(field, version) {
    window.clearTimeout(articleSavedTimersRef.current[field]);
    articleSavedTimersRef.current[field] = window.setTimeout(() => {
      if (articleVersionsRef.current[field] === version) {
        setArticleState(field, null);
      }
    }, ARTICLE_SAVED_FEEDBACK_MS);
  }

  function updateArticleDraftAndAutosave(field, value, delay = ARTICLE_AUTOSAVE_DELAY_MS) {
    const nextDraft = { ...latestArticleDraftRef.current, [field]: value };
    latestArticleDraftRef.current = nextDraft;
    setArticleDraft(nextDraft);
    queueArticleSave(field, value, delay);
  }

  function queueArticleSave(field, value, delay = ARTICLE_AUTOSAVE_DELAY_MS) {
    window.clearTimeout(articleTimersRef.current[field]);
    window.clearTimeout(articleSavedTimersRef.current[field]);
    const version = (articleVersionsRef.current[field] || 0) + 1;
    articleVersionsRef.current[field] = version;
    articleTimersRef.current[field] = window.setTimeout(() => {
      void saveArticleField(field, value, version);
    }, delay);
  }

  async function saveArticleField(field, value, version) {
    window.clearTimeout(articleTimersRef.current[field]);
    if (articleVersionsRef.current[field] !== version) {
      return;
    }
    setArticleState(field, { status: "saving" });
    setError("");
    try {
      const response = await apiRequest(
        `/quarta-taglio/${encodeURIComponent(codOdp)}/article-data`,
        {
          method: "PATCH",
          body: JSON.stringify({ [field]: value.trim() ? value : null }),
        },
        token,
      );
      if (articleVersionsRef.current[field] !== version) {
        return;
      }
      const nextResponse =
        certificateId || selectedCandidateCodF3
          ? await apiRequest(quartaDetailApiPath(codOdp, { certificateId, candidateCodF3: selectedCandidateCodF3 }), {}, token)
          : response;
      setData(nextResponse);
      const nextDraft = {
        descrizione: nextResponse.header?.descrizione || "",
        disegno: nextResponse.header?.disegno || "",
      };
      latestArticleDraftRef.current = nextDraft;
      setArticleDraft(nextDraft);
      setArticleState(field, { status: "saved" });
      clearArticleSavedFeedback(field, version);
    } catch (requestError) {
      if (articleVersionsRef.current[field] === version) {
        const message = handleRequestError(requestError, "Errore salvataggio automatico");
        setArticleState(field, { status: "error", message });
        setError(message);
      }
    }
  }

  function flushArticleField(field) {
    const value = latestArticleDraftRef.current[field] || "";
    queueArticleSave(field, value, 0);
  }

  function generateWordDraft(candidateCodF3 = activeCandidateCodF3) {
    const blockedReason =
      candidateCodF3 && codF3ExactKey(activeCodF3Candidate?.cod_f3) === codF3ExactKey(candidateCodF3) ? activeWordBlockedReason : "";
    if (!canCreateWord || blockedReason) {
      setWordDraftState({
        status: "error",
        message: blockedReason
          ? `Word non creabile: ${blockedReason}.`
          : wordCreationBlockers.length
          ? `Word non creabile: ${wordCreationBlockers.join("; ")}`
          : "Word non creabile: dati certificato non completi.",
      });
      return;
    }
    setPendingWordCandidateCodF3(candidateCodF3);
    if ((data?.conformity_issues || []).length > 0) {
      setWordConformityDialogOpen(true);
      return;
    }
    void performGenerateWordDraft(false, false, candidateCodF3);
  }

  async function performGenerateWordDraft(forceNonConforming = false, forceRegenerate = false, candidateCodF3 = pendingWordCandidateCodF3) {
    setWordDraftState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await apiRequest(
        `/quarta-taglio/${encodeURIComponent(codOdp)}/word-draft`,
        {
          method: "POST",
          body: JSON.stringify({
            force_non_conforming: forceNonConforming,
            force_regenerate: forceRegenerate,
            certificate_id: certificateId ? Number(certificateId) : null,
            candidate_cod_f3: candidateCodF3 || null,
          }),
        },
        token,
      );
      const link = document.createElement("a");
      link.href = resolveApiAssetUrl(response.download_url);
      link.download = response.file_name || `${codOdp}_bozza.docx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, { certificateId: response.id }), {}, token);
      setData(refreshed);
      navigate(quartaDetailUiPath(codOdp, { certificateId: response.id }), { replace: true });
      setPendingWordCandidateCodF3(null);
      setWordDraftState({ status: "saved", message: `Word certificato creato: ${response.draft_number}` });
    } catch (requestError) {
      setWordDraftState({
        status: "error",
        message: handleRequestError(requestError, "Errore generazione bozza Word"),
      });
    }
  }

  async function applyQuickIncomingConfirmationRequest(targetCertificateId = activeCertificateId) {
    const response = await apiRequest(
      targetCertificateId
        ? `/quarta-taglio/${encodeURIComponent(codOdp)}/quick-incoming-confirm?certificate_id=${encodeURIComponent(targetCertificateId)}`
        : `/quarta-taglio/${encodeURIComponent(codOdp)}/quick-incoming-confirm`,
      { method: "POST" },
      token,
    );
    setIncomingRefreshNonce(String(Date.now()));
    return response;
  }

  async function applyQuickIncomingConfirmation() {
    setQuickConfirmState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await applyQuickIncomingConfirmationRequest();
      setData(response);
      setQuickConfirmState({
        status: "saved",
        message: "Incoming aggiornato: chimica, proprietà e note confermate.",
      });
    } catch (requestError) {
      setQuickConfirmState({
        status: "error",
        message: handleRequestError(requestError, "Errore conferma rapida Incoming"),
      });
    }
  }

  function downloadCurrentWord() {
    if (!wordInfo.download_url) {
      return;
    }
    const link = document.createElement("a");
    link.href = resolveApiAssetUrl(wordInfo.download_url);
    link.download = `${codOdp}_word_corrente.docx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  async function downloadAdditionalPageTemplate() {
    setAdditionalPagesState({ status: "saving", message: "" });
    try {
      const blob = await fetchApiBlob("/api/quarta-taglio/additional-pages/template", token);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "modello_seconda_pagina_forgialluminio.docx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setAdditionalPagesState({ status: "saved", message: "Modello seconda pagina scaricato." });
    } catch (requestError) {
      setAdditionalPagesState({
        status: "error",
        message: handleRequestError(requestError, "Errore download modello seconda pagina"),
      });
    }
  }

  function regenerateWordFromScratch() {
    if (!hasWord) {
      generateWordDraft();
      return;
    }
    if (isManualWord) {
      setWordRegenerateDialogOpen(true);
      return;
    }
    void performGenerateWordDraft(false, true, null);
  }

  async function uploadEditedWord() {
    if (!wordUploadFile) {
      setWordUploadState({ status: "error", message: "Seleziona un file Word .docx da ricaricare." });
      return;
    }
    setWordUploadState({ status: "saving", message: "" });
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", wordUploadFile);
      const response = await apiRequest(
        activeCertificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/word-file?certificate_id=${encodeURIComponent(activeCertificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/word-file`,
        {
          method: "POST",
          body: formData,
        },
        token,
      );
      setWordUploadFile(null);
      const fileInput = document.getElementById("quarta-word-upload");
      if (fileInput) {
        fileInput.value = "";
      }
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, { certificateId, candidateCodF3: selectedCandidateCodF3 }), {}, token);
      setData(refreshed);
      setWordUploadState({ status: "saved", message: `Word ricaricato sul certificato ${response.draft_number}` });
    } catch (requestError) {
      setWordUploadState({
        status: "error",
        message: handleRequestError(requestError, "Errore caricamento Word modificato"),
      });
    }
  }

  async function uploadAdditionalPages() {
    if (!additionalPagesFile) {
      setAdditionalPagesState({ status: "error", message: "Seleziona un file Word .docx con le pagine aggiuntive." });
      return;
    }
    setAdditionalPagesState({ status: "saving", message: "" });
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", additionalPagesFile);
      const response = await apiRequest(
        activeCertificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/additional-pages?certificate_id=${encodeURIComponent(activeCertificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/additional-pages`,
        {
          method: "POST",
          body: formData,
        },
        token,
      );
      setAdditionalPagesFile(null);
      const fileInput = document.getElementById("quarta-additional-pages-upload");
      if (fileInput) {
        fileInput.value = "";
      }
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, { certificateId, candidateCodF3: selectedCandidateCodF3 }), {}, token);
      setData(refreshed);
      setAdditionalPagesState({
        status: "saved",
        message: `Pagine aggiuntive collegate al certificato ${response.draft_number}`,
      });
      setWordDraftState({ status: "saved", message: `Word completo aggiornato: ${response.draft_number}` });
    } catch (requestError) {
      setAdditionalPagesState({
        status: "error",
        message: handleRequestError(requestError, "Errore caricamento pagine aggiuntive"),
      });
    }
  }

  async function uploadPdfAttachment() {
    if (!pdfAttachmentFile) {
      setPdfAttachmentState({ status: "error", message: "Seleziona un PDF da allegare." });
      return;
    }
    setPdfAttachmentState({ status: "saving", message: "" });
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", pdfAttachmentFile);
      const response = await apiRequest(
        activeCertificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/pdf-attachments?certificate_id=${encodeURIComponent(activeCertificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/pdf-attachments`,
        {
          method: "POST",
          body: formData,
        },
        token,
      );
      setPdfAttachmentFile(null);
      const fileInput = document.getElementById("quarta-pdf-attachment-upload");
      if (fileInput) {
        fileInput.value = "";
      }
      setData(response);
      setPdfAttachmentState({ status: "saved", message: "PDF allegato e Word aggiornato." });
    } catch (requestError) {
      setPdfAttachmentState({
        status: "error",
        message: handleRequestError(requestError, "Errore caricamento allegato PDF"),
      });
    }
  }

  async function deletePdfAttachment(attachmentId) {
    setPdfAttachmentState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await apiRequest(
        activeCertificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/pdf-attachments/${encodeURIComponent(attachmentId)}?certificate_id=${encodeURIComponent(activeCertificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/pdf-attachments/${encodeURIComponent(attachmentId)}`,
        { method: "DELETE" },
        token,
      );
      setData(response);
      setPdfAttachmentState({ status: "saved", message: "Allegato PDF rimosso e Word aggiornato." });
    } catch (requestError) {
      setPdfAttachmentState({
        status: "error",
        message: handleRequestError(requestError, "Errore rimozione allegato PDF"),
      });
    }
  }

  function openCodF3Candidate(candidate) {
    setWordDraftState({ status: "idle", message: "" });
    if (candidate.certificate_id) {
      navigate(quartaDetailUiPath(codOdp, { certificateId: candidate.certificate_id }));
      return;
    }
    navigate(quartaDetailUiPath(codOdp, { candidateCodF3: candidate.cod_f3 }));
  }

  const standardDefinitionRows = useMemo(() => {
    const header = data?.header || {};
    return [
      ["Materiale fornito", header.materiale_fornito || "-"],
      ["Materiale / profilo raw", header.materiale_raw || "-"],
    ];
  }, [data]);
  const headerSummaryRows = useMemo(() => {
    const header = data?.header || {};
    const cdqList = Array.from(new Set((data?.materials || []).map((item) => item.cdq).filter(Boolean)));
    return [
      ["Certificato", header.numero_certificato || "Da assegnare"],
      ["Data", header.data_certificato || "-"],
      ["CDQ", cdqList.length ? cdqList.join(", ") : "-"],
      ["Colata", header.colata || "-"],
    ];
  }, [data]);
  const linkedIncomingRowIds = useMemo(
    () => Array.from(new Set((data?.materials || []).flatMap((item) => item.matching_row_ids || []))).filter(Boolean),
    [data],
  );
  const linkedIncomingPath = useMemo(() => {
    if (!linkedIncomingRowIds.length) {
      return "";
    }
    const query = new URLSearchParams();
    query.set("scope", "certificazione");
    query.set("ol", data?.cod_odp || codOdp || "");
    query.set("row_ids", linkedIncomingRowIds.join(","));
    if (incomingRefreshNonce) {
      query.set("refresh", incomingRefreshNonce);
    }
    query.set("returnTo", `${location.pathname}${location.search}${location.hash}`);
    return `/acquisition?${query.toString()}`;
  }, [codOdp, data?.cod_odp, incomingRefreshNonce, linkedIncomingRowIds, location.hash, location.pathname, location.search]);
  const materialByCdqColata = useMemo(() => {
    const map = new Map();
    (data?.materials || []).forEach((item) => {
      map.set(`${String(item.cdq || "").toLowerCase()}|${String(item.colata || "").toLowerCase()}`, item);
    });
    return map;
  }, [data?.materials]);

  function resolveIncomingPathForMissingItem(item) {
    const material = materialByCdqColata.get(`${String(item.cdq || "").toLowerCase()}|${String(item.colata || "").toLowerCase()}`);
    const rowIds = Array.from(new Set(material?.matching_row_ids || [])).filter(Boolean);
    if (rowIds.length < 2) {
      return "";
    }
    const query = new URLSearchParams();
    query.set("scope", "certificazione");
    query.set("mode", "resolve_row");
    query.set("ol", data?.cod_odp || codOdp || "");
    query.set("cdq", item.cdq || "");
    query.set("colata", item.colata || "");
    if (material?.qta_totale != null) {
      query.set("qta", String(material.qta_totale));
    }
    query.set("row_ids", rowIds.join(","));
    query.set("returnTo", `${location.pathname}${location.search}${location.hash}`);
    return `/acquisition?${query.toString()}`;
  }
  const codF3Candidates = data?.cod_f3_candidates || [];
  const rawCodF3Candidate = codF3Candidates.find((candidate) => candidate.relation === "raw") || null;
  const selectedCodF3Candidate =
    selectedCandidateCodF3
      ? codF3Candidates.find((candidate) => codF3ExactKey(candidate.cod_f3) === codF3ExactKey(selectedCandidateCodF3)) || null
      : null;
  const activeCodF3Candidate = certificateId ? null : selectedCodF3Candidate || rawCodF3Candidate;
  const activeCandidateCodF3 = activeCodF3Candidate?.cod_f3 || null;
  const codF3CandidateSummary = data?.cod_f3_candidate_summary || {};
  const visibleCodF3Candidates = codF3Candidates.filter((candidate) => candidate.confidence !== "review").slice(0, 25);
  const hiddenCodF3CandidateCount = Math.max((codF3CandidateSummary.count || 0) - visibleCodF3Candidates.length, 0);
  const headerFlowColumns = useMemo(() => {
    const header = data?.header || {};
    return [
      {
        title: "Cliente",
        rows: [
          ["Purchaser", header.cliente || ""],
          ["Order", header.ordine_cliente || ""],
          ["Confirm of order", header.conferma_ordine || ""],
        ],
      },
      {
        title: "Raw",
        rows: [
          ["Cod. F3 Raw", header.codice_f3_raw || ""],
          ["Drawing / Description Raw", header.descrizione_raw || ""],
          ["D.d.T.", header.ddt_raw || ""],
          ["Quantity", header.quantita_raw || ""],
        ],
      },
      {
        title: "Finished",
        rows: [
          ["Cod. F3 Finished", header.codice_f3_finished || ""],
          ["Drawing / Description Finished", header.descrizione_finished || ""],
          ["D.d.T.", header.ddt_finished || ""],
          ["Quantity", header.quantita_finished || ""],
        ],
      },
    ];
  }, [data]);
  const conformityIssues = data?.conformity_issues || [];
  const hasConformityIssues = conformityIssues.length > 0;
  const certificateNumber = data?.header?.numero_certificato;
  const hasCertificateNumber = Boolean(certificateNumber && certificateNumber !== "Da assegnare");
  const canCreateWord = Boolean(data?.can_create_word);
  const wordCreationBlockers = data?.word_creation_blockers || [];
  const standardConfirmationBlockers = data?.standard_confirmation_blockers || [];
  const canConfirmStandard = Boolean(data?.can_confirm_standard);
  const standardConfirmationBlockedMessage = standardConfirmationBlockers.join("; ");
  const wordInfo = activeCodF3Candidate && !activeCodF3Candidate.certificate_id
    ? { has_word: false, source_label: "Nessun Word per il CodF3 selezionato" }
    : data?.word_info || {};
  const pdfAttachments = data?.pdf_attachments || [];
  const isPdfFinal = Boolean(wordInfo.is_pdf_final || wordInfo.certificate_status === "pdf_final");
  const hasWord = Boolean(wordInfo.has_word && wordInfo.download_url);
  const activeCertificateId = certificateId || data?.header?.certificate_id || "";
  const isManualWord = wordInfo.source === "user_uploaded" || wordInfo.source === "fields_updated";
  const activeWordLabel = certificateId
    ? `${data?.header?.codice_f3 || "CodF3"}${certificateNumber ? ` - ${certificateNumber}` : ""}`
    : activeCodF3Candidate
      ? `${activeCodF3Candidate.cod_f3}${activeCodF3Candidate.relation === "raw" ? " - Raw" : ""}`
      : data?.header?.codice_f3 || "OL";
  const activeWordBlockedReason = activeCodF3Candidate?.blocked_reason || "";
  const canGenerateActiveWord = canCreateWord && !activeWordBlockedReason && !isPdfFinal;
  const customerRequirement = useMemo(
    () => findCustomerRequirementForCodF3(customerRequirements, data?.header?.codice_f3),
    [customerRequirements, data?.header?.codice_f3],
  );

  if (loading) {
    return <p className="text-sm text-slate-500">Caricamento certificato...</p>;
  }

  if (error) {
    return (
      <section className="space-y-3">
        <Link className="text-sm font-semibold text-accent hover:underline" to="/quarta-taglio">
          Torna a Certificazione
        </Link>
        <p className="text-sm text-rose-600">{error}</p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <Link className="text-sm font-semibold text-accent hover:underline" to="/quarta-taglio">
            Torna a Certificazione
          </Link>
          <p className="mt-3 text-sm uppercase tracking-[0.3em] text-slate-500">Certificato materiale</p>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-5 gap-y-2">
            <h2 className="text-2xl font-semibold text-slate-950">OL {data.cod_odp}</h2>
            {linkedIncomingPath ? (
              <Link
                className="inline-flex rounded-xl border border-sky-200 bg-sky-50 px-3 py-1.5 text-sm font-semibold text-sky-800 hover:bg-sky-100"
                to={linkedIncomingPath}
              >
                Apri righe Incoming
              </Link>
            ) : (
              <span className="inline-flex cursor-not-allowed rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-400">
                Nessuna riga Incoming
              </span>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
              {headerSummaryRows.map(([label, value]) => (
                <span className="inline-flex items-baseline gap-1.5" key={label}>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</span>
                  <span className="font-semibold text-slate-900">{value}</span>
                </span>
              ))}
            </div>
          </div>
          <p className="mt-1 text-sm text-slate-500">{data.status_message}</p>
        </div>
        <span className={`inline-flex w-fit rounded-lg border px-3 py-1.5 text-sm font-semibold ${statusClass(data.status_color)}`}>
          {STATUS_LABELS[data.status_color] || data.status_color}
        </span>
      </div>

      {quickConfirmState.message ? (
        <div
          className={`rounded-xl border px-4 py-2 text-sm font-medium ${
            quickConfirmState.status === "error"
              ? "border-rose-200 bg-rose-50 text-rose-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          {quickConfirmState.message}
        </div>
      ) : null}

      {customerRequirement ? (
        <Panel title="Requisiti cliente">
          <div className="overflow-x-auto rounded-xl border border-rose-200 bg-rose-50">
            <table className="w-full table-fixed border-collapse text-sm">
              <colgroup>
                {CUSTOMER_REQUIREMENT_FIELDS.map((field) => (
                  <col key={field.field} className="w-[92px]" />
                ))}
                <col />
              </colgroup>
              <thead className="bg-rose-50">
                <tr className="text-left text-[10px] font-semibold uppercase leading-4 tracking-[0.08em] text-rose-800">
                  {CUSTOMER_REQUIREMENT_FIELDS.map((field) => (
                    <th className="px-2 py-2 align-bottom" key={field.field}>
                      {field.label}
                    </th>
                  ))}
                  <th className="px-3 py-2 align-bottom">Note</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-rose-200 bg-rose-50/70">
                  {CUSTOMER_REQUIREMENT_FIELDS.map((field) => (
                    <td className="px-2 py-3 text-center" key={field.field}>
                      <input className="h-4 w-4 accent-rose-700" checked={Boolean(customerRequirement[field.field])} readOnly type="checkbox" />
                    </td>
                  ))}
                  <td className="px-3 py-3 text-sm font-medium text-rose-950">{customerRequirement.note || "-"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}

      {hasConformityIssues ? (
        <div className="rounded-2xl border-2 border-rose-300 bg-rose-50 px-5 py-4 text-rose-900 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose-100 text-xl font-black text-rose-700">
              !
            </div>
            <div>
              <h3 className="text-base font-bold">Non conformità standard</h3>
              <p className="mt-1 text-sm text-rose-800">
                Uno o più valori di chimica o proprietà non rispettano lo standard confermato.
              </p>
              <ul className="mt-3 space-y-1 text-sm font-semibold">
                {conformityIssues.map((issue) => (
                  <li key={`${issue.block}-${issue.field}`}>{formatConformityIssue(issue)}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4">
        <Panel className="mx-auto w-full xl:w-1/2 border-2 border-slate-950" title="Selezione Standard" titleClassName="text-xl font-semibold text-slate-900">
          <div className="mb-3 text-sm text-slate-700">
            {standardDefinitionRows.map(([label, value], index) => (
              <span key={label}>
                {index > 0 ? " · " : ""}
                <span>{label}:</span> <span className="font-semibold text-slate-900">{value}</span>
              </span>
            ))}
          </div>
          {data.selected_standard ? (
            <div
              className={`rounded-lg border px-3 py-2 text-sm ${
                data.selected_standard_confirmed
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              <div className="font-semibold">{data.selected_standard.label}</div>
              <div className="mt-1 text-xs">
                {data.selected_standard_confirmed ? "Standard confermato per questo OL." : "Scelta proposta: confermare prima della generazione."}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Standard non scelto automaticamente: serve conferma utente.
            </div>
          )}
          {standardError ? <div className="mt-2 text-sm text-rose-600">{standardError}</div> : null}
          {!canConfirmStandard && standardConfirmationBlockers.length ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
              Standard non confermabile: {standardConfirmationBlockedMessage}
            </div>
          ) : null}
          {data.quick_incoming_confirm_warning ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
              {data.quick_incoming_confirm_warning}
            </div>
          ) : null}
          <div className="mt-3 space-y-2">
            {(data.standard_candidates || []).map((candidate) => (
              <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm" key={candidate.id}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-slate-900">{candidate.label}</span>
                  <span className="text-xs font-semibold uppercase text-slate-500">{candidate.confidence}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{candidate.reasons.join(" · ") || candidate.code}</div>
                <button
                  className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={
                    savingStandardId !== null ||
                    !canConfirmStandard ||
                    (data.selected_standard_confirmed && data.selected_standard?.id === candidate.id)
                  }
                  onClick={() => confirmStandard(candidate.id)}
                  title={!canConfirmStandard ? standardConfirmationBlockedMessage : undefined}
                  type="button"
                >
                  {data.selected_standard_confirmed && data.selected_standard?.id === candidate.id
                    ? "Confermato"
                    : savingStandardId === candidate.id
                      ? "Salvataggio..."
                      : "Conferma standard"}
                </button>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="manual-standard">
              Conferma manuale
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                className="min-w-0 flex-1 rounded-lg border border-border bg-white px-3 py-2 text-sm text-slate-700"
                id="manual-standard"
                onChange={(event) => setManualStandardId(event.target.value)}
                value={manualStandardId}
              >
                <option value="">Scegli standard</option>
                {standards.map((standard) => (
                  <option key={standard.id} value={standard.id}>
                    {standardLabel(standard)}
                  </option>
                ))}
              </select>
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!manualStandardId || savingStandardId !== null || !canConfirmStandard}
                onClick={() => confirmStandard(Number(manualStandardId))}
                title={!canConfirmStandard ? standardConfirmationBlockedMessage : undefined}
                type="button"
              >
                {savingStandardId === Number(manualStandardId) ? "Salvataggio..." : "Conferma"}
              </button>
            </div>
          </div>
        </Panel>
      </div>

      <div className="rounded-xl border-2 border-slate-950 bg-white p-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-xl font-semibold text-slate-900">Certificati Word per Lavorazione</h3>
          <p className="mt-1 text-sm font-semibold text-slate-900">Certificato attivo: {activeWordLabel}</p>
          <p className="mt-1 text-sm text-slate-600">
            {isPdfFinal
              ? "Certificato PDF chiuso. Il Word resta consultabile, ma non modificabile da questa pagina."
              : canCreateWord
              ? "Certificato creabile: standard e righe Incoming sono pronti. Se manca la data DDT, resterà come campo mancante."
              : "Serve standard confermato e righe Incoming accettate o accettate con riserva."}
          </p>
          {isPdfFinal ? (
            <div className="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900">
              Per correzioni riaprire il certificato dal Registro certificazione.
            </div>
          ) : null}
          {activeWordBlockedReason ? (
            <p className="mt-1 text-sm font-semibold text-amber-700">{activeWordBlockedReason}</p>
          ) : null}
          {!canCreateWord && wordCreationBlockers.length ? (
            <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <div className="font-semibold uppercase tracking-[0.14em]">Blocchi creazione Word</div>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {wordCreationBlockers.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {wordDraftState.message ? (
            <p className={`mt-1 text-sm ${wordDraftState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {wordDraftState.message}
            </p>
          ) : null}
          {wordUploadState.message ? (
            <p className={`mt-1 text-sm ${wordUploadState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {wordUploadState.message}
            </p>
          ) : null}
          {additionalPagesState.message ? (
            <p className={`mt-1 text-sm ${additionalPagesState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {additionalPagesState.message}
            </p>
          ) : null}
          {pdfAttachmentState.message ? (
            <p className={`mt-1 text-sm ${pdfAttachmentState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {pdfAttachmentState.message}
            </p>
          ) : null}
          <span className={`mt-3 inline-flex w-fit rounded-lg border px-3 py-1 text-xs font-semibold ${conformityClass(data.conformity_status)}`}>
            Conformità standard: {conformityLabel(data.conformity_status)}
          </span>
          <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${wordInfoPanelClass(wordInfo)}`}>
            <div className="font-semibold uppercase tracking-[0.16em] text-current opacity-70">Word corrente</div>
            <p className="mt-1">
              {wordInfo.source_label || "Nessun Word"}
              {wordInfo.original_filename ? `: ${wordInfo.original_filename}` : ""}
            </p>
            {hasWord ? (
              <p className={`mt-1 font-semibold ${wordInfo.content_controls_ok ? "text-emerald-700" : "text-amber-700"}`}>
                Content controls: {wordInfo.content_controls_ok ? "OK" : `mancano ${(wordInfo.content_controls_missing || []).join(", ")}`}
              </p>
            ) : null}
            {isPdfFinal ? <p className="mt-1 font-semibold text-sky-700">PDF chiuso</p> : null}
          </div>
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <div className="font-semibold uppercase tracking-[0.16em] text-slate-500">Pagine aggiuntive</div>
            {data.additional_pages ? (
              <p className="mt-1">
                {data.additional_pages.is_inherited ? "Ereditate" : "Specifiche"} da certificato{" "}
                <span className="font-semibold text-slate-800">{data.additional_pages.certificate_number}</span>
                {data.additional_pages.is_inherited && data.additional_pages.inherited_from_cod_f3
                  ? `, CodF3 ${data.additional_pages.inherited_from_cod_f3}`
                  : ""}
                {data.additional_pages.original_filename ? `: ${data.additional_pages.original_filename}` : ""}.
              </p>
            ) : (
              <p className="mt-1">
                Nessuna pagina aggiuntiva caricata. Le pagine successive devono essere senza operatore e con Quality Manager.
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-2 md:min-w-[360px]">
          {hasWord ? (
            <button
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-dark"
              onClick={downloadCurrentWord}
              type="button"
            >
              Scarica Word corrente
            </button>
          ) : (
            <button
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={wordDraftState.status === "saving" || !canGenerateActiveWord}
              onClick={() => generateWordDraft()}
              type="button"
            >
              {wordDraftState.status === "saving"
                ? "Creazione..."
                : activeCodF3Candidate
                  ? `Genera Word ${activeCodF3Candidate.relation === "raw" ? "Raw" : activeCodF3Candidate.cod_f3}`
                  : "Genera Word"}
            </button>
          )}
          {isPdfFinal && wordInfo.pdf_download_url ? (
            <a
              className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-center text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100"
              href={resolveApiAssetUrl(wordInfo.pdf_download_url)}
              rel="noreferrer"
              target="_blank"
            >
              Scarica PDF chiuso
            </a>
          ) : null}
          <div className="grid grid-cols-1 gap-2">
            <button
              className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-700 transition hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPdfFinal || wordDraftState.status === "saving" || !canGenerateActiveWord || !hasWord}
              onClick={regenerateWordFromScratch}
              type="button"
            >
              Rigenera da zero
            </button>
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
            <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-word-upload">
              Ricarica Word modificato
            </label>
            <div className="flex gap-2">
              <input
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                disabled={isPdfFinal || !hasWord || !activeCertificateId}
                id="quarta-word-upload"
                onChange={(event) => setWordUploadFile(event.target.files?.[0] || null)}
                type="file"
              />
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isPdfFinal || wordUploadState.status === "saving" || !wordUploadFile || !hasWord || !activeCertificateId}
                onClick={uploadEditedWord}
                type="button"
              >
                {wordUploadState.status === "saving" ? "Carico..." : "Carica"}
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-sky-100 bg-sky-50/60 p-2">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-additional-pages-upload">
                Carica pagine aggiuntive
              </label>
              <button
                className="w-fit rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-700 transition hover:border-sky-500 hover:text-sky-900"
                onClick={downloadAdditionalPageTemplate}
                type="button"
              >
                Scarica modello seconda pagina
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Il file caricato diventa specifico per questo numero certificato. Se il Word corrente è manuale, aggiungi o togli pagine in Word e ricaricalo.
            </p>
            <div className="flex gap-2">
              <input
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                disabled={isPdfFinal || !hasCertificateNumber || !activeCertificateId || isManualWord}
                id="quarta-additional-pages-upload"
                onChange={(event) => setAdditionalPagesFile(event.target.files?.[0] || null)}
                type="file"
              />
              <button
                className="rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-700 transition hover:border-sky-500 hover:text-sky-900 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isPdfFinal || additionalPagesState.status === "saving" || !additionalPagesFile || !hasCertificateNumber || !activeCertificateId || isManualWord}
                onClick={uploadAdditionalPages}
                type="button"
              >
                {additionalPagesState.status === "saving" ? "Carico..." : "Carica"}
              </button>
            </div>
            {isPdfFinal ? <p className="text-xs text-sky-700">PDF chiuso: le modifiche Word sono bloccate.</p> : null}
            {!hasCertificateNumber ? <p className="text-xs text-amber-700">Genera prima il Word numerato.</p> : null}
            {isManualWord ? <p className="text-xs text-amber-700">Word manuale corrente: gestisci le pagine in Word e ricarica il file.</p> : null}
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-2">
            <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-pdf-attachment-upload">
              Allegati PDF
            </label>
            <p className="text-xs text-slate-500">Ogni PDF viene inserito intero in coda al Word.</p>
            <div className="flex gap-2">
              <input
                accept=".pdf,application/pdf"
                className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                disabled={isPdfFinal || !hasCertificateNumber || !activeCertificateId || isManualWord}
                id="quarta-pdf-attachment-upload"
                onChange={(event) => setPdfAttachmentFile(event.target.files?.[0] || null)}
                type="file"
              />
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isPdfFinal || pdfAttachmentState.status === "saving" || !pdfAttachmentFile || !hasCertificateNumber || !activeCertificateId || isManualWord}
                onClick={uploadPdfAttachment}
                type="button"
              >
                {pdfAttachmentState.status === "saving" ? "Carico..." : "Carica"}
              </button>
            </div>
            {pdfAttachments.length ? (
              <div className="space-y-1">
                {pdfAttachments.map((attachment) => (
                  <div
                    className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700"
                    key={attachment.id}
                  >
                    <span className="min-w-0 truncate font-semibold">{attachment.original_filename}</span>
                    <button
                      className="shrink-0 rounded-lg border border-rose-200 bg-white px-2 py-1 font-semibold text-rose-700 transition hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={isPdfFinal || pdfAttachmentState.status === "saving" || isManualWord}
                      onClick={() => deletePdfAttachment(attachment.id)}
                      type="button"
                    >
                      Rimuovi
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">Nessun allegato PDF.</p>
            )}
            {isManualWord ? <p className="text-xs text-amber-700">Word manuale corrente: gestisci gli allegati in Word e ricarica il file.</p> : null}
          </div>
        </div>
        </div>
        {codF3CandidateSummary.count ? (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <h3 className="text-xl font-semibold text-slate-900">Seleziona Lavorazioni - finitura: CODF3</h3>
            {codF3CandidateSummary.status === "review" && hiddenCodF3CandidateCount > 0 ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {codF3CandidateSummary.message || "CodF3 candidati da verificare."}
                <span className="ml-2 font-semibold">{codF3CandidateSummary.label}</span>
              </div>
            ) : null}
            {visibleCodF3Candidates.length ? (
              <div className="mt-3 grid gap-2 xl:grid-cols-2">
                {visibleCodF3Candidates.map((candidate) => {
                  const canOpenCandidate = candidate.confidence !== "review";
                  const isActiveCandidate =
                    (certificateId && String(candidate.certificate_id || "") === String(certificateId)) ||
                    (!certificateId && activeCodF3Candidate && codF3ExactKey(activeCodF3Candidate.cod_f3) === codF3ExactKey(candidate.cod_f3));
                  const candidateActionLabel = candidate.certificate_id ? "Apri" : isActiveCandidate ? "Selezionato" : "Seleziona";
                  return (
                    <div
                      className={`rounded-xl border px-3 py-3 ${codF3CandidateCardClass(candidate, isActiveCandidate)}`}
                      key={candidate.cod_f3}
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-slate-950">{candidate.cod_f3}</span>
                            <span className={`rounded-lg border px-2 py-0.5 text-[11px] font-semibold ${codF3CandidateStatusClass(candidate)}`}>
                              {codF3CandidateLabel(candidate)}
                            </span>
                          </div>
                          <p className="mt-1 break-words text-sm text-slate-700">{candidate.des_f3 || "-"}</p>
                          {candidate.message ? <p className="mt-1 text-xs text-slate-500">{candidate.message}</p> : null}
                          {candidate.reasons?.length ? (
                            <p className="mt-1 text-xs text-slate-500">{candidate.reasons.join(" · ")}</p>
                          ) : null}
                        </div>
                        <button
                          className="w-fit shrink-0 rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-700 transition hover:border-sky-500 hover:text-sky-900 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={!canOpenCandidate}
                          onClick={() => openCodF3Candidate(candidate)}
                          type="button"
                        >
                          {candidateActionLabel}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Nessun CodF3 preparabile automaticamente. Attendere DDT o verifica manuale.</p>
            )}
          </div>
        ) : null}
      </div>

      {!data.ready ? (
        <Panel title="Blocchi / dati mancanti">
          <Table
            columns={["Ambito", "Riferimento", "Stato", "Cosa manca"]}
            rows={(data.missing_items || []).map((item) => {
              const resolvePath = resolveIncomingPathForMissingItem(item);
              const isEsolverBlock = String(item.cdq || "").toLowerCase().includes("esolver");
              const ambito = isEsolverBlock ? "eSolver/DDT" : "Incoming/CDQ";
              const riferimento = isEsolverBlock ? data.cod_odp || codOdp || "-" : [item.cdq, item.colata ? `colata ${item.colata}` : ""].filter(Boolean).join(" - ");
              return [
                <span className="font-semibold text-slate-800" key="scope">{ambito}</span>,
                riferimento || "-",
                <StatusPill key="status" status={item.status_color} />,
                <div className="space-y-2" key="details">
                  <div className="font-medium">{item.message}</div>
                  {(item.details || []).map((detail) => (
                    <div className="text-xs text-slate-500" key={detail}>
                      {detail}
                    </div>
                  ))}
                  {resolvePath ? (
                    <Link
                      className="inline-flex rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-800 hover:bg-sky-50"
                      to={resolvePath}
                    >
                      Risolvi in Incoming
                    </Link>
                  ) : null}
                </div>,
              ];
            })}
            emptyText="Nessun blocco tecnico rilevato."
          />
        </Panel>
      ) : null}

      <section className="rounded-2xl border-2 border-slate-950 bg-white p-4 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-900">Certificato Materiale</h2>
        <div className="mt-4 space-y-4">
          <Panel title="Header Certificato" titleClassName="text-xl font-semibold text-slate-900">
            <div className="rounded-lg border border-slate-200 bg-white text-sm text-slate-800">
              <div className="grid divide-y divide-slate-200 md:grid-cols-3 md:divide-x md:divide-y-0">
                {headerFlowColumns.map((column) => (
                  <div className="min-w-0" key={column.title}>
                    <div className="bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">{column.title}</div>
                    <div className="divide-y divide-slate-100">
                      {column.rows.map(([label, value]) => (
                        <div className="px-3 py-2" key={label}>
                          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
                          <div className="mt-1 min-h-[18px] break-words font-medium text-sky-700">{value || ""}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Chimica">
              <ValueTable numberDigits={3} values={data.chemistry || []} />
            </Panel>

            <div className="space-y-4">
              <Panel title="Proprietà">
                <ValueTable numberDigits={2} values={data.properties || []} />
              </Panel>
              <Panel title="Note">
                <Table
                  columns={["Nota", "Valore", "Stato", "Messaggio"]}
                  rows={(data.notes || []).map((item) => [item.label, item.value || "-", <StatusPill key="status" status={item.status} />, item.message])}
                />
              </Panel>
            </div>
          </div>
        </div>
      </section>

      {wordConformityDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-xl rounded-2xl border-2 border-rose-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-2xl font-black text-rose-700">
                !
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-950">Creare il Word con non conformità?</h3>
                <p className="mt-2 text-sm text-slate-600">
                  Il numero certificato verrà assegnato ora. Sono presenti valori fuori standard:
                </p>
                <ul className="mt-3 max-h-44 space-y-1 overflow-y-auto text-sm font-semibold text-rose-800">
                  {conformityIssues.map((issue) => (
                    <li key={`${issue.block}-${issue.field}-dialog`}>{formatConformityIssue(issue)}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
                onClick={() => {
                  setWordConformityDialogOpen(false);
                  setPendingWordCandidateCodF3(null);
                }}
                type="button"
              >
                Torna a controllare
              </button>
              <button
                className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-800"
                onClick={() => {
                  setWordConformityDialogOpen(false);
                  void performGenerateWordDraft(true);
                }}
                type="button"
              >
                Crea comunque Word numerato
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {standardConformityDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-xl rounded-2xl border-2 border-rose-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-2xl font-black text-rose-700">
                !
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-950">Standard non conforme</h3>
                <p className="mt-2 text-sm text-slate-600">
                  Lo standard confermato porta questi valori fuori limite:
                </p>
                <ul className="mt-3 max-h-44 space-y-1 overflow-y-auto text-sm font-semibold text-rose-800">
                  {conformityIssues.map((issue) => (
                    <li key={`${issue.block}-${issue.field}-standard-dialog`}>{formatConformityIssue(issue)}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-800"
                onClick={() => setStandardConformityDialogOpen(false)}
                type="button"
              >
                Ho capito
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {wordRegenerateDialogOpen ? (
        <ConfirmActionDialog
          confirmLabel="Rigenera da zero"
          message="Il Word corrente è stato caricato o modificato dall'utente. Rigenerando da zero perderai quelle modifiche manuali."
          onCancel={() => setWordRegenerateDialogOpen(false)}
          onConfirm={() => {
            setWordRegenerateDialogOpen(false);
            void performGenerateWordDraft(false, true, null);
          }}
          title="Rigenerare il Word?"
        />
      ) : null}
    </section>
  );
}

function ConfirmActionDialog({ confirmLabel, message, onCancel, onConfirm, title }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xl font-black text-amber-700">
            !
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-950">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
            onClick={onCancel}
            type="button"
          >
            Annulla
          </button>
          <button
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700"
            onClick={onConfirm}
            type="button"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function Panel({ title, children, className = "", titleClassName = "text-sm font-semibold uppercase tracking-[0.16em] text-slate-500" }) {
  return (
    <div className={`rounded-xl border border-border bg-white p-4 ${className}`}>
      <h3 className={titleClassName}>{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function EditableArticleField({ label, onBlur, onChange, origin, proposal, state, title, value, warning }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</label>
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
          {state?.status === "saving" ? "salvataggio" : state?.status === "saved" ? "salvato" : origin === "utente" ? "utente" : "quarta"}
        </span>
      </div>
      <input
        className={`mt-1 w-full rounded-lg border px-2 py-1.5 text-sm font-medium ${articleFieldClass(state?.status)}`}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
        title={title}
        value={value || ""}
      />
      {warning ? <div className="mt-1 text-xs text-amber-700">Valore salvato diverso dalla proposta Quarta.</div> : null}
      {proposal && origin === "utente" ? <div className="mt-1 truncate text-xs text-slate-500">Quarta: {proposal}</div> : null}
    </div>
  );
}

function Table({ columns, rows, emptyText = "Nessun dato." }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {columns.map((column) => (
              <th className="px-3 py-2.5" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length ? (
            rows.map((row, index) => (
              <tr className="align-top" key={index}>
                {row.map((cell, cellIndex) => (
                  <td className="px-3 py-2.5 text-slate-700" key={cellIndex}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td className="px-3 py-4 text-slate-500" colSpan={columns.length}>
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ValueTable({ numberDigits = 4, values }) {
  return (
    <Table
      columns={["Campo", "Valore", "Metodo", "Standard", "Stato", "Messaggio"]}
      rows={values.map((item) => [
        item.field,
        formatNumber(item.value, numberDigits),
        METHOD_LABELS[item.method] || item.method,
        item.standard_label || formatLimit(item.standard_min, item.standard_max, numberDigits),
        <StatusPill key="status" status={item.status} />,
        item.message || "-",
      ])}
    />
  );
}

function StatusPill({ status }) {
  return <span className={`inline-flex rounded-lg border px-2 py-1 text-xs font-semibold ${statusClass(status)}`}>{STATUS_LABELS[status] || status}</span>;
}
