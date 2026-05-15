import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

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
  mismatch: "Non coerente",
  error: "Errore",
};

const METHOD_LABELS = {
  weighted: "media pesata",
  average: "media",
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
  return [
    standard.lega_base,
    standard.norma,
    standard.trattamento_termico,
    standard.tipo_prodotto,
    standard.misura_tipo,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function QuartaTaglioDetailPage() {
  const { codOdp } = useParams();
  const { clearAuth, token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingStandardId, setSavingStandardId] = useState(null);
  const [standardError, setStandardError] = useState("");
  const [standards, setStandards] = useState([]);
  const [manualStandardId, setManualStandardId] = useState("");
  const [articleDraft, setArticleDraft] = useState({ descrizione: "", disegno: "" });
  const [articleStates, setArticleStates] = useState({});
  const [wordDraftState, setWordDraftState] = useState({ status: "idle", message: "" });
  const [wordUploadFile, setWordUploadFile] = useState(null);
  const [wordUploadState, setWordUploadState] = useState({ status: "idle", message: "" });
  const [wordConformityDialogOpen, setWordConformityDialogOpen] = useState(false);
  const [standardConformityDialogOpen, setStandardConformityDialogOpen] = useState(false);
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
    apiRequest(`/quarta-taglio/${encodeURIComponent(codOdp)}`, {}, token)
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
  }, [codOdp, token]);

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
      .then((response) => {
        setData(response);
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
      setData(response);
      const nextDraft = {
        descrizione: response.header?.descrizione || "",
        disegno: response.header?.disegno || "",
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
    if ((data?.conformity_issues || []).length > 0) {
      setWordConformityDialogOpen(true);
      return;
    }
    void performGenerateWordDraft(false);
  }

  async function performGenerateWordDraft(forceNonConforming = false) {
    setWordDraftState({ status: "saving", message: "" });
    setError("");
    try {
      const response = await apiRequest(
        `/quarta-taglio/${encodeURIComponent(codOdp)}/word-draft`,
        {
          method: "POST",
          body: JSON.stringify({ force_non_conforming: forceNonConforming }),
        },
        token,
      );
      const link = document.createElement("a");
      link.href = resolveApiAssetUrl(response.download_url);
      link.download = response.file_name || `${codOdp}_bozza.docx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      const refreshed = await apiRequest(`/quarta-taglio/${encodeURIComponent(codOdp)}`, {}, token);
      setData(refreshed);
      setWordDraftState({ status: "saved", message: `Word certificato creato: ${response.draft_number}` });
    } catch (requestError) {
      setWordDraftState({
        status: "error",
        message: handleRequestError(requestError, "Errore generazione bozza Word"),
      });
    }
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
        `/quarta-taglio/${encodeURIComponent(codOdp)}/word-file`,
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
      const refreshed = await apiRequest(`/quarta-taglio/${encodeURIComponent(codOdp)}`, {}, token);
      setData(refreshed);
      setWordUploadState({ status: "saved", message: `Word ricaricato sul certificato ${response.draft_number}` });
    } catch (requestError) {
      setWordUploadState({
        status: "error",
        message: handleRequestError(requestError, "Errore caricamento Word modificato"),
      });
    }
  }

  const headerRows = useMemo(() => {
    const header = data?.header || {};
    const codiceF3Value = header.codice_f3 ? (
      <div>
        <div>{header.codice_f3}</div>
        {header.codice_f3_origine === "quarta_fallback" ? (
          <div className="mt-1 text-[11px] font-semibold text-amber-700">Fallback Quarta</div>
        ) : null}
        {header.codice_f3_warning ? <div className="mt-1 text-[11px] font-semibold text-amber-700">{header.codice_f3_warning}</div> : null}
      </div>
    ) : (
      "-"
    );
    return [
      ["Certificato", header.numero_certificato || "Da assegnare"],
      ["Cliente", header.cliente || "Da eSolver"],
      ["Ordine cliente", header.ordine_cliente || "Da eSolver"],
      ["C.d.O.", header.conferma_ordine || "Da eSolver"],
      ["DDT", header.ddt || "Da eSolver"],
      ["Codice F3", codiceF3Value],
      ["Colata", header.colata || "-"],
      ["Quantità", header.quantita ? formatNumber(header.quantita, 2) : "-"],
    ];
  }, [data]);
  const conformityIssues = data?.conformity_issues || [];
  const hasConformityIssues = conformityIssues.length > 0;

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

      <div className="flex flex-col gap-2 rounded-xl border border-border bg-white p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Word certificato</h3>
          <p className="mt-1 text-sm text-slate-600">
            {data.selected_standard_confirmed
              ? "Standard confermato: puoi creare il Word numerato anche se alcuni dati sono ancora mancanti."
              : "Serve standard confermato prima di creare il Word."}
          </p>
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
          <span className={`mt-3 inline-flex w-fit rounded-lg border px-3 py-1 text-xs font-semibold ${conformityClass(data.conformity_status)}`}>
            Conformità standard: {conformityLabel(data.conformity_status)}
          </span>
        </div>
        <div className="flex flex-col gap-2 md:min-w-[360px]">
          <button
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={wordDraftState.status === "saving" || !data.selected_standard_confirmed}
            onClick={generateWordDraft}
            type="button"
          >
            {wordDraftState.status === "saving" ? "Creazione..." : "Genera Word"}
          </button>
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

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="Dati certificato">
          <div className="grid gap-2 md:grid-cols-2">
            {headerRows.map(([label, value]) => (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" key={label}>
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
                <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
              </div>
            ))}
            <EditableArticleField
              label="Descrizione"
              onBlur={() => flushArticleField("descrizione")}
              onChange={(value) => updateArticleDraftAndAutosave("descrizione", value)}
              origin={data.header?.descrizione_origine}
              proposal={data.header?.descrizione_proposta}
              state={articleStates.descrizione}
              title={articleAutosaveTitle(articleStates.descrizione)}
              value={articleDraft.descrizione}
              warning={data.header?.descrizione_diversa_da_quarta === "true"}
            />
            <EditableArticleField
              label="Disegno"
              onBlur={() => flushArticleField("disegno")}
              onChange={(value) => updateArticleDraftAndAutosave("disegno", value)}
              origin={data.header?.disegno_origine}
              proposal={data.header?.disegno_proposta}
              state={articleStates.disegno}
              title={articleAutosaveTitle(articleStates.disegno)}
              value={articleDraft.disegno}
              warning={data.header?.disegno_diverso_da_quarta === "true"}
            />
          </div>
          {data.header?.descrizione_articolo_quarta ? (
            <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
              <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">DES_ART Quarta</div>
              <div className="mt-1 font-medium text-slate-900">{data.header.descrizione_articolo_quarta}</div>
              <div className="mt-1 text-xs text-slate-500">Separazione disegno: {data.header.disegno_confidenza || "da verificare"}</div>
            </div>
          ) : null}
        </Panel>

        <Panel title="Standard">
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

      <Panel title="Dati eSolver">
        <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-slate-600">{data.esolver_message || "Collegamento eSolver non verificato."}</div>
          <StatusPill status={data.esolver_status || "not_checked"} />
        </div>
        <Table
          columns={["Cod F3", "OL", "Cliente", "Ordine cliente", "C.d.O.", "DDT", "Quantità"]}
          rows={(data.esolver_rows || []).map((item) => [
            item.cod_f3 || "-",
            item.orp || "-",
            item.rag_soc || "-",
            item.odv_cli || "-",
            item.odv_f3 || "-",
            item.ddt || "-",
            formatNumber(item.qta_um_mag, 2),
          ])}
          emptyText="Nessuna riga DDT eSolver collegata a questo OL."
        />
      </Panel>

      <Panel title="Materiali collegati">
        <Table
          columns={["CDQ", "Colata", "Articolo Quarta", "Quantità", "Lotti", "Righe app"]}
          rows={(data.materials || []).map((item) => [
            item.cdq,
            item.colata || "-",
            <div key="article">
              <div className="font-medium">{item.cod_art || "-"}</div>
              {item.des_art ? <div className="mt-1 text-xs text-slate-500">{item.des_art}</div> : null}
            </div>,
            formatNumber(item.qta_totale, 2),
            (item.cod_lotti || []).join(", ") || "-",
            item.matching_row_ids?.length
              ? item.matching_row_ids.map((rowId) => (
                  <Link className="mr-2 font-semibold text-accent hover:underline" key={rowId} to={`/acquisition/${rowId}`}>
                    #{rowId}
                  </Link>
                ))
              : "-",
          ])}
        />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Chimica">
          <ValueTable numberDigits={3} values={data.chemistry || []} />
        </Panel>
        <Panel title="Proprietà">
          <ValueTable values={data.properties || []} />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Note">
          <Table
            columns={["Nota", "Valore", "Stato", "Messaggio"]}
            rows={(data.notes || []).map((item) => [item.label, item.value || "-", <StatusPill key="status" status={item.status} />, item.message])}
          />
        </Panel>
        <Panel title="Seconda pagina">
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
            Placeholder per la seconda pagina del certificato. La compileremo quando saranno definite le regole finali.
          </div>
        </Panel>
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
    </section>
  );
}

function Panel({ title, children }) {
  return (
    <div className="rounded-xl border border-border bg-white p-4">
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
        formatLimit(item.standard_min, item.standard_max, numberDigits),
        <StatusPill key="status" status={item.status} />,
        item.message || "-",
      ])}
    />
  );
}

function StatusPill({ status }) {
  return <span className={`inline-flex rounded-lg border px-2 py-1 text-xs font-semibold ${statusClass(status)}`}>{STATUS_LABELS[status] || status}</span>;
}
