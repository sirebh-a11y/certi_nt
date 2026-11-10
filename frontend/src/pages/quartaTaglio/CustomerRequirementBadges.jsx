import { customerRequirementBadges } from "../../app/customerRequirements";

// Never change row state, filters, or document readiness from these badges.
export default function CustomerRequirementBadges({ matches, present, context, onClick }) {
  const kinds = customerRequirementBadges(matches);
  const available = matches.some(match => match.candidates.length);
  if (present === false || (present !== true && !available)) return null;
  const hint = !available ? "Requisiti presenti: dettagli non disponibili, riprova il caricamento"
    : kinds.ambiguous ? "Più schede alternative: consulta i requisiti per verificare il Cod. F3"
      : "Consulta i requisiti previsti per questo articolo";
  return <div className="mt-1 flex flex-wrap gap-1">
    {kinds.general || !available ? <button type="button" onClick={onClick} disabled={!available}
      title={hint} aria-label={`Requisiti cliente per ${context}`}
      className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-70">
      Requisiti cliente
    </button> : null}
    {kinds.pdfName ? <button type="button" onClick={onClick} title={hint}
      aria-label={`Nome PDF particolare per ${context}`}
      className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100">
      Nome PDF particolare
    </button> : null}
  </div>;
}
