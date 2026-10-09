"""Word provenance, separate from live conformity and Incoming material changes.

Legacy baselines record the start of monitoring, NOT the standard of generation.
No document bytes, closed-PDF state or Incoming values are changed here.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from fastapi import HTTPException
from sqlalchemy import select, update, inspect, text
from sqlalchemy.orm import object_session

from app.modules.standards.models import NormativeStandard as S, NormativeStandardChemistry as C, NormativeStandardProperty as P
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as Certificate, QuartaTaglioStandardSelection as Selection

MESSAGE = "Lo standard è cambiato: aggiorna il Word prima di creare il PDF."


def snapshot(db, ol):
    # Column queries intentionally bypass ORM identity-map cached relationships.
    fields = ('id', 'lega_base', 'lega_designazione', 'variante_lega', 'norma',
              'trattamento_termico', 'tipo_prodotto', 'misura_tipo')
    row = db.execute(select(*(getattr(S, f) for f in fields)).join(
        Selection, Selection.standard_id == S.id).where(Selection.cod_odp == ol)).first()
    if row is None:
        return None
    result = dict(zip(fields, row))
    # Omit the new key for legacy standards: adding the column alone must NOT
    # invalidate every existing Word. Explicit metadata changes are monitored.
    elongation_basis = db.scalar(select(S.elongation_basis).where(S.id == row.id))
    if elongation_basis is not None:
        result['elongation_basis'] = elongation_basis
    for key, model, names in [('chemistry', C, ('elemento', 'min_value', 'max_value')),
                              ('properties', P, ('proprieta', 'misura_min', 'misura_max', 'range_label', 'min_value', 'max_value'))]:
        values = [dict(zip(names, r)) for r in db.execute(select(*(getattr(model, f) for f in names)).where(model.standard_id == row.id))]
        result[key] = sorted(values, key=lambda v: json.dumps(v, sort_keys=True))
    return result


def provenance(value, origin):
    return dict(version=1, origin=origin, recorded_at=datetime.now(timezone.utc).isoformat(), standard=deepcopy(value))


def baseline_legacy(db, ol=None):
    query = select(Certificate).where(Certificate.storage_key_docx.is_not(None), Certificate.word_standard_snapshot.is_(None))
    if ol is not None:
        query = query.where(Certificate.cod_odp == ol)
    count = 0
    cache = {}
    for certificate in db.scalars(query):
        if certificate.cod_odp not in cache:
            cache[certificate.cod_odp] = snapshot(db, certificate.cod_odp)
        value = provenance(cache[certificate.cod_odp], 'legacy_baseline')
        # Baseline must not make an old document appear recently edited.
        db.execute(update(Certificate).where(Certificate.id == certificate.id).values(
            word_standard_snapshot=value, updated_at=Certificate.updated_at))
        count += 1
    return count


def is_stale(certificate, db=None, *, for_reuse=False):
    if certificate is None or not certificate.storage_key_docx:
        return False
    if certificate.status == 'pdf_final' and not for_reuse:
        return False
    saved = getattr(certificate, 'word_standard_snapshot', None)
    # Pre-migration legacy is not retroactively declared incorrect.
    if saved is None:
        return False
    db = db or object_session(certificate)
    if db is None:
        return False
    return saved.get('standard') != snapshot(db, certificate.cod_odp)


def require_current(db, certificate, *, for_reuse=False):
    if is_stale(certificate, db, for_reuse=for_reuse):
        raise HTTPException(409, MESSAGE)


def copy_provenance(source, target):
    target.word_standard_snapshot = deepcopy(getattr(source, 'word_standard_snapshot', None))


def require_unchanged(db, ol, expected):
    if expected and db.get_bind().dialect.name == 'postgresql':
        # Standards editor takes the same row lock before replacing its limits.
        db.execute(select(S.id).where(S.id == expected['id']).with_for_update(read=True)).all()
    if snapshot(db, ol) != expected:
        raise HTTPException(409, "Lo standard è cambiato durante l'operazione: aggiorna la pagina e riprova.")


def ensure_schema(connection):
    """One additive column, no bootstrap or document mutation. Caller owns txn."""
    table = Certificate.__tablename__
    schema = connection.get_execution_options().get('schema_translate_map', {}).get(None)
    inspector = inspect(connection)
    if not inspector.has_table(table, schema=schema):
        raise ValueError('certificate_table_required')
    if 'word_standard_snapshot' in {c['name'] for c in inspector.get_columns(table, schema=schema)}:
        return False
    quote = connection.dialect.identifier_preparer
    qualified = (quote.quote_schema(schema) + '.' if schema else '') + quote.quote(table)
    connection.execute(text(f'ALTER TABLE {qualified} ADD COLUMN word_standard_snapshot JSON'))
    return True
