import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function AcquisitionUploadPage() {
  const { token } = useAuth();
  const [ddtFiles, setDdtFiles] = useState([]);
  const [certificateFiles, setCertificateFiles] = useState([]);
  const [processingDdt, setProcessingDdt] = useState(false);
  const [processingCertificates, setProcessingCertificates] = useState(false);
  const [error, setError] = useState("");
  const [ddtResult, setDdtResult] = useState(null);
  const [certificateResult, setCertificateResult] = useState(null);

  const ddtCount = useMemo(() => ddtFiles.length, [ddtFiles]);
  const certificateCount = useMemo(() => certificateFiles.length, [certificateFiles]);

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
    files.forEach((file) => formData.append("files", file));

    setProcessing(true);
    setError("");
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
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessing(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
            <h2 className="mt-2 text-2xl font-semibold">Caricamento documenti</h2>
            <p className="mt-2 text-sm text-slate-500">
              Upload massivo semplice per DDT e certificati. In questo step carichiamo i documenti nel repository, senza creare ancora righe acquisition in automatico.
            </p>
          </div>
          <Link className="rounded-xl border border-border px-4 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-ink" to="/acquisition">
            Torna alla lista
          </Link>
        </div>

        {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-2">
          <UploadCard
            buttonLabel={processingDdt ? "Carico DDT..." : "Carica DDT"}
            count={ddtCount}
            files={ddtFiles}
            helperText="Puoi selezionare molti DDT insieme."
            onChange={(event) => setDdtFiles(Array.from(event.target.files || []))}
            onSubmit={() => handleBatchUpload("ddt")}
            processing={processingDdt}
            result={ddtResult}
            title="Batch DDT"
          />

          <UploadCard
            buttonLabel={processingCertificates ? "Carico certificati..." : "Carica certificati"}
            count={certificateCount}
            files={certificateFiles}
            helperText="Puoi selezionare molti certificati insieme."
            onChange={(event) => setCertificateFiles(Array.from(event.target.files || []))}
            onSubmit={() => handleBatchUpload("certificato")}
            processing={processingCertificates}
            result={certificateResult}
            title="Batch certificati"
          />
        </div>
      </div>
    </section>
  );
}

function UploadCard({ title, helperText, files, count, processing, buttonLabel, onChange, onSubmit, result }) {
  return (
    <div className="rounded-3xl border border-border bg-white p-6 shadow-sm shadow-slate-200/40">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-slate-500">{helperText}</p>

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
          <p className="mt-1 text-xs text-slate-500">
            Falliti: {result.failed_count}
          </p>

          {result.uploaded?.length ? (
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Caricati</p>
              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                {result.uploaded.slice(0, 8).map((item) => (
                  <li key={item.id}>
                    #{item.id} · {item.nome_file_originale}
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
