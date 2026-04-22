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

function extractRawNumericToken(value) {
  if (value === null || value === undefined) {
    return "";
  }

  const raw = String(value).trim();
  if (!raw) {
    return "";
  }

  const match = raw.match(/-?\d+(?:[.,]\d+)?(?:[.,]\d+)?/);
  return match ? match[0] : raw;
}

function parseWeightToken(value) {
  const token = extractRawNumericToken(value);
  if (!token) {
    return null;
  }

  const sign = token.startsWith("-") ? -1 : 1;
  const unsigned = sign < 0 ? token.slice(1) : token;

  if (/^\d{1,3}(?:[.,]\d{3})+$/.test(unsigned)) {
    return sign * Number(unsigned.replace(/[.,]/g, ""));
  }

  if (/^\d+$/.test(unsigned)) {
    return sign * Number(unsigned);
  }

  if (unsigned.includes(",") && unsigned.includes(".")) {
    const normalized =
      unsigned.lastIndexOf(",") > unsigned.lastIndexOf(".")
        ? unsigned.replace(/\./g, "").replace(",", ".")
        : unsigned.replace(/,/g, "");
    return sign * Number(normalized);
  }

  if (unsigned.includes(",")) {
    return sign * Number(unsigned.replace(",", "."));
  }

  return sign * Number(unsigned);
}

function formatWeightDisplay(value) {
  const parsed = parseWeightToken(value);
  if (parsed === null || Number.isNaN(parsed)) {
    return "";
  }

  if (Number.isInteger(parsed)) {
    return new Intl.NumberFormat("it-IT", {
      maximumFractionDigits: 0,
      minimumFractionDigits: 0,
      useGrouping: true,
    }).format(parsed);
  }

  return new Intl.NumberFormat("it-IT", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
    useGrouping: true,
  }).format(parsed);
}

export function formatFieldDisplay(block, field, value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  if (block === "ddt" && field === "peso") {
    return formatWeightDisplay(value) || String(value).trim();
  }

  if (!isNumericField(block, field)) {
    return String(value).trim();
  }

  return extractDisplayNumericToken(value);
}

export function formatRowFieldDisplay(field, value) {
  return formatFieldDisplay("ddt", field, value);
}
