"""Register projection only. Never delete/update sources or choose a reuse Word."""
import json
from collections import defaultdict
from app.modules.quarta_taglio.ddt_shipments import base_number


def clean(value):
    return str(value).strip() if value is not None else ""


def material_key(certificate):
    values = certificate.cdq_values or []
    if not values or any(not isinstance(v, dict) or not clean(v.get('cdq'))
                         or not clean(v.get('colata')) for v in values):
        return None  # Incomplete legacy evidence must remain visible.
    return (clean(certificate.cdq_key),
            tuple(sorted(certificate.cdq_signature or [])),
            tuple(sorted(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in values)))


def superseded_bases(certificates, *, file_available):
    """Map early bases to corresponding shipment documents, not merely same OL.

    Same-number shipments remain distinct, including two lines of one DDT.
    Manual-source divergence is intentionally NOT resolved by this projection.
    """
    shipments = defaultdict(list)
    def key(c):
        identity = (clean(c.cod_odp), clean(c.cod_f3), base_number(c))
        material = material_key(c)
        return (*identity, material) if all(identity) and material else None

    for c in certificates:
        k = key(c)
        if k and clean(c.ddt) and (file_available(c.storage_key_docx) or
                                  (c.status == 'pdf_final' and file_available(c.storage_key_pdf))):
            shipments[k].append(c.id)
    result = {}
    for c in certificates:
        if (clean(c.ddt) or c.status == 'pdf_final' or c.storage_key_pdf
                or any(clean(getattr(c, f)) for f in ('esolver_id_documento', 'esolver_id_riga_doc', 'esolver_rif_lotto_alfanum'))):
            continue
        targets = shipments.get(key(c), [])
        if targets:
            result[c.id] = targets
    return result
