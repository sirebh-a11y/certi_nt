// Keep regeneration intent when passing through the non-conformity dialog.
export function wordGenerationPayload({ forceNonConforming = false, regenerate = false,
  activeCertificateId, certificateId, candidateCodF3, ddtWorkItemId }) {
  const target = regenerate ? activeCertificateId : certificateId;
  if (regenerate && (!Number.isSafeInteger(Number(target)) || Number(target) <= 0)) {
    throw new Error("Certificato da rigenerare non identificato: aggiorna la pagina.");
  }
  return {
    force_non_conforming: forceNonConforming,
    force_regenerate: regenerate,
    certificate_id: target ? Number(target) : null,
    candidate_cod_f3: ddtWorkItemId || target ? null : candidateCodF3 || null,
    ddt_work_item_id: ddtWorkItemId ? Number(ddtWorkItemId) : null,
  };
}
