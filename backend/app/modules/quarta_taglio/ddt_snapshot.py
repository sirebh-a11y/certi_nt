"""Complete eSolver snapshots, independent from the certification page cache.

The entry point owns a dedicated transaction/session. Never pass the UI session:
failures must not commit or roll back the operator's work.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock

from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.core.integrations.models import ExternalConnection
from app.core.logs.service import log_service
from app.core.security.crypto import decrypt_secret
from app.modules.quarta_taglio.models import QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem
from app.modules.quarta_taglio.service import _certifiable_unit_key, _sql_identifier


# Transaction-scoped PostgreSQL lock, released also after errors/process death.
_LOCK_NAMESPACE = 1128616532
_LOCK_ID = 1
_PROCESS_LOCK = Lock()
_COLUMNS = (
    "IdDocumento", "IdRigaDoc", "RifLottoAlfanum", "ORP", "CodF3", "DDT",
    "RagSoc", "ODVCli", "ODVF3", "QtaUmMag", "CertificatoPresente",
)
_QUERY = """
select IdDocumento, IdRigaDoc, RifLottoAlfanum, ORP, CodF3, DDT,
       RagSoc, ODVCli, ODVF3, QtaUmMag, CertificatoPresente
from {qualified_view}
order by IdDocumento, IdRigaDoc, ORP, RifLottoAlfanum
"""


class SnapshotError(Exception):
    """Only a fixed code may leave this module; never driver/credential text."""


@dataclass(frozen=True)
class SnapshotResult:
    status: str
    error_code: str | None = None
    source_rows: int = 0
    inserted: int = 0
    updated: int = 0
    reconciled: int = 0
    disappeared: int = 0


def _clean(value):
    if value is None:
        return None
    return str(value).strip() or None


def source_key(id_documento, id_riga_doc, cod_odp, rif_lotto_alfanum):
    # JSON avoids separator collisions; case and leading zeroes remain intact.
    parts = [_clean(v) for v in (id_documento, id_riga_doc, cod_odp, rif_lotto_alfanum)]
    if not parts[0] or not parts[1]:
        raise SnapshotError("missing_identity")
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


def _date_from_ddt(value):
    match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", value or "")
    if match:
        try:
            return datetime.strptime(match.group(), "%d/%m/%Y").date()
        except ValueError:
            pass
    return None  # Keep the raw value even if its date cannot be interpreted.


def _normalize(row):
    if not isinstance(row, dict) or not set(_COLUMNS).issubset(row):
        raise SnapshotError("invalid_source_columns")
    quantity = row["QtaUmMag"]
    try:
        quantity = Decimal(str(quantity)) if quantity is not None else None
    except (InvalidOperation, ValueError):
        raise SnapshotError("invalid_quantity") from None
    if quantity is not None and not quantity.is_finite():
        raise SnapshotError("invalid_quantity")
    flag = row["CertificatoPresente"]
    if flag is not None and flag not in (0, 1, False, True):
        raise SnapshotError("invalid_certificate_flag")
    values = {
        "id_documento": _clean(row["IdDocumento"]),
        "id_riga_doc": _clean(row["IdRigaDoc"]),
        "rif_lotto_alfanum": _clean(row["RifLottoAlfanum"]),
        "cod_odp": _clean(row["ORP"]),
        "cod_f3": _clean(row["CodF3"]),
        "ddt_raw": _clean(row["DDT"]),
        "cliente": _clean(row["RagSoc"]),
        "ordine_cliente": _clean(row["ODVCli"]),
        "conferma_ordine": _clean(row["ODVF3"]),
        "quantita": quantity,
        "certificato_presente_esolver": bool(flag) if flag is not None else None,
    }
    values["source_key"] = source_key(
        values["id_documento"], values["id_riga_doc"], values["cod_odp"], values["rif_lotto_alfanum"],
    )
    values["ddt_date"] = _date_from_ddt(values["ddt_raw"])
    values["certification_unit_key"] = (
        _certifiable_unit_key(
            cod_odp=values["cod_odp"], cod_f3=values["cod_f3"], ddt=values["ddt_raw"],
            id_documento=values["id_documento"], id_riga_doc=values["id_riga_doc"],
            rif_lotto_alfanum=values["rif_lotto_alfanum"],
            ordine_cliente=values["ordine_cliente"], conferma_ordine=values["conferma_ordine"],
        ) if values["cod_odp"] else None
    )
    return values


def _fetch_complete_snapshot(db):
    connection = db.scalar(select(ExternalConnection).where(ExternalConnection.code == "esolver"))
    if connection is None or not connection.enabled:
        raise SnapshotError("connection_disabled")
    if not connection.password_encrypted:
        raise SnapshotError("credentials_missing")
    view = _sql_identifier(str((connection.object_settings or {}).get("righe_ddt_view") or "CertiRigheDDT"))
    schema = _sql_identifier(connection.schema_name or "dbo")
    if not view or not schema:
        raise SnapshotError("invalid_view_name")
    try:
        import pymssql

        with pymssql.connect(
            server=connection.server_host, port=connection.port, user=connection.username,
            password=decrypt_secret(connection.password_encrypted), database=connection.database_name,
            login_timeout=connection.connection_timeout, timeout=connection.query_timeout, as_dict=True,
        ) as external:
            with external.cursor() as cursor:
                cursor.execute(_QUERY.format(qualified_view=f"[{schema}].[{view}]"))
                # Exhaust the cursor before any local snapshot mutation.
                return list(cursor.fetchall())
    except Exception:
        raise SnapshotError("source_read_failed") from None


def _base_key(values):
    return (values["id_documento"], values["id_riga_doc"], values["rif_lotto_alfanum"])


def _apply_snapshot(db, raw_rows, *, now):
    incoming = {}
    for raw in raw_rows:
        values = _normalize(raw)
        if values["source_key"] in incoming:
            # Even identical duplicates could be distinct shares: do not guess/sum.
            raise SnapshotError("duplicate_source_identity")
        incoming[values["source_key"]] = values

    existing = list(db.scalars(select(QuartaTaglioDdtWorkItem)))
    if not incoming and existing:
        # A successful SQL SELECT returning zero rows does not prove that every
        # previous DDT has legitimately left the source. Keep the last baseline.
        raise SnapshotError("empty_source_requires_review")
    by_key = {item.source_key: item for item in existing}
    old_by_base = defaultdict(list)
    new_by_base = defaultdict(list)
    for item in existing:
        old_by_base[(item.id_documento, item.id_riga_doc, item.rif_lotto_alfanum)].append(item)
    for values in incoming.values():
        new_by_base[_base_key(values)].append(values)

    counts = dict(source_rows=len(raw_rows), inserted=0, updated=0, reconciled=0, disappeared=0)
    for key, values in incoming.items():
        item = by_key.get(key)
        review_reason = None
        if item is None:
            old_peers = old_by_base[_base_key(values)]
            new_peers = new_by_base[_base_key(values)]
            # Promote only a single missing-OL share replaced by one linked share.
            if (values["cod_odp"] and len(old_peers) == len(new_peers) == 1
                    and old_peers[0].cod_odp is None
                    and old_peers[0].source_key not in incoming):
                item = old_peers[0]
                by_key.pop(item.source_key)
                item.source_key = key
                counts["reconciled"] += 1
            else:
                # A disappearing peer plus a new identity needs manual review.
                # Never discard blank-OL peers just because a linked peer exists.
                ambiguous = [old for old in existing
                             if old.id_documento == values["id_documento"]
                             and old.id_riga_doc == values["id_riga_doc"]
                             and old.source_key not in incoming]
                if ambiguous:
                    review_reason = "source_identity_changed"
                    for old in ambiguous:
                        old.source_review_reason = review_reason
                item = QuartaTaglioDdtWorkItem(first_seen_at=now, source_key=key)
                db.add(item)
                counts["inserted"] += 1
            by_key[key] = item
        else:
            counts["updated"] += 1
        for name, value in values.items():
            setattr(item, name, value)
        item.last_seen_at = now
        item.source_present = True
        item.source_disappeared_at = None
        if review_reason:
            item.source_review_reason = review_reason
        elif item.source_review_reason == "ddt_date_unrecognized" and item.ddt_date is not None:
            # A corrected source date resolves this warning, not identity conflicts.
            item.source_review_reason = None
        if item.ddt_raw and item.ddt_date is None:
            item.source_review_reason = item.source_review_reason or "ddt_date_unrecognized"

    for item in existing:
        if item.source_key not in incoming and item.source_present:
            item.source_present = False
            item.source_disappeared_at = now
            counts["disappeared"] += 1
    db.flush()
    from app.modules.quarta_taglio.ddt_decisions import invalidate_changed_exclusions
    invalidate_changed_exclusions(db, list(db.scalars(select(QuartaTaglioDdtWorkItem))), now)
    from app.modules.quarta_taglio.ddt_archive import invalidate_archives
    invalidate_archives(db, list(db.scalars(select(QuartaTaglioDdtWorkItem))), now)
    db.flush()
    return SnapshotResult(status="success", **counts)


def sync_ddt_snapshot(*, session_factory=SessionLocal):
    """Use a dedicated session, atomic batch, and lock shared by PG workers."""
    if not _PROCESS_LOCK.acquire(blocking=False):
        return SnapshotResult(status="busy")
    try:
        with session_factory() as db, db.begin():
            dialect = db.get_bind().dialect.name
            if dialect == "postgresql":
                locked = db.scalar(text("SELECT pg_try_advisory_xact_lock(:namespace, :key)"),
                                   {"namespace": _LOCK_NAMESPACE, "key": _LOCK_ID})
                if not locked:
                    return SnapshotResult(status="busy")
            elif dialect != "sqlite":
                raise SnapshotError("unsupported_database")
            started_at = datetime.now(timezone.utc)
            run = QuartaTaglioDdtSyncRun(status="running", started_at=started_at)
            db.add(run)
            db.flush()
            try:
                with db.begin_nested():
                    rows = _fetch_complete_snapshot(db)
                    result = _apply_snapshot(db, rows, now=datetime.now(timezone.utc))
            except SnapshotError as exc:
                result = SnapshotResult(status="error", error_code=str(exc))
            except Exception:
                # Savepoint restores all row edits; never persist exception text.
                result = SnapshotResult(status="error", error_code="snapshot_write_failed")
            run.status = result.status
            run.error_code = result.error_code
            run.finished_at = datetime.now(timezone.utc)
            for name in ("source_rows", "inserted", "updated", "reconciled", "disappeared"):
                setattr(run, name, getattr(result, name))
        log_service.record("ddt_snapshot", f"Snapshot DDT: {result.status}; righe {result.source_rows}; "
                           f"nuove {result.inserted}; errore {result.error_code or '-'}")
        return result
    finally:
        _PROCESS_LOCK.release()


def last_snapshot_runs(db):
    """Last attempt and last complete success are deliberately independent."""
    latest = db.scalar(select(QuartaTaglioDdtSyncRun).order_by(QuartaTaglioDdtSyncRun.id.desc()).limit(1))
    successful = db.scalar(select(QuartaTaglioDdtSyncRun)
                           .where(QuartaTaglioDdtSyncRun.status == "success")
                           .order_by(QuartaTaglioDdtSyncRun.id.desc()).limit(1))
    return latest, successful
