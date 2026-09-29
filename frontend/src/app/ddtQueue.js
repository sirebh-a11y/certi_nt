export const DDT_QUEUE_REFRESH_EVENT = "certi_nt:ddt-queue-refresh";

export function ddtCertificationPath(item) {
  if (!item?.cod_odp || !item?.id) {
    return null;
  }
  return `/quarta-taglio/${encodeURIComponent(item.cod_odp)}?ddtWorkItemId=${encodeURIComponent(item.id)}`;
}
