from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.integrations.models import ExternalConnection
from app.core.security.crypto import decrypt_secret
from app.modules.acquisition.models import AcquisitionRow
from app.modules.acquisition.service import _compute_block_states_from_db
from app.modules.quarta_taglio.models import QuartaTaglioRow, QuartaTaglioSyncRun
from app.modules.quarta_taglio.schemas import QuartaTaglioListResponse, QuartaTaglioRowResponse, QuartaTaglioSyncRunResponse


TAGLIO_QUERY = """
with taglio_saldato as (
    select
        iu.UID_INSTANCE as COD_ODP,
        ip.UID_INSTANCE as CODICE_REGISTRO,
        ip.DT_INSERT as DATA_REGISTRO,
        ip.CFG_CHK_SALDO as SALDO,
        row_number() over (
            partition by iu.UID_INSTANCE
            order by ip.DT_INSERT desc, ip.UID_INSTANCE desc
        ) as rn
    from Q3.dbo.MYQBT_ONGIP ip
    join Q3.dbo.MYQBT_ONGIU iu
        on iu.COD_AZIENDA = ip.COD_AZIENDA
       and iu.COD_RIFERIMENTO = ip.KEY_IU
    join Q3.dbo.MYQBT_PHASE ph
        on ph.COD_AZIENDA = ip.COD_AZIENDA
       and ph.COD_RIFERIMENTO = ip.KEY_PHASE
    where ph.DES_INSTANCE = 'TAGLIO'
      and ip.UID_PHASE_TYPE = 'ONGPHT0002'
      and ip.CFG_CHK_SALDO = '1'
), latest as (
    select top 500 COD_ODP, CODICE_REGISTRO, DATA_REGISTRO, SALDO
    from taglio_saldato
    where rn = 1
    order by DATA_REGISTRO desc, CODICE_REGISTRO desc
)
select
    l.COD_ODP,
    l.CODICE_REGISTRO,
    l.DATA_REGISTRO,
    l.SALDO,
    tr.COD_ART,
    tr.CERT_FORN as CDQ,
    tr.COLATA,
    count(*) as RIGHE_MATERIALE,
    count(distinct tr.COD_LOTTO) as LOTTI,
    sum(cast(tr.QTA as decimal(18,2))) as QTA_TOTALE,
    string_agg(cast(tr.COD_LOTTO as varchar(max)), ',') within group (order by tr.COD_LOTTO) as COD_LOTTI
from latest l
join dbo.CFG_Q3ESS_ONGIUDET_TRACMP tr
    on tr.COD_ODP = l.COD_ODP
group by l.COD_ODP, l.CODICE_REGISTRO, l.DATA_REGISTRO, l.SALDO, tr.COD_ART, tr.CERT_FORN, tr.COLATA
order by l.DATA_REGISTRO desc, l.COD_ODP desc, tr.CERT_FORN, tr.COLATA;
"""


def sync_and_list_quarta_taglio(db: Session, *, actor_id: int | None = None) -> QuartaTaglioListResponse:
    run = QuartaTaglioSyncRun(status="running", triggered_by_user_id=actor_id)
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        external_rows = _fetch_quarta_taglio_rows(db)
        _persist_quarta_rows(db=db, run=run, external_rows=external_rows)
        run.status = "ok"
        run.message = "Aggiornamento Quarta completato"
        run.total_ol = len({str(item.get("COD_ODP") or "").strip() for item in external_rows if item.get("COD_ODP")})
        run.total_cdq_rows = len(external_rows)
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
    except Exception as exc:
        run.status = "error"
        run.message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Aggiornamento Quarta fallito: {exc}") from exc

    return QuartaTaglioListResponse(
        sync_run=_serialize_run(run),
        items=[
            _serialize_row(item)
            for item in db.query(QuartaTaglioRow)
            .filter(QuartaTaglioRow.seen_in_last_sync.is_(True))
            .order_by(QuartaTaglioRow.data_registro.desc(), QuartaTaglioRow.cod_odp.desc(), QuartaTaglioRow.cdq.asc())
            .all()
        ],
    )


def _fetch_quarta_taglio_rows(db: Session) -> list[dict[str, Any]]:
    connection = db.query(ExternalConnection).filter(ExternalConnection.code == "quarta").one_or_none()
    if connection is None or not connection.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connessione Quarta non configurata o disabilitata")
    if not connection.password_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password Quarta non configurata")

    try:
        import pymssql
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Driver SQL Server pymssql non installato") from exc

    password = decrypt_secret(connection.password_encrypted)
    with pymssql.connect(
        server=connection.server_host,
        port=connection.port,
        user=connection.username,
        password=password,
        database=connection.database_name,
        login_timeout=connection.connection_timeout,
        timeout=connection.query_timeout,
        as_dict=True,
    ) as sql_connection:
        with sql_connection.cursor() as cursor:
            cursor.execute(TAGLIO_QUERY)
            return list(cursor.fetchall())


