"""Strict selection of one saved eSolver share; never choose by OL alone."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.modules.quarta_taglio.models import QuartaTaglioDdtWorkItem, QuartaTaglioFinalCertificate
from app.modules.quarta_taglio.schemas import QuartaTaglioEsolverDdtRowResponse


def _clean(value):
    return str(value).strip() if value is not None else ""


def exact_certificate(item, certificate):
    pairs = (
        (item.cod_odp, certificate.cod_odp), (item.cod_f3, certificate.cod_f3),
        (item.ddt_raw, certificate.ddt), (item.id_documento, certificate.esolver_id_documento),
        (item.id_riga_doc, certificate.esolver_id_riga_doc),
        (item.rif_lotto_alfanum, certificate.esolver_rif_lotto_alfanum),
        (item.ordine_cliente, certificate.ordine_cliente),
    )
    return bool(item.cod_odp and item.cod_f3 and item.ddt_raw and item.certification_unit_key) and (
        item.certification_unit_key == certificate.unit_key
        and all(_clean(left) == _clean(right) for left, right in pairs)
    )


def quantity_matches(item, certificate):
    if item.quantita is None or certificate.quantita is None:
        return item.quantita is None and certificate.quantita is None
    source, target = Decimal(str(item.quantita)), Decimal(str(certificate.quantita))
    return source.is_finite() and target.is_finite() and abs(source - target) <= Decimal("0.000001")


def resolve_saved_ddt(db, *, cod_odp, work_item_id=None, certificate=None, lock=False):
    """Explicit queue selection, or an exact persisted certificate on later actions.

    Existing certificates without any corresponding snapshot keep their old flow.
    A changed snapshot identity is a conflict, not a fallback to another DDT.
    """
    statement = select(QuartaTaglioDdtWorkItem).where(QuartaTaglioDdtWorkItem.cod_odp == cod_odp)
    if work_item_id is not None:
        statement = statement.where(QuartaTaglioDdtWorkItem.id == work_item_id)
    elif certificate is not None and certificate.unit_key and certificate.esolver_id_documento and certificate.esolver_id_riga_doc:
        statement = statement.where(or_(
            QuartaTaglioDdtWorkItem.certification_unit_key == certificate.unit_key,
            (QuartaTaglioDdtWorkItem.id_documento == certificate.esolver_id_documento)
            & (QuartaTaglioDdtWorkItem.id_riga_doc == certificate.esolver_id_riga_doc)
            & (QuartaTaglioDdtWorkItem.rif_lotto_alfanum == certificate.esolver_rif_lotto_alfanum),
        ))
    else:
        return None
    if lock:
        statement = statement.with_for_update()
    items = list(db.scalars(statement.execution_options(populate_existing=True)))
    if not items:
        if work_item_id is not None:
            raise HTTPException(status_code=404, detail="Quota DDT non trovata per questo OL")
        return None
    if len(items) != 1:
        raise HTTPException(status_code=409, detail="Quota DDT ambigua: verifica richiesta")
    item = items[0]
    from app.modules.quarta_taglio.ddt_archive import require_operational
    require_operational(db, item)
    if item.source_review_reason or not item.cod_f3 or not item.ddt_raw or not item.ddt_date:
        raise HTTPException(status_code=409, detail="Dati della quota DDT da verificare prima di certificare")
    if certificate is not None and not exact_certificate(item, certificate):
        raise HTTPException(status_code=409, detail="Certificato e quota DDT non coincidono: nessuna riassegnazione automatica")
    if certificate is not None and not quantity_matches(item, certificate):
        raise HTTPException(status_code=409, detail="Quantità DDT modificata rispetto al certificato: verifica richiesta")
    return item


def saved_ddt_row(item):
    return QuartaTaglioEsolverDdtRowResponse(
        id_documento=item.id_documento, id_riga_doc=item.id_riga_doc,
        rif_lotto_alfanum=item.rif_lotto_alfanum, orp=item.cod_odp, cod_f3=item.cod_f3,
        ddt=item.ddt_raw, qta_um_mag=float(item.quantita) if item.quantita is not None else None,
        rag_soc=item.cliente, odv_cli=item.ordine_cliente, odv_f3=item.conferma_ordine,
        certificato_presente=item.certificato_presente_esolver,
    )


def certificate_for_saved_ddt(db, item):
    """Return exact certificate or a unique early Word; never a legacy DDT guess."""
    certificates = list(db.scalars(select(QuartaTaglioFinalCertificate)
                        .where(QuartaTaglioFinalCertificate.cod_odp == item.cod_odp)))
    exact = [cert for cert in certificates if exact_certificate(item, cert)]
    if len(exact) > 1:
        raise HTTPException(status_code=409, detail="Più certificati per la quota DDT: verifica richiesta")
    if exact:
        if not quantity_matches(item, exact[0]):
            raise HTTPException(status_code=409, detail="Quantità DDT modificata rispetto al certificato: verifica richiesta")
        return exact[0]
    conflicting = [cert for cert in certificates if (
        cert.unit_key == item.certification_unit_key
        or (_clean(cert.esolver_id_documento) == item.id_documento
            and _clean(cert.esolver_id_riga_doc) == item.id_riga_doc
            and _clean(cert.esolver_rif_lotto_alfanum) == _clean(item.rif_lotto_alfanum))
        or (not cert.esolver_id_documento and not cert.esolver_id_riga_doc
            and _clean(cert.cod_f3) == item.cod_f3 and _clean(cert.ddt) == item.ddt_raw)
    )]
    if conflicting:
        raise HTTPException(status_code=409, detail="Certificato con identità precedente o incompleta: verifica richiesta")
    early = [cert for cert in certificates if _clean(cert.cod_f3) == item.cod_f3
             and not _clean(cert.ddt) and not cert.esolver_id_documento and not cert.esolver_id_riga_doc
             and not cert.esolver_rif_lotto_alfanum and cert.status != "pdf_final" and cert.storage_key_docx]
    if not early:
        return None
    peers = list(db.scalars(select(QuartaTaglioDdtWorkItem.id).where(
        QuartaTaglioDdtWorkItem.cod_odp == item.cod_odp, QuartaTaglioDdtWorkItem.cod_f3 == item.cod_f3)))
    if len(early) != 1 or len(peers) != 1:
        raise HTTPException(status_code=409, detail="Word anticipato associabile a più quote: verifica richiesta")
    return early[0]
