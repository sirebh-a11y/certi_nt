import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const UPLOAD_BATCH_STORAGE_KEY = "acquisition.uploadBatchId";

function mergeUploadedDocuments(currentItems, uploadedItems) {
  const map = new Map(currentItems.map((item) => [item.id, item]));
  uploadedItems.forEach((item) => {
    map.set(item.id, item);
  });
  return [...map.values()].sort((left, right) => left.id - right.id);
}

function mergeSelectedFiles(currentFiles, incomingFiles) {
  const map = new Map(currentFiles.map((file) => [`${file.name}|${file.size}|${file.lastModified}`, file]));
  incomingFiles.forEach((file) => {
    map.set(`${file.name}|${file.size}|${file.lastModified}`, file);
  });
  return [...map.values()].sort((left, right) => left.name.localeCompare(right.name));
}

function runProgress(run) {
  if (!run || !run.totale_righe_target) {
    return 0;
  }
  return Math.max(5, Math.min(100, Math.round((run.righe_processate / run.totale_righe_target) * 100)));
}

function runStateLabel(run) {
  if (!run) {
    return "Nessun run";
  }
  if (run.stato === "in_esecuzione") {
    return "In corso";
  }
  if (run.stato === "completato") {
    return "Completato";
  }
  if (run.stato === "errore") {
    return "Errore";
  }
  return "In coda";
}

