export const CUSTOMER_REQUIREMENT_FIELDS = [
  { field: "requires_chemical_analysis", label: "Analisi Chimica" },
  { field: "requires_mechanical_mp", label: "Caratt. Mecc. MP" },
  { field: "requires_mechanical_forged", label: "Caratt. Mecc. Forgiato" },
  { field: "requires_hardness_hb", label: "Durezza HB" },
  { field: "requires_lot_traceability_text", label: "Tracciabilita Lotto (datario) Indicazione" },
  { field: "requires_lot_traceability_photo", label: "Tracciabilita Lotto (datario) Foto" },
  { field: "requires_dimensional", label: "Dimensionale (Dimensioni concordate con cliente)" },
  { field: "requires_electrical_conductivity_forged", label: "Conducibilita elettrica (sul forgiato)" },
  { field: "requires_marking", label: "Marcature (Tracciabilita aggiuntive)" },
  { field: "requires_macro_micro", label: "Macrografie e/o Micrografie" },
  { field: "requires_ndt", label: "Tracciabilita Controllo NDT" },
];

function digits(value) {
  return String(value || "").replace(/\D/g, "");
}

// Preserve the existing exact-code priority and family fallback. Never choose
// the first of several family requirements: the user must see the ambiguity.
export function resolveCustomerRequirements(requirements, codF3) {
  const target = digits(codF3);
  if (target.length <= 2) return { item: null, candidates: [], ambiguous: false };
  const active = requirements.filter(item => item.active !== false);
  const exact = active.filter(item => digits(item.cod_f3) === target);
  const candidates = exact.length ? exact : active.filter(item => digits(item.cod_f3).slice(0, -2) === target.slice(0, -2));
  return { item: candidates.length === 1 ? candidates[0] : null, candidates, ambiguous: candidates.length > 1 };
}
