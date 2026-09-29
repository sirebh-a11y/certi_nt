"""Transactional recovery of unambiguous DDT history from the old OL cache.

Only a complete, freshly read eSolver view can establish that a cached row is
historical. The caller owns the transaction and the snapshot advisory lock.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.quarta_taglio.ddt_legacy_audit import classify_legacy_cache
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _apply_snapshot
from app.modules.quarta_taglio.models import QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem


_SOURCE_FIELDS = (
    "source_key", "id_documento", "id_riga_doc", "rif_lotto_alfanum",
    "cod_odp", "cod_f3", "ddt_raw", "ddt_date", "cliente",
    "ordine_cliente", "conferma_ordine", "quantita",
    "certificato_presente_esolver", "certification_unit_key",
)


def import_legacy_cache(db, *, current_rows, now=None):
    """Import current snapshot and safe cached history in one transaction.

    Duplicate/conflicting cache identities are excluded by the shared audit.
    Existing rows are never overwritten with older cache facts.
    """
    now = now or datetime.now(timezone.utc)
    report, candidates = classify_legacy_cache(db, current_rows=current_rows)
    if report["status"] != "classified":
        raise SnapshotError("legacy_source_baseline_required")

    snapshot = _apply_snapshot(db, current_rows, now=now)
    existing = list(db.scalars(select(QuartaTaglioDdtWorkItem)))
    by_key = {item.source_key: item for item in existing}
    by_base = {}
    for item in existing:
        by_base.setdefault((item.id_documento, item.id_riga_doc, item.rif_lotto_alfanum), []).append(item)

    imported = 0
    already_present = report["counts"].get("already_saved_historical", 0)
    existing_conflicts = report["issues"].get("existing_snapshot_data_changed", 0)
    peer_conflicts = report["issues"].get("historical_identity_group_ambiguous", 0)
    for candidate in candidates:
        prior = by_key.get(candidate.source_key)
        if prior is not None:
            raise SnapshotError("legacy_plan_changed")
        base = (candidate.id_documento, candidate.id_riga_doc, candidate.rif_lotto_alfanum)
        if by_base.get(base):
            raise SnapshotError("legacy_plan_changed")
        cached_at = candidate.cache_checked_at or now
        item = QuartaTaglioDdtWorkItem(
            **{field: getattr(candidate, field) for field in _SOURCE_FIELDS},
            first_seen_at=cached_at,
            last_seen_at=cached_at,
            source_present=False,
            # This is when CERTI detected absence, not the unknown eSolver removal time.
            source_disappeared_at=now,
        )
        db.add(item)
        by_key[item.source_key] = item
        by_base.setdefault(base, []).append(item)
        imported += 1

    db.add(QuartaTaglioDdtSyncRun(
        status="success", started_at=now, finished_at=datetime.now(timezone.utc),
        source_rows=snapshot.source_rows, inserted=snapshot.inserted,
        updated=snapshot.updated, reconciled=snapshot.reconciled,
        disappeared=snapshot.disappeared,
    ))
    db.flush()
    return {
        "audit": report,
        "current_snapshot": {
            "source_rows": snapshot.source_rows, "inserted": snapshot.inserted,
            "updated": snapshot.updated, "reconciled": snapshot.reconciled,
            "disappeared": snapshot.disappeared,
        },
        "historical_imported": imported,
        "historical_already_present": already_present,
        "historical_existing_conflicts": existing_conflicts,
        "historical_peer_conflicts": peer_conflicts,
    }
