"""Manual queue decisions; source facts and certificates retain their own lifecycle."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.core.deps import is_quality_area_admin
from app.modules.quarta_taglio.models import QuartaTaglioDdtDecision as Decision, QuartaTaglioDdtWorkItem


SOURCE_FIELDS = (
    "id_documento", "id_riga_doc", "rif_lotto_alfanum", "cod_odp", "cod_f3",
    "ddt_raw", "ddt_date", "cliente", "ordine_cliente", "conferma_ordine",
    "quantita", "source_review_reason",
)
REVIEW_MESSAGE = "Dati eSolver modificati dopo l’esclusione: verificare nuovamente la quota."


def source_facts(item):
    facts = {}
    for name in SOURCE_FIELDS:
        value = getattr(item, name)
        if name == "quantita" and value is not None:
            value = format(Decimal(str(value)).normalize(), "f")
        facts[name] = str(value) if value is not None else None
    return facts


def source_revision(item):
    return hashlib.sha256(json.dumps(source_facts(item), sort_keys=True).encode()).hexdigest()


def latest_decisions(db, ids):
    result = {}
    ids = list(ids)
    for start in range(0, len(ids), 400):
        latest = (select(func.max(Decision.id)).where(Decision.work_item_id.in_(ids[start:start + 400]))
                  .group_by(Decision.work_item_id))
        for decision in db.scalars(select(Decision).where(Decision.id.in_(latest))):
            result[decision.work_item_id] = decision
    return result


def exclusion_valid(item, decision):
    return bool(decision and decision.action == "exclude" and decision.source_facts == source_facts(item))


def invalidate_changed_exclusions(db, items, now):
    """Called within the snapshot transaction; history survives later source reversions."""
    latest = latest_decisions(db, [item.id for item in items])
    for item in items:
        decision = latest.get(item.id)
        if decision and decision.action == "exclude" and not exclusion_valid(item, decision):
            db.add(Decision(work_item_id=item.id, action="review", reason=REVIEW_MESSAGE,
                            actor_name="Sistema", source_facts=source_facts(item), created_at=now))


def require_quality_decider(user):
    if not is_quality_area_admin(user):
        raise HTTPException(403, "Operazione riservata agli amministratori Qualità e IT")
    return user


def change_decision(db, item_id, payload, user):
    require_quality_decider(user)
    # Serialize with snapshot and recovery, including the source-read/decision interval.
    from app.modules.quarta_taglio.ddt_snapshot import _LOCK_ID, _LOCK_NAMESPACE
    from app.modules.quarta_taglio.ddt_queue import _project

    try:
        if db.get_bind().dialect.name == "postgresql":
            locked = db.scalar(text("SELECT pg_try_advisory_xact_lock(:n, :k)"),
                               {"n": _LOCK_NAMESPACE, "k": _LOCK_ID})
            if not locked:
                raise HTTPException(409, "Aggiornamento DDT in corso. Riprova tra poco.")
        item = db.scalar(select(QuartaTaglioDdtWorkItem).where(QuartaTaglioDdtWorkItem.id == item_id)
                         .with_for_update().execution_options(populate_existing=True))
        if item is None:
            raise HTTPException(404, "Quota DDT non trovata")
        from app.modules.quarta_taglio.ddt_archive import require_operational
        require_operational(db, item)
        previous = latest_decisions(db, [item.id]).get(item.id)
        if (payload.expected_decision_id != (previous.id if previous else 0)
                or payload.source_revision != source_revision(item)):
            raise HTTPException(409, "La quota è cambiata. Aggiorna la vista e ripeti la scelta.")
        if payload.action == "exclude":
            if exclusion_valid(item, previous):
                raise HTTPException(409, "Quota già esclusa. Aggiorna la vista.")
            if _project(db, [item])[0].state == "completed":
                raise HTTPException(409, "Il PDF finale è già pronto. Aggiorna la vista.")
        elif not previous or previous.action not in {"exclude", "review"}:
            raise HTTPException(409, "La quota non ha un’esclusione da ripristinare.")
        decision = Decision(work_item_id=item.id, action=payload.action, reason=payload.reason,
                            actor_user_id=user.id, actor_name=user.name,
                            source_facts=source_facts(item), created_at=datetime.now(timezone.utc))
        db.add(decision)
        db.flush()
        result = dict(id=decision.id, action=decision.action)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
