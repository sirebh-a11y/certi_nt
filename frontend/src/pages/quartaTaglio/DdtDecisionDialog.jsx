import { useEffect, useRef, useState } from "react";
import { apiRequest } from "../../app/api";

const ACTION_LABELS = { exclude: "Esclusione", restore: "Ripristino", review: "Riapertura per dati modificati" };

export default function DdtDecisionDialog({ item, action, token, onClose, onSaved }) {
  const dialog = useRef(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState(null);
  const isHistory = action === "history";
  const title = isHistory ? "Storico decisioni" : action === "exclude" ? "Non richiede certificazione" : "Ripristina quota";

  useEffect(() => { dialog.current.showModal(); }, []);
  useEffect(() => {
    if (!isHistory) return undefined;
    let cancelled = false;
    apiRequest(`/quarta-taglio/ddt-work-items/${item.id}/decisions`, {}, token)
      .then((result) => { if (!cancelled) setHistory(result); })
      .catch((err) => { if (!cancelled) setError(err.message || "Impossibile leggere lo storico."); });
    return () => { cancelled = true; };
  }, [isHistory, item.id, token]);

  async function save(event) {
    event.preventDefault();
    if (busy || !reason.trim()) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/quarta-taglio/ddt-work-items/${item.id}/decisions`, {
        method: "POST", body: JSON.stringify({ action, reason: reason.trim(),
          expected_decision_id: item.latest_decision?.id || 0, source_revision: item.source_revision }),
      }, token);
      onSaved(action);
    } catch (err) {
      setError(err.message || "Impossibile salvare la decisione.");
    } finally { setBusy(false); }
  }

  return (
    <dialog ref={dialog} aria-labelledby="ddt-decision-title" onCancel={(event) => {
      event.preventDefault();
      if (!busy) onClose();
    }} className="m-auto max-h-[85vh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl backdrop:bg-slate-900/40">
      <h2 id="ddt-decision-title" className="text-lg font-semibold">{title}</h2>
      <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm break-words">
        <p>DDT: <strong>{item.ddt_raw || "-"}</strong> · OL: <strong>{item.cod_odp || "Da collegare"}</strong></p>
        <p>Cod. F3: {item.cod_f3 || "-"} · Quantità: {item.quantita ?? "-"}</p>
        <p>Documento: {item.id_documento} · Riga: {item.id_riga_doc} · Lotto: {item.rif_lotto_alfanum || "-"}</p>
      </div>
      {isHistory ? <>
        {!history && !error ? <p className="mt-4 text-sm">Caricamento storico...</p> : null}
        {history?.length === 0 ? <p className="mt-4 text-sm">Nessuna decisione registrata.</p> : null}
        <ol className="mt-4 space-y-3 text-sm">
          {history?.map((entry) => <li key={entry.id} className="rounded-lg border border-slate-200 p-3">
            <p className="font-semibold">{ACTION_LABELS[entry.action] || entry.action}</p>
            <p className="text-xs text-slate-500">{entry.actor_name} · {new Date(entry.created_at).toLocaleString("it-IT")}</p>
            <p className="mt-1 whitespace-pre-wrap break-words">{entry.reason}</p>
          </li>)}
        </ol>
        {error ? <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p> : null}
        <button type="button" onClick={onClose} className="mt-4 rounded-lg border px-4 py-2 text-sm">Chiudi</button>
      </> : <form onSubmit={save} className="mt-4 space-y-4">
        <p className="text-sm text-slate-600">{action === "exclude"
          ? "Questa quota uscirà dagli Attivi e dal numero nella sidebar. La ritroverai in Vista → Esclusi e potrai ripristinarla."
          : "La quota tornerà negli Attivi con la scadenza originale, se il suo PDF finale non è già pronto."}</p>
        <label className="block text-sm font-semibold">Motivo della decisione
          <textarea autoFocus required maxLength={2000} rows={4} value={reason} onChange={(event) => setReason(event.target.value)}
            disabled={busy} className="mt-1 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal" />
        </label>
        {error ? <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <button type="button" disabled={busy} onClick={onClose} className="rounded-lg border px-4 py-2 text-sm disabled:opacity-40">Annulla</button>
          <button type="submit" disabled={busy || !reason.trim()} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {busy ? "Salvataggio..." : action === "exclude" ? "Conferma esclusione" : "Conferma ripristino"}
          </button>
        </div>
      </form>}
    </dialog>
  );
}
