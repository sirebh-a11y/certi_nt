// Only currently referenced, unconfirmed values can trigger this warning.
// Old orphaned evidence must not keep the warning visible after a new reading.
export function hasUnverifiedSourcePage(row, block) {
  const evidenceById = new Map((row?.evidences || []).map((item) => [item.id, item]));
  return (row?.values || []).some((value) =>
    value.blocco === block && value.stato !== "confermato" &&
    evidenceById.get(value.document_evidence_id)?.tipo_evidenza === "testo_pagina_da_verificare"
  );
}
