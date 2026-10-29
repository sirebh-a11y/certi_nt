"""Manual entry is a document policy, not a frozen match or an AI reading.

Never infer it from the upload's author, the combined row's AI run, or the
other document's note. No values, hidden supplier anchors or scores are changed.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import AcquisitionHistoryEvent, AcquisitionRow, Document, DocumentEvidence, ReadValue

MANUAL_ENTRY_EVIDENCE = "manual_document_entry"
_explicit_ai = ContextVar("manual_document_explicit_ai", default=frozenset())


@contextmanager
def allow_explicit_ai(*document_ids):
    token = _explicit_ai.set(_explicit_ai.get() | {i for i in document_ids if i is not None})
    try:
        yield
    finally:
        _explicit_ai.reset(token)


def manual_document_reason(db, document):
    """Read-only, including on the old schema; no memoized match/row values."""
    if not isinstance(db, Session) or document is None or document.id is None:
        return None
    evidence = db.query(DocumentEvidence.tipo_evidenza, DocumentEvidence.metodo_estrazione).filter_by(document_id=document.id).all()
    if any(e.tipo_evidenza == MANUAL_ENTRY_EVIDENCE for e in evidence):
        return "explicit_manual_entry"
    if document.tipo_documento not in {"ddt", "certificato"}:
        return None
    side = document.tipo_documento
    column = AcquisitionRow.document_ddt_id if side == "ddt" else AcquisitionRow.document_certificato_id
    row_ids = [row_id for (row_id,) in db.query(AcquisitionRow.id).filter(column == document.id)]
    if not row_ids:
        return None
    event = db.query(AcquisitionHistoryEvent.id).filter(
        AcquisitionHistoryEvent.acquisition_row_id.in_(row_ids),
        AcquisitionHistoryEvent.azione == f"{side}_manuale_creato",
        AcquisitionHistoryEvent.nota_breve == f"Documento #{document.id}",
    ).first()
    if event:
        return "legacy_manual_creation_event"
    # A type check is NOT an extraction of the user's certificate fields.
    if any(e.tipo_evidenza == "ai_payload" or
           (e.metodo_estrazione == "chatgpt" and e.tipo_evidenza != "leichtmetall_document_type_check")
           for e in evidence):
        return None
    block = "ddt" if side == "ddt" else "match"
    fields = ({"numero_certificato_ddt", "colata", "diametro", "lega", "peso", "ordine", "ddt", "customer_order_no"}
              if side == "ddt" else
              {"numero_certificato_certificato", "colata_certificato", "diametro_certificato", "lega_certificato",
               "peso_certificato", "ordine_cliente_certificato", "ddt_certificato"})
    values = db.query(ReadValue).filter(ReadValue.acquisition_row_id.in_(row_ids), ReadValue.blocco == block,
                                      ReadValue.campo.in_(fields)).all()
    # Certainty is per side AND row. Never collect a synthetic identity by
    # combining two partial rows or interpret an edited AI row as manual entry.
    for row_id in row_ids:
        populated = [v for v in values if v.acquisition_row_id == row_id and v.stato != "scartato"
                     and any(str(x).strip() for x in (v.valore_finale, v.valore_standardizzato, v.valore_grezzo) if x is not None)]
        if len(populated) >= 3 and all(v.metodo_lettura == "utente" and v.stato == "confermato" for v in populated):
            return "legacy_manual_side_values"
    return None


def automatic_ai_disabled(db, document):
    return document is not None and document.id not in _explicit_ai.get() and manual_document_reason(db, document) is not None


def require_ai_allowed(db, document):
    if automatic_ai_disabled(db, document):
        raise HTTPException(409, "Documento inserito manualmente: nessuna lettura AI automatica. I dati salvati restano invariati.")


def mark_manual_entry(db, document, *, actor_id):
    """Call in the manual action's transaction. Survives merges and detachments."""
    if db.query(DocumentEvidence.id).filter_by(document_id=document.id, tipo_evidenza=MANUAL_ENTRY_EVIDENCE).first():
        return
    db.add(DocumentEvidence(document_id=document.id, acquisition_row_id=None, blocco="documento",
        tipo_evidenza=MANUAL_ENTRY_EVIDENCE, metodo_estrazione="utente", mascherato=True,
        utente_creazione_id=actor_id,
        testo_grezzo=json.dumps({"version":1,"side":document.tipo_documento,"file_hash":document.hash_file})))
    db.flush()


def protected_document(db, document_id):
    return db.get(Document, document_id) if isinstance(db, Session) and document_id is not None else None
