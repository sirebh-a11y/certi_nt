import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { apiRequest, resolveApiAssetUrl } from "../../app/api";
import { useAuth } from "../../app/auth";

const STATUS_CLASSES = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  yellow: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  missing: "border-amber-200 bg-amber-50 text-amber-800",
  missing_from_supplier: "border-rose-200 bg-rose-50 text-rose-800",
  different: "border-amber-200 bg-amber-50 text-amber-800",
  out_of_range: "border-rose-200 bg-rose-50 text-rose-800",
  not_in_standard: "border-rose-200 bg-rose-50 text-rose-800",
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

function quartaDetailApiPath(codOdp, certificateId) {
  const basePath = `/quarta-taglio/${encodeURIComponent(codOdp)}`;
  return certificateId ? `${basePath}?certificate_id=${encodeURIComponent(certificateId)}` : basePath;
}

function codF3MatchKey(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length <= 2) {
    return "";
  }
  return digits.slice(0, -2);
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
  const [wordFieldsState, setWordFieldsState] = useState({ status: "idle", message: "" });
  const [additionalPagesFile, setAdditionalPagesFile] = useState(null);
  const [additionalPagesState, setAdditionalPagesState] = useState({ status: "idle", message: "" });
  const [wordConformityDialogOpen, setWordConformityDialogOpen] = useState(false);
  const [standardConformityDialogOpen, setStandardConformityDialogOpen] = useState(false);
  const [wordRegenerateDialogOpen, setWordRegenerateDialogOpen] = useState(false);
  const [quickConfirmEnabled, setQuickConfirmEnabled] = useState(false);
  const [quickConfirmState, setQuickConfirmState] = useState({ status: "idle", message: "" });
  const articleTimersRef = useRef({});
  const articleSavedTimersRef = useRef({});
  const articleVersionsRef = useRef({});
  const latestArticleDraftRef = useRef({ descrizione: "", disegno: "" });

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
    apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token)
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
  }, [codOdp, certificateId, token]);

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
        const nextResponse = certificateId ? await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token) : response;
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
      const nextResponse = certificateId ? await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token) : response;
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

  function generateWordDraft() {
    if (!canCreateWord) {
      setWordDraftState({
        status: "error",
        message: wordCreationBlockers.length
          ? `Word non creabile: ${wordCreationBlockers.join("; ")}`
          : "Word non creabile: dati certificato non completi.",
      });
      return;
    }
    if ((data?.conformity_issues || []).length > 0) {
      setWordConformityDialogOpen(true);
      return;
    }
    void performGenerateWordDraft(false);
  }

  async function performGenerateWordDraft(forceNonConforming = false, forceRegenerate = false) {
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
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token);
      setData(refreshed);
      setWordDraftState({ status: "saved", message: `Word certificato creato: ${response.draft_number}` });
    } catch (requestError) {
      setWordDraftState({
        status: "error",
        message: handleRequestError(requestError, "Errore generazione bozza Word"),
      });
    }
  }

  async function applyQuickIncomingConfirmation() {
    if (!quickConfirmEnabled) {
      return;
    }
    setQuickConfirmState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await apiRequest(
        certificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/quick-incoming-confirm?certificate_id=${encodeURIComponent(certificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/quick-incoming-confirm`,
        { method: "POST" },
        token,
      );
      setData(response);
      setQuickConfirmState({ status: "saved", message: "Incoming aggiornato: chimica e proprietà confermate." });
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

  async function updateWordFields() {
    if (!hasWord) {
      setWordFieldsState({ status: "error", message: "Genera o ricarica prima un Word corrente." });
      return;
    }
    setWordFieldsState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await apiRequest(
        certificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/word-fields?certificate_id=${encodeURIComponent(certificateId)}`
          : `/quarta-taglio/${encodeURIComponent(codOdp)}/word-fields`,
        { method: "POST" },
        token,
      );
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token);
      setData(refreshed);
      setWordFieldsState({ status: "saved", message: `Campi Word aggiornati: ${response.draft_number}` });
    } catch (requestError) {
      setWordFieldsState({
        status: "error",
        message: handleRequestError(requestError, "Errore aggiornamento campi Word"),
      });
    }
  }

  function regenerateWordFromScratch() {
    if (isManualWord) {
      setWordRegenerateDialogOpen(true);
      return;
    }
    void performGenerateWordDraft(false, true);
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
        certificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/word-file?certificate_id=${encodeURIComponent(certificateId)}`
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
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token);
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
        certificateId
          ? `/quarta-taglio/${encodeURIComponent(codOdp)}/additional-pages?certificate_id=${encodeURIComponent(certificateId)}`
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
      const refreshed = await apiRequest(quartaDetailApiPath(codOdp, certificateId), {}, token);
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

  const headerRows = useMemo(() => {
    const header = data?.header || {};
    return [
      ["Certificato", header.numero_certificato || "Da assegnare"],
      ["Data certificato", header.data_certificato || "-"],
      ["Colata", header.colata || "-"],
      ["Materiale fornito", header.materiale_fornito || "-"],
      ["Materiale / profilo raw", header.materiale_raw || "-"],
    ];
  }, [data]);
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
  const wordInfo = data?.word_info || {};
  const hasWord = Boolean(wordInfo.has_word && wordInfo.download_url);
  const isManualWord = wordInfo.source === "user_uploaded" || wordInfo.source === "fields_updated";
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
          <h2 className="mt-1 text-2xl font-semibold text-slate-950">OL {data.cod_odp}</h2>
          <p className="mt-1 text-sm text-slate-500">{data.status_message}</p>
        </div>
        <span className={`inline-flex w-fit rounded-lg border px-3 py-1.5 text-sm font-semibold ${statusClass(data.status_color)}`}>
          {STATUS_LABELS[data.status_color] || data.status_color}
        </span>
      </div>

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

      <div className="flex flex-col gap-2 rounded-xl border border-border bg-white p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Word certificato</h3>
          <p className="mt-1 text-sm text-slate-600">
            {canCreateWord
              ? "Certificato creabile: standard e righe Incoming sono pronti. Se manca la data DDT, resterà come campo mancante."
              : "Serve standard confermato e righe Incoming accettate o accettate con riserva."}
          </p>
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
          {wordFieldsState.message ? (
            <p className={`mt-1 text-sm ${wordFieldsState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {wordFieldsState.message}
            </p>
          ) : null}
          {additionalPagesState.message ? (
            <p className={`mt-1 text-sm ${additionalPagesState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
              {additionalPagesState.message}
            </p>
          ) : null}
          <span className={`mt-3 inline-flex w-fit rounded-lg border px-3 py-1 text-xs font-semibold ${conformityClass(data.conformity_status)}`}>
            Conformità standard: {conformityLabel(data.conformity_status)}
          </span>
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <div className="font-semibold uppercase tracking-[0.16em] text-slate-500">Word corrente</div>
            <p className="mt-1">
              {wordInfo.source_label || "Nessun Word"}
              {wordInfo.original_filename ? `: ${wordInfo.original_filename}` : ""}
            </p>
            {hasWord ? (
              <p className={`mt-1 font-semibold ${wordInfo.content_controls_ok ? "text-emerald-700" : "text-amber-700"}`}>
                Content controls: {wordInfo.content_controls_ok ? "OK" : `mancano ${(wordInfo.content_controls_missing || []).join(", ")}`}
              </p>
            ) : null}
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
              disabled={wordDraftState.status === "saving" || !canCreateWord}
              onClick={generateWordDraft}
              type="button"
            >
              {wordDraftState.status === "saving" ? "Creazione..." : "Genera Word"}
            </button>
          )}
          <div className="grid grid-cols-2 gap-2">
            <button
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!hasWord || wordFieldsState.status === "saving"}
              onClick={updateWordFields}
              type="button"
            >
              {wordFieldsState.status === "saving" ? "Aggiorno..." : "Aggiorna campi Word"}
            </button>
            <button
              className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-700 transition hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={wordDraftState.status === "saving" || !canCreateWord}
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
                id="quarta-word-upload"
                onChange={(event) => setWordUploadFile(event.target.files?.[0] || null)}
                type="file"
              />
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={wordUploadState.status === "saving" || !wordUploadFile}
                onClick={uploadEditedWord}
                type="button"
              >
                {wordUploadState.status === "saving" ? "Carico..." : "Carica"}
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-sky-100 bg-sky-50/60 p-2">
            <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="quarta-additional-pages-upload">
              Carica pagine aggiuntive
            </label>
            <p className="text-xs text-slate-500">
              Il file caricato diventa specifico per questo numero certificato. Se il Word corrente è manuale, aggiungi o togli pagine in Word e ricaricalo.
            </p>
            <div className="flex gap-2">
              <input
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                disabled={!hasCertificateNumber || isManualWord}
                id="quarta-additional-pages-upload"
                onChange={(event) => setAdditionalPagesFile(event.target.files?.[0] || null)}
                type="file"
              />
              <button
                className="rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-700 transition hover:border-sky-500 hover:text-sky-900 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={additionalPagesState.status === "saving" || !additionalPagesFile || !hasCertificateNumber || isManualWord}
                onClick={uploadAdditionalPages}
                type="button"
              >
                {additionalPagesState.status === "saving" ? "Carico..." : "Carica"}
              </button>
            </div>
            {!hasCertificateNumber ? <p className="text-xs text-amber-700">Genera prima il Word numerato.</p> : null}
            {isManualWord ? <p className="text-xs text-amber-700">Word manuale corrente: gestisci le pagine in Word e ricarica il file.</p> : null}
          </div>
        </div>
      </div>

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

      {!data.ready ? (
        <Panel title="Dati ancora mancanti">
          <Table
            columns={["CDQ", "Colata", "Stato", "Cosa manca"]}
            rows={(data.missing_items || []).map((item) => [
              item.cdq,
              item.colata || "-",
              <StatusPill key="status" status={item.status_color} />,
              <div className="space-y-1" key="details">
                <div className="font-medium">{item.message}</div>
                {(item.details || []).map((detail) => (
                  <div className="text-xs text-slate-500" key={detail}>
                    {detail}
                  </div>
                ))}
              </div>,
            ])}
            emptyText="Nessun blocco tecnico rilevato."
          />
        </Panel>
      ) : null}

      <Panel title="Dati importanti">
        <div className="grid gap-2 md:grid-cols-4 xl:grid-cols-8">
          {headerRows.map(([label, value]) => (
            <div
              className={`rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 ${
                label === "Materiale / profilo raw" ? "md:col-span-2 xl:col-span-4" : ""
              }`}
              key={label}
            >
              <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
              <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2 xl:items-stretch">
        <Panel className="h-full" title="Header Word">
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

        <Panel className="h-full" title="Standard">
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
          {data.quick_incoming_confirm_warning ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
              {data.quick_incoming_confirm_warning}
            </div>
          ) : null}
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <input
                  checked={quickConfirmEnabled}
                  className="h-4 w-4 accent-accent"
                  onChange={(event) => setQuickConfirmEnabled(event.target.checked)}
                  type="checkbox"
                />
                Conferma rapida Incoming
              </label>
              <button
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!quickConfirmEnabled || !data.quick_incoming_confirm_available || quickConfirmState.status === "saving"}
                onClick={applyQuickIncomingConfirmation}
                type="button"
              >
                {quickConfirmState.status === "saving" ? "Confermo..." : "Applica"}
              </button>
            </div>
            {quickConfirmState.message ? (
              <p className={`mt-2 text-xs ${quickConfirmState.status === "error" ? "text-rose-600" : "text-emerald-700"}`}>
                {quickConfirmState.message}
              </p>
            ) : null}
            {quickConfirmEnabled && !data.quick_incoming_confirm_available ? (
              <div className="mt-2 space-y-1 text-xs text-amber-800">
                {(data.quick_incoming_confirm_blockers || []).map((item) => (
                  <div key={item}>{item}</div>
                ))}
              </div>
            ) : null}
            {data.quick_incoming_confirm_applied ? (
              <p className="mt-2 text-xs text-slate-500">Conferma rapida già applicata ad almeno una riga Incoming collegata.</p>
            ) : null}
          </div>
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
                  disabled={savingStandardId !== null || (data.selected_standard_confirmed && data.selected_standard?.id === candidate.id)}
                  onClick={() => confirmStandard(candidate.id)}
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
                disabled={!manualStandardId || savingStandardId !== null}
                onClick={() => confirmStandard(Number(manualStandardId))}
                type="button"
              >
                {savingStandardId === Number(manualStandardId) ? "Salvataggio..." : "Conferma"}
              </button>
            </div>
          </div>
        </Panel>
      </div>

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
                onClick={() => setWordConformityDialogOpen(false)}
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
            void performGenerateWordDraft(false, true);
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

function Panel({ title, children, className = "" }) {
  return (
    <div className={`rounded-xl border border-border bg-white p-4 ${className}`}>
      <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h3>
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
