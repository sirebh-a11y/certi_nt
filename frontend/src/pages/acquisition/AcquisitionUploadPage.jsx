import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

function mergeUploadedDocuments(currentItems, uploadedItems) {
  const map = new Map(currentItems.map((item) => [item.id, item]));
  uploadedItems.forEach((item) => {
    map.set(item.id, item);
  });
  return [...map.values()].sort((left, right) => left.id - right.id);
}

function runProgress(run) {
  if (!run || !run.totale_righe_target) {
    return 0;
  }
  return Math.max(5, Math.min(100, Math.round((run.righe_processate / run.totale_righe_target) * 100)));
}

function runStateLabel(run) {
  if (!run) {
    return "Nessuna presa in carico";
  }
  if (run.stato === "in_esecuzione") {
    return "In corso";
  }
  if (run.stato === "completato") {
    return "Completata";
  }
  if (run.stato === "errore") {
    return "Interrotta";
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

export default function AcquisitionUploadPage() {
  const { token } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [ddtFiles, setDdtFiles] = useState([]);
  const [certificateFiles, setCertificateFiles] = useState([]);
  const [ddtSupplierId, setDdtSupplierId] = useState("");
  const [certificateSupplierId, setCertificateSupplierId] = useState("");
  const [processingDdt, setProcessingDdt] = useState(false);
  const [processingCertificates, setProcessingCertificates] = useState(false);
  const [startingRun, setStartingRun] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ddtResult, setDdtResult] = useState(null);
  const [certificateResult, setCertificateResult] = useState(null);
  const [sessionDdtDocuments, setSessionDdtDocuments] = useState([]);
  const [sessionCertificateDocuments, setSessionCertificateDocuments] = useState([]);
  const [autoStartEnabled, setAutoStartEnabled] = useState(true);
  const [currentRun, setCurrentRun] = useState(null);
  const [lastStartedSignature, setLastStartedSignature] = useState("");

  const ddtCount = useMemo(() => ddtFiles.length, [ddtFiles]);
  const certificateCount = useMemo(() => certificateFiles.length, [certificateFiles]);

  const automationSignature = useMemo(() => {
    const ddtIds = sessionDdtDocuments.map((item) => item.id).join(",");
    const certificateIds = sessionCertificateDocuments.map((item) => item.id).join(",");
    return `${ddtIds}|${certificateIds}`;
  }, [sessionCertificateDocuments, sessionDdtDocuments]);

  useEffect(() => {
    let ignore = false;
    apiRequest("/suppliers", {}, token)
      .then((data) => {
        if (!ignore) {
          setSuppliers(data.items || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setSuppliers([]);
        }
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  async function handleBatchUpload(tipoDocumento) {
    const files = tipoDocumento === "ddt" ? ddtFiles : certificateFiles;
    const setProcessing = tipoDocumento === "ddt" ? setProcessingDdt : setProcessingCertificates;
    const setResult = tipoDocumento === "ddt" ? setDdtResult : setCertificateResult;
    const resetFiles = tipoDocumento === "ddt" ? setDdtFiles : setCertificateFiles;
    const supplierId = tipoDocumento === "ddt" ? ddtSupplierId : certificateSupplierId;

    if (!files.length) {
      setError(`Seleziona almeno un file ${tipoDocumento === "ddt" ? "DDT" : "certificato"}.`);
      return;
    }

    const formData = new FormData();
    formData.append("tipo_documento", tipoDocumento);
    if (supplierId) {
      formData.append("fornitore_id", supplierId);
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
      setResult(response);
      resetFiles([]);
      const uploadedDocuments = response.uploaded || [];
      const detectedDdt = uploadedDocuments.filter((item) => item.tipo_documento === "ddt");
      const detectedCertificates = uploadedDocuments.filter((item) => item.tipo_documento === "certificato");

      setSessionDdtDocuments((current) => mergeUploadedDocuments(current, detectedDdt));
      setSessionCertificateDocuments((current) => mergeUploadedDocuments(current, detectedCertificates));

      const movedCount =
        tipoDocumento === "ddt"
          ? detectedCertificates.length
          : detectedDdt.length;
      if (movedCount) {
        setNotice(`${movedCount} file ${movedCount === 1 ? "è stato riconosciuto" : "sono stati riconosciuti"} come ${tipoDocumento === "ddt" ? "certificato" : "DDT"} e spostato automaticamente nel gruppo corretto.`);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessing(false);
    }
  }

  async function startAutomationRun(signature = automationSignature) {
    if (!sessionDdtDocuments.length) {
      setError("Carica almeno un DDT per avviare la presa in carico automatica.");
      return;
    }

    setStartingRun(true);
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
          }),
        },
        token,
      );
      setCurrentRun(run);
      setLastStartedSignature(signature);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStartingRun(false);
    }
  }

  useEffect(() => {
    if (!currentRun || !["in_coda", "in_esecuzione"].includes(currentRun.stato)) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const refreshedRun = await apiRequest(`/acquisition/automation/runs/${currentRun.id}`, {}, token);
        setCurrentRun(refreshedRun);
      } catch (requestError) {
        setError(requestError.message);
        window.clearInterval(intervalId);
      }
    }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [currentRun, token]);

  useEffect(() => {
    const hasRunningRun = currentRun && ["in_coda", "in_esecuzione"].includes(currentRun.stato);
    if (!autoStartEnabled || hasRunningRun || startingRun) {
      return;
    }
    if (!sessionDdtDocuments.length) {
      return;
    }
    if (!automationSignature || automationSignature === lastStartedSignature) {
      return;
    }
    startAutomationRun(automationSignature);
  }, [
    autoStartEnabled,
    automationSignature,
    currentRun,
    lastStartedSignature,
    sessionDdtDocuments.length,
    startingRun,
  ]);

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
            <h2 className="mt-2 text-2xl font-semibold">Caricamento documenti</h2>
            <p className="mt-2 text-sm text-slate-500">
              Carichi DDT e certificati nel repository, poi il sistema prende in carico da solo il piu possibile:
              crea le righe, legge i campi DDT, propone il match e prova a compilare chimica, proprietà e note prima di passare la parola a quality.
            </p>
          </div>
          <Link className="rounded-xl border border-border px-4 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-ink" to="/acquisition">
            Torna alla lista
          </Link>
        </div>

        {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
        {notice ? <p className="mt-3 text-sm text-amber-700">{notice}</p> : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-2">
          <UploadCard
            suppliers={suppliers}
            selectedSupplierId={ddtSupplierId}
            onSupplierChange={setDdtSupplierId}
            buttonLabel={processingDdt ? "Carico DDT..." : "Carica DDT"}
            count={ddtCount}
            files={ddtFiles}
            helperText="Carica uno o più DDT. Se un file assomiglia a un certificato, il sistema prova a correggere il tipo."
            onChange={(event) => setDdtFiles(Array.from(event.target.files || []))}
            onSubmit={() => handleBatchUpload("ddt")}
            processing={processingDdt}
            result={ddtResult}
            title="1. Carica DDT"
          />

          <UploadCard
            suppliers={suppliers}
            selectedSupplierId={certificateSupplierId}
            onSupplierChange={setCertificateSupplierId}
            buttonLabel={processingCertificates ? "Carico certificati..." : "Carica certificati"}
            count={certificateCount}
            files={certificateFiles}
            helperText="Carica uno o più certificati. Se un file assomiglia a un DDT, il sistema prova a correggere il tipo."
            onChange={(event) => setCertificateFiles(Array.from(event.target.files || []))}
            onSubmit={() => handleBatchUpload("certificato")}
            processing={processingCertificates}
            result={certificateResult}
            title="2. Carica certificati"
          />
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-[1fr,1.3fr]">
          <div className="rounded-3xl border border-border bg-white p-6 shadow-sm shadow-slate-200/40">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Documenti pronti</p>
            <p className="mt-2 text-sm text-slate-600">
              Qui vedi cosa il sistema ha riconosciuto davvero prima di far partire la lavorazione.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-1">
              <UploadedList title="DDT pronti" items={sessionDdtDocuments} emptyLabel="Nessun DDT pronto." />
              <UploadedList title="Certificati pronti" items={sessionCertificateDocuments} emptyLabel="Nessun certificato pronto." />
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-white p-6 shadow-sm shadow-slate-200/40">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">3. Avvia lavorazione automatica</p>
                <p className="mt-2 text-sm text-slate-600">
                  Il sistema usa i DDT caricati e tutti i certificati disponibili: quelli della sessione e quelli già presenti nel repository.
                </p>
              </div>
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
                <input
                  checked={autoStartEnabled}
                  className="h-4 w-4 accent-teal-700"
                  onChange={(event) => setAutoStartEnabled(event.target.checked)}
                  type="checkbox"
                />
                Avvio automatico
              </label>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <SessionTile label="DDT pronti" value={sessionDdtDocuments.length} />
              <SessionTile label="Certificati pronti" value={sessionCertificateDocuments.length} />
              <SessionTile label="Run attuale" value={currentRun ? `#${currentRun.id}` : "-"} />
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                disabled={startingRun || !sessionDdtDocuments.length || (currentRun && ["in_coda", "in_esecuzione"].includes(currentRun.stato))}
                onClick={() => startAutomationRun(automationSignature)}
                type="button"
              >
                {startingRun ? "Avvio in corso..." : "Avvia lavorazione"}
              </button>
              <p className="self-center text-sm text-slate-500">
                Vision DDT viene usata quando serve e quando e disponibile una chiave OpenAI utente o di sistema.
              </p>
            </div>

            {currentRun ? <AutomationRunCard run={currentRun} /> : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function UploadCard({
  title,
  helperText,
  files,
  count,
  processing,
  buttonLabel,
  onChange,
  onSubmit,
  result,
  suppliers,
  selectedSupplierId,
  onSupplierChange,
}) {
  return (
    <div className="rounded-3xl border border-border bg-white p-6 shadow-sm shadow-slate-200/40">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-slate-500">{helperText}</p>

      <label className="mt-4 block text-sm font-medium text-slate-700">
        Fornitore del batch
        <select
          className="mt-2 w-full rounded-2xl border border-border bg-slate-50 px-4 py-3 text-sm text-slate-700"
          onChange={(event) => onSupplierChange(event.target.value)}
          value={selectedSupplierId}
        >
          <option value="">Rilevamento automatico</option>
          {suppliers.map((supplier) => (
            <option key={supplier.id} value={String(supplier.id)}>
              {supplier.ragione_sociale}
            </option>
          ))}
        </select>
      </label>

      <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
        <input accept=".pdf,application/pdf" className="w-full text-sm text-slate-700" multiple onChange={onChange} type="file" />
        <p className="mt-3 text-sm text-slate-600">
          {count ? `${count} file selezionati` : "Nessun file selezionato"}
        </p>
        {files.length ? (
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {files.slice(0, 8).map((file) => (
              <li key={`${file.name}-${file.size}`}>{file.name}</li>
            ))}
            {files.length > 8 ? <li>… e altri {files.length - 8}</li> : null}
          </ul>
        ) : null}
      </div>

      <button
        className="mt-4 rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
        disabled={processing || !count}
        onClick={onSubmit}
        type="button"
      >
        {buttonLabel}
      </button>

      {result ? (
        <div className="mt-5 rounded-2xl border border-border p-4">
          <p className="text-sm font-semibold text-slate-800">
            Caricati {result.uploaded_count} di {result.requested_count}
          </p>
          <p className="mt-1 text-xs text-slate-500">Falliti: {result.failed_count}</p>

          {result.uploaded?.length ? (
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Caricati</p>
              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                {result.uploaded.slice(0, 8).map((item) => (
                  <li key={item.id}>
                    #{item.id} · {item.nome_file_originale} · {item.tipo_documento.toUpperCase()} {item.fornitore_nome ? `· ${item.fornitore_nome}` : ""}
                  </li>
                ))}
                {result.uploaded.length > 8 ? <li>… e altri {result.uploaded.length - 8}</li> : null}
              </ul>
            </div>
          ) : null}

          {result.failed?.length ? (
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-500">Falliti</p>
              <ul className="mt-2 space-y-2 text-sm text-rose-700">
                {result.failed.map((item) => (
                  <li key={`${item.file_name}-${item.detail}`}>
                    {item.file_name} · {item.detail}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AutomationRunCard({ run }) {
  const progress = runProgress(run);
  const completed = run.stato === "completato";

  return (
    <div className={`mt-5 rounded-3xl border p-5 ${runStateClasses(run)}`}>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em]">Run #{run.id}</p>
          <p className="mt-2 text-lg font-semibold">{runStateLabel(run)}</p>
          <p className="mt-2 text-sm opacity-90">{run.messaggio_corrente || "Il sistema sta lavorando sui documenti caricati."}</p>
        </div>
        <div className="rounded-2xl bg-white/70 px-4 py-3 text-sm">
          <p className="font-semibold">{progress}%</p>
          <p className="mt-1 opacity-80">{run.righe_processate} di {run.totale_righe_target} righe gestite</p>
        </div>
      </div>

      <div className="mt-4 h-3 overflow-hidden rounded-full bg-white/60">
        <div className="h-full rounded-full bg-current transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <RunMetric label="Righe create" value={run.righe_create} />
        <RunMetric label="Match proposti" value={run.match_proposti} />
        <RunMetric label="Chimica letta" value={run.chimica_rilevata} />
        <RunMetric label="Note lette" value={run.note_rilevate} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium opacity-90">
        <span className="rounded-full bg-white/70 px-3 py-1">Fase: {run.fase_corrente}</span>
        {run.current_row_id ? <span className="rounded-full bg-white/70 px-3 py-1">Riga corrente #{run.current_row_id}</span> : null}
        {run.current_document_name ? <span className="rounded-full bg-white/70 px-3 py-1">{run.current_document_name}</span> : null}
      </div>

      {run.ultimo_errore ? <p className="mt-4 text-sm text-rose-700">Ultimo errore: {run.ultimo_errore}</p> : null}

      {completed ? (
        <div className="mt-4 flex flex-wrap gap-3">
          <Link className="rounded-xl border border-emerald-300 bg-white px-4 py-3 text-sm font-semibold text-emerald-700 hover:bg-emerald-50" to="/acquisition">
            Apri lista quality
          </Link>
        </div>
      ) : null}
    </div>
  );
}

function SessionTile({ label, value }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function RunMetric({ label, value }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.2em] opacity-70">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

function UploadedList({ title, items, emptyLabel }) {
  return (
    <div className="rounded-2xl border border-border bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{title}</p>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm text-slate-700">
          {items.slice(0, 8).map((item) => (
            <li key={item.id}>
              #{item.id} · {item.nome_file_originale}
              <div className="mt-1 text-xs text-slate-500">
                {item.tipo_documento.toUpperCase()} {item.fornitore_nome ? `· ${item.fornitore_nome}` : "· fornitore non riconosciuto"}
              </div>
            </li>
          ))}
          {items.length > 8 ? <li>… e altri {items.length - 8}</li> : null}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{emptyLabel}</p>
      )}
    </div>
  );
}
