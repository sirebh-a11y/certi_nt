export function registerDdtNotice(item) {
  return !item.ddt && item.ddt_received ? "DDT presente — verifica richiesta" : null;
}

// Refresh can replace an early base with one or several shipment records.
// Do not resurrect the hidden base or collapse equal certificate numbers/DDTs.
export function mergeRegisterRefresh(currentItems, response) {
  const hidden = new Set(response.hidden_certificate_ids || []);
  const updated = new Map((response.items || []).map(item => [item.id, item]));
  const result = currentItems.filter(item => !hidden.has(item.id)).map(item => {
    const value = updated.get(item.id) || item;
    updated.delete(item.id);
    return value;
  });
  return [...result, ...[...updated.values()].filter(item => !hidden.has(item.id))];
}
