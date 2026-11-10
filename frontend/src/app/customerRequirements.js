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
  { field: "requires_custom_pdf_name", label: "Nome PDF particolare" },
];

// A visual distinction only: both kinds remain a single customer requirement
// for the existing with/without filter. Preserve blank legacy profiles as well.
export function customerRequirementBadges(matches = []) {
  const profiles = matches.flatMap(match => match?.candidates || []);
  return {
    general: profiles.some(profile => !profile.requires_custom_pdf_name ||
      CUSTOMER_REQUIREMENT_FIELDS.some(({ field }) => field !== "requires_custom_pdf_name" && profile[field]) ||
      String(profile.specific_requirements || "").trim() || String(profile.note || "").trim()),
    pdfName: profiles.some(profile => profile.requires_custom_pdf_name),
    ambiguous: matches.some(match => match?.ambiguous),
  };
}

export function pdfNameRequirement(match) {
  if (!match?.candidates?.some(profile => profile.requires_custom_pdf_name)) return "none";
  return match.ambiguous ? "ambiguous" : "required";
}

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

// An OL can contain several F3. Never feed a joined display value to the
// digit-based resolver: it would silently concatenate distinct article codes.
export function resolveOlCustomerRequirements(requirements, articles = []) {
  const unique = new Map();
  for (const article of articles) {
    const code = String(article.cod_f3 || "").trim();
    if (!/^\d{3,}$/.test(code)) continue;
    const previous = unique.get(code);
    unique.set(code, previous ? {
      ...previous,
      cliente: previous.cliente || article.cliente,
      needs_verification: Boolean(previous.needs_verification && article.needs_verification),
    } : { ...article, cod_f3: code });
  }
  return [...unique.values()].map(article => ({
    ...article, match: resolveCustomerRequirements(requirements, article.cod_f3),
  })).filter(group => group.match.candidates.length);
}

// A filtered response carries the server's article snapshot. Keep its badge
// visible even if the separate dialog-data request is still loading/fails.
export function hasOlCustomerRequirements(item, groups) {
  return typeof item.has_customer_requirements === "boolean"
    ? item.has_customer_requirements
    : groups.length > 0;
}
