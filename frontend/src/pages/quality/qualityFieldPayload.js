export function qualityFieldError(field, value) {
  if (field !== "qualita_numero_colli" || String(value ?? "").trim() === "") return "";
  const text = String(value).trim();
  const count = Number(text);
  if (!/^\d+$/.test(text) || !Number.isInteger(count) || count < 1 || count > 2147483647) {
    return "N° colli: inserire un numero intero positivo oppure lasciare vuoto.";
  }
  return "";
}

export function qualityFieldPayloadValue(field, value) {
  const error = qualityFieldError(field, value);
  if (error) throw new Error(error);
  if (field === "qualita_numero_colli") {
    return String(value ?? "").trim() === "" ? null : Number(value);
  }
  return value === "" ? null : value;
}
