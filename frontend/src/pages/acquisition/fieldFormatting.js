const DDT_NUMERIC_FIELDS = new Set(["diametro", "peso"]);
const CHEMISTRY_NUMERIC_FIELDS = new Set([
  "Si",
  "Fe",
  "Cu",
  "Mn",
  "Mg",
  "Cr",
  "Ni",
  "Zn",
  "Ti",
  "Cd",
  "Hg",
  "Pb",
  "V",
  "Bi",
  "Sn",
  "Zr",
  "Be",
  "Zr+Ti",
  "Mn+Cr",
  "Bi+Pb",
]);
const PROPERTY_NUMERIC_FIELDS = new Set(["HB", "Rp0.2", "Rm", "A%", "Rp0.2 / Rm", "IACS%"]);

function isNumericField(block, field) {
  if (block === "ddt") {
    return DDT_NUMERIC_FIELDS.has(field);
  }
  if (block === "chimica") {
    return CHEMISTRY_NUMERIC_FIELDS.has(field);
  }
  if (block === "proprieta") {
    return PROPERTY_NUMERIC_FIELDS.has(field);
  }
  return false;
}

function extractDisplayNumericToken(value) {
  if (value === null || value === undefined) {
    return "";
  }

  const raw = String(value).trim();
  if (!raw) {
    return "";
  }

  const match = raw.match(/-?\d+(?:[.,]\d+)?/);
  if (!match) {
    return raw;
  }

  const token = match[0];
  return token.includes(".") && !token.includes(",") ? token.replace(".", ",") : token;
}

export function formatFieldDisplay(block, field, value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  if (!isNumericField(block, field)) {
    return String(value).trim();
  }

  return extractDisplayNumericToken(value);
}

export function formatRowFieldDisplay(field, value) {
  return formatFieldDisplay("ddt", field, value);
}
