// These are work filters, not replacements for lifecycle/permission checks.
export const DDT_WORK_FILTERS = [
  ["", "Tutti"],
  ["pdf_ready", "PDF da generare"],
  ["waiting_incoming", "Incoming da completare"],
  ["anomalies", "Anomalie"],
];

export function isClosedQueueScope(scope) {
  return ["completed", "excluded", "archived"].includes(scope);
}

export function updateDdtQueueFilters(current, field, value) {
  const next = { ...current, [field]: value };
  // Terminal views have no open-work subfilter. No hidden combination can
  // accidentally hide completed/excluded/archived items after a scope switch.
  if (field === "scope" || isClosedQueueScope(next.scope)) next.state = "";
  return next;
}

export function ddtQueueStatus(item) {
  // Normalize the former ambiguous labels as well during a coherent rollout.
  if (item.state === "ready") return "ddt_date" in item && !item.ddt_date
    ? { label: "Data DDT da verificare", tone: "review" }
    : { label: "Da certificare", tone: "ready" };
  if (item.state === "waiting_incoming") return { label: "Incoming da completare", tone: "waiting_incoming" };
  if (item.state === "word_ready") return item.pdf_action
    ? { label: "PDF da generare", tone: "word_ready" }
    : { label: "Word da verificare", tone: "review" };
  return { label: item.label?.trim() || "Verifica richiesta", tone: item.state };
}
