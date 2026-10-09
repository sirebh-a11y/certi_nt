"""Explicit, additive installation: never seed/replace customer standards on startup."""
from app.modules.standards.models import NormativeStandard
from app.modules.standards.schemas import StandardCreateRequest, StandardChemistryPayload, StandardPropertyPayload
from app.modules.standards.service import (
    _apply_standard_payload, _chemistry_from_payload, _property_from_payload,
    _validate_payload_limits, _ensure_unique_display_label,
)


def prepare_7003(db, *, source_standard_id, activate=False, apply=False):
    source = db.get(NormativeStandard, source_standard_id)
    if source is None or source.lega_base.strip() != "7003" or not source.chemistry_limits:
        raise ValueError("Scegliere uno standard 7003 esistente con chimica verificata")
    report = []
    for basis, minimum in (("A", 10), ("A50mm", 8)):
        code = f"7003_t6_barre_{basis.lower()}_20261009"
        chemistry = [StandardChemistryPayload(elemento=c.elemento, min_value=c.min_value, max_value=c.max_value)
                     for c in source.chemistry_limits]
        properties = [StandardPropertyPayload(proprieta=field, misura_min=lower, misura_max=upper,
                         range_label="<= 50" if lower is None else "> 50 - 150", min_value=value)
                      for lower, upper, rp, rm in ((None, 50, 290, 350), (50, 150, 280, 340))
                      for field, value in (("Rp0.2", rp), ("Rm", rm), ("A%", minimum))]
        payload = StandardCreateRequest(code=code, lega_base="7003", lega_designazione="7003",
            norma="EN AW 755-2", trattamento_termico="T6", tipo_prodotto="BARRE", misura_tipo="diametro",
            elongation_basis=basis, stato_validazione="attivo" if activate else "bozza",
            fonte_excel_foglio="7003", fonte_excel_blocco="AD19:AH22",
            note=f"Configurazione approvata 09/10/2026: {basis}, minimo {minimum}%. "
                 f"Chimica copiata dallo standard locale #{source.id}; precedente invariato. "
                 "A50mm: Excel cliente; A: riscontro EN 755-2:2008 tabella 49. "
                 "Non equivale a una verifica dell'edizione 2025. Conferma operatore necessaria.",
            chemistry=chemistry, properties=properties)
        existing = db.query(NormativeStandard).filter(NormativeStandard.code == code).one_or_none()
        if existing is not None:
            # Idempotency without erasing operator changes or reactivating drafts.
            report.append(dict(code=code, action="existing_unchanged", id=existing.id,
                               state=existing.stato_validazione))
            continue
        for std in db.query(NormativeStandard).filter(NormativeStandard.lega_base == "7003").all():
            if std.elongation_basis == basis and (std.trattamento_termico or "").upper() == "T6" and (std.tipo_prodotto or "").upper() == "BARRE":
                raise ValueError(f"Standard {basis} T6 BARRE già presente #{std.id}: verificare prima di creare duplicati")
        _validate_payload_limits(payload)
        _ensure_unique_display_label(db, payload)
        report.append(dict(code=code, action="create", payload=payload.model_dump()))
        if apply:
            item = NormativeStandard()
            _apply_standard_payload(item, payload)
            item.chemistry_limits = [_chemistry_from_payload(p) for p in chemistry]
            item.property_limits = [_property_from_payload(p) for p in properties]
            db.add(item)
            db.flush()
            report[-1]["id"] = item.id
    return report