function runStateClasses(run) {
  if (!run) {
    return "border-slate-200 bg-slate-50 text-slate-700";
  }
  if (run.stato === "completato") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (run.stato === "errore") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function MaskedAiIcon() {
  return (
    <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/15 ring-1 ring-white/25">
      <img alt="" className="h-full w-full object-contain" src="/assets/branding/ai-masked-bot.png" />
    </span>
  );
}

export default function AcquisitionUploadPage() {
  const { token, clearAuth } = useAuth();
  const navigate = useNavigate();
  const [uploadBatchId, setUploadBatchId] = useState(() => {
    if (typeof window === "undefined") {
      return "";
    }
    return window.sessionStorage.getItem(UPLOAD_BATCH_STORAGE_KEY) || "";
  });
  const [ddtFiles, setDdtFiles] = useState([]);
  const [certificateFiles, setCertificateFiles] = useState([]);
  const [processingDdt, setProcessingDdt] = useState(false);
  const [processingCertificates, setProcessingCertificates] = useState(false);
  const [startingAiRun, setStartingAiRun] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ddtResult, setDdtResult] = useState(null);
  const [certificateResult, setCertificateResult] = useState(null);
  const [sessionDdtDocuments, setSessionDdtDocuments] = useState([]);
  const [sessionCertificateDocuments, setSessionCertificateDocuments] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [savingSupplierDocumentId, setSavingSupplierDocumentId] = useState(null);
  const [currentRun, setCurrentRun] = useState(null);

  const ddtCount = useMemo(() => ddtFiles.length, [ddtFiles]);
  const certificateCount = useMemo(() => certificateFiles.length, [certificateFiles]);
  const activeSuppliers = useMemo(() => suppliers.filter((item) => item.attivo), [suppliers]);

  function addDdtFiles(incomingFiles) {
    setDdtFiles((current) => mergeSelectedFiles(current, incomingFiles));
  }

  function addCertificateFiles(incomingFiles) {
    setCertificateFiles((current) => mergeSelectedFiles(current, incomingFiles));
  }

  const hasAutomationDocuments = sessionDdtDocuments.length > 0 || sessionCertificateDocuments.length > 0;
  const hasDocumentsWithoutSupplier = [...sessionDdtDocuments, ...sessionCertificateDocuments].some((item) => !item.fornitore_id);

  function handleRequestError(requestError) {
    const message = requestError?.message || "Request failed";
    if (["Invalid token", "Invalid token type", "User not available"].includes(message)) {
      clearAuth();
      navigate("/login", { replace: true });
      return;
    }
    setError(message);
  }

  async function loadCurrentBatch() {
    try {
      const response = await apiRequest("/acquisition/documents/current-batch", {}, token);
      const batchId = response.upload_batch_id || "";
      const documents = response.items || [];
      setUploadBatchId(batchId);
      setSessionDdtDocuments(documents.filter((item) => item.tipo_documento === "ddt"));
      setSessionCertificateDocuments(documents.filter((item) => item.tipo_documento === "certificato"));
      if (batchId && documents.length) {
        setNotice("Hai un batch temporaneo aperto: puoi continuare oppure scartarlo.");
      }
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function loadSuppliers() {
    try {
      const response = await apiRequest("/suppliers", {}, token);
      setSuppliers(response.items || []);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function discardCurrentBatch() {
    setError("");
    setNotice("");
    try {
      await apiRequest(
        "/acquisition/documents/current-batch",
        {
          method: "DELETE",
        },
        token,
      );
      setUploadBatchId("");
      setSessionDdtDocuments([]);
      setSessionCertificateDocuments([]);
      setDdtResult(null);
      setCertificateResult(null);
      setNotice("Batch temporaneo scartato.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function loadActiveRun() {
    try {
      const run = await apiRequest("/acquisition/automation/runs/active", {}, token);
      setCurrentRun(run);
      if (run) {
        setError("");
      }
      return run;
    } catch (requestError) {
      handleRequestError(requestError);
      return null;
    }
  }

  async function handleBatchUpload(tipoDocumento) {
    const files = tipoDocumento === "ddt" ? ddtFiles : certificateFiles;
    const setProcessing = tipoDocumento === "ddt" ? setProcessingDdt : setProcessingCertificates;
    const setResult = tipoDocumento === "ddt" ? setDdtResult : setCertificateResult;
    const resetFiles = tipoDocumento === "ddt" ? setDdtFiles : setCertificateFiles;

    if (!files.length) {
      setError(`Seleziona almeno un file ${tipoDocumento === "ddt" ? "DDT" : "certificato"}.`);
      return;
    }

    const formData = new FormData();
    formData.append("tipo_documento", tipoDocumento);
    if (uploadBatchId) {
      formData.append("upload_batch_id", uploadBatchId);
    }
    files.forEach((file) => formData.append("files", file));

    setProcessing(true);
    setError("");
    setNotice("");
    try {
      const response = await apiRequest(
        "/acquisition/documents/upload-batch",
        {
          method: "POST",
          body: formData,
        },
        token,
      );
      if (response.upload_batch_id) {
        setUploadBatchId(response.upload_batch_id);
      }
      setResult(response);
      resetFiles([]);
      const uploadedDocuments = response.uploaded || [];
      const detectedDdt = uploadedDocuments.filter((item) => item.tipo_documento === "ddt");
      const detectedCertificates = uploadedDocuments.filter((item) => item.tipo_documento === "certificato");

      setSessionDdtDocuments((current) => mergeUploadedDocuments(current, detectedDdt));
      setSessionCertificateDocuments((current) => mergeUploadedDocuments(current, detectedCertificates));

      const movedCount = tipoDocumento === "ddt" ? detectedCertificates.length : detectedDdt.length;
      if (movedCount) {
        setNotice(`${movedCount} file ${movedCount === 1 ? "è stato riclassificato" : "sono stati riclassificati"} automaticamente.`);
      }
    } catch (requestError) {
      handleRequestError(requestError);
    } finally {
      setProcessing(false);
    }
  }

  async function startAutomationRun() {
    if (!hasAutomationDocuments) {
      setError("Carica almeno un DDT o un certificato per avviare la lavorazione.");
      return;
    }
    if (hasDocumentsWithoutSupplier) {
      setError("Assegna un fornitore a tutti i documenti pronti prima di avviare la lettura intelligente.");
      return;
    }

    setStartingAiRun(true);
    setError("");
    try {
      const run = await apiRequest(
        "/acquisition/automation/runs",
        {
          method: "POST",
          body: JSON.stringify({
            ddt_document_ids: sessionDdtDocuments.map((item) => item.id),
            certificate_document_ids: sessionCertificateDocuments.map((item) => item.id),
            usa_ddt_vision: true,
            usa_intervento_ai: true,
          }),
        },
        token,
      );
      setCurrentRun(run);
      setUploadBatchId("");
    } catch (requestError) {
      const message = requestError?.message || "Request failed";
      if (message === "There is already an autonomous processing run in progress") {
        setError("");
        setNotice("C'è già una lavorazione automatica in corso: mi aggancio a quel run.");
        await loadActiveRun();
        return;
      }
      handleRequestError(requestError);
    } finally {
      setStartingAiRun(false);
    }
  }

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (uploadBatchId) {
      window.sessionStorage.setItem(UPLOAD_BATCH_STORAGE_KEY, uploadBatchId);
    } else {
      window.sessionStorage.removeItem(UPLOAD_BATCH_STORAGE_KEY);
    }
  }, [uploadBatchId]);

  useEffect(() => {
    loadCurrentBatch();
    loadSuppliers();
  }, [token]);

  useEffect(() => {
    let cancelled = false;

    async function initializeActiveRun() {
      try {
        const run = await apiRequest("/acquisition/automation/runs/active", {}, token);
        if (cancelled) {
          return;
        }
        setCurrentRun(run);
        if (run) {
          setError("");
        }
      } catch (requestError) {
        if (!cancelled) {
          handleRequestError(requestError);
        }
      }
    }

    initializeActiveRun();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!currentRun || !["in_coda", "in_esecuzione"].includes(currentRun.stato)) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const refreshedRun = await apiRequest(`/acquisition/automation/runs/${currentRun.id}`, {}, token);
        setCurrentRun(refreshedRun);
      } catch (requestError) {
        handleRequestError(requestError);
        window.clearInterval(intervalId);
      }
    }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [currentRun, token]);

  function replaceSessionDocument(updatedDocument) {
    const updater = (items) => items.map((item) => (item.id === updatedDocument.id ? updatedDocument : item));
    setSessionDdtDocuments(updater);
    setSessionCertificateDocuments(updater);
  }

  async function handleDocumentSupplierChange(documentId, supplierIdValue) {
    const supplierId = supplierIdValue ? Number(supplierIdValue) : null;
    setSavingSupplierDocumentId(documentId);
    setError("");
    try {
      const updatedDocument = await apiRequest(
        `/acquisition/documents/${documentId}/supplier`,
        {
          method: "PATCH",
          body: JSON.stringify({ fornitore_id: supplierId }),
        },
        token,
      );
      replaceSessionDocument(updatedDocument);
    } catch (requestError) {
      handleRequestError(requestError);
    } finally {
      setSavingSupplierDocumentId(null);
    }
  }

  return (
    <section className="space-y-4">
      <div className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming materiale</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Caricamento documenti</h2>
            <p className="mt-2 text-sm text-slate-500">
              Flusso: carichi DDT e certificati nel batch corrente, il sistema li riconosce e poi premi l'assistente AI per processarli.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm font-semibold text-sky-700 hover:bg-sky-100" to="/acquisition/manual/ddt">
              Fallback manuale DDT
            </Link>
            <Link className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm font-semibold text-sky-700 hover:bg-sky-100" to="/acquisition/manual/certificato">
              Fallback manuale certificato
            </Link>
            <Link className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100" to="/acquisition">
              Torna alla griglia
            </Link>
          </div>
        </div>

        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
        {notice ? <p className="mt-2 text-sm text-amber-700">{notice}</p> : null}

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <UploadSection
            buttonLabel={processingDdt ? "Carico DDT..." : "Carica DDT"}
            count={ddtCount}
            files={ddtFiles}
            helperText="Puoi caricare molti DDT insieme."
            onAddFiles={addDdtFiles}
            onSubmit={() => handleBatchUpload("ddt")}
            processing={processingDdt}
            result={ddtResult}
            title="1. DDT"
          />
          <UploadSection
            buttonLabel={processingCertificates ? "Carico certificati..." : "Carica certificati"}
            count={certificateCount}
            files={certificateFiles}
            helperText="Puoi caricare molti certificati insieme."
            onAddFiles={addCertificateFiles}
            onSubmit={() => handleBatchUpload("certificato")}
            processing={processingCertificates}
            result={certificateResult}
            title="2. Certificati"
          />
        </div>

        <div className="mt-4 rounded-2xl border border-border bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Documenti pronti</h3>
              <p className="mt-1 text-sm text-slate-500">Tipo reale riconosciuto e fornitore dove disponibile.</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-xs text-slate-500">
                {sessionDdtDocuments.length} DDT · {sessionCertificateDocuments.length} certificati
              </div>
              {uploadBatchId ? (
                <button
                  className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                  onClick={discardCurrentBatch}
                  type="button"
                >
                  Scarta batch
                </button>
              ) : null}
            </div>
          </div>

          {uploadBatchId ? <div className="mt-3 text-xs text-slate-500">Batch corrente: {uploadBatchId}</div> : null}

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <DocumentTable
              emptyLabel="Nessun DDT pronto."
              items={sessionDdtDocuments}
              onSupplierChange={handleDocumentSupplierChange}
              savingSupplierDocumentId={savingSupplierDocumentId}
              suppliers={activeSuppliers}
              title="DDT pronti"
            />
            <DocumentTable
              emptyLabel="Nessun certificato pronto."
              items={sessionCertificateDocuments}
              onSupplierChange={handleDocumentSupplierChange}
              savingSupplierDocumentId={savingSupplierDocumentId}
              suppliers={activeSuppliers}
              title="Certificati pronti"
            />
          </div>
          {hasDocumentsWithoutSupplier ? (
            <p className="mt-3 text-sm text-amber-700">Controlla il fornitore: i documenti senza fornitore non possono avviare la lettura intelligente.</p>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Controlla il fornitore prima di avviare la lettura intelligente.</p>
          )}
        </div>

        <div className="mt-4 rounded-2xl border border-border bg-white p-4">
          <div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">3. Lavorazione automatica</h3>
              <p className="mt-1 text-sm text-slate-500">
                Usa i documenti pronti del batch corrente che vedi qui sopra.
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className="flex min-h-[78px] items-center gap-4 rounded-2xl bg-accent px-6 py-3.5 text-left text-white shadow-sm transition hover:bg-teal-700 disabled:opacity-60"
              disabled={
                startingAiRun ||
                !hasAutomationDocuments ||
                hasDocumentsWithoutSupplier ||
                (currentRun && ["in_coda", "in_esecuzione"].includes(currentRun.stato))
              }
              onClick={startAutomationRun}
              type="button"
            >
              <MaskedAiIcon />
              <span className="flex flex-col">
                <span className="text-base font-semibold leading-tight">
                  {startingAiRun ? "Avvio lettura intelligente..." : "Avvia lettura intelligente dei documenti"}
                </span>
                <span className="text-sm font-medium text-white/80">Sensitive data masked</span>
              </span>
            </button>
          </div>

          <div className={`mt-4 rounded-2xl border p-4 ${runStateClasses(currentRun)}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em]">Run</div>
                <div className="mt-1 text-lg font-semibold">{currentRun ? `#${currentRun.id}` : "-"}</div>
                <div className="mt-1 text-sm">{runStateLabel(currentRun)}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-semibold">{runProgress(currentRun)}%</div>
                <div className="text-xs opacity-80">
                  {currentRun ? `${currentRun.righe_processate}/${currentRun.totale_righe_target}` : "0/0"} righe
                </div>
              </div>
            </div>

            <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/60">
              <div className="h-full rounded-full bg-current transition-all duration-300" style={{ width: `${runProgress(currentRun)}%` }} />
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <RunStat label="Match proposti" value={currentRun?.match_proposti || 0} />
              <RunStat label="Note rilevate" value={currentRun?.note_rilevate || 0} />
              <RunStat label="Chimica" value={currentRun?.chimica_rilevata || 0} />
              <RunStat label="Proprietà" value={currentRun?.proprieta_rilevate || 0} />
            </div>

            {currentRun?.messaggio_corrente ? <div className="mt-3 text-sm opacity-90">{currentRun.messaggio_corrente}</div> : null}
            {currentRun?.ultimo_errore ? <div className="mt-2 text-sm text-rose-700">Errore: {currentRun.ultimo_errore}</div> : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function UploadSection({
  title,
  helperText,
  files,
  count,
  processing,
  buttonLabel,
  onAddFiles,
  onSubmit,
  result,
}) {
  const inputId = `${title}-files`;

  function handleIncomingFiles(fileList) {
    const incomingFiles = Array.from(fileList || []).filter((file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"));
    if (!incomingFiles.length) {
      return;
    }
    onAddFiles(incomingFiles);
  }

  return (
    <div className="rounded-2xl border border-border bg-white p-4">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 text-sm text-slate-500">{helperText}</p>

      <div
        className="mt-3 min-h-64 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          handleIncomingFiles(event.dataTransfer.files);
        }}
      >
        <div className="flex flex-wrap items-center gap-3">
          <input
            accept=".pdf,application/pdf"
            className="hidden"
            id={inputId}
            multiple
            onChange={(event) => {
              handleIncomingFiles(event.target.files);
              event.target.value = "";
            }}
            type="file"
          />
          <label className="cursor-pointer rounded-lg border border-border bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100" htmlFor={inputId}>
            Scegli file
          </label>
          <span className="text-sm text-slate-600">oppure trascina qui i PDF</span>
        </div>

        <div className="mt-3 text-sm text-slate-600">{count ? `${count} file selezionati` : "Nessun file selezionato"}</div>
        {files.length ? (
          <ul className="mt-3 space-y-1 text-sm text-slate-700">
            {files.slice(0, 10).map((file) => (
              <li key={`${file.name}-${file.size}`}>{file.name}</li>
            ))}
            {files.length > 10 ? <li>… e altri {files.length - 10}</li> : null}
          </ul>
        ) : null}
      </div>

      <div className="mt-3">
        <button
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
          disabled={processing || !count}
          onClick={onSubmit}
          type="button"
        >
          {buttonLabel}
        </button>
      </div>

      {result ? (
        <div className="mt-3 rounded-2xl border border-border bg-slate-50 p-4">
          <div className="text-sm font-medium text-slate-800">
            Caricati {result.uploaded_count}/{result.requested_count} · falliti {result.failed_count}
          </div>
          {result.uploaded?.length ? (
            <div className="mt-2 text-xs text-slate-500">
              {result.uploaded.slice(0, 4).map((item) => (
                <div key={item.id}>
                  #{item.id} · {item.nome_file_originale} · {item.tipo_documento} {item.fornitore_nome ? `· ${item.fornitore_nome}` : ""}
                </div>
              ))}
            </div>
          ) : null}
          {result.failed?.length ? (
            <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {result.failed.map((item, index) => (
                <div key={`${item.file_name}-${index}`}>
                  {item.file_name}: {item.detail}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DocumentTable({ title, items, emptyLabel, suppliers, savingSupplierDocumentId, onSupplierChange }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</div>
      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">File</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Fornitore</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {items.map((item) => (
              <tr key={item.id}>
                <td className="whitespace-nowrap px-3 py-2 text-slate-700">{item.id}</td>
                <td className="px-3 py-2 text-slate-800">{item.nome_file_originale}</td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-700">{item.tipo_documento}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <select
                      className={`min-w-56 rounded-lg border px-3 py-2 text-sm ${
                        item.fornitore_id ? "border-slate-200 bg-white text-slate-800" : "border-amber-300 bg-amber-50 text-amber-900"
                      }`}
                      disabled={savingSupplierDocumentId === item.id}
                      onChange={(event) => onSupplierChange(item.id, event.target.value)}
                      value={item.fornitore_id || ""}
                    >
                      <option value="">Seleziona fornitore...</option>
                      {suppliers.map((supplier) => (
                        <option key={supplier.id} value={supplier.id}>
                          {supplier.ragione_sociale}
                        </option>
                      ))}
                    </select>
                    {!item.fornitore_id ? <span className="text-sm font-semibold text-amber-700">!</span> : null}
                    {savingSupplierDocumentId === item.id ? <span className="text-xs text-slate-500">Salvo...</span> : null}
                  </div>
                </td>
              </tr>
            ))}
            {!items.length ? (
              <tr>
                <td className="px-3 py-4 text-sm text-slate-500" colSpan={4}>
                  {emptyLabel}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunStat({ label, value }) {
  return (
    <div className="rounded-xl bg-white/70 px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-75">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
