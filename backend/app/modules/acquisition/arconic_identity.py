"""Optional Arconic identity reread. Never changes matching or persisted fields."""
from __future__ import annotations

from copy import deepcopy
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

CERTIFICATE_IDENTITY_INSTRUCTION = (
    "cert_number contiene solo Cert Number EEP..., senza aggiungere il job. "
    "cast_job_number deve trascrivere integralmente CAST/JOB NUMBER, inclusi slash "
    "e TUTTI i job/package dopo slash, nell'ordine stampato nel documento. "
    "Non omettere il job e non ricavarlo da Delivery Note, ordine, nome file o annotazioni a penna. "
    "Se un dato non e visibile usa null, non indovinare. "
)
DDT_IDENTITY_INSTRUCTION = (
    "package_ids_raw deve contenere tutti i job/package numerici della stessa riga materiale. "
    "Nel layout possono essere nella prima colonna sotto la descrizione, accanto al CAST, "
    "mentre Package Number puo contenere codici imballo BG5-PKG: non confonderli. "
    "Non usare Delivery Note, ordini, annotazioni a penna o nome file come package. "
    "Tieni separati i package di righe, articoli o CAST diversi; conserva l'ordine stampato. "
)


def _text(value: object) -> str:
    return str(value or '').strip().upper()


def _jobs(value: object) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r'\b\d{8}\b', _text(value))))


def _cast(value: object) -> str:
    match = re.search(r'\bC\d{9,}\b', _text(value))
    return match.group() if match else ''


def _certificate_complete(core: dict) -> bool:
    return bool(re.fullmatch(r'EEP[0-9A-Z]+', _text(core.get('cert_number')))
                and re.search(r'\bC\d{9,}\s*/\s*\d{8}\b', _text(core.get('cast_job_number'))))


def _ddt_missing(row: dict, ddt: object) -> bool:
    jobs = _jobs(row.get('package_ids_raw'))
    forbidden = {_text(ddt), _text(row.get('sales_order_raw')), _text(row.get('customer_po_raw'))}
    return not jobs or any(job in forbidden for job in jobs)


def _row_key(row: dict) -> tuple[str, str, str] | None:
    # Never use row_index alone: AI may reorder the reread rows.
    key = (_text(row.get('line_no_raw')), _text(row.get('arconic_item_number_raw')),
           _cast(row.get('cast_number_raw')))
    return key if all(key) else None


def recover_identity(payload: dict, *, kind: str, reread: Callable[[], dict]) -> dict:
    """One attempt per invocation/document; failures preserve the successful first read.

    Called before normalization/cache, not against database values. Existing manual
    protections remain at the normal persistence boundary. Raw first/retry identities
    are retained separately so recovered values cannot masquerade as the first response.
    """
    try:
        if kind == 'certificate':
            core = payload.get('core') or {}
            if _certificate_complete(core):
                return payload
        else:
            rows = payload.get('rows') or []
            if not rows or not any(_ddt_missing(r, payload.get('ddt_number_raw')) for r in rows):
                return payload
        second = reread()
        updated = deepcopy(payload)
        applied = False
        if kind == 'certificate':
            new = second.get('core') or {}
            old_root = re.search(r'\bEEP[0-9A-Z]+', _text(core.get('cert_number')))
            new_root = re.fullmatch(r'EEP[0-9A-Z]+', _text(new.get('cert_number')))
            compatible = (new_root and (not old_root or old_root.group() == new_root.group())
                          and (not _cast(core.get('cast_job_number'))
                               or _cast(core.get('cast_job_number')) == _cast(new.get('cast_job_number'))))
            old_jobs = set(_jobs(core.get('cast_job_number')))
            if compatible and _certificate_complete(new) and old_jobs.issubset(_jobs(new.get('cast_job_number'))):
                target = updated.setdefault('core', {})
                for key in ('cert_number', 'cast_job_number'):
                    target[key] = new[key]
                applied = True
        else:
            old_ddt = _text(payload.get('ddt_number_raw'))
            new_ddt = _text(second.get('ddt_number_raw'))
            if old_ddt and old_ddt == new_ddt:
                fresh = second.get('rows') or []
                keys = [_row_key(r) for r in rows]
                for index, row in enumerate(rows):
                    key = keys[index]
                    candidates = [r for r in fresh if key and _row_key(r) == key]
                    if (not key or keys.count(key) != 1 or len(candidates) != 1
                            or not _ddt_missing(row, old_ddt)):
                        continue
                    candidate = candidates[0]
                    if _ddt_missing(candidate, new_ddt):
                        continue
                    updated['rows'][index]['package_ids_raw'] = candidate['package_ids_raw']
                    applied = True
        updated['_identity_recovery'] = {
            'status': 'applied' if applied else 'not_applied',
            'first': payload, 'reread': second,
        }
        return updated
    except Exception as exc:
        # A supplementary reading must not turn a readable document into a failed
        # file, abort a batch, add UI blockers, or discard chemistry/mechanics.
        logger.warning('Optional Arconic %s identity reread unavailable (%s); keeping first read', kind, type(exc).__name__)
        return payload
