"""Transient operational view: current cache plus conserved DDT, never cache writes."""
from collections import defaultdict
from sqlalchemy import select

from app.modules.quarta_taglio.models import QuartaTaglioDdtWorkItem, QuartaTaglioEsolverLink
from app.modules.quarta_taglio.ddt_context import saved_ddt_row
from app.modules.quarta_taglio.ddt_archive import archived_ids


def _key(row):
    return tuple(str(v).strip() if v is not None else '' for v in
                 (row.id_documento, row.id_riga_doc, row.orp, row.rif_lotto_alfanum))


def operational_links(db, links, cod_odps):
    from app.modules.quarta_taglio import service
    result = dict(links)
    by_ol = defaultdict(list)
    codes = list(cod_odps)
    items = []
    for start in range(0, len(codes), 400):
        items.extend(db.scalars(select(QuartaTaglioDdtWorkItem).where(
            QuartaTaglioDdtWorkItem.cod_odp.in_(codes[start:start + 400]))))
    if not items:
        return result
    archived = archived_ids(db, items)
    for item in items:
        by_ol[item.cod_odp].append(item)
    for ol, saved in by_ol.items():
        original = links.get(ol)
        live = service._esolver_rows_from_link(original)
        hidden = {_key(saved_ddt_row(i)) for i in saved if i.id in archived}
        rows = [r for r in live if _key(r) not in hidden]
        keys = {_key(r) for r in rows}
        historical = False
        for item in saved:
            row = saved_ddt_row(item)
            if item.id not in archived and _key(row) not in keys:
                rows.append(row)
                keys.add(_key(row))
                historical = True
        clone = QuartaTaglioEsolverLink(cod_odp=ol)
        status = 'ok' if rows else (original.status if original else 'missing')
        message = original.message if original else None
        if rows and historical:
            message = 'DDT disponibili in CERTI, inclusi quelli conservati fuori dalla finestra eSolver.'
            if original and original.status not in {'ok', 'missing', 'not_checked'}:
                message += ' Lettura eSolver non riuscita: i dati conservati restano disponibili.'
        if not rows:
            status, message = 'missing', 'Nessun DDT operativo disponibile; eventuali DDT archiviati sono consultabili nella coda.'
        service._apply_esolver_link_values(clone, esolver_rows=rows, status_value=status,
            message=message, checked_at=original.last_checked_at if original else max(i.last_seen_at for i in saved))
        result[ol] = clone
    return result
