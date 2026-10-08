import { useState } from "react";

export default function ConfirmPdfDialog({ busy, error, item, onCancel, onConfirm, onClearError }) {
  const inheritedWord = item.has_word && item.word_source === "inherited";
  const [fileName, setFileName] = useState(item.pdf_file_name || item.default_pdf_file_name || "");
  const trimmedFileName = fileName.trim();
  const normalizedFileName = trimmedFileName.toLowerCase().endsWith(".pdf")
    ? `${trimmedFileName.slice(0, -4)}.pdf`
    : `${trimmedFileName}.pdf`;
  function changeFileName(value) {
    setFileName(value);
    if (error) onClearError();
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4" role="dialog" aria-modal="true" aria-labelledby="pdf-dialog-title">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xl font-black text-amber-700">
            !
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="pdf-dialog-title" className="text-lg font-bold text-slate-950">Generare PDF finale?</h3>
            <p className="mt-2 break-words text-sm font-semibold text-slate-800">{item.cod_odp} · DDT {item.ddt} · Cod. F3 {item.cod_f3}</p>
            {inheritedWord ? (
              <p className="mt-2 text-sm leading-6 text-slate-700">
                Il certificato <span className="font-semibold text-slate-900">{item.certificate_number}</span> usa un Word ereditato, creato
                automaticamente senza conferma definitiva della Qualità per questa lavorazione. Puoi generare il PDF, ma consigliamo di contattare
                la Qualità prima di chiudere il certificato.
              </p>
            ) : (
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Il PDF finale chiude il certificato{" "}
                <span className="font-semibold text-slate-900">{item.certificate_number}</span> e sarà il documento usabile da amministrazione e qualità.
                Se hai dubbi sul contenuto, o se servono modifiche amministrative da riportare nel documento, scarica prima il Word e confrontati con
                l'ufficio qualità.
              </p>
            )}
            <label className="mt-4 block text-sm font-semibold text-slate-800" htmlFor="pdf-file-name">Nome file PDF</label>
            <input
              id="pdf-file-name"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
              value={fileName}
              onChange={(event) => changeFileName(event.target.value)}
              disabled={busy}
              maxLength={255}
              autoComplete="off"
              aria-describedby="pdf-file-name-help"
            />
            <p id="pdf-file-name-help" className="mt-2 text-xs leading-5 text-slate-600">
              Puoi adattare il nome alle richieste del cliente. Sarà usato per il download e reso disponibile a eSolver.
              Il numero del certificato resta invariato. L'estensione .pdf viene aggiunta se manca.
            </p>
            {item.default_pdf_file_name ? (
              <button type="button" disabled={busy} onClick={() => changeFileName(item.default_pdf_file_name)}
                className="mt-2 text-xs font-semibold text-teal-700 underline disabled:opacity-50">
                Ripristina nome standard
              </button>
            ) : null}
            {error ? <p role="alert" className="mt-3 text-sm font-semibold text-rose-600">{error}</p> : null}
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
            disabled={busy}
            onClick={onCancel}
            type="button"
          >
            Esci senza generare
          </button>
          <button
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={busy || !trimmedFileName}
            onClick={() => onConfirm(normalizedFileName)}
            type="button"
          >
            {busy ? "Generazione..." : "Genera PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}
