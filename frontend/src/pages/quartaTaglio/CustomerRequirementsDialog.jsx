import { useEffect, useRef } from "react";
import { CUSTOMER_REQUIREMENT_FIELDS } from "../../app/customerRequirements";

export default function CustomerRequirementsDialog({ item, match, onClose }) {
  const dialog = useRef(null);
  useEffect(() => { dialog.current.showModal(); }, []);
  return (
    <dialog ref={dialog} onCancel={onClose} aria-labelledby="ddt-requirements-title"
      className="m-auto max-h-[85vh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-2xl border border-rose-200 bg-white p-6 text-slate-900 shadow-xl backdrop:bg-slate-900/40">
      <h3 id="ddt-requirements-title" className="text-lg font-semibold">Requisiti cliente</h3>
      <p className="mt-2 break-words text-sm">{item.cliente} · {item.cod_odp} · Cod. F3 <strong>{item.cod_f3}</strong> · DDT {item.ddt_raw}</p>
      {match.ambiguous ? <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Più schede per questa famiglia di articoli. Verificare il Cod. F3: le schede sotto sono alternative, non requisiti da sommare.</p> : null}
      {match.candidates.map(requirement => (
        <div key={requirement.id} className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950">
          <p className="font-semibold">{requirement.cliente} · Scheda {requirement.cod_f3}</p>
          <ul className="mt-3 list-disc space-y-1 pl-5">
            {CUSTOMER_REQUIREMENT_FIELDS.filter(field => requirement[field.field]).map(field => <li key={field.field}>{field.label}</li>)}
          </ul>
          <p className="mt-4 whitespace-pre-wrap break-words"><strong>Requisiti specifici:</strong> {requirement.specific_requirements || "—"}</p>
          <p className="mt-3 whitespace-pre-wrap break-words"><strong>Note:</strong> {requirement.note || "—"}</p>
        </div>
      ))}
      <div className="mt-5 flex justify-end"><button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold">Chiudi</button></div>
    </dialog>
  );
}
