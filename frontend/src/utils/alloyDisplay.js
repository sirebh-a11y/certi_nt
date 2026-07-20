const SIMPLE_ALLOY_PATTERN = /^[1-8]\d{3}[A-Z]?$/i;
const ATTACHED_TREATMENT_PATTERN = /^([1-8]\d{3}[A-Z]?)(T\d{1,4}|H\d{2,3}|[FOW])$/i;
const TREATMENT_PATTERN = /^(?:[FOW]|T\d{1,4}|H\d{2,3})$/i;
const MATERIAL_CONTEXT_PATTERN =
  /\b(?:BARRA|BARRE|BAR|BARS|TONDA|TONDO|TONDI|ROUND|DIAM|DIAMETRO|MM|LUNGHEZZA|LENGTH|PROFIL|PROFILI|PROFILE|PROFILO|ESTRUS|EXTRUDED|FORGI|FORGING|BILLET|BILLETS|CAST|HOMOGENIZED|SCALPED|VOSTRO\s+CODICE|CODICE|ALBERO|SUPPORTO)\b/i;

function normalizeToken(value) {
  return String(value || "")
    .trim()
    .replace(/^[([{]+/g, "")
    .replace(/[.,;:)\]}]+$/g, "")
    .toUpperCase();
}

function isTreatmentToken(value) {
  return TREATMENT_PATTERN.test(normalizeToken(value));
}

function stripAttachedTreatment(value) {
  const text = String(value || "").trim();
  const upper = text.toUpperCase();
  const match = upper.match(ATTACHED_TREATMENT_PATTERN);

  if (!match) {
    return text;
  }

  const base = match[1];
  const treatment = match[2];

  if (!SIMPLE_ALLOY_PATTERN.test(base) || !isTreatmentToken(treatment)) {
    return text;
  }

  return text.slice(0, base.length);
}

export function normalizeAlloyForDisplay(value) {
  const raw = String(value ?? "").trim().replace(/\s+/g, " ");
  if (!raw || raw === "-") {
    return raw || "-";
  }

  if (MATERIAL_CONTEXT_PATTERN.test(raw)) {
    return raw;
  }

  const tokens = raw
    .replace(/[()[\]{},;]+/g, " ")
    .replace(/[/-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ");

  if (tokens.length === 0 || tokens.length > 5) {
    return raw;
  }

  while (tokens.length > 1 && isTreatmentToken(tokens[tokens.length - 1])) {
    tokens.pop();
  }

  for (let index = 0; index < tokens.length; index += 1) {
    tokens[index] = stripAttachedTreatment(tokens[index]);
  }

  return tokens.join(" ").trim() || raw;
}

export function alloySearchText(value) {
  const raw = String(value ?? "").trim();
  const normalized = normalizeAlloyForDisplay(raw);
  return Array.from(new Set([raw, normalized].filter(Boolean))).join(" ");
}