def _persist_quarta_rows(db: Session, *, run: QuartaTaglioSyncRun, external_rows: list[dict[str, Any]]) -> None:
    app_rows = (
        db.query(AcquisitionRow)
        .options(selectinload(AcquisitionRow.values), selectinload(AcquisitionRow.certificate_match))
        .all()
    )
    rows_by_cdq: dict[str, list[AcquisitionRow]] = defaultdict(list)
    for row in app_rows:
        key = _norm(row.cdq)
        if key:
            rows_by_cdq[key].append(row)

    db.query(QuartaTaglioRow).update({QuartaTaglioRow.seen_in_last_sync: False})
    for external_row in external_rows:
        cdq = _clean_text(external_row.get("CDQ"))
        cod_odp = _clean_text(external_row.get("COD_ODP"))
        cod_art = _clean_text(external_row.get("COD_ART"))
        colata = _clean_text(external_row.get("COLATA"))
        if not cdq or not cod_odp:
            continue

        status_color, status_message, status_details, matching_row_ids = _evaluate_cdq(
            db=db,
            cdq=cdq,
            colata=colata,
            rows_by_cdq=rows_by_cdq,
        )

        item = (
            db.query(QuartaTaglioRow)
            .filter(
                QuartaTaglioRow.cod_odp == cod_odp,
                QuartaTaglioRow.cod_art == cod_art,
                QuartaTaglioRow.cdq == cdq,
                QuartaTaglioRow.colata == colata,
            )
            .one_or_none()
        )
        if item is None:
            item = QuartaTaglioRow(cod_odp=cod_odp, cod_art=cod_art, cdq=cdq, colata=colata)

        item.latest_run_id = run.id
        item.codice_registro = _clean_text(external_row.get("CODICE_REGISTRO")) or ""
        item.data_registro = _as_datetime(external_row.get("DATA_REGISTRO"))
        item.saldo = str(external_row.get("SALDO") or "").strip() == "1"
        item.righe_materiale = int(external_row.get("RIGHE_MATERIALE") or 0)
        item.lotti_count = int(external_row.get("LOTTI") or 0)
        item.qta_totale = _as_float(external_row.get("QTA_TOTALE"))
        item.cod_lotti = _split_lotti(external_row.get("COD_LOTTI"))
        item.status_color = status_color
        item.status_message = status_message
        item.status_details = status_details
        item.matching_row_ids = matching_row_ids
        item.seen_in_last_sync = True
        db.add(item)
    db.commit()


def _evaluate_cdq(
    *,
    db: Session,
    cdq: str,
    colata: str | None,
    rows_by_cdq: dict[str, list[AcquisitionRow]],
) -> tuple[str, str, list[str], list[int]]:
    candidates = rows_by_cdq.get(_norm(cdq), [])
    if not candidates:
        return "red", "CDQ non presente in Incoming Quality", ["Certificato/riga mancante nella nostra lista"], []

    exact_rows = [row for row in candidates if _norm(row.colata) == _norm(colata)]
    if not exact_rows:
        details = [f"Colate in app: {', '.join(sorted({_clean_text(row.colata) or '-' for row in candidates}))}"]
        return "red", "CDQ trovato in app, ma colata non coerente con Quarta", details, [row.id for row in candidates]

    details: list[str] = []
    matching_ids = [row.id for row in exact_rows]
    if len(exact_rows) > 1:
        details.append("CDQ presente su più righe app: verifica manuale")

    for row in exact_rows:
        if row.qualita_valutazione == "respinto":
            return "red", "Respinto da qualità", [f"Riga app #{row.id}: valutazione qualità respinta"], matching_ids

    for row in exact_rows:
        block_states = _compute_block_states_from_db(db, row)
        for block, label in (("match", "match"), ("chimica", "chimica"), ("proprieta", "proprietà"), ("note", "note")):
            if block_states.get(block) != "verde":
                details.append(f"Riga app #{row.id}: manca conferma {label}")
        if row.qualita_valutazione is None:
            details.append(f"Riga app #{row.id}: qualità non valutata")
        elif row.qualita_valutazione == "accettato_con_riserva":
            details.append(f"Riga app #{row.id}: accettato con riserva")

    if details:
        return "yellow", "CDQ trovato, ma iter non completo", sorted(set(details)), matching_ids
    return "green", "CDQ coerente e completo", [], matching_ids


def _serialize_run(run: QuartaTaglioSyncRun) -> QuartaTaglioSyncRunResponse:
    return QuartaTaglioSyncRunResponse.model_validate(run)


def _serialize_row(row: QuartaTaglioRow) -> QuartaTaglioRowResponse:
    return QuartaTaglioRowResponse.model_validate(row)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _norm(value: Any) -> str:
    return (_clean_text(value) or "").casefold()


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_lotti(value: Any) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
