const PENDING_CLOSURE_LABELS = {
  attesa_ddt: {
    compact: "Attesa DDT",
    full: "Attesa DDT",
    search: "attesa ddt ddt mancante",
  },
  ddt_da_confermare: {
    compact: "DDT da conf.",
    full: "DDT da confermare",
    search: "ddt da confermare ddt incompleto",
  },
  match_da_confermare: {
    compact: "Match da conf.",
    full: "Match da confermare",
    search: "match da confermare attesa match",
  },
  ddt_match_da_confermare: {
    compact: "DDT+Match da conf.",
    full: "DDT e match da confermare",
    search: "ddt e match da confermare ddt incompleto attesa match",
  },
};

export function pendingClosureReason(row) {
  if (!row?.qualita_valutazione) {
    return null;
  }
  if (!row.document_ddt_id) {
    return "attesa_ddt";
  }
  const ddtPending = row.block_states?.ddt !== "verde";
  const matchPending = row.block_states?.match !== "verde";
  if (ddtPending && matchPending) {
    return "ddt_match_da_confermare";
  }
  if (ddtPending) {
    return "ddt_da_confermare";
  }
  if (matchPending) {
    return "match_da_confermare";
  }
  if (row.pending_closure_reason in PENDING_CLOSURE_LABELS) {
    return row.pending_closure_reason;
  }
  return null;
}

export function pendingClosurePresentation(row) {
  const reason = pendingClosureReason(row);
  if (!reason) {
    return null;
  }
  return { reason, ...PENDING_CLOSURE_LABELS[reason] };
}
