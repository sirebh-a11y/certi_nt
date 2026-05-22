from __future__ import annotations

import re
import secrets
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.integrations.models import ExternalConnection
from app.core.roles.constants import ROLE_ADMIN, ROLE_MANAGER
from app.core.security.crypto import decrypt_secret
from app.core.users.models import User
from app.modules.acquisition.models import AcquisitionHistoryEvent, AcquisitionRow, ReadValue
from app.modules.acquisition.service import _compute_block_states_from_db, _sync_row_statuses
from app.modules.quarta_taglio.certificate_docx import (
    build_additional_page_template_docx,
    build_forgialluminio_draft_docx,
    inspect_docx_content_controls,
    update_docx_content_controls,
)
from app.modules.quarta_taglio.models import (
    QuartaTaglioArticleOverride,
    QuartaTaglioCertificateExtraPages,
    QuartaTaglioEsolverLink,
    QuartaTaglioFinalCertificate,
    QuartaTaglioRow,
    QuartaTaglioStandardSelection,
    QuartaTaglioSyncRun,
)
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioAdditionalPagesResponse,
    QuartaTaglioAggregateValueResponse,
    QuartaTaglioCertificateResponse,
    QuartaTaglioCertifiableUnitResponse,
    QuartaTaglioCodF3CandidateResponse,
    QuartaTaglioCodF3CandidateSummaryResponse,
    QuartaTaglioDetailResponse,
    QuartaTaglioEsolverDdtRowResponse,
    QuartaTaglioFinalCertificateRegisterItem,
    QuartaTaglioFinalCertificateRegisterResponse,
    QuartaTaglioListResponse,
    QuartaTaglioMaterialResponse,
    QuartaTaglioMissingItemResponse,
    QuartaTaglioNoteResponse,
    QuartaTaglioConformityIssueResponse,
    QuartaTaglioRowResponse,
    QuartaTaglioStandardCandidateResponse,
    QuartaTaglioSyncRunResponse,
    QuartaTaglioWordDraftResponse,
    QuartaTaglioWordInfoResponse,
)


from app.modules.standards.models import NormativeStandard
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate


@dataclass(frozen=True)
class _AdditionalPagesResolution:
    extra_pages: QuartaTaglioCertificateExtraPages
    is_inherited: bool = False
    inherited_from_certificate_number: str | None = None
    inherited_from_cod_f3: str | None = None


@dataclass(frozen=True)
class _CertiOlRow:
    orp: str | None
    cod_cli: str | None
    rag_soc: str | None
    cod_f3_odp: str | None
    cod_f3: str | None
    des_f3: str | None

STATUS_SEVERITY = {
    "green": 1,
    "yellow": 2,
    "red": 3,
}

CHEMISTRY_FIELDS = [
    "Si",
    "Fe",
    "Cu",
    "Mn",
    "Mg",
    "Cr",
    "Zn",
    "Ti",
    "Ni",
    "Pb",
    "Bi",
    "Sn",
    "V",
    "Zr",
    "Cd",
    "Hg",
    "Be",
    "Mn+Cr",
    "Zr+Ti",
    "Bi+Pb",
]

PROPERTY_FIELDS = ["Rp0.2", "Rm", "A%", "HB", "IACS%", "Rp0.2 / Rm"]

CERTIFICATE_NUMBER_START = 7000
STANDARD_LIMIT_EPSILON = 1e-9
ESOLVER_DDT_BATCH_SIZE = 500

NOTE_FIELDS = [
    ("nota_rohs", "RoHS"),
    ("nota_radioactive_free", "Radioactive free"),
    ("nota_us_control_class_a", "US control Class A"),
    ("nota_us_control_class_b", "US control Class B"),
]

US_CONTROL_NOTE_KEYS = {"nota_us_control_class_a", "nota_us_control_class_b"}

SYSTEM_NOTE_TEXT_FALLBACKS = {
    "nota_us_control_class_a": "U.S. control according to ASTM 594 or SAE AMS STD 2154 class A.",
    "nota_us_control_class_b": "U.S. control according to ASTM 594 or SAE AMS STD 2154 class B.",
    "nota_rohs": (
        "We hereby declare that material is in compliance with DIRECTIVE 2011/65/EU OF THE "
        "EUROPEAN PARLIAMENT AND OF THE COUNCIL of 8 June 2011 on the restriction of the use "
        "of certain hazardous substances (ROHS II) in electrical and electronic equipment."
    ),
    "nota_radioactive_free": "Material free from radioactive contamination.",
}

SYSTEM_NOTE_CODE_KEYS = {
    "us_control_class_a": "nota_us_control_class_a",
    "us_control_class_b": "nota_us_control_class_b",
    "rohs": "nota_rohs",
    "radioactive_free": "nota_radioactive_free",
}


TAGLIO_QUERY = """
with taglio_latest_source as (
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
), latest as (
    select COD_ODP, CODICE_REGISTRO, DATA_REGISTRO, SALDO
    from taglio_latest_source
    where rn = 1
)
select
    coalesce(tr.COD_ODP, l.COD_ODP) as COD_ODP,
    coalesce(l.CODICE_REGISTRO, '') as CODICE_REGISTRO,
    l.DATA_REGISTRO,
    coalesce(l.SALDO, '0') as SALDO,
    case when l.COD_ODP is not null and l.SALDO = '1' then 1 else 0 end as TAGLIO_ATTIVO,
    tr.COD_ART,
    max(cast(tr.DES_ART as nvarchar(max))) as DES_ART,
    tr.CERT_FORN as CDQ,
    tr.COLATA,
    count(tr.COD_ODP) as RIGHE_MATERIALE,
    count(distinct tr.COD_LOTTO) as LOTTI,
    sum(cast(tr.QTA as decimal(18,2))) as QTA_TOTALE,
    string_agg(cast(tr.COD_LOTTO as varchar(max)), ',') within group (order by tr.COD_LOTTO) as COD_LOTTI
from latest l
full outer join dbo.CFG_Q3ESS_ONGIUDET_TRACMP tr
    on tr.COD_ODP = l.COD_ODP
where coalesce(tr.COD_ODP, l.COD_ODP) is not null
group by coalesce(tr.COD_ODP, l.COD_ODP), l.COD_ODP, l.CODICE_REGISTRO, l.DATA_REGISTRO, l.SALDO, tr.COD_ART, tr.CERT_FORN, tr.COLATA
order by
    case when l.DATA_REGISTRO is null then 1 else 0 end,
    l.DATA_REGISTRO desc,
    coalesce(tr.COD_ODP, l.COD_ODP) desc,
    tr.CERT_FORN,
    tr.COLATA;
"""


ESOLVER_DDT_QUERY_TEMPLATE = """
select
    cast(CodF3 as varchar(128)) as CodF3,
    cast(ORP as varchar(128)) as ORP,
    cast(RagSoc as varchar(255)) as RagSoc,
    cast(ODVCli as varchar(128)) as ODVCli,
    cast(ODVF3 as varchar(128)) as ODVF3,
    cast(DDT as varchar(128)) as DDT,
    QtaUmMag,
    CertificatoPresente
from {qualified_view}
where ltrim(rtrim(cast(ORP as varchar(128)))) = %s
order by DDT, IdDocumento, IdRigaDoc
"""


ESOLVER_DDT_BATCH_QUERY_TEMPLATE = """
select
    cast(CodF3 as varchar(128)) as CodF3,
    cast(ORP as varchar(128)) as ORP,
    cast(RagSoc as varchar(255)) as RagSoc,
    cast(ODVCli as varchar(128)) as ODVCli,
    cast(ODVF3 as varchar(128)) as ODVF3,
    cast(DDT as varchar(128)) as DDT,
    QtaUmMag,
    CertificatoPresente
from {qualified_view}
where ltrim(rtrim(cast(ORP as varchar(128)))) in ({placeholders})
order by ORP, DDT, IdDocumento, IdRigaDoc
"""

ESOLVER_CERTIOL_BATCH_QUERY_TEMPLATE = """
select
    cast(ORP as varchar(128)) as ORP,
    cast(CodCli as varchar(128)) as CodCli,
    cast(RagSoc as varchar(255)) as RagSoc,
    cast(CodF3ODP as varchar(128)) as CodF3ODP,
    cast(CodF3 as varchar(128)) as CodF3,
    cast(DesF3 as varchar(max)) as DesF3
from {qualified_view}
where ltrim(rtrim(cast(ORP as varchar(128)))) in ({placeholders})
order by ORP, CodF3
"""


def sync_and_list_quarta_taglio(
    db: Session,
    *,
    actor_id: int | None = None,
    sync_data: bool = True,
    only_taglio_active: bool = False,
    hide_certified: bool = False,
    limit: int = 25,
    offset: int = 0,
    query_one: str | None = None,
    query_two: str | None = None,
    query_three: str | None = None,
    operator_one: str = "and",
    operator_two: str = "and",
    sort_field: str | None = None,
    sort_direction: str = "asc",
) -> QuartaTaglioListResponse:
    run = _sync_quarta_rows(db, actor_id=actor_id) if sync_data else _latest_quarta_sync_run(db)
    if run is None:
        run = _sync_quarta_rows(db, actor_id=actor_id)

    rows_query = db.query(QuartaTaglioRow).filter(QuartaTaglioRow.seen_in_last_sync.is_(True))
    if only_taglio_active:
        rows_query = rows_query.filter(QuartaTaglioRow.taglio_attivo.is_(True))
    if hide_certified:
        certified_cod_odps = (
            db.query(QuartaTaglioFinalCertificate.cod_odp)
            .filter(QuartaTaglioFinalCertificate.certificate_number.isnot(None))
            .distinct()
        )
        rows_query = rows_query.filter(QuartaTaglioRow.cod_odp.not_in(certified_cod_odps))
    rows = rows_query.order_by(QuartaTaglioRow.data_registro.desc(), QuartaTaglioRow.cod_odp.desc(), QuartaTaglioRow.cdq.asc()).all()

    grouped_rows = _group_quarta_rows(rows)
    cached_esolver_links = _load_esolver_links_for_rows(db, rows=rows)
    group_summaries = [
        _serialize_ol_group(group_rows, esolver_link=cached_esolver_links.get(group_rows[0].cod_odp))
        for group_rows in grouped_rows
    ]
    filtered_groups = _filter_quarta_groups(
        list(zip(group_summaries, grouped_rows, strict=True)),
        query_one=query_one,
        query_two=query_two,
        query_three=query_three,
        operator_one=operator_one,
        operator_two=operator_two,
    )
    filtered_groups.sort(
        key=lambda item: _quarta_group_sort_key(item[0], sort_field=sort_field),
        reverse=True if not sort_field else (sort_direction == "desc"),
    )
    total_items = len(filtered_groups)
    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 1000)
    page_groups = filtered_groups[safe_offset : safe_offset + safe_limit]
    page_raw_rows = [row for _summary, group_rows in page_groups for row in group_rows]
    esolver_links = _refresh_esolver_links_for_rows(db, rows=page_raw_rows)
    certiol_rows_by_odp = _fetch_certiol_rows_batch(db, [summary.cod_odp for summary, _group_rows in page_groups])
    page_items = [
        _serialize_ol_group(
            group_rows,
            esolver_link=esolver_links.get(summary.cod_odp),
            cod_f3_candidates=_build_certiol_candidates(
                certiol_rows=certiol_rows_by_odp.get(summary.cod_odp, []),
                quarta_rows=group_rows,
                esolver_rows=_esolver_rows_from_link(esolver_links.get(summary.cod_odp)),
            ),
        )
        for summary, group_rows in page_groups
    ]
    return QuartaTaglioListResponse(
        sync_run=_serialize_run(run),
        items=page_items,
        total_items=total_items,
        offset=safe_offset,
        limit=safe_limit,
        only_taglio_active=only_taglio_active,
        hide_certified=hide_certified,
    )


def _sync_quarta_rows(db: Session, *, actor_id: int | None = None) -> QuartaTaglioSyncRun:
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
        return run
    except Exception as exc:
        run.status = "error"
        run.message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Aggiornamento Quarta fallito: {exc}") from exc


def _latest_quarta_sync_run(db: Session) -> QuartaTaglioSyncRun | None:
    return db.query(QuartaTaglioSyncRun).order_by(QuartaTaglioSyncRun.started_at.desc(), QuartaTaglioSyncRun.id.desc()).first()


def list_quarta_taglio_final_certificates(db: Session) -> QuartaTaglioFinalCertificateRegisterResponse:
    _refresh_final_certificate_register_from_external_data(db)
    certificates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(QuartaTaglioFinalCertificate.certificate_number.isnot(None))
        .order_by(QuartaTaglioFinalCertificate.cert_date.desc(), QuartaTaglioFinalCertificate.id.desc())
        .all()
    )
    ol_with_unit_specific_certificates = {
        certificate.cod_odp
        for certificate in certificates
        if _clean_text(certificate.unit_key)
    }
    visible_certificates = [
        certificate
        for certificate in certificates
        if _clean_text(certificate.unit_key) or certificate.cod_odp not in ol_with_unit_specific_certificates
    ]
    return QuartaTaglioFinalCertificateRegisterResponse(
        items=[_serialize_final_certificate_register_item(certificate) for certificate in visible_certificates],
        total_items=len(visible_certificates),
    )


def _refresh_final_certificate_register_from_external_data(db: Session) -> None:
    cod_odps = [
        row[0]
        for row in db.query(QuartaTaglioFinalCertificate.cod_odp)
        .filter(QuartaTaglioFinalCertificate.certificate_number.isnot(None))
        .distinct()
        .all()
        if _clean_text(row[0])
    ]
    stale_cod_odps = _stale_register_cod_odps(db, cod_odps=cod_odps)
    for cod_odp in stale_cod_odps:
        try:
            get_quarta_taglio_detail(db, cod_odp=cod_odp)
        except HTTPException:
            db.rollback()
    db.commit()


def _stale_register_cod_odps(db: Session, *, cod_odps: list[str]) -> list[str]:
    if not cod_odps:
        return []
    freshness_cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    links = (
        db.query(QuartaTaglioEsolverLink)
        .filter(QuartaTaglioEsolverLink.cod_odp.in_(cod_odps))
        .all()
    )
    links_by_odp = {_clean_text(link.cod_odp): link for link in links}
    stale: list[str] = []
    for cod_odp in cod_odps:
        link = links_by_odp.get(_clean_text(cod_odp))
        if link is None or link.last_checked_at is None or link.last_checked_at < freshness_cutoff:
            stale.append(cod_odp)
    return stale


def get_quarta_taglio_detail(db: Session, *, cod_odp: str, certificate_id: int | None = None) -> QuartaTaglioDetailResponse:
    rows = (
        db.query(QuartaTaglioRow)
        .filter(QuartaTaglioRow.cod_odp == cod_odp)
        .order_by(QuartaTaglioRow.cdq.asc(), QuartaTaglioRow.colata.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OL non trovato in Certificazione")

    esolver_links = _refresh_esolver_links_for_rows(db, rows=rows)
    esolver_link = esolver_links.get(cod_odp)
    group = _serialize_ol_group(rows, esolver_link=esolver_link)
    app_rows = _load_matching_app_rows(db, rows)
    materials = [
        QuartaTaglioMaterialResponse(
            cdq=row.cdq,
            colata=row.colata,
            cod_art=row.cod_art,
            des_art=row.des_art,
            qta_totale=row.qta_totale,
            righe_materiale=row.righe_materiale,
            cod_lotti=row.cod_lotti,
            matching_row_ids=row.matching_row_ids,
        )
        for row in rows
    ]
    missing_items = [
        QuartaTaglioMissingItemResponse(
            cdq=row.cdq,
            colata=row.colata,
            status_color=row.status_color,
            message=row.status_message,
            details=row.status_details,
        )
        for row in rows
        if row.status_color != "green"
    ]

    standard_candidates = _suggest_standard_candidates(db, app_rows=app_rows, materials=materials)
    confirmed_selection = (
        db.query(QuartaTaglioStandardSelection)
        .options(selectinload(QuartaTaglioStandardSelection.standard))
        .filter(QuartaTaglioStandardSelection.cod_odp == group.cod_odp)
        .one_or_none()
    )
    selected_standard_confirmed = confirmed_selection is not None
    selected_standard = _selection_to_candidate(confirmed_selection) if confirmed_selection else None
    if selected_standard is None and standard_candidates and standard_candidates[0].confidence == "alta":
        selected_standard = standard_candidates[0]
    selected_standard_model = (
        db.query(NormativeStandard)
        .options(selectinload(NormativeStandard.chemistry_limits), selectinload(NormativeStandard.property_limits))
        .filter(NormativeStandard.id == selected_standard.id)
        .one_or_none()
        if selected_standard
        else None
    )

    material_weights = {_norm(row.cdq): row.qta_totale for row in rows if _norm(row.cdq)}
    chemistry = _aggregate_block_values(
        fields=_chemistry_fields_for_detail(standard=selected_standard_model, app_rows=app_rows),
        block="chimica",
        app_rows=app_rows,
        material_weights=material_weights,
        standard=selected_standard_model,
    )
    properties = _aggregate_block_values(
        fields=PROPERTY_FIELDS,
        block="proprieta",
        app_rows=app_rows,
        material_weights=material_weights,
        standard=selected_standard_model,
        standard_confirmed=selected_standard_confirmed,
    )
    conformity_status, conformity_issues = _build_standard_conformity(
        chemistry=chemistry,
        properties=properties,
        selected_standard_confirmed=selected_standard_confirmed,
    )
    quick_confirm_blockers = _quick_incoming_confirm_blockers(
        app_rows=app_rows,
        selected_standard_confirmed=selected_standard_confirmed,
        conformity_status=conformity_status,
    )
    quick_confirm_applied = _quick_incoming_confirm_applied(app_rows)
    quick_confirm_warning = (
        "Standard modificato: controlla in Incoming chimica e proprietà dei CDQ collegati."
        if quick_confirm_applied and selected_standard_confirmed and conformity_status != "conforme"
        else None
    )
    esolver_rows = _esolver_rows_from_link(esolver_link)
    esolver_status = esolver_link.status if esolver_link else "not_checked"
    esolver_message = esolver_link.message if esolver_link else "Dati eSolver non ancora controllati"
    certiol_rows = _fetch_certiol_rows_batch(db, [group.cod_odp]).get(group.cod_odp, [])
    cod_f3_candidates = _build_certiol_candidates(
        certiol_rows=certiol_rows,
        quarta_rows=rows,
        esolver_rows=esolver_rows,
    )
    cod_f3_candidates = _enrich_certiol_candidates_with_certificates(
        db,
        cod_odp=group.cod_odp,
        candidates=cod_f3_candidates,
    )
    if esolver_status != "ok":
        missing_items.append(
            QuartaTaglioMissingItemResponse(
                cdq="eSolver/DDT",
                status_color=_esolver_block_color(esolver_status),
                message=esolver_message or "Dati eSolver mancanti",
                details=["Cliente, ordine, DDT e quantità finale non ancora disponibili"] if esolver_status in {"missing", "not_checked"} else [],
            )
        )
    notes = _evaluate_notes(app_rows, system_note_texts=_system_note_texts(db))
    ready = group.status_color == "green" and esolver_status == "ok"
    detail_status_color = group.status_color if esolver_status == "ok" else _max_status_color(group.status_color, _esolver_block_color(esolver_status))
    des_art = _join_unique((row.des_art for row in rows), separator=" | ")
    descrizione_proposta, disegno_proposta, disegno_confidenza = _split_des_art(des_art)
    article_override = db.query(QuartaTaglioArticleOverride).filter(QuartaTaglioArticleOverride.cod_odp == group.cod_odp).one_or_none()
    descrizione_override = article_override.descrizione if article_override else None
    disegno_override = article_override.disegno if article_override else None
    descrizione = descrizione_override or descrizione_proposta
    disegno = disegno_override or disegno_proposta
    esolver_header_rows = esolver_rows
    certifiable_units = _build_certifiable_units(cod_odp=group.cod_odp, esolver_rows=esolver_rows, quarta_rows=rows)
    selected_certificate = _get_certificate_context(db, cod_odp=group.cod_odp, certificate_id=certificate_id)
    primary_unit = _select_unit_for_certificate(certifiable_units, selected_certificate) or _primary_certifiable_unit(certifiable_units)
    esolver_qta = (
        selected_certificate.quantita
        if selected_certificate is not None and selected_certificate.quantita is not None
        else primary_unit.quantita
        if primary_unit
        else _sum_optional(row.qta_um_mag for row in esolver_header_rows)
    )
    codice_f3 = _codice_f3_from_unit_or_quarta(unit=primary_unit, quarta_rows=rows)
    open_certificate = selected_certificate or _find_open_certificate_for_detail(db, cod_odp=group.cod_odp, unit_key=primary_unit.unit_key if primary_unit else None)
    header_flow = _certificate_header_flow(
        current_unit=primary_unit,
        certifiable_units=certifiable_units,
        quarta_rows=rows,
        raw_description=des_art,
        raw_cod_f3_override=next((_clean_text(candidate.cod_f3_odp) for candidate in cod_f3_candidates if _clean_text(candidate.cod_f3_odp)), None),
    )
    detail_certificate_date = (
        _certificate_datetime_from_ddt(open_certificate.ddt if open_certificate else None)
        or _certificate_datetime_from_ddt(primary_unit.ddt if primary_unit else None)
    )
    open_certificate_number = (
        open_certificate.certificate_number or open_certificate.draft_number
        if open_certificate is not None and (open_certificate.certificate_number or open_certificate.draft_number)
        else None
    )

    word_creation_blockers = _word_creation_blockers(
        db=db,
        quarta_rows=rows,
        app_rows=app_rows,
        selected_standard_confirmed=selected_standard_confirmed,
    )
    can_create_word = not word_creation_blockers

    detail = QuartaTaglioDetailResponse(
        cod_odp=group.cod_odp,
        ready=ready,
        status_color=detail_status_color,
        status_message="Certificato pronto da preparare" if ready else "Dati ancora mancanti per creare il certificato",
        can_create_word=can_create_word,
        word_creation_blockers=word_creation_blockers,
        header={
            "numero_certificato": open_certificate_number,
            "certificate_id": str(open_certificate.id) if open_certificate else None,
            "unit_key": _clean_text(open_certificate.unit_key) if open_certificate else primary_unit.unit_key if primary_unit else None,
            "cliente": _clean_text(open_certificate.fornitore_cliente) if open_certificate else primary_unit.cliente if primary_unit else _join_unique(row.rag_soc for row in esolver_header_rows) or None,
            "ordine_cliente": _clean_text(open_certificate.ordine_cliente) if open_certificate else primary_unit.ordine_cliente if primary_unit else _join_unique(row.odv_cli for row in esolver_header_rows) or None,
            "conferma_ordine": _clean_text(open_certificate.cdo_lega) if open_certificate else primary_unit.conferma_ordine if primary_unit else _join_unique(row.odv_f3 for row in esolver_header_rows) or None,
            "ddt": _clean_text(open_certificate.ddt) if open_certificate else primary_unit.ddt if primary_unit else _join_unique(row.ddt for row in esolver_header_rows) or None,
            "data_certificato": _format_certificate_date(detail_certificate_date),
            "codice_f3": _clean_text(open_certificate.cod_f3) if open_certificate else codice_f3["value"],
            "codice_f3_origine": codice_f3["origin"],
            "codice_f3_esolver": codice_f3["esolver"],
            "codice_f3_quarta": codice_f3["quarta"],
            "codice_f3_warning": codice_f3["warning"],
            "codice_f3_raw": header_flow["raw_cod_f3"],
            "descrizione_raw": header_flow["raw_description"],
            "ddt_raw": header_flow["raw_ddt"],
            "quantita_raw": header_flow["raw_quantita"],
            "codice_f3_finished": header_flow["finished_cod_f3"],
            "descrizione_finished": header_flow["finished_description"],
            "ddt_finished": header_flow["finished_ddt"],
            "quantita_finished": header_flow["finished_quantita"],
            "descrizione_articolo_quarta": des_art,
            "descrizione": descrizione,
            "descrizione_proposta": descrizione_proposta,
            "descrizione_override": descrizione_override,
            "descrizione_origine": "utente" if descrizione_override else "quarta",
            "descrizione_diversa_da_quarta": "true" if descrizione_override and _norm(descrizione_override) != _norm(descrizione_proposta) else None,
            "disegno": disegno,
            "disegno_proposta": disegno_proposta,
            "disegno_override": disegno_override,
            "disegno_origine": "utente" if disegno_override else "quarta",
            "disegno_diverso_da_quarta": "true" if disegno_override and _norm(disegno_override) != _norm(disegno_proposta) else None,
            "disegno_confidenza": disegno_confidenza,
            "colata": group.colata,
            "materiale_fornito": _join_unique(_materiale_fornito_from_app_row(row) for row in app_rows) or None,
            "diametro": _join_unique(row.diametro for row in app_rows) or None,
            "materiale_raw": _join_unique((_materiale_raw_from_app_row(row) for row in app_rows), separator=" | ") or None,
            "quantita": _format_quantity(esolver_qta if esolver_qta is not None else group.qta_totale)
            if (esolver_qta is not None or group.qta_totale is not None)
            else None,
        },
        materials=materials,
        missing_items=missing_items,
        standard_candidates=standard_candidates,
        selected_standard=selected_standard,
        selected_standard_confirmed=selected_standard_confirmed,
        chemistry=chemistry,
        properties=properties,
        notes=notes,
        conformity_status=conformity_status,
        conformity_issues=conformity_issues,
        quick_incoming_confirm_available=not quick_confirm_blockers,
        quick_incoming_confirm_applied=quick_confirm_applied,
        quick_incoming_confirm_blockers=quick_confirm_blockers,
        quick_incoming_confirm_warning=quick_confirm_warning,
        esolver_status=esolver_status,
        esolver_message=esolver_message,
        esolver_rows=esolver_rows,
        cod_f3_candidates=cod_f3_candidates,
        cod_f3_candidate_summary=_certiol_candidate_summary(cod_f3_candidates),
        certifiable_units=certifiable_units,
        additional_pages=_serialize_additional_pages(
            db,
            certificate_number=open_certificate_number,
            cod_odp=group.cod_odp,
            cod_f3=_clean_text(open_certificate.cod_f3) if open_certificate else primary_unit.cod_f3 if primary_unit else None,
        ),
        word_info=_serialize_word_info(open_certificate),
    )
    if _has_numbered_certificate_for_ol(db, cod_odp=group.cod_odp):
        _sync_certifiable_unit_register(db, detail=detail, actor=None, create_missing=True)
        db.commit()
    return detail


def confirm_quarta_taglio_standard(
    db: Session,
    *,
    cod_odp: str,
    standard_id: int,
    actor_id: int | None,
) -> QuartaTaglioDetailResponse:
    exists = db.query(QuartaTaglioRow.id).filter(QuartaTaglioRow.cod_odp == cod_odp).first()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OL non trovato in Certificazione")

    standard = (
        db.query(NormativeStandard)
        .filter(NormativeStandard.id == standard_id, NormativeStandard.stato_validazione == "attivo")
        .one_or_none()
    )
    if standard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standard non trovato o non attivo")

    selection = (
        db.query(QuartaTaglioStandardSelection)
        .filter(QuartaTaglioStandardSelection.cod_odp == cod_odp)
        .one_or_none()
    )
    if selection is None:
        selection = QuartaTaglioStandardSelection(cod_odp=cod_odp)
    selection.standard_id = standard.id
    selection.selected_by_user_id = actor_id
    db.add(selection)
    db.commit()
    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp)
    _sync_open_certificate_conformity(db, detail=detail)
    return detail


def apply_quick_incoming_confirmation(
    db: Session,
    *,
    cod_odp: str,
    certificate_id: int | None,
    actor_id: int | None,
) -> QuartaTaglioDetailResponse:
    rows = (
        db.query(QuartaTaglioRow)
        .filter(QuartaTaglioRow.cod_odp == cod_odp)
        .order_by(QuartaTaglioRow.cdq.asc(), QuartaTaglioRow.colata.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OL non trovato in Certificazione")

    app_rows = _load_matching_app_rows(db, rows)
    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)
    blockers = _quick_incoming_confirm_blockers(
        app_rows=app_rows,
        selected_standard_confirmed=detail.selected_standard_confirmed,
        conformity_status=detail.conformity_status,
    )
    if blockers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(blockers))

    for row in app_rows:
        for block in ("chimica", "proprieta"):
            block_values = [
                value
                for value in row.values
                if value.blocco == block and _read_value_has_payload_for_quick_confirm(value)
            ]
            block_changed = False
            for value in block_values:
                if value.stato != "confermato":
                    value.stato = "confermato"
                    value.utente_ultima_modifica_id = actor_id
                    value.timestamp_ultima_modifica = datetime.now(timezone.utc)
                    db.add(value)
                    block_changed = True
            if block_changed or not _has_quick_confirmation_event(row, block):
                db.add(
                    AcquisitionHistoryEvent(
                        acquisition_row_id=row.id,
                        blocco=block,
                        azione="conferma_rapida_certificazione",
                        utente_id=actor_id,
                        nota_breve=f"OL {cod_odp}",
                    )
                )
        _sync_row_statuses(db, row)
        db.add(row)

    db.commit()
    return get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)


def update_quarta_taglio_article_data(
    db: Session,
    *,
    cod_odp: str,
    descrizione: str | None,
    disegno: str | None,
    fields_set: set[str],
    actor_id: int | None,
) -> QuartaTaglioDetailResponse:
    exists = db.query(QuartaTaglioRow.id).filter(QuartaTaglioRow.cod_odp == cod_odp).first()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OL non trovato in Certificazione")

    override = db.query(QuartaTaglioArticleOverride).filter(QuartaTaglioArticleOverride.cod_odp == cod_odp).one_or_none()
    if override is None:
        override = QuartaTaglioArticleOverride(cod_odp=cod_odp)

    if "descrizione" in fields_set:
        override.descrizione = _clean_text(descrizione)
    if "disegno" in fields_set:
        override.disegno = _clean_text(disegno)
    override.updated_by_user_id = actor_id
    db.add(override)
    db.commit()
    return get_quarta_taglio_detail(db, cod_odp=cod_odp)


def create_quarta_taglio_word_draft(
    db: Session,
    *,
    cod_odp: str,
    actor: User,
    force_non_conforming: bool = False,
    force_regenerate: bool = False,
    certificate_id: int | None = None,
    candidate_cod_f3: str | None = None,
) -> QuartaTaglioWordDraftResponse:
    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)
    candidate = _candidate_by_cod_f3(detail.cod_f3_candidates, candidate_cod_f3)
    candidate_unit: QuartaTaglioCertifiableUnitResponse | None = None
    if candidate_cod_f3 and candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CodF3 candidato non trovato per questo OL")
    if candidate is not None:
        if candidate.confidence == "review":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CodF3 candidato da verificare: attendere DDT o scegliere un candidato affidabile")
        if candidate.blocked_reason:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=candidate.blocked_reason)
        candidate_unit = _unit_from_certiol_candidate(detail=detail, candidate=candidate)
        detail = _detail_for_certiol_candidate(detail=detail, candidate=candidate, unit=candidate_unit)
    _ensure_word_draft_can_be_created(detail)
    if detail.conformity_issues and not force_non_conforming:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Non conformità standard presenti: confermare esplicitamente per creare il Word numerato",
                "conformity_status": detail.conformity_status,
                "conformity_issues": [issue.model_dump() for issue in detail.conformity_issues],
            },
        )

    _sync_certifiable_unit_register(db, detail=detail, actor=actor, create_missing=True)
    certificate = (
        _get_or_create_open_certificate_for_unit(db, detail=detail, unit=candidate_unit, actor=actor)
        if candidate_unit is not None
        else _get_or_create_open_certificate(db, detail=detail, actor=actor)
    )
    if _is_manual_word(certificate) and not force_regenerate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Word corrente caricato dall'utente: usa Aggiorna campi Word oppure conferma Rigenera da zero.",
        )
    certificate_date = _certificate_datetime_from_detail(detail)
    certificate.cert_date = certificate_date
    certificate_number = certificate.certificate_number or _assign_certificate_number(
        db,
        cdq_key=certificate.cdq_key,
        cod_odp=certificate.cod_odp,
        cod_f3=certificate.cod_f3 or (detail.header or {}).get("codice_f3"),
        now=certificate_date,
    )
    certificate.certificate_number = certificate_number
    certificate.draft_number = certificate_number
    certificate.status = certificate.status or "draft"
    certificate.cert_date = certificate_date
    certificate.cdq_key = certificate.cdq_key or _cdq_key_from_detail(detail)
    certificate.cdq_signature = _cdq_signature_from_detail(detail)
    certificate.cdq_values = _cdq_values_from_detail(detail)
    _apply_certificate_register_fields(certificate, detail)
    _apply_certificate_conformity(certificate, detail)

    storage_key = _certificate_docx_storage_key(cod_odp)
    output_path = _certificate_storage_path(storage_key)
    quality_manager = _select_quality_manager(db)
    additional_pages_path = _additional_pages_path_for_certificate(
        db,
        certificate_number=certificate_number,
        cod_odp=certificate.cod_odp,
        cod_f3=certificate.cod_f3 or (detail.header or {}).get("codice_f3"),
    )
    build_forgialluminio_draft_docx(
        detail=detail,
        output_path=output_path,
        draft_number=certificate_number,
        certified_by=actor,
        quality_manager=quality_manager,
        additional_pages_path=additional_pages_path,
    )

    certificate.storage_key_docx = storage_key
    certificate.download_token = secrets.token_urlsafe(32)
    certificate.certified_by_user_id = actor.id
    certificate.quality_manager_user_id = quality_manager.id if quality_manager else None
    _apply_word_file_state(certificate, output_path, source="generated")
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return QuartaTaglioWordDraftResponse(
        id=certificate.id,
        cod_odp=certificate.cod_odp,
        draft_number=certificate.draft_number,
        file_name=_certificate_file_name(certificate),
        download_url=f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}",
        created_at=certificate.created_at,
    )


def upload_quarta_taglio_additional_pages(
    db: Session,
    *,
    cod_odp: str,
    uploaded_file: UploadFile,
    actor: User,
    certificate_id: int | None = None,
) -> QuartaTaglioWordDraftResponse:
    if uploaded_file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file Word deve avere un nome")

    original_name = Path(uploaded_file.filename).name
    if Path(original_name).suffix.lower() != ".docx":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caricare un file Word .docx")

    file_bytes = uploaded_file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file Word caricato è vuoto")

    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)
    certificate = _certificate_for_current_detail(db, detail=detail, certificate_id=certificate_id, require_number=True)
    if certificate is None or not certificate.certificate_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generare prima il Word numerato del certificato")
    if _is_manual_word(certificate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Word corrente caricato dall'utente: aggiungi o togli pagine in Word e ricarica il file modificato.",
        )

    extra_storage_key = _certificate_extra_pages_storage_key(certificate.certificate_number, original_name=original_name)
    extra_path = _certificate_storage_path(extra_storage_key)
    extra_path.parent.mkdir(parents=True, exist_ok=True)
    extra_path.write_bytes(file_bytes)

    extra_pages = (
        db.query(QuartaTaglioCertificateExtraPages)
        .filter(QuartaTaglioCertificateExtraPages.certificate_number == certificate.certificate_number)
        .one_or_none()
    )
    if extra_pages is None:
        extra_pages = QuartaTaglioCertificateExtraPages(
            certificate_number=certificate.certificate_number,
            cod_odp=cod_odp,
        )
    extra_pages.storage_key_docx = extra_storage_key
    extra_pages.original_filename = original_name
    extra_pages.uploaded_by_user_id = actor.id
    db.add(extra_pages)

    storage_key = _certificate_docx_storage_key(cod_odp)
    output_path = _certificate_storage_path(storage_key)
    quality_manager = _select_quality_manager(db)
    build_forgialluminio_draft_docx(
        detail=detail,
        output_path=output_path,
        draft_number=certificate.certificate_number,
        certified_by=actor,
        quality_manager=quality_manager,
        additional_pages_path=extra_path,
    )
    certificate.storage_key_docx = storage_key
    certificate.download_token = secrets.token_urlsafe(32)
    certificate.certified_by_user_id = actor.id
    certificate.quality_manager_user_id = quality_manager.id if quality_manager else None
    certificate.status = certificate.status or "draft"
    _apply_certificate_register_fields(certificate, detail)
    _apply_certificate_conformity(certificate, detail)
    _apply_word_file_state(certificate, output_path, source="generated")
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return QuartaTaglioWordDraftResponse(
        id=certificate.id,
        cod_odp=certificate.cod_odp,
        draft_number=certificate.draft_number,
        file_name=_certificate_file_name(certificate),
        download_url=f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}",
        created_at=certificate.created_at,
    )


def get_quarta_taglio_additional_page_template_file() -> tuple[Path, str]:
    file_name = "modello_seconda_pagina_forgialluminio.docx"
    path = Path(settings.document_storage_root) / "templates" / file_name
    build_additional_page_template_docx(path)
    return path, file_name


def upload_quarta_taglio_word_file(
    db: Session,
    *,
    cod_odp: str,
    uploaded_file: UploadFile,
    actor: User,
    certificate_id: int | None = None,
) -> QuartaTaglioWordDraftResponse:
    if uploaded_file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file Word deve avere un nome")

    original_name = Path(uploaded_file.filename).name
    if Path(original_name).suffix.lower() != ".docx":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caricare un file Word .docx")

    file_bytes = uploaded_file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file Word caricato è vuoto")

    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)
    certificate = _find_open_certificate_for_detail(
        db,
        cod_odp=cod_odp,
        unit_key=(detail.header or {}).get("unit_key"),
        require_number=True,
    )
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generare prima il Word numerato del certificato")

    storage_key = _certificate_uploaded_docx_storage_key(cod_odp, original_name=original_name)
    output_path = _certificate_storage_path(storage_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(file_bytes)

    certificate.storage_key_docx = storage_key
    certificate.download_token = secrets.token_urlsafe(32)
    certificate.certified_by_user_id = actor.id
    certificate.status = certificate.status or "draft"
    _apply_word_file_state(certificate, output_path, source="user_uploaded", original_filename=original_name)
    _apply_certificate_register_fields(certificate, detail)
    _apply_certificate_conformity(certificate, detail)
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return QuartaTaglioWordDraftResponse(
        id=certificate.id,
        cod_odp=certificate.cod_odp,
        draft_number=certificate.draft_number,
        file_name=_certificate_file_name(certificate),
        download_url=f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}",
        created_at=certificate.created_at,
    )


def update_quarta_taglio_word_fields(
    db: Session,
    *,
    cod_odp: str,
    actor: User,
    certificate_id: int | None = None,
) -> QuartaTaglioWordDraftResponse:
    detail = get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)
    certificate = _certificate_for_current_detail(db, detail=detail, certificate_id=certificate_id, require_number=True)
    if certificate is None or not certificate.storage_key_docx:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nessun Word corrente da aggiornare")
    source_path = _certificate_storage_path(certificate.storage_key_docx)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File Word corrente non trovato")

    storage_key = _certificate_docx_storage_key(cod_odp)
    output_path = _certificate_storage_path(storage_key)
    update_docx_content_controls(source_path, output_path, _word_content_control_values(detail, certificate))
    certificate.storage_key_docx = storage_key
    certificate.download_token = secrets.token_urlsafe(32)
    certificate.certified_by_user_id = actor.id
    certificate.word_source = "fields_updated"
    certificate.word_content_controls, certificate.word_missing_content_controls = inspect_docx_content_controls(output_path)
    certificate.status = certificate.status or "draft"
    _apply_certificate_register_fields(certificate, detail)
    _apply_certificate_conformity(certificate, detail)
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return QuartaTaglioWordDraftResponse(
        id=certificate.id,
        cod_odp=certificate.cod_odp,
        draft_number=certificate.draft_number,
        file_name=_certificate_file_name(certificate),
        download_url=f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}",
        created_at=certificate.created_at,
    )


def _apply_word_file_state(
    certificate: QuartaTaglioFinalCertificate,
    path: Path,
    *,
    source: str,
    original_filename: str | None = None,
) -> None:
    present, missing = inspect_docx_content_controls(path)
    certificate.word_source = source
    certificate.word_original_filename = original_filename
    certificate.word_content_controls = present
    certificate.word_missing_content_controls = missing


def _is_manual_word(certificate: QuartaTaglioFinalCertificate | None) -> bool:
    return _clean_text(getattr(certificate, "word_source", None)) in {"user_uploaded", "fields_updated"}


def _word_content_control_values(detail: QuartaTaglioDetailResponse, certificate: QuartaTaglioFinalCertificate) -> dict[str, object]:
    header = detail.header or {}
    return _word_content_control_values_from_header(header, certificate)


def _word_content_control_values_from_header(header: dict[str, object], certificate: QuartaTaglioFinalCertificate) -> dict[str, object]:
    return {
        "CERT_NUMBER": certificate.certificate_number or certificate.draft_number or header.get("numero_certificato") or "",
        "CERT_DATE": header.get("data_certificato") or "",
        "PURCHASER": header.get("cliente") or "",
        "ORDER_CLIENT": header.get("ordine_cliente") or "",
        "CONFIRM_ORDER": header.get("conferma_ordine") or "",
        "COD_F3_RAW": header.get("codice_f3_raw") or "",
        "RAW_DESCRIPTION": header.get("descrizione_raw") or "",
        "DDT_RAW": header.get("ddt_raw") or "",
        "QUANTITY_RAW": header.get("quantita_raw") or "",
        "COD_F3_FINISHED": header.get("codice_f3_finished") or "",
        "FINISHED_DESCRIPTION": header.get("descrizione_finished") or "",
        "DDT_FINISHED": header.get("ddt_finished") or "",
        "QUANTITY_FINISHED": header.get("quantita_finished") or "",
    }


def _word_content_control_values_for_unit(
    detail: QuartaTaglioDetailResponse,
    certificate: QuartaTaglioFinalCertificate,
    unit: QuartaTaglioCertifiableUnitResponse,
) -> dict[str, object]:
    header = dict(detail.header or {})
    raw_cod_f3 = _clean_text(header.get("codice_f3_raw")) or _join_unique(item.cod_art for item in detail.materials) or None
    raw_unit = unit if _norm(unit.cod_f3) == _norm(raw_cod_f3) else _unit_for_cod_f3(detail.certifiable_units, raw_cod_f3)
    finished_unit = unit if _norm(unit.cod_f3) and _norm(unit.cod_f3) != _norm(raw_cod_f3) else None
    unit_date = _certificate_datetime_from_ddt(unit.ddt)
    header.update(
        {
            "numero_certificato": certificate.certificate_number or certificate.draft_number,
            "data_certificato": _format_certificate_date(unit_date) or header.get("data_certificato") or "",
            "cliente": unit.cliente or header.get("cliente") or "",
            "ordine_cliente": unit.ordine_cliente or header.get("ordine_cliente") or "",
            "conferma_ordine": unit.conferma_ordine or header.get("conferma_ordine") or "",
            "codice_f3_raw": raw_cod_f3 or "",
            "descrizione_raw": header.get("descrizione_raw") or _join_unique((item.des_art for item in detail.materials), separator=" | ") or "",
            "ddt_raw": raw_unit.ddt if raw_unit and raw_unit.ddt else "",
            "quantita_raw": _format_quantity(raw_unit.quantita) if raw_unit and raw_unit.ddt and raw_unit.quantita is not None else "",
            "codice_f3_finished": _clean_text(finished_unit.cod_f3) if finished_unit else "",
            "descrizione_finished": header.get("descrizione_finished") or "",
            "ddt_finished": _clean_text(finished_unit.ddt) if finished_unit and finished_unit.ddt else "",
            "quantita_finished": _format_quantity(finished_unit.quantita) if finished_unit and finished_unit.ddt and finished_unit.quantita is not None else "",
        }
    )
    return _word_content_control_values_from_header(header, certificate)


def _unit_from_certiol_candidate(
    *,
    detail: QuartaTaglioDetailResponse,
    candidate: QuartaTaglioCodF3CandidateResponse,
) -> QuartaTaglioCertifiableUnitResponse:
    return QuartaTaglioCertifiableUnitResponse(
        unit_key=_certifiable_unit_key(cod_odp=detail.cod_odp, cod_f3=candidate.cod_f3, ddt=None),
        cod_odp=detail.cod_odp,
        cod_f3=candidate.cod_f3,
        ddt=None,
        cliente=candidate.rag_soc,
        quantita=None,
        certificato_presente=None,
        source="certiol",
        status="ready",
        message="CodF3 preparato da CertiOL in attesa DDT",
        rows_count=1,
        is_primary=True,
    )


def _detail_for_certiol_candidate(
    *,
    detail: QuartaTaglioDetailResponse,
    candidate: QuartaTaglioCodF3CandidateResponse,
    unit: QuartaTaglioCertifiableUnitResponse,
) -> QuartaTaglioDetailResponse:
    raw_cod_f3 = candidate.cod_f3_odp or _join_unique(item.cod_art for item in detail.materials) or None
    raw_description = (detail.header or {}).get("descrizione_raw") or _join_unique((item.des_art for item in detail.materials), separator=" | ") or ""
    is_raw = _norm(candidate.cod_f3) == _norm(raw_cod_f3)
    units = [item.model_copy(update={"is_primary": False}) for item in detail.certifiable_units if item.unit_key != unit.unit_key]
    units.insert(0, unit)
    header = dict(detail.header or {})
    header.update(
        {
            "unit_key": unit.unit_key,
            "cliente": candidate.rag_soc or header.get("cliente"),
            "codice_f3": candidate.cod_f3,
            "codice_f3_origine": "certiol",
            "codice_f3_esolver": candidate.cod_f3,
            "codice_f3_warning": None,
            "codice_f3_raw": raw_cod_f3,
            "descrizione_raw": candidate.des_f3 if is_raw and candidate.des_f3 else raw_description,
            "ddt_raw": header.get("ddt_raw") if is_raw else "",
            "quantita_raw": header.get("quantita_raw") if is_raw else "",
            "codice_f3_finished": "" if is_raw else candidate.cod_f3,
            "descrizione_finished": "" if is_raw else candidate.des_f3 or "",
            "ddt_finished": "",
            "quantita_finished": "",
            "descrizione": candidate.des_f3 or header.get("descrizione"),
            "data_certificato": header.get("data_certificato") or "",
            "ddt": "",
            "quantita": header.get("quantita") or "",
        }
    )
    return detail.model_copy(update={"header": header, "certifiable_units": units})


def _certificate_for_current_detail(
    db: Session,
    *,
    detail: QuartaTaglioDetailResponse,
    certificate_id: int | None,
    require_number: bool,
) -> QuartaTaglioFinalCertificate | None:
    if certificate_id is not None:
        certificate = _get_certificate_context(db, cod_odp=detail.cod_odp, certificate_id=certificate_id)
        if require_number and not certificate.certificate_number:
            return None
        return certificate
    return _find_open_certificate_for_detail(
        db,
        cod_odp=detail.cod_odp,
        unit_key=(detail.header or {}).get("unit_key"),
        require_number=require_number,
    )


def _get_or_create_open_certificate(
    db: Session,
    *,
    detail: QuartaTaglioDetailResponse,
    actor: User,
) -> QuartaTaglioFinalCertificate:
    certificate = _find_open_certificate_for_detail(db, cod_odp=detail.cod_odp, unit_key=(detail.header or {}).get("unit_key"))
    if certificate is None:
        certificate = QuartaTaglioFinalCertificate(
            cod_odp=detail.cod_odp,
            status="draft",
            certificate_number=None,
            draft_number="",
            unit_key=(detail.header or {}).get("unit_key"),
            cdq_key=_cdq_key_from_detail(detail),
            cdq_signature=_cdq_signature_from_detail(detail),
            cdq_values=_cdq_values_from_detail(detail),
            cert_date=_certificate_datetime_from_detail(detail) or datetime.now(timezone.utc),
            download_token=secrets.token_urlsafe(32),
            created_by_user_id=actor.id,
        )
        _apply_certificate_register_fields(certificate, detail)
        db.add(certificate)
        db.flush()
    else:
        _apply_certificate_register_fields(certificate, detail)
        if not certificate.cdq_key:
            certificate.cdq_key = _cdq_key_from_detail(detail)
        detail_certificate_date = _certificate_datetime_from_detail(detail)
        if detail_certificate_date:
            certificate.cert_date = detail_certificate_date
        elif not certificate.cert_date:
            certificate.cert_date = datetime.now(timezone.utc)
    return certificate


def _get_or_create_open_certificate_for_unit(
    db: Session,
    *,
    detail: QuartaTaglioDetailResponse,
    unit: QuartaTaglioCertifiableUnitResponse | None,
    actor: User,
) -> QuartaTaglioFinalCertificate:
    if unit is None:
        return _get_or_create_open_certificate(db, detail=detail, actor=actor)
    certificate = _find_open_certificate_for_detail(db, cod_odp=detail.cod_odp, unit_key=unit.unit_key)
    if certificate is None:
        certificate = QuartaTaglioFinalCertificate(
            cod_odp=detail.cod_odp,
            status="draft",
            certificate_number=None,
            draft_number="",
            unit_key=unit.unit_key,
            cdq_key=_cdq_key_from_detail(detail),
            cdq_signature=_cdq_signature_from_detail(detail),
            cdq_values=_cdq_values_from_detail(detail),
            cert_date=_certificate_datetime_from_ddt(unit.ddt) or datetime.now(timezone.utc),
            download_token=secrets.token_urlsafe(32),
            created_by_user_id=actor.id,
        )
        _apply_certificate_register_unit_fields(certificate, detail=detail, unit=unit)
        db.add(certificate)
        db.flush()
    else:
        _apply_certificate_register_unit_fields(certificate, detail=detail, unit=unit)
        if not certificate.cdq_key:
            certificate.cdq_key = _cdq_key_from_detail(detail)
        if not certificate.cert_date:
            certificate.cert_date = datetime.now(timezone.utc)
    return certificate


def _find_open_certificate_for_detail(
    db: Session,
    *,
    cod_odp: str,
    unit_key: str | None,
    require_number: bool = False,
) -> QuartaTaglioFinalCertificate | None:
    query = db.query(QuartaTaglioFinalCertificate).filter(
        QuartaTaglioFinalCertificate.cod_odp == cod_odp,
        QuartaTaglioFinalCertificate.status != "pdf_final",
    )
    if require_number:
        query = query.filter(QuartaTaglioFinalCertificate.certificate_number.isnot(None))

    if unit_key:
        certificate = (
            query.filter(QuartaTaglioFinalCertificate.unit_key == unit_key)
            .order_by(QuartaTaglioFinalCertificate.created_at.desc(), QuartaTaglioFinalCertificate.id.desc())
            .first()
        )
        if certificate is not None:
            return certificate
        has_unit_specific_certificate = query.filter(QuartaTaglioFinalCertificate.unit_key.isnot(None)).first() is not None
        if has_unit_specific_certificate:
            return None

    return (
        query.filter(QuartaTaglioFinalCertificate.unit_key.is_(None))
        .order_by(QuartaTaglioFinalCertificate.created_at.desc(), QuartaTaglioFinalCertificate.id.desc())
        .first()
    )


def _cdq_key_from_detail(detail: QuartaTaglioDetailResponse) -> str:
    values = sorted(
        {
            re.sub(r"\s+", "", _clean_text(item.cdq) or "").upper()
            for item in detail.materials
            if _clean_text(item.cdq)
        }
    )
    return "|".join(values)


def _cdq_values_from_detail(detail: QuartaTaglioDetailResponse) -> list[dict[str, Any]]:
    return [
        {
            "cdq": item.cdq,
            "colata": item.colata,
            "codice_f3": detail.header.get("codice_f3") if detail.header else None,
            "cod_art": item.cod_art,
            "qta_totale": item.qta_totale,
            "lotti": item.cod_lotti,
        }
        for item in detail.materials
    ]


def _apply_certificate_register_fields(certificate: QuartaTaglioFinalCertificate, detail: QuartaTaglioDetailResponse) -> None:
    header = detail.header or {}
    certificate.unit_key = _clean_text(header.get("unit_key")) or certificate.unit_key
    certificate.cod_f3 = _clean_text(header.get("codice_f3")) or _join_unique(item.cod_art for item in detail.materials) or None
    certificate.ddt = _clean_text(header.get("ddt"))
    certificate_date = _certificate_datetime_from_detail(detail)
    if certificate_date:
        certificate.cert_date = certificate_date
    certificate.ordine_cliente = _clean_text(header.get("ordine_cliente"))
    certificate.quantita = _as_float(header.get("quantita"))
    certificate.lega_cod_f3 = certificate.cod_f3
    certificate.cdo_lega = _clean_text(header.get("conferma_ordine")) or certificate.ordine_cliente
    certificate.fornitore_cliente = _clean_text(header.get("cliente"))


def _apply_certificate_register_unit_fields(
    certificate: QuartaTaglioFinalCertificate,
    *,
    detail: QuartaTaglioDetailResponse,
    unit: QuartaTaglioCertifiableUnitResponse,
) -> None:
    certificate.unit_key = unit.unit_key
    certificate.cod_f3 = _clean_text(unit.cod_f3)
    certificate.ddt = _clean_text(unit.ddt)
    certificate_date = _certificate_datetime_from_ddt(unit.ddt)
    if certificate_date:
        certificate.cert_date = certificate_date
    certificate.ordine_cliente = _clean_text(unit.ordine_cliente)
    certificate.quantita = unit.quantita
    certificate.lega_cod_f3 = certificate.cod_f3
    certificate.cdo_lega = _clean_text(unit.conferma_ordine) or certificate.ordine_cliente
    certificate.fornitore_cliente = _clean_text(unit.cliente)
    certificate.cdq_key = certificate.cdq_key or _cdq_key_from_detail(detail)
    certificate.cdq_signature = _cdq_signature_from_detail(detail)
    certificate.cdq_values = _cdq_values_from_detail(detail)


def _has_numbered_certificate_for_ol(db: Session, *, cod_odp: str) -> bool:
    return (
        db.query(QuartaTaglioFinalCertificate.id)
        .filter(
            QuartaTaglioFinalCertificate.cod_odp == cod_odp,
            QuartaTaglioFinalCertificate.certificate_number.isnot(None),
        )
        .first()
        is not None
    )


def _sync_certifiable_unit_register(
    db: Session,
    *,
    detail: QuartaTaglioDetailResponse,
    actor: User | None,
    create_missing: bool,
) -> list[QuartaTaglioFinalCertificate]:
    units = [unit for unit in detail.certifiable_units if unit.status == "ready"]
    if not units:
        return []

    existing_certificates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(QuartaTaglioFinalCertificate.cod_odp == detail.cod_odp)
        .order_by(QuartaTaglioFinalCertificate.created_at.asc(), QuartaTaglioFinalCertificate.id.asc())
        .all()
    )
    existing_by_unit_key = {
        _clean_text(certificate.unit_key): certificate
        for certificate in existing_certificates
        if _clean_text(certificate.unit_key)
    }
    used_certificate_ids: set[int] = set()
    synced: list[QuartaTaglioFinalCertificate] = []
    cert_date = datetime.now(timezone.utc)
    cdq_key = _cdq_key_from_detail(detail)
    for unit in units:
        certificate = existing_by_unit_key.get(unit.unit_key) or _find_existing_certificate_for_unit(
            existing_certificates,
            unit=unit,
            used_certificate_ids=used_certificate_ids,
        )
        if certificate is None:
            if not create_missing:
                continue
            certificate = QuartaTaglioFinalCertificate(
                cod_odp=detail.cod_odp,
                status="draft",
                certificate_number=None,
                draft_number="",
                unit_key=unit.unit_key,
                cdq_key=cdq_key,
                cdq_signature=_cdq_signature_from_detail(detail),
                cdq_values=_cdq_values_from_detail(detail),
                cert_date=_certificate_datetime_from_ddt(unit.ddt) or cert_date,
                download_token=secrets.token_urlsafe(32),
                created_by_user_id=actor.id if actor else None,
            )
            db.add(certificate)
            db.flush()
            existing_by_unit_key[unit.unit_key] = certificate
        if certificate.id is not None:
            used_certificate_ids.add(certificate.id)

        if certificate.status == "pdf_final":
            synced.append(certificate)
            continue
        _apply_certificate_register_unit_fields(certificate, detail=detail, unit=unit)
        if certificate.unit_key:
            existing_by_unit_key[certificate.unit_key] = certificate
        unit_certificate_date = _certificate_datetime_from_ddt(unit.ddt)
        if unit_certificate_date:
            certificate.cert_date = unit_certificate_date
        elif not certificate.cert_date:
            certificate.cert_date = cert_date
        if not certificate.certificate_number:
            certificate.certificate_number = _assign_certificate_number(
                db,
                cdq_key=certificate.cdq_key,
                cod_odp=certificate.cod_odp,
                cod_f3=certificate.cod_f3,
                now=certificate.cert_date,
            )
        certificate.draft_number = certificate.certificate_number or certificate.draft_number
        _apply_certificate_conformity(certificate, detail)
        if certificate.certificate_number and _ensure_register_word_current(db, certificate=certificate, detail=detail, unit=unit):
            db.add(certificate)
        db.add(certificate)
        synced.append(certificate)
    db.flush()
    return synced


def _find_existing_certificate_for_unit(
    certificates: list[QuartaTaglioFinalCertificate],
    *,
    unit: QuartaTaglioCertifiableUnitResponse,
    used_certificate_ids: set[int],
) -> QuartaTaglioFinalCertificate | None:
    unit_cod_f3 = _norm(unit.cod_f3)
    if not unit_cod_f3:
        return None

    candidates = [
        certificate
        for certificate in certificates
        if certificate.id not in used_certificate_ids
        and certificate.status != "pdf_final"
        and _norm(certificate.cod_f3) == unit_cod_f3
    ]
    if not candidates:
        return None

    unit_ddt = _norm(unit.ddt)
    exact_ddt = next((certificate for certificate in candidates if unit_ddt and _norm(certificate.ddt) == unit_ddt), None)
    if exact_ddt is not None:
        return exact_ddt
    missing_ddt = next((certificate for certificate in candidates if not _norm(certificate.ddt)), None)
    return missing_ddt


def _apply_certificate_conformity(certificate: QuartaTaglioFinalCertificate, detail: QuartaTaglioDetailResponse) -> None:
    certificate.conformity_status = detail.conformity_status
    certificate.conformity_issues = [issue.model_dump() for issue in detail.conformity_issues]


def _get_certificate_context(
    db: Session,
    *,
    cod_odp: str,
    certificate_id: int | None,
) -> QuartaTaglioFinalCertificate | None:
    if certificate_id is None:
        return None
    certificate = db.get(QuartaTaglioFinalCertificate, certificate_id)
    if certificate is None or certificate.cod_odp != cod_odp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Riga certificato non trovata per questo OL")
    return certificate


def _select_unit_for_certificate(
    units: list[QuartaTaglioCertifiableUnitResponse],
    certificate: QuartaTaglioFinalCertificate | None,
) -> QuartaTaglioCertifiableUnitResponse | None:
    if certificate is None:
        return None
    certificate_unit_key = _clean_text(certificate.unit_key)
    if certificate_unit_key:
        unit = next((item for item in units if item.unit_key == certificate_unit_key), None)
        if unit is not None:
            return unit
    certificate_cod_f3 = _norm(certificate.cod_f3)
    certificate_ddt = _norm(certificate.ddt)
    certificate_order = _norm(certificate.ordine_cliente)
    certificate_cdo = _norm(certificate.cdo_lega)
    return next(
        (
            item
            for item in units
            if _norm(item.cod_f3) == certificate_cod_f3
            and _norm(item.ddt) == certificate_ddt
            and _norm(item.ordine_cliente) == certificate_order
            and _norm(item.conferma_ordine) == certificate_cdo
        ),
        None,
    )


def _sync_open_certificate_conformity(db: Session, *, detail: QuartaTaglioDetailResponse) -> None:
    certificate = _find_open_certificate_for_detail(
        db,
        cod_odp=detail.cod_odp,
        unit_key=(detail.header or {}).get("unit_key"),
        require_number=True,
    )
    if certificate is None:
        return
    _apply_certificate_conformity(certificate, detail)
    db.add(certificate)
    db.commit()


def _assign_certificate_number(
    db: Session,
    *,
    cdq_key: str | None,
    cod_odp: str | None = None,
    cod_f3: str | None = None,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    year_suffix = f"{issued_at.year % 100:02d}"
    key = _clean_text(cdq_key)
    cod_f3_suffix = _cod_f3_certificate_suffix(cod_f3)
    if key:
        existing_for_key = (
            db.query(QuartaTaglioFinalCertificate)
            .filter(
                QuartaTaglioFinalCertificate.cdq_key == key,
                QuartaTaglioFinalCertificate.certificate_number.isnot(None),
            )
            .order_by(QuartaTaglioFinalCertificate.created_at.asc(), QuartaTaglioFinalCertificate.id.asc())
            .all()
        )
        if existing_for_key:
            base_number = _certificate_main_number(existing_for_key[0].certificate_number)
            if base_number is not None:
                suffix = _certificate_suffix_for_ol_or_next(
                    existing_for_key,
                    base_number=base_number,
                    year_suffix=year_suffix,
                    cod_odp=cod_odp,
                )
                return f"{base_number}_{_format_certificate_suffix(suffix)}_{cod_f3_suffix}/{year_suffix}"

    max_main = CERTIFICATE_NUMBER_START - 1
    for certificate in db.query(QuartaTaglioFinalCertificate).filter(QuartaTaglioFinalCertificate.certificate_number.isnot(None)).all():
        main_number = _certificate_main_number(certificate.certificate_number)
        if main_number is not None:
            max_main = max(max_main, main_number)
    return f"{max_main + 1}_00_{cod_f3_suffix}/{year_suffix}"


def _certificate_main_number(value: str | None) -> int | None:
    match = re.match(r"^\s*(\d+)(?:_\d+)?(?:_\d+)?/\d{2}\s*$", value or "")
    if not match:
        return None
    return int(match.group(1))


def _certificate_suffix_parts(value: str | None) -> tuple[int, int | None, str] | None:
    match = re.match(r"^\s*(\d+)(?:_(\d+))?(?:_\d+)?/(\d{2})\s*$", value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)) if match.group(2) else None, match.group(3)


def _next_certificate_suffix(
    certificates: list[QuartaTaglioFinalCertificate],
    *,
    base_number: int,
    year_suffix: str,
) -> int:
    max_suffix = -1
    for certificate in certificates:
        parts = _certificate_suffix_parts(certificate.certificate_number)
        if parts is None:
            continue
        main_number, suffix, suffix_year = parts
        if main_number == base_number and suffix_year == year_suffix and suffix is not None:
            max_suffix = max(max_suffix, suffix)
    return max_suffix + 1


def _certificate_suffix_for_ol_or_next(
    certificates: list[QuartaTaglioFinalCertificate],
    *,
    base_number: int,
    year_suffix: str,
    cod_odp: str | None,
) -> int:
    current_ol = _norm(cod_odp)
    if current_ol:
        for certificate in certificates:
            if _norm(getattr(certificate, "cod_odp", None)) != current_ol:
                continue
            parts = _certificate_suffix_parts(certificate.certificate_number)
            if parts is None:
                continue
            main_number, suffix, suffix_year = parts
            if main_number == base_number and suffix_year == year_suffix:
                return suffix or 0
    return _next_certificate_suffix(certificates, base_number=base_number, year_suffix=year_suffix)


def _format_certificate_suffix(suffix: int) -> str:
    return f"{suffix:02d}"


def _cod_f3_certificate_suffix(cod_f3: str | None) -> str:
    digits = re.sub(r"\D", "", _clean_text(cod_f3) or "")
    if len(digits) >= 2:
        return digits[-2:]
    if digits:
        return digits.zfill(2)
    return "00"


def get_quarta_taglio_word_draft_file(db: Session, *, draft_id: int, download_token: str | None) -> tuple[Path, str]:
    certificate = db.get(QuartaTaglioFinalCertificate, draft_id)
    if certificate is None or not certificate.storage_key_docx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bozza Word non trovata")
    if not certificate.download_token or not download_token or not secrets.compare_digest(certificate.download_token, download_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Download non autorizzato")
    path = _certificate_storage_path(certificate.storage_key_docx)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File Word non trovato")
    return path, _certificate_file_name(certificate)


def _ensure_word_draft_can_be_created(detail: QuartaTaglioDetailResponse) -> None:
    if not detail.can_create_word:
        blockers = detail.word_creation_blockers or ["Dati certificato non completi"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile creare il Word: " + "; ".join(blockers),
        )


def _certificate_docx_storage_key(cod_odp: str) -> str:
    now = datetime.now(timezone.utc)
    filename = f"{uuid4().hex}_{_safe_file_part(cod_odp)}_bozza.docx"
    return f"certificati_finali/{now:%Y/%m}/{filename}"


def _certificate_uploaded_docx_storage_key(cod_odp: str, *, original_name: str) -> str:
    now = datetime.now(timezone.utc)
    filename = f"{uuid4().hex}_{_safe_file_part(cod_odp)}_{_safe_file_part(original_name)}"
    return f"certificati_finali/{now:%Y/%m}/{filename}"


def _certificate_extra_pages_storage_key(certificate_number: str, *, original_name: str) -> str:
    now = datetime.now(timezone.utc)
    filename = f"{uuid4().hex}_{_safe_file_part(certificate_number)}_{_safe_file_part(original_name)}"
    return f"certificati_finali/{now:%Y/%m}/pagine_aggiuntive/{filename}"


def _certificate_storage_path(storage_key: str) -> Path:
    root = Path(settings.document_storage_root).resolve()
    path = (root / Path(storage_key)).resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percorso certificato non valido")
    return path


def _certificate_file_name(certificate: QuartaTaglioFinalCertificate) -> str:
    return f"{_safe_file_part(certificate.draft_number)}_{_safe_file_part(certificate.cod_odp)}.docx"


def _additional_pages_path_for_certificate(
    db: Session,
    *,
    certificate_number: str | None,
    cod_odp: str | None = None,
    cod_f3: str | None = None,
) -> Path | None:
    resolution = _resolve_additional_pages_for_certificate(
        db,
        certificate_number=certificate_number,
        cod_odp=cod_odp,
        cod_f3=cod_f3,
    )
    if resolution is None:
        return None
    path = _certificate_storage_path(resolution.extra_pages.storage_key_docx)
    return path if path.exists() else None


def _additional_pages_for_certificate(
    db: Session,
    *,
    certificate_number: str | None,
) -> QuartaTaglioCertificateExtraPages | None:
    cleaned_number = _clean_text(certificate_number)
    if not cleaned_number:
        return None
    return (
        db.query(QuartaTaglioCertificateExtraPages)
        .filter(QuartaTaglioCertificateExtraPages.certificate_number == cleaned_number)
        .one_or_none()
    )


def _resolve_additional_pages_for_certificate(
    db: Session,
    *,
    certificate_number: str | None,
    cod_odp: str | None = None,
    cod_f3: str | None = None,
) -> _AdditionalPagesResolution | None:
    cleaned_number = _clean_text(certificate_number)
    exact_pages = _additional_pages_for_certificate(db, certificate_number=cleaned_number)
    if exact_pages is not None:
        return _AdditionalPagesResolution(extra_pages=exact_pages)

    current_cod_f3 = _cod_f3_sort_value(cod_f3)
    current_ol = _norm(cod_odp)
    if current_cod_f3 is None or not current_ol:
        return None

    certificates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(
            QuartaTaglioFinalCertificate.cod_odp == cod_odp,
            QuartaTaglioFinalCertificate.certificate_number.isnot(None),
            QuartaTaglioFinalCertificate.cod_f3.isnot(None),
        )
        .order_by(QuartaTaglioFinalCertificate.created_at.desc(), QuartaTaglioFinalCertificate.id.desc())
        .all()
    )
    visited_numbers = {cleaned_number} if cleaned_number else set()
    for _ in range(len(certificates) + 1):
        previous = _previous_cod_f3_certificate(
            certificates,
            cod_odp=cod_odp,
            current_cod_f3=current_cod_f3,
            visited_numbers=visited_numbers,
        )
        if previous is None or not previous.certificate_number:
            return None
        previous_number = _clean_text(previous.certificate_number)
        visited_numbers.add(previous_number)
        previous_pages = _additional_pages_for_certificate(db, certificate_number=previous_number)
        if previous_pages is not None:
            return _AdditionalPagesResolution(
                extra_pages=previous_pages,
                is_inherited=True,
                inherited_from_certificate_number=previous_number,
                inherited_from_cod_f3=_clean_text(previous.cod_f3),
            )
        previous_cod_f3 = _cod_f3_sort_value(previous.cod_f3)
        if previous_cod_f3 is None or previous_cod_f3 >= current_cod_f3:
            return None
        current_cod_f3 = previous_cod_f3
    return None


def _previous_cod_f3_certificate(
    certificates: list[QuartaTaglioFinalCertificate],
    *,
    cod_odp: str | None,
    current_cod_f3: int,
    visited_numbers: set[str],
) -> QuartaTaglioFinalCertificate | None:
    current_ol = _norm(cod_odp)
    best: QuartaTaglioFinalCertificate | None = None
    best_cod_f3: int | None = None
    for certificate in certificates:
        certificate_number = _clean_text(certificate.certificate_number)
        if not certificate_number or certificate_number in visited_numbers:
            continue
        if _norm(certificate.cod_odp) != current_ol:
            continue
        candidate_cod_f3 = _cod_f3_sort_value(certificate.cod_f3)
        if candidate_cod_f3 is None or candidate_cod_f3 >= current_cod_f3:
            continue
        if best_cod_f3 is None or candidate_cod_f3 > best_cod_f3:
            best = certificate
            best_cod_f3 = candidate_cod_f3
    return best


def _cod_f3_sort_value(value: str | None) -> int | None:
    digits = re.sub(r"\D", "", _clean_text(value) or "")
    return int(digits) if digits else None


def _serialize_additional_pages(
    db: Session,
    *,
    certificate_number: str | None,
    cod_odp: str | None = None,
    cod_f3: str | None = None,
) -> QuartaTaglioAdditionalPagesResponse | None:
    resolution = _resolve_additional_pages_for_certificate(
        db,
        certificate_number=certificate_number,
        cod_odp=cod_odp,
        cod_f3=cod_f3,
    )
    if resolution is None:
        return None
    extra_pages = resolution.extra_pages
    uploader = db.get(User, extra_pages.uploaded_by_user_id) if extra_pages.uploaded_by_user_id else None
    return QuartaTaglioAdditionalPagesResponse(
        certificate_number=extra_pages.certificate_number,
        original_filename=extra_pages.original_filename,
        uploaded_at=extra_pages.updated_at,
        uploaded_by=uploader.name if uploader else None,
        is_inherited=resolution.is_inherited,
        inherited_from_certificate_number=resolution.inherited_from_certificate_number,
        inherited_from_cod_f3=resolution.inherited_from_cod_f3,
    )


def _serialize_word_info(certificate: QuartaTaglioFinalCertificate | None) -> QuartaTaglioWordInfoResponse:
    if certificate is None or not certificate.storage_key_docx:
        return QuartaTaglioWordInfoResponse()
    download_url = (
        f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}"
        if certificate.download_token
        else None
    )
    present = certificate.word_content_controls or []
    missing = certificate.word_missing_content_controls or []
    source = certificate.word_source or "generated"
    if not present and not missing and certificate.storage_key_docx:
        path = _certificate_storage_path(certificate.storage_key_docx)
        if path.exists():
            present, missing = inspect_docx_content_controls(path)
    return QuartaTaglioWordInfoResponse(
        has_word=True,
        source=source,
        source_label=_word_source_label(source),
        original_filename=certificate.word_original_filename,
        content_controls_present=present,
        content_controls_missing=missing,
        content_controls_ok=not missing,
        updated_at=certificate.updated_at,
        download_url=download_url,
    )


def _word_source_label(source: str | None) -> str:
    if source == "user_uploaded":
        return "Caricato dall'utente"
    if source == "fields_updated":
        return "Aggiornato nei campi"
    if source == "inherited":
        return "Ereditato e aggiornato"
    if source == "generated":
        return "Generato dal sistema"
    return "Word corrente"


def _ensure_register_word_current(
    db: Session,
    *,
    certificate: QuartaTaglioFinalCertificate,
    detail: QuartaTaglioDetailResponse,
    unit: QuartaTaglioCertifiableUnitResponse | None = None,
) -> bool:
    if certificate.status == "pdf_final" or not certificate.certificate_number:
        return False
    values = _word_content_control_values_for_unit(detail, certificate, unit) if unit is not None else _word_content_control_values(detail, certificate)
    current_path = _certificate_storage_path(certificate.storage_key_docx) if certificate.storage_key_docx else None
    source_path = _certificate_word_source_path_for_auto_update(db, certificate=certificate, values=values)
    if source_path is None:
        return False
    source_label = certificate.word_source or "generated"
    if current_path is None or source_path != current_path:
        source_label = "inherited"

    storage_key = _certificate_docx_storage_key(certificate.cod_odp)
    output_path = _certificate_storage_path(storage_key)
    update_docx_content_controls(source_path, output_path, values)
    certificate.storage_key_docx = storage_key
    certificate.download_token = secrets.token_urlsafe(32)
    certificate.word_source = source_label
    certificate.word_original_filename = None
    certificate.word_content_controls, certificate.word_missing_content_controls = inspect_docx_content_controls(output_path)
    return True


def _certificate_word_source_path_for_auto_update(
    db: Session,
    *,
    certificate: QuartaTaglioFinalCertificate,
    values: dict[str, object],
) -> Path | None:
    current_path = _certificate_storage_path(certificate.storage_key_docx) if certificate.storage_key_docx else None
    if current_path is not None and current_path.exists() and certificate.word_source in {None, "generated", "inherited"}:
        if _docx_needs_content_control_update(current_path, values):
            return current_path
        return None

    if certificate.storage_key_docx:
        return None

    source_certificate = _previous_word_certificate_for_inheritance(db, certificate=certificate)
    if source_certificate is None or not source_certificate.storage_key_docx:
        return None
    source_path = _certificate_storage_path(source_certificate.storage_key_docx)
    if not source_path.exists():
        return None
    present, _missing = inspect_docx_content_controls(source_path)
    return source_path if present else None


def _previous_word_certificate_for_inheritance(
    db: Session,
    *,
    certificate: QuartaTaglioFinalCertificate,
) -> QuartaTaglioFinalCertificate | None:
    current_cod_f3 = _cod_f3_sort_value(certificate.cod_f3)
    if current_cod_f3 is None:
        return None
    candidates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(
            QuartaTaglioFinalCertificate.cod_odp == certificate.cod_odp,
            QuartaTaglioFinalCertificate.id != certificate.id,
            QuartaTaglioFinalCertificate.certificate_number.isnot(None),
            QuartaTaglioFinalCertificate.storage_key_docx.isnot(None),
            QuartaTaglioFinalCertificate.cod_f3.isnot(None),
        )
        .order_by(QuartaTaglioFinalCertificate.created_at.desc(), QuartaTaglioFinalCertificate.id.desc())
        .all()
    )
    return _previous_cod_f3_certificate(
        candidates,
        cod_odp=certificate.cod_odp,
        current_cod_f3=current_cod_f3,
        visited_numbers={_clean_text(certificate.certificate_number) or ""},
    )


def _docx_needs_content_control_update(path: Path, values: dict[str, object]) -> bool:
    expected_values = [str(value) for value in values.values() if value not in (None, "")]
    if not expected_values:
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            xml = "".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("word/") and name.endswith(".xml")
            )
    except (OSError, zipfile.BadZipFile):
        return False
    return any(value not in xml and escape(value) not in xml for value in expected_values)


def _cdq_signature_from_detail(detail: QuartaTaglioDetailResponse) -> list[str]:
    return sorted({_norm(item.cdq) for item in detail.materials if _norm(item.cdq)})


def _select_quality_manager(db: Session) -> User | None:
    return (
        db.query(User)
        .filter(User.active.is_(True), User.role.in_([ROLE_MANAGER, ROLE_ADMIN]))
        .order_by((User.role == ROLE_MANAGER).desc(), User.name)
        .first()
    )


def _safe_file_part(value: Any) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return safe.strip("._") or "certificato"


def _load_matching_app_rows(db: Session, rows: list[QuartaTaglioRow]) -> list[AcquisitionRow]:
    row_ids = sorted({row_id for row in rows for row_id in (row.matching_row_ids or [])})
    if not row_ids:
        return []
    return (
        db.query(AcquisitionRow)
        .options(
            selectinload(AcquisitionRow.values),
            selectinload(AcquisitionRow.history_events),
            selectinload(AcquisitionRow.certificate_match),
            selectinload(AcquisitionRow.custom_note_links).joinedload(AcquisitionRowNoteTemplate.note_template),
        )
        .filter(AcquisitionRow.id.in_(row_ids))
        .order_by(AcquisitionRow.cdq.asc(), AcquisitionRow.colata.asc(), AcquisitionRow.id.asc())
        .all()
    )


def _quick_incoming_confirm_blockers(
    *,
    app_rows: list[AcquisitionRow],
    selected_standard_confirmed: bool,
    conformity_status: str,
) -> list[str]:
    blockers: list[str] = []
    if not selected_standard_confirmed:
        blockers.append("Standard non confermato")
    if not app_rows:
        blockers.append("Nessuna riga Incoming collegata")
    if conformity_status != "conforme":
        blockers.append("Conformità standard non OK")
    return blockers


def _quick_incoming_confirm_applied(app_rows: list[AcquisitionRow]) -> bool:
    return any(
        event.azione == "conferma_rapida_certificazione"
        for row in app_rows
        for event in (getattr(row, "history_events", None) or [])
    )


def _has_quick_confirmation_event(row: AcquisitionRow, block: str) -> bool:
    return any(
        event.blocco == block and event.azione == "conferma_rapida_certificazione"
        for event in (getattr(row, "history_events", None) or [])
    )


def _read_value_has_payload_for_quick_confirm(value: ReadValue) -> bool:
    return bool(_clean_text(value.valore_finale) or _clean_text(value.valore_standardizzato) or _clean_text(value.valore_grezzo))


def _word_creation_blockers(
    *,
    db: Session,
    quarta_rows: list[QuartaTaglioRow],
    app_rows: list[AcquisitionRow],
    selected_standard_confirmed: bool,
) -> list[str]:
    blockers: list[str] = []
    if not selected_standard_confirmed:
        blockers.append("Standard non confermato")

    app_rows_by_key: dict[tuple[str, str], list[AcquisitionRow]] = defaultdict(list)
    for row in app_rows:
        app_rows_by_key[(_norm(row.cdq), _norm(row.colata))].append(row)

    seen_material_keys: set[tuple[str, str]] = set()
    for quarta_row in quarta_rows:
        key = (_norm(quarta_row.cdq), _norm(quarta_row.colata))
        if key in seen_material_keys:
            continue
        seen_material_keys.add(key)

        label = _certificate_material_label(quarta_row)
        if not key[0]:
            blockers.append(f"{label}: CDQ mancante da Quarta")
            continue
        if not key[1]:
            blockers.append(f"{label}: colata mancante da Quarta")
            continue

        exact_rows = app_rows_by_key.get(key, [])
        if not exact_rows:
            candidates = [row for row in app_rows if _norm(row.cdq) == key[0]]
            if candidates:
                colate = ", ".join(sorted({_clean_text(row.colata) or "-" for row in candidates}))
                blockers.append(f"{label}: CDQ trovato in Incoming ma colata non coerente. Colate Incoming: {colate}")
            else:
                blockers.append(f"{label}: CDQ non presente in Incoming")
            continue
        if len(exact_rows) > 1:
            ids = ", ".join(f"#{row.id}" for row in exact_rows)
            blockers.append(f"{label}: CDQ/colata presenti su più righe Incoming ({ids}), serve verifica manuale")
            continue

        row = exact_rows[0]
        block_states = _compute_block_states_from_db(db, row)
        for block, label_text in (("chimica", "chimica"), ("proprieta", "proprietà"), ("note", "note")):
            if block_states.get(block) != "verde":
                blockers.append(f"{label}: riga Incoming #{row.id} manca conferma {label_text}")
        if row.qualita_valutazione == "respinto":
            blockers.append(f"{label}: riga Incoming #{row.id} respinta da qualità")
        elif row.qualita_valutazione not in {"accettato", "accettato_con_riserva"}:
            blockers.append(f"{label}: riga Incoming #{row.id} non accettata da qualità")

    return sorted(set(blockers))


def _certificate_material_label(row: QuartaTaglioRow) -> str:
    return f"CDQ {_clean_text(row.cdq) or '-'}, colata {_clean_text(row.colata) or '-'}"


def _selection_to_candidate(selection: QuartaTaglioStandardSelection | None) -> QuartaTaglioStandardCandidateResponse | None:
    if selection is None or selection.standard is None:
        return None
    standard = selection.standard
    return QuartaTaglioStandardCandidateResponse(
        id=standard.id,
        code=standard.code,
        label=_standard_label(standard),
        confidence="confermata",
        score=999,
        reasons=["confermato manualmente"],
        warnings=[],
    )


def _chemistry_fields_for_detail(
    *,
    standard: NormativeStandard | None,
    app_rows: list[AcquisitionRow],
) -> list[str]:
    recovered_fields = _block_field_names(app_rows, "chimica")
    if standard is None:
        return recovered_fields

    standard_fields = [limit.elemento for limit in standard.chemistry_limits]
    standard_keys = {_field_key(field) for field in standard_fields}
    extra_fields = [field for field in recovered_fields if _field_key(field) not in standard_keys]
    return _unique_clean([*standard_fields, *extra_fields])


def _block_field_names(app_rows: list[AcquisitionRow], block: str) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in app_rows:
        for value in row.values:
            if _norm(value.blocco) != _norm(block):
                continue
            key = _field_key(value.campo)
            if not key or key in seen:
                continue
            seen.add(key)
            fields.append(value.campo)
    return fields


def _standard_chemistry_field_keys(standard: NormativeStandard | None) -> set[str]:
    if standard is None:
        return set()
    return {_field_key(limit.elemento) for limit in standard.chemistry_limits}


def _aggregate_block_values(
    *,
    fields: list[str],
    block: str,
    app_rows: list[AcquisitionRow],
    material_weights: dict[str, float | None],
    standard: NormativeStandard | None,
    standard_confirmed: bool = True,
) -> list[QuartaTaglioAggregateValueResponse]:
    result: list[QuartaTaglioAggregateValueResponse] = []
    standard_chemistry_keys = _standard_chemistry_field_keys(standard) if block == "chimica" else set()
    for field in fields:
        values: list[tuple[AcquisitionRow, float, float | None]] = []
        missing_rows: list[str] = []
        for row in app_rows:
            value = _as_float(_read_value(row, block, field))
            if value is None:
                missing_rows.append(row.cdq or f"riga #{row.id}")
                continue
            values.append((row, value, _material_weight_for_app_row(row, material_weights)))

        if block == "chimica" and standard is not None and _field_key(field) not in standard_chemistry_keys:
            if values:
                aggregated, method = _aggregate_numeric_values(values, block=block)
                result.append(
                    QuartaTaglioAggregateValueResponse(
                        field=field,
                        value=_round_aggregate_value(block, aggregated),
                        method=method,
                        status="not_in_standard",
                        message="Elemento trovato nei certificati fornitore ma non previsto dallo standard: non riportare nel certificato finale",
                    )
                )
            continue

        if not values:
            missing_message = (
                "Elemento previsto dallo standard ma non trovato nei certificati fornitore collegati"
                if block == "chimica" and standard is not None and _field_key(field) in standard_chemistry_keys
                else "Valore non trovato nei certificati collegati"
            )
            result.append(
                QuartaTaglioAggregateValueResponse(
                    field=field,
                    method="missing",
                    status="missing_from_supplier" if block == "chimica" and standard is not None else "missing",
                    message=missing_message,
                )
            )
            continue

        aggregated, method = _aggregate_numeric_values(values, block=block)

        if block == "proprieta" and standard is not None and not standard_confirmed:
            result.append(
                QuartaTaglioAggregateValueResponse(
                    field=field,
                    value=_round_aggregate_value(block, aggregated),
                    method=method,
                    status="not_checked",
                    message="Confermare standard per verificare le proprietà",
                )
            )
            continue

        limit_min, limit_max, standard_label, property_message, property_status = _standard_check_context_for_field(
            standard=standard,
            block=block,
            field=field,
            values=values,
            app_rows=app_rows,
            aggregated=aggregated,
        )
        if block == "chimica" and standard is None:
            check_status = "not_checked"
            message = "Confermare lo standard per sapere se l'elemento va riportato"
        elif property_status is not None:
            check_status = property_status
            message = property_message
        else:
            check_status, message = _check_against_limits(
                value=aggregated,
                limit_min=limit_min,
                limit_max=limit_max,
                missing_rows=missing_rows,
            )
            if block == "chimica" and standard is not None and check_status == "missing":
                check_status = "missing_from_supplier"
        result.append(
            QuartaTaglioAggregateValueResponse(
                field=field,
                value=_round_aggregate_value(block, aggregated),
                method=method,
                standard_min=limit_min,
                standard_max=limit_max,
                standard_label=standard_label,
                status=check_status,
                message=message,
            )
        )
    return result


def _round_aggregate_value(block: str, value: float) -> float:
    return round(value, 3 if block == "chimica" else 4)


def _material_weight_for_app_row(row: AcquisitionRow, material_weights: dict[str, float | None]) -> float | None:
    cdq_weight = material_weights.get(_norm(row.cdq)) or material_weights.get(row.cdq or "")
    if cdq_weight is not None and cdq_weight > 0:
        return cdq_weight
    row_weight = _as_float(getattr(row, "peso", None))
    if row_weight is not None and row_weight > 0:
        return row_weight
    return None


def _aggregate_numeric_values(values: list[tuple[AcquisitionRow, float, float | None]], *, block: str) -> tuple[float, str]:
    if len(values) == 1:
        return values[0][1], "single"
    if block == "proprieta":
        return min(value for _, value, _ in values), "minimum"
    if len(values) > 1 and all(weight is not None and weight > 0 for _, _, weight in values):
        total_weight = sum(float(weight or 0) for _, _, weight in values)
        return sum(value * float(weight or 0) for _, value, weight in values) / total_weight, "weighted"
    return sum(value for _, value, _ in values) / len(values), "average"


def _build_standard_conformity(
    *,
    chemistry: list[QuartaTaglioAggregateValueResponse],
    properties: list[QuartaTaglioAggregateValueResponse],
    selected_standard_confirmed: bool,
) -> tuple[str, list[QuartaTaglioConformityIssueResponse]]:
    if not selected_standard_confirmed:
        return "da_verificare", []

    issues: list[QuartaTaglioConformityIssueResponse] = []
    for block, items in (("chimica", chemistry), ("proprieta", properties)):
        for item in items:
            if item.status == "out_of_range" or (block == "proprieta" and item.status in {"missing_diameter", "range_not_found"}):
                issues.append(
                    QuartaTaglioConformityIssueResponse(
                        block=block,
                        field=item.field,
                        value=item.value,
                        standard_min=item.standard_min,
                        standard_max=item.standard_max,
                        message=item.message,
                    )
                )
    if issues:
        return "non_conforme", issues

    return "conforme", []


def _standard_limits_for_field(
    standard: NormativeStandard | None,
    *,
    block: str,
    field: str,
    app_rows: list[AcquisitionRow],
) -> tuple[float | None, float | None]:
    if standard is None:
        return None, None

    if block == "chimica":
        for limit in standard.chemistry_limits:
            if _field_key(limit.elemento) == _field_key(field):
                return limit.min_value, limit.max_value
        return None, None

    diameter = _first_numeric(row.diametro for row in app_rows)
    matching_limits = [limit for limit in standard.property_limits if _field_key(limit.proprieta) == _field_key(field)]
    if not matching_limits:
        return None, None
    if diameter is None:
        return matching_limits[0].min_value, matching_limits[0].max_value
    ranged_limits = [
        limit
        for limit in matching_limits
        if (limit.misura_min is None or diameter > limit.misura_min)
        and (limit.misura_max is None or diameter <= limit.misura_max)
    ]
    selected = ranged_limits[0] if ranged_limits else matching_limits[0]
    return selected.min_value, selected.max_value


def _standard_check_context_for_field(
    *,
    standard: NormativeStandard | None,
    block: str,
    field: str,
    values: list[tuple[AcquisitionRow, float, float | None]],
    app_rows: list[AcquisitionRow],
    aggregated: float,
) -> tuple[float | None, float | None, str | None, str | None, str | None]:
    if standard is None:
        return None, None, None, None, None
    if block != "proprieta":
        limit_min, limit_max = _standard_limits_for_field(standard, block=block, field=field, app_rows=app_rows)
        return limit_min, limit_max, None, None, None

    matching_limits = [limit for limit in standard.property_limits if _field_key(limit.proprieta) == _field_key(field)]
    if not matching_limits:
        return None, None, None, None, None

    if not values:
        return None, None, None, None, None

    checked_rows: list[tuple[AcquisitionRow, float, Any]] = []
    missing_diameter: list[str] = []
    range_not_found: list[str] = []
    for row, value, _ in values:
        diameter = _as_float(row.diametro)
        row_label = row.cdq or f"riga #{row.id}"
        if diameter is None:
            missing_diameter.append(row_label)
            continue
        limit = _property_limit_for_diameter(matching_limits, diameter)
        if limit is None:
            range_not_found.append(f"{row_label} Ø{diameter:g}")
            continue
        checked_rows.append((row, value, limit))

    if missing_diameter:
        return (
            None,
            None,
            None,
            f"Diametro mancante per {', '.join(sorted(set(missing_diameter)))}: impossibile scegliere il range standard",
            "missing_diameter",
        )
    if range_not_found:
        return (
            None,
            None,
            None,
            f"Diametro fuori dai range standard: {', '.join(range_not_found)}",
            "range_not_found",
        )
    if not checked_rows:
        return matching_limits[0].min_value, matching_limits[0].max_value, None, None, None

    unique_ranges = {
        (
            limit.misura_min,
            limit.misura_max,
            limit.min_value,
            limit.max_value,
            _property_range_label(limit),
        )
        for _, _, limit in checked_rows
    }
    if len(unique_ranges) == 1:
        limit = checked_rows[0][2]
        return limit.min_value, limit.max_value, None, None, None

    checked_row_ids = {row.id for row, _, _ in checked_rows}
    missing_value_rows = sorted(
        {
            row.cdq or f"riga #{row.id}"
            for row in app_rows
            if row.id not in checked_row_ids and _as_float(_read_value(row, "proprieta", field)) is None
        }
    )
    messages: list[str] = []
    out_of_range = False
    for row, value, limit in checked_rows:
        row_label = row.cdq or f"riga #{row.id}"
        diameter = _as_float(row.diametro)
        range_label = _property_range_label(limit)
        if _value_within_limits(value=value, limit_min=limit.min_value, limit_max=limit.max_value):
            messages.append(f"{row_label} Ø{diameter:g}: OK su {range_label}")
            continue
        out_of_range = True
        status, message = _check_against_limits(value=value, limit_min=limit.min_value, limit_max=limit.max_value, missing_rows=[])
        messages.append(f"{row_label} Ø{diameter:g}: {field} {value:g} {message or status}")
    if missing_value_rows:
        messages.append(f"manca valore per {', '.join(missing_value_rows)}")
    return (
        None,
        None,
        "range multipli",
        "; ".join(messages),
        "out_of_range" if out_of_range else "missing" if missing_value_rows else "ok",
    )


def _property_limit_for_diameter(limits: list[Any], diameter: float) -> Any | None:
    for limit in limits:
        if (limit.misura_min is None or diameter > limit.misura_min) and (limit.misura_max is None or diameter <= limit.misura_max):
            return limit
    return None


def _property_range_label(limit: Any) -> str:
    lower = f">{limit.misura_min:g}" if limit.misura_min is not None else ""
    upper = f"<={limit.misura_max:g}" if limit.misura_max is not None else ""
    measure = "Ø"
    range_part = " ".join(part for part in (lower, upper) if part) or "range non definito"
    standard_part = _format_standard_limit(limit.min_value, limit.max_value)
    return f"{measure} {range_part} ({standard_part})" if standard_part else f"{measure} {range_part}"


def _format_standard_limit(limit_min: float | None, limit_max: float | None) -> str | None:
    if limit_min is not None and limit_max is not None:
        return f"{limit_min:g}-{limit_max:g}"
    if limit_min is not None:
        return f">= {limit_min:g}"
    if limit_max is not None:
        return f"<= {limit_max:g}"
    return None


def _check_against_limits(
    *,
    value: float,
    limit_min: float | None,
    limit_max: float | None,
    missing_rows: list[str],
) -> tuple[str, str | None]:
    messages: list[str] = []
    if missing_rows:
        messages.append(f"manca valore per {', '.join(sorted(set(missing_rows)))}")
    if limit_min is None and limit_max is None:
        return ("missing" if missing_rows else "not_checked"), "; ".join(messages) or "standard non selezionato o limite non presente"
    if not _value_within_limits(value=value, limit_min=limit_min, limit_max=limit_max):
        if limit_min is not None and value < limit_min:
            messages.append(f"sotto minimo {limit_min:g}")
        if limit_max is not None and value > limit_max:
            messages.append(f"sopra massimo {limit_max:g}")
    if messages:
        return "out_of_range" if any("minimo" in item or "massimo" in item for item in messages) else "missing", "; ".join(messages)
    return "ok", None


def _value_within_limits(*, value: float, limit_min: float | None, limit_max: float | None) -> bool:
    if limit_min is not None and limit_max is not None:
        return (value + STANDARD_LIMIT_EPSILON) >= limit_min and (value - STANDARD_LIMIT_EPSILON) <= limit_max
    if limit_min is not None:
        return (value + STANDARD_LIMIT_EPSILON) >= limit_min
    if limit_max is not None:
        return (value - STANDARD_LIMIT_EPSILON) <= limit_max
    return True


def _evaluate_notes(app_rows: list[AcquisitionRow], system_note_texts: dict[str, str] | None = None) -> list[QuartaTaglioNoteResponse]:
    system_note_texts = system_note_texts or {}
    notes: list[QuartaTaglioNoteResponse] = []
    values_by_code = {
        code: [_clean_note_value(_read_value(row, "note", code)) for row in app_rows]
        for code, _ in NOTE_FIELDS
    }
    us_control_present = any(value for code in US_CONTROL_NOTE_KEYS for value in values_by_code.get(code, []) if value)
    for code, label in NOTE_FIELDS:
        values = values_by_code[code]
        filled = [value for value in values if value]
        unique_values = sorted(set(filled))
        if not filled:
            if code in US_CONTROL_NOTE_KEYS and us_control_present:
                continue
            notes.append(
                QuartaTaglioNoteResponse(
                    code=code,
                    label=label,
                    status="missing",
                    message="Nota non trovata nei certificati collegati",
                )
            )
        elif len(unique_values) == 1 and len(filled) == len(app_rows):
            notes.append(
                QuartaTaglioNoteResponse(
                    code=code,
                    label=label,
                    value=_system_note_display_text(code, system_note_texts, unique_values[0]),
                    status="ok",
                    message="Nota uniforme: può essere riportata",
                )
            )
        else:
            notes.append(
                QuartaTaglioNoteResponse(
                    code=code,
                    label=label,
                    status="different",
                    message="Note non uniformi: non riportare automaticamente",
                )
            )
    notes.extend(_evaluate_custom_notes(app_rows))
    return notes


def _system_note_texts(db: Session) -> dict[str, str]:
    notes = (
        db.query(NoteTemplate)
        .filter(NoteTemplate.is_system.is_(True), NoteTemplate.is_active.is_(True), NoteTemplate.note_key.isnot(None))
        .all()
    )
    result: dict[str, str] = {}
    for note in notes:
        if note.note_key:
            result[str(note.note_key)] = note.text
        code_key = SYSTEM_NOTE_CODE_KEYS.get(str(note.code))
        if code_key:
            result[code_key] = note.text
    return result


def _system_note_display_text(code: str, system_note_texts: dict[str, str], extracted_value: str) -> str:
    configured = _clean_text(system_note_texts.get(code))
    if configured:
        return configured
    fallback = SYSTEM_NOTE_TEXT_FALLBACKS.get(code)
    if fallback and _norm(extracted_value) in {"true", "si", "sì", "yes", "ok", "1"}:
        return fallback
    return extracted_value


def _evaluate_custom_notes(app_rows: list[AcquisitionRow]) -> list[QuartaTaglioNoteResponse]:
    if not app_rows:
        return []

    row_ids = {row.id for row in app_rows}
    cdq_by_row_id = {row.id: row.cdq or f"riga #{row.id}" for row in app_rows}
    templates_by_id: dict[int, Any] = {}
    present_by_template_id: dict[int, set[int]] = defaultdict(set)

    for row in app_rows:
        for link in getattr(row, "custom_note_links", []):
            template = link.note_template
            if template is None or template.is_system or not template.is_active:
                continue
            templates_by_id[template.id] = template
            present_by_template_id[template.id].add(row.id)

    notes: list[QuartaTaglioNoteResponse] = []
    for template in sorted(templates_by_id.values(), key=lambda item: (item.sort_order, item.id)):
        present_row_ids = present_by_template_id[template.id]
        missing_row_ids = row_ids - present_row_ids
        if not missing_row_ids:
            notes.append(
                QuartaTaglioNoteResponse(
                    code=f"custom_note_{template.id}",
                    label="Nota utente",
                    value=template.text,
                    status="ok",
                    message="Nota utente uniforme: può essere riportata",
                )
            )
            continue

        present_cdq = ", ".join(sorted(cdq_by_row_id[row_id] for row_id in present_row_ids))
        missing_cdq = ", ".join(sorted(cdq_by_row_id[row_id] for row_id in missing_row_ids))
        notes.append(
            QuartaTaglioNoteResponse(
                code=f"custom_note_{template.id}",
                label="Nota utente",
                value=template.text,
                status="different",
                message=f"Nota utente non uniforme: presente su {present_cdq}; manca su {missing_cdq}",
            )
        )
    return notes


def _suggest_standard_candidates(
    db: Session,
    *,
    app_rows: list[AcquisitionRow],
    materials: list[QuartaTaglioMaterialResponse],
) -> list[QuartaTaglioStandardCandidateResponse]:
    if not app_rows:
        return []

    alloys = sorted(
        set(
            filter(
                None,
                (
                    _normalize_alloy_for_standard(row.lega_base or row.lega_designazione or row.variante_lega)
                    for row in app_rows
                ),
            )
        )
    )
    measure_type = "diametro" if _first_numeric(row.diametro for row in app_rows) is not None else None
    product_type = _infer_product_type(app_rows=app_rows, materials=materials)
    standards = (
        db.query(NormativeStandard)
        .options(selectinload(NormativeStandard.chemistry_limits), selectinload(NormativeStandard.property_limits))
        .filter(NormativeStandard.stato_validazione == "attivo")
        .all()
    )

    candidates: list[tuple[int, NormativeStandard, list[str], list[str]]] = []
    for standard in standards:
        reasons: list[str] = []
        warnings: list[str] = []
        score = 0
        standard_alloy = _normalize_alloy_for_standard(standard.lega_base)
        if alloys and standard_alloy not in alloys:
            continue
        if standard_alloy in alloys:
            score += 50
            reasons.append(f"lega {_standard_alloy_label(standard)}")

        if measure_type and standard.misura_tipo:
            if _norm(standard.misura_tipo) != _norm(measure_type):
                continue
            score += 20
            reasons.append(f"misura {standard.misura_tipo}")

        if product_type and standard.tipo_prodotto:
            if _norm(standard.tipo_prodotto) == _norm(product_type):
                score += 25
                reasons.append(f"prodotto {standard.tipo_prodotto}")
            else:
                continue

        treatment = _clean_text(standard.trattamento_termico)
        if treatment:
            score += 5
            reasons.append(treatment)

        if not standard.property_limits:
            warnings.append("proprietà standard non presenti")
        if not standard.chemistry_limits:
            warnings.append("chimica standard non presente")
        candidates.append((score, standard, reasons, warnings))

    candidates.sort(key=lambda item: item[0], reverse=True)
    top_score = candidates[0][0] if candidates else 0
    result: list[QuartaTaglioStandardCandidateResponse] = []
    for score, standard, reasons, warnings in candidates[:3]:
        close_competitor = score < top_score or any(candidate_score >= score - 15 for candidate_score, other, _, _ in candidates if other.id != standard.id)
        if score >= 95 and not close_competitor:
            confidence = "alta"
        elif score >= 70:
            confidence = "media"
        else:
            confidence = "bassa"
        result.append(
            QuartaTaglioStandardCandidateResponse(
                id=standard.id,
                code=standard.code,
                label=_standard_label(standard),
                confidence=confidence,
                score=score,
                reasons=reasons,
                warnings=warnings,
            )
        )
    return result


def _read_value(row: AcquisitionRow, block: str, field: str) -> str | None:
    for value in row.values:
        if _norm(value.blocco) == _norm(block) and _field_key(value.campo) == _field_key(field):
            return value.valore_finale or value.valore_standardizzato or value.valore_grezzo
    return None


def _clean_note_value(value: Any) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    if _norm(cleaned) in {"true", "si", "sì", "yes", "ok", "1"}:
        return "OK"
    if _norm(cleaned) in {"false", "no", "0"}:
        return None
    return cleaned


def _normalize_alloy_for_standard(value: Any) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    compact = re.sub(r"[^0-9A-Za-z]", "", cleaned).upper()
    match = re.search(r"([0-9]{4})([A-Z]*)", compact)
    if not match:
        return compact
    number, suffix = match.groups()
    if number == "6082" and suffix.startswith("HF"):
        return "6082H"
    if number == "6082" and suffix.startswith("LF"):
        return "6082L"
    if suffix in {"F", "T6", "T76", ""}:
        return number
    return f"{number}{suffix[:1]}" if number == "6082" and suffix[:1] in {"H", "L"} else number


def _infer_product_type(
    *,
    app_rows: list[AcquisitionRow],
    materials: list[QuartaTaglioMaterialResponse],
) -> str | None:
    haystack = " ".join(
        filter(
            None,
            [
                *(row.note_documento for row in app_rows),
                *(row.lega_designazione for row in app_rows),
                *(_read_value(row, "ddt", field) for row in app_rows for field in ("descrizione", "descrizione_articolo", "materiale")),
                *(material.cod_art for material in materials),
            ],
        )
    ).upper()
    if any(token in haystack for token in ("BARRA", "BARRE", "ROUND BAR", "BAR ")):
        return "BARRE"
    if any(token in haystack for token in ("PROFILO", "PROFILI", "PROFILE")):
        return "PROFILI"
    return None


def _standard_label(standard: NormativeStandard) -> str:
    parts = [
        _standard_alloy_label(standard),
        standard.norma,
        standard.trattamento_termico,
        standard.tipo_prodotto,
        standard.misura_tipo,
    ]
    return " · ".join(_unique_clean(parts)) or standard.code


def _standard_alloy_label(standard: NormativeStandard) -> str:
    designation = _clean_text(standard.lega_designazione)
    base = _clean_text(standard.lega_base)
    variant = _clean_text(standard.variante_lega)
    label = designation or base or ""
    if variant and _norm(variant) not in _norm(label):
        label = f"{label} {variant}".strip()
    return label or standard.code


def _first_numeric(values: Any) -> float | None:
    for value in values:
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _field_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", (_clean_text(value) or "").casefold())


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


def _load_esolver_ddt_rows(
    db: Session,
    *,
    cod_odp: str,
    cod_art_values: list[str | None],
) -> tuple[list[QuartaTaglioEsolverDdtRowResponse], str, str | None]:
    result = _fetch_esolver_ddt_rows_batch(db, {cod_odp: cod_art_values})
    return result.get(cod_odp, ([], "missing", "Nessuna riga DDT eSolver trovata per questo OL"))


def _fetch_esolver_ddt_rows_batch(
    db: Session,
    groups: dict[str, list[str | None]],
) -> dict[str, tuple[list[QuartaTaglioEsolverDdtRowResponse], str, str | None]]:
    if not groups:
        return {}
    group_items = list(groups.items())
    if len(group_items) > ESOLVER_DDT_BATCH_SIZE:
        chunked_result: dict[str, tuple[list[QuartaTaglioEsolverDdtRowResponse], str, str | None]] = {}
        for index in range(0, len(group_items), ESOLVER_DDT_BATCH_SIZE):
            chunked_result.update(_fetch_esolver_ddt_rows_batch(db, dict(group_items[index : index + ESOLVER_DDT_BATCH_SIZE])))
        return chunked_result

    connection = db.query(ExternalConnection).filter(ExternalConnection.code == "esolver").one_or_none()
    if connection is None or not connection.enabled:
        return {cod_odp: ([], "missing", "Connessione eSolver non configurata o disabilitata") for cod_odp in groups}
    if not connection.password_encrypted:
        return {cod_odp: ([], "missing", "Password eSolver non configurata") for cod_odp in groups}

    try:
        import pymssql
    except ImportError:
        return {cod_odp: ([], "error", "Driver SQL Server pymssql non installato") for cod_odp in groups}

    object_settings = connection.object_settings or {}
    view_name = _sql_identifier(str(object_settings.get("righe_ddt_view") or "CertiRigheDDT"))
    schema_name = _sql_identifier(connection.schema_name or "dbo")
    if view_name is None or schema_name is None:
        return {cod_odp: ([], "error", "Nome vista eSolver non valido") for cod_odp in groups}

    result: dict[str, tuple[list[QuartaTaglioEsolverDdtRowResponse], str, str | None]] = {}
    try:
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
                cod_odps = list(groups.keys())
                placeholders = ", ".join(["%s"] * len(cod_odps))
                query = ESOLVER_DDT_BATCH_QUERY_TEMPLATE.format(
                    qualified_view=f"[{schema_name}].[{view_name}]",
                    placeholders=placeholders,
                )
                cursor.execute(query, tuple(cod_odps))
                raw_rows_by_odp: dict[str, list[dict[str, Any]]] = defaultdict(list)
                odp_key_map = {_norm(cod_odp): cod_odp for cod_odp in cod_odps}
                for raw_row in list(cursor.fetchall()):
                    source_odp = odp_key_map.get(_norm(raw_row.get("ORP")))
                    if source_odp:
                        raw_rows_by_odp[source_odp].append(raw_row)

                for cod_odp, cod_art_values in groups.items():
                    cod_art_keys = {_norm(value) for value in cod_art_values if _norm(value)}
                    rows = [_serialize_esolver_ddt_row(row, cod_art_keys=cod_art_keys) for row in raw_rows_by_odp.get(cod_odp, [])]
                    result[cod_odp] = _esolver_status_for_rows(rows, cod_art_keys=cod_art_keys)
    except Exception as exc:
        return {cod_odp: ([], "error", f"Lettura eSolver fallita: {exc}") for cod_odp in groups}

    return result


def _fetch_certiol_rows_batch(db: Session, cod_odps: list[str]) -> dict[str, list[_CertiOlRow]]:
    cleaned_odps = _unique_clean(cod_odps)
    if not cleaned_odps:
        return {}
    if len(cleaned_odps) > ESOLVER_DDT_BATCH_SIZE:
        combined: dict[str, list[_CertiOlRow]] = {}
        for index in range(0, len(cleaned_odps), ESOLVER_DDT_BATCH_SIZE):
            combined.update(_fetch_certiol_rows_batch(db, cleaned_odps[index : index + ESOLVER_DDT_BATCH_SIZE]))
        return combined

    connection = db.query(ExternalConnection).filter(ExternalConnection.code == "esolver").one_or_none()
    if connection is None or not connection.enabled or not connection.password_encrypted:
        return {}

    try:
        import pymssql
    except ImportError:
        return {}

    object_settings = connection.object_settings or {}
    view_name = _sql_identifier(str(object_settings.get("certiol_view") or "CertiOL"))
    schema_name = _sql_identifier(connection.schema_name or "dbo")
    if view_name is None or schema_name is None:
        return {}

    result: dict[str, list[_CertiOlRow]] = defaultdict(list)
    try:
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
                placeholders = ", ".join(["%s"] * len(cleaned_odps))
                query = ESOLVER_CERTIOL_BATCH_QUERY_TEMPLATE.format(
                    qualified_view=f"[{schema_name}].[{view_name}]",
                    placeholders=placeholders,
                )
                cursor.execute(query, tuple(cleaned_odps))
                odp_key_map = {_norm(cod_odp): cod_odp for cod_odp in cleaned_odps}
                for raw_row in list(cursor.fetchall()):
                    source_odp = odp_key_map.get(_norm(raw_row.get("ORP")))
                    if not source_odp:
                        continue
                    result[source_odp].append(
                        _CertiOlRow(
                            orp=_clean_text(raw_row.get("ORP")),
                            cod_cli=_clean_text(raw_row.get("CodCli")),
                            rag_soc=_clean_text(raw_row.get("RagSoc")),
                            cod_f3_odp=_clean_text(raw_row.get("CodF3ODP")),
                            cod_f3=_clean_text(raw_row.get("CodF3")),
                            des_f3=_clean_text(raw_row.get("DesF3")),
                        )
                    )
    except Exception:
        return {}
    return dict(result)


def _esolver_status_for_rows(
    rows: list[QuartaTaglioEsolverDdtRowResponse],
    *,
    cod_art_keys: set[str],
) -> tuple[list[QuartaTaglioEsolverDdtRowResponse], str, str | None]:
    if not rows:
        return [], "missing", "Nessuna riga DDT eSolver trovata per questo OL"
    unique_ddt = _unique_clean(row.ddt for row in rows)
    if len(unique_ddt) > 1:
        return rows, "ok", f"Dati eSolver/DDT collegati: {len(unique_ddt)} DDT trovati"
    return rows, "ok", "Dati eSolver/DDT collegati"


def _refresh_esolver_links_for_rows(db: Session, *, rows: list[QuartaTaglioRow]) -> dict[str, QuartaTaglioEsolverLink]:
    groups: dict[str, list[str | None]] = defaultdict(list)
    for row in rows:
        if row.cod_odp:
            groups[row.cod_odp].append(row.cod_art)

    if not groups:
        return {}

    fetched = _fetch_esolver_ddt_rows_batch(db, groups)
    now = datetime.now(timezone.utc)
    existing_links = {
        link.cod_odp: link
        for link in db.query(QuartaTaglioEsolverLink).filter(QuartaTaglioEsolverLink.cod_odp.in_(groups.keys())).all()
    }
    for cod_odp in groups:
        esolver_rows, esolver_status, esolver_message = fetched.get(cod_odp, ([], "missing", "Nessuna riga DDT eSolver trovata per questo OL"))
        link = existing_links.get(cod_odp)
        if link is None:
            link = QuartaTaglioEsolverLink(cod_odp=cod_odp)
            existing_links[cod_odp] = link
        _apply_esolver_link_values(link, esolver_rows=esolver_rows, status_value=esolver_status, message=esolver_message, checked_at=now)
        db.add(link)
    db.commit()
    return existing_links


def _load_esolver_links_for_rows(db: Session, *, rows: list[QuartaTaglioRow]) -> dict[str, QuartaTaglioEsolverLink]:
    cod_odps = sorted({row.cod_odp for row in rows if row.cod_odp})
    if not cod_odps:
        return {}
    return {
        link.cod_odp: link
        for link in db.query(QuartaTaglioEsolverLink).filter(QuartaTaglioEsolverLink.cod_odp.in_(cod_odps)).all()
    }


def _apply_esolver_link_values(
    link: QuartaTaglioEsolverLink,
    *,
    esolver_rows: list[QuartaTaglioEsolverDdtRowResponse],
    status_value: str,
    message: str | None,
    checked_at: datetime,
) -> None:
    header_rows = esolver_rows
    link.status = status_value
    link.message = message
    link.cod_f3 = _join_unique(row.cod_f3 for row in header_rows) or None
    link.cliente = _join_unique(row.rag_soc for row in header_rows) or None
    link.ordine_cliente = _join_unique(row.odv_cli for row in header_rows) or None
    link.conferma_ordine = _join_unique(row.odv_f3 for row in header_rows) or None
    link.ddt = _join_unique(row.ddt for row in header_rows) or None
    link.qta_totale = _sum_optional(row.qta_um_mag for row in header_rows)
    link.rows = [row.model_dump() for row in esolver_rows]
    link.last_checked_at = checked_at


def _esolver_rows_from_link(link: QuartaTaglioEsolverLink | None) -> list[QuartaTaglioEsolverDdtRowResponse]:
    if link is None:
        return []
    return [QuartaTaglioEsolverDdtRowResponse(**row) for row in (link.rows or [])]


def _serialize_esolver_ddt_row(row: dict[str, Any], *, cod_art_keys: set[str]) -> QuartaTaglioEsolverDdtRowResponse:
    cod_f3 = _clean_text(row.get("CodF3"))
    return QuartaTaglioEsolverDdtRowResponse(
        cod_f3=cod_f3,
        orp=_clean_text(row.get("ORP")),
        rag_soc=_clean_text(row.get("RagSoc")),
        odv_cli=_clean_text(row.get("ODVCli")),
        odv_f3=_clean_text(row.get("ODVF3")),
        ddt=_clean_text(row.get("DDT")),
        qta_um_mag=_as_float(row.get("QtaUmMag")),
        certificato_presente=_as_bool(row.get("CertificatoPresente")),
        cod_f3_matches_quarta=not cod_art_keys or _norm(cod_f3) in cod_art_keys,
    )


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
        cdq = _clean_text(external_row.get("CDQ")) or "Non indicato"
        cod_odp = _clean_text(external_row.get("COD_ODP"))
        cod_art = _clean_text(external_row.get("COD_ART"))
        des_art = _clean_text(external_row.get("DES_ART"))
        colata = _clean_text(external_row.get("COLATA"))
        if not cod_odp:
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
        item.des_art = des_art
        item.saldo = str(external_row.get("SALDO") or "").strip() == "1"
        item.taglio_attivo = _as_bool(external_row.get("TAGLIO_ATTIVO"))
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
        for block, label in (("chimica", "chimica"), ("proprieta", "proprietà"), ("note", "note")):
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


def _serialize_final_certificate_register_item(
    certificate: QuartaTaglioFinalCertificate,
    *,
    db: Session | None = None,
) -> QuartaTaglioFinalCertificateRegisterItem:
    conformity_status = _certificate_conformity_status(certificate)
    conformity_issues = certificate.conformity_issues or []
    if db is not None:
        conformity_status, conformity_issues = _live_certificate_conformity_for_register(db, certificate=certificate)
    word_download_url = None
    if certificate.storage_key_docx and certificate.download_token:
        word_download_url = f"/api/quarta-taglio/word-drafts/{certificate.id}/file?download_token={certificate.download_token}"
    return QuartaTaglioFinalCertificateRegisterItem(
        id=certificate.id,
        cod_odp=certificate.cod_odp,
        status=certificate.status,
        certificate_number=certificate.certificate_number or certificate.draft_number,
        draft_number=certificate.draft_number,
        unit_key=certificate.unit_key,
        cod_f3=certificate.cod_f3,
        ddt=certificate.ddt,
        ordine_cliente=certificate.ordine_cliente,
        quantita=certificate.quantita,
        cdq=_certificate_cdq_display(certificate),
        cert_date=certificate.cert_date,
        lega_cod_f3=_certificate_cod_f3_display(certificate),
        cdo_lega=certificate.cdo_lega,
        fornitore_cliente=certificate.fornitore_cliente,
        has_word=bool(certificate.storage_key_docx),
        has_pdf=bool(certificate.storage_key_pdf),
        word_download_url=word_download_url,
        conformity_status=conformity_status,
        conformity_issues=conformity_issues,
        created_at=certificate.created_at,
        updated_at=certificate.updated_at,
        closed_at=certificate.closed_at,
    )


def _certificate_cdq_display(certificate: QuartaTaglioFinalCertificate) -> str | None:
    values = certificate.cdq_values or []
    cdq_values = [item.get("cdq") for item in values if isinstance(item, dict)]
    return _join_unique(cdq_values) or _clean_text(certificate.cdq_key)


def _live_certificate_conformity_for_register(
    db: Session,
    *,
    certificate: QuartaTaglioFinalCertificate,
) -> tuple[str, list[dict[str, Any]]]:
    try:
        detail = get_quarta_taglio_detail(db, cod_odp=certificate.cod_odp)
    except HTTPException:
        return _certificate_conformity_status(certificate), certificate.conformity_issues or []

    issues = [issue.model_dump() for issue in detail.conformity_issues]
    if certificate.conformity_status != detail.conformity_status or (certificate.conformity_issues or []) != issues:
        certificate.conformity_status = detail.conformity_status
        certificate.conformity_issues = issues
        db.add(certificate)
        db.flush()
    return detail.conformity_status, issues


def _certificate_conformity_status(certificate: QuartaTaglioFinalCertificate) -> str:
    status_value = _clean_text(certificate.conformity_status)
    if status_value in {"conforme", "non_conforme"}:
        return status_value
    return "da_verificare"


def _certificate_cod_f3_display(certificate: QuartaTaglioFinalCertificate) -> str | None:
    if _clean_text(certificate.cod_f3):
        return _clean_text(certificate.cod_f3)
    stored_value = _clean_text(certificate.lega_cod_f3)
    if stored_value and "·" not in stored_value:
        return stored_value
    values = certificate.cdq_values or []
    codice_f3_values = [item.get("codice_f3") for item in values if isinstance(item, dict)]
    cod_art_values = [item.get("cod_art") for item in values if isinstance(item, dict)]
    return _join_unique(codice_f3_values) or _join_unique(cod_art_values) or None


def _serialize_row(row: QuartaTaglioRow) -> QuartaTaglioRowResponse:
    return QuartaTaglioRowResponse.model_validate(row)


def _serialize_grouped_rows(
    rows: list[QuartaTaglioRow],
    *,
    esolver_links: dict[str, QuartaTaglioEsolverLink] | None = None,
) -> list[QuartaTaglioRowResponse]:
    return [_serialize_ol_group(group_rows, esolver_link=(esolver_links or {}).get(group_rows[0].cod_odp)) for group_rows in _group_quarta_rows(rows)]


def _group_quarta_rows(rows: list[QuartaTaglioRow]) -> list[list[QuartaTaglioRow]]:
    rows_by_ol: dict[str, list[QuartaTaglioRow]] = defaultdict(list)
    for row in rows:
        rows_by_ol[row.cod_odp].append(row)
    return list(rows_by_ol.values())


def _filter_quarta_groups(
    groups: list[tuple[QuartaTaglioRowResponse, list[QuartaTaglioRow]]],
    *,
    query_one: str | None,
    query_two: str | None,
    query_three: str | None,
    operator_one: str,
    operator_two: str,
) -> list[tuple[QuartaTaglioRowResponse, list[QuartaTaglioRow]]]:
    if not (query_one or query_two or query_three):
        return groups

    result: list[tuple[QuartaTaglioRowResponse, list[QuartaTaglioRow]]] = []
    for item, group_rows in groups:
        values = _quarta_searchable_values(item)
        first = _evaluate_quarta_filter(values, query_one or "")
        second = _evaluate_quarta_filter(first["remaining_values"], query_two or "")
        third = _evaluate_quarta_filter(second["remaining_values"], query_three or "")
        first_match = first["matched"] if first["active"] else None
        second_match = second["matched"] if second["active"] else None
        third_match = third["matched"] if third["active"] else None
        combined = _combine_quarta_filter_results(first_match, second_match, operator_one)
        final = _combine_quarta_filter_results(combined, third_match, operator_two)
        if final is None or final:
            result.append((item, group_rows))
    return result


def _quarta_searchable_values(item: QuartaTaglioRowResponse) -> list[str]:
    values: list[Any] = [
        item.cod_odp,
        item.cdq,
        item.colata,
        item.cod_art,
        item.codice_registro,
        item.data_registro,
        item.status_color,
        item.status_message,
        item.esolver_status,
        item.esolver_message,
        item.esolver_cliente,
        item.esolver_cod_f3,
        item.esolver_ordine_cliente,
        item.esolver_conferma_ordine,
        item.esolver_ddt,
        item.esolver_qta_totale,
        item.qta_totale,
        item.lotti_count,
        "taglio attivo" if item.taglio_attivo else "tutti",
        "saldo" if item.saldo else "non saldo",
    ]
    values.extend(item.status_details or [])
    values.extend(item.cod_lotti or [])
    values.extend(item.matching_row_ids or [])
    for certificate in item.certificates or []:
        values.extend(
            [
                certificate.cdq,
                certificate.colata,
                certificate.cod_art,
                certificate.status_color,
                certificate.status_message,
                *(certificate.status_details or []),
            ]
        )
    return [str(value).lower() for value in values if value not in (None, "")]


def _evaluate_quarta_filter(values: list[str], query: str) -> dict[str, Any]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return {"active": False, "matched": True, "remaining_values": values}
    matched_indexes = [index for index, value in enumerate(values) if normalized_query in value]
    return {
        "active": True,
        "matched": bool(matched_indexes),
        "remaining_values": [value for index, value in enumerate(values) if index not in matched_indexes],
    }


def _combine_quarta_filter_results(left: bool | None, right: bool | None, operator: str) -> bool | None:
    if left is None:
        return right
    if right is None:
        return left
    if operator == "or":
        return left or right
    return left and right


def _quarta_group_sort_key(item: QuartaTaglioRowResponse, *, sort_field: str | None) -> Any:
    if sort_field == "status":
        return STATUS_SEVERITY.get(item.status_color, 0)
    if sort_field == "taglio_attivo":
        return 1 if item.taglio_attivo else 0
    if sort_field == "cod_odp":
        return item.cod_odp or ""
    if sort_field == "cdq":
        return item.cdq or ""
    if sort_field == "colata":
        return item.colata or ""
    if sort_field == "cod_art":
        return item.cod_art or ""
    if sort_field == "qta_totale":
        return item.qta_totale or 0
    if sort_field == "lotti_count":
        return item.lotti_count or 0
    if sort_field == "codice_registro":
        return item.codice_registro or ""
    if sort_field == "data_registro":
        return item.data_registro or datetime.min.replace(tzinfo=timezone.utc)
    if sort_field == "status_message":
        return item.status_message or ""
    if sort_field == "matching_rows":
        return len(item.matching_row_ids or [])
    if sort_field == "esolver_status":
        return item.esolver_status or ""
    if sort_field == "esolver_cliente":
        return item.esolver_cliente or ""
    if sort_field == "esolver_cod_f3":
        return item.esolver_cod_f3 or ""
    if sort_field == "esolver_ddt":
        return item.esolver_ddt or ""
    if sort_field == "esolver_qta_totale":
        return item.esolver_qta_totale or 0
    return (
        item.data_registro is not None,
        item.data_registro or datetime.min.replace(tzinfo=timezone.utc),
        item.cod_odp or "",
        item.cdq or "",
    )


def _serialize_ol_group(
    rows: list[QuartaTaglioRow],
    *,
    esolver_link: QuartaTaglioEsolverLink | None = None,
    cod_f3_candidates: list[QuartaTaglioCodF3CandidateResponse] | None = None,
) -> QuartaTaglioRowResponse:
    primary = rows[0]
    worst_color = max((row.status_color for row in rows), key=lambda color: STATUS_SEVERITY.get(color, 0))
    status_details = _group_status_details(rows)
    return QuartaTaglioRowResponse(
        id=primary.id,
        codice_registro=primary.codice_registro,
        data_registro=primary.data_registro,
        cod_odp=primary.cod_odp,
        cod_art=", ".join(_unique_clean(row.cod_art for row in rows)) or None,
        des_art=_join_unique(row.des_art for row in rows) or None,
        cdq=", ".join(_unique_clean(row.cdq for row in rows)),
        colata=", ".join(_unique_clean(row.colata for row in rows)) or None,
        qta_totale=_sum_optional(row.qta_totale for row in rows),
        righe_materiale=sum(row.righe_materiale for row in rows),
        lotti_count=len(_unique_clean(lotto for row in rows for lotto in row.cod_lotti)),
        cod_lotti=_unique_clean(lotto for row in rows for lotto in row.cod_lotti),
        saldo=all(row.saldo for row in rows),
        taglio_attivo=all(row.taglio_attivo for row in rows),
        status_color=worst_color,
        status_message=_group_status_message(worst_color, rows),
        status_details=status_details,
        matching_row_ids=sorted({row_id for row in rows for row_id in row.matching_row_ids}),
        esolver_status=esolver_link.status if esolver_link else "not_checked",
        esolver_message=esolver_link.message if esolver_link else None,
        esolver_cliente=esolver_link.cliente if esolver_link else None,
        esolver_cod_f3=esolver_link.cod_f3 if esolver_link else None,
        esolver_ordine_cliente=esolver_link.ordine_cliente if esolver_link else None,
        esolver_conferma_ordine=esolver_link.conferma_ordine if esolver_link else None,
        esolver_ddt=esolver_link.ddt if esolver_link else None,
        esolver_qta_totale=esolver_link.qta_totale if esolver_link else None,
        esolver_last_checked_at=esolver_link.last_checked_at if esolver_link else None,
        cod_f3_candidate_summary=_certiol_candidate_summary(cod_f3_candidates or []),
        certificates=[_serialize_certificate(row) for row in rows],
        seen_in_last_sync=all(row.seen_in_last_sync for row in rows),
        first_seen_at=min(row.first_seen_at for row in rows),
        last_seen_at=max(row.last_seen_at for row in rows),
    )


def _certiol_candidate_summary(candidates: list[QuartaTaglioCodF3CandidateResponse]) -> QuartaTaglioCodF3CandidateSummaryResponse:
    count = len(candidates)
    if count == 0:
        return QuartaTaglioCodF3CandidateSummaryResponse()
    visible = [candidate for candidate in candidates if candidate.confidence != "review"]
    if visible:
        return QuartaTaglioCodF3CandidateSummaryResponse(
            count=count,
            visible_count=len(visible),
            status="ready",
            label=f"{count} CodF3",
            message="CodF3 disponibili da eSolver",
        )
    if count > 10:
        return QuartaTaglioCodF3CandidateSummaryResponse(
            count=count,
            visible_count=len(visible),
            status="review",
            label=f"{count} CodF3: verifica",
            message="Troppi CodF3 candidati per proposta automatica",
        )
    return QuartaTaglioCodF3CandidateSummaryResponse(
        count=count,
        visible_count=0,
        status="review",
        label=f"{count} CodF3 da verificare",
        message="Candidati presenti ma non abbastanza chiari",
    )


def _enrich_certiol_candidates_with_certificates(
    db: Session,
    *,
    cod_odp: str,
    candidates: list[QuartaTaglioCodF3CandidateResponse],
) -> list[QuartaTaglioCodF3CandidateResponse]:
    if not candidates:
        return []

    certificates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(
            QuartaTaglioFinalCertificate.cod_odp == cod_odp,
            QuartaTaglioFinalCertificate.certificate_number.isnot(None),
        )
        .order_by(QuartaTaglioFinalCertificate.created_at.desc(), QuartaTaglioFinalCertificate.id.desc())
        .all()
    )
    latest_by_cod_f3: dict[str, QuartaTaglioFinalCertificate] = {}
    for certificate in certificates:
        key = _norm(certificate.cod_f3)
        if key and key not in latest_by_cod_f3:
            latest_by_cod_f3[key] = certificate

    raw_key = _norm(next((_clean_text(candidate.cod_f3_odp) for candidate in candidates if _clean_text(candidate.cod_f3_odp)), None))
    raw_certificate = latest_by_cod_f3.get(raw_key) if raw_key else None
    raw_has_word = bool(raw_certificate and raw_certificate.storage_key_docx)

    enriched: list[QuartaTaglioCodF3CandidateResponse] = []
    for candidate in candidates:
        key = _norm(candidate.cod_f3)
        certificate = latest_by_cod_f3.get(key)
        is_raw = bool(raw_key and key == raw_key)
        blocked_reason = candidate.blocked_reason
        message = candidate.message
        if not blocked_reason and not is_raw and not raw_has_word:
            blocked_reason = "Crea prima il Word Raw"
            message = blocked_reason
        certificate_has_ddt = bool(certificate and _clean_text(certificate.ddt))
        waiting_ddt = bool(certificate and certificate.certificate_number and not certificate_has_ddt)
        enriched.append(
            candidate.model_copy(
                update={
                    "message": message,
                    "certificate_id": certificate.id if certificate else None,
                    "certificate_number": certificate.certificate_number if certificate else None,
                    "has_word": bool(certificate and certificate.storage_key_docx),
                    "certificate_has_ddt": certificate_has_ddt,
                    "waiting_ddt": waiting_ddt,
                    "blocked_reason": blocked_reason,
                }
            )
        )
    return enriched


def _build_certiol_candidates(
    *,
    certiol_rows: list[_CertiOlRow],
    quarta_rows: list[QuartaTaglioRow],
    esolver_rows: list[QuartaTaglioEsolverDdtRowResponse] | None = None,
) -> list[QuartaTaglioCodF3CandidateResponse]:
    if not certiol_rows:
        return []
    by_cod_f3: dict[str, _CertiOlRow] = {}
    for row in certiol_rows:
        key = _norm(row.cod_f3)
        if key and key not in by_cod_f3:
            by_cod_f3[key] = row
    rows = list(by_cod_f3.values())
    if not rows:
        return []

    raw_values = sorted({_clean_text(row.cod_f3_odp) for row in rows if _clean_text(row.cod_f3_odp)})
    raw_anomaly = len(raw_values) > 1
    raw_cod_f3 = raw_values[0] if raw_values else _join_unique(row.cod_art for row in quarta_rows) or None
    raw_key = _norm(raw_cod_f3)
    raw_row = next((row for row in rows if _norm(row.cod_f3) == raw_key), None)
    raw_description = _clean_text(raw_row.des_f3) if raw_row else _join_unique((row.des_art for row in quarta_rows), separator=" | ")
    candidate_count = len(rows)
    raw_suffix = _cod_f3_last_two(raw_cod_f3)
    is_old_codification = _is_old_certiol_codification(raw_cod_f3)
    prefix = _cod_f3_prefix(raw_cod_f3)
    ddt_cod_f3_keys = {_norm(row.cod_f3) for row in (esolver_rows or []) if _norm(row.cod_f3)}

    result: list[QuartaTaglioCodF3CandidateResponse] = []
    if raw_cod_f3 and raw_row is None and not raw_anomaly:
        result.append(
            QuartaTaglioCodF3CandidateResponse(
                cod_f3_odp=raw_cod_f3,
                cod_f3=raw_cod_f3,
                des_f3=raw_description,
                relation="raw",
                confidence="raw",
                message="Raw CodF3ODP non presente tra i CodF3 esposti",
                reasons=["CodF3ODP", "raw teorico"],
                has_ddt=raw_key in ddt_cod_f3_keys,
            )
        )
    for row in sorted(rows, key=lambda item: (_cod_f3_sort_value(item.cod_f3) is None, _cod_f3_sort_value(item.cod_f3) or 0, item.cod_f3 or "")):
        cod_f3 = _clean_text(row.cod_f3)
        if not cod_f3:
            continue
        key = _norm(cod_f3)
        is_raw = key == raw_key
        same_prefix = bool(prefix and _cod_f3_prefix(cod_f3) == prefix)
        same_old_family = _is_old_certiol_child(raw_cod_f3, cod_f3)
        same_family = same_old_family if is_old_codification else same_prefix
        description_score = _description_similarity_score(raw_description, row.des_f3)
        reasons: list[str] = []
        if is_raw:
            reasons.append("CodF3ODP")
        if same_family:
            reasons.append("vecchia codifica" if is_old_codification and not is_raw else "stesso prefisso")
        if description_score >= 2:
            reasons.append("descrizione coerente")
        if key in ddt_cod_f3_keys:
            reasons.append("DDT presente")

        confidence = "review"
        message = "Da verificare prima di preparare il Word"
        blocked_reason = None
        if raw_anomaly:
            blocked_reason = "Anomalia CodF3ODP: più raw dichiarati per lo stesso OL"
            message = blocked_reason
        elif key in ddt_cod_f3_keys:
            confidence = "ddt"
            message = "Confermato da DDT eSolver"
        elif is_raw:
            confidence = "raw"
            message = "CodF3ODP/raw"
        elif is_old_codification and same_old_family and candidate_count <= 25:
            confidence = "ready" if description_score >= 1 else "medium"
            message = "Candidato preparabile" if confidence == "ready" else "Candidato probabile"
        elif is_old_codification and same_old_family:
            message = "Troppi candidati vecchia codifica: attendere DDT o verificare manualmente"
        elif candidate_count <= 5 and raw_suffix in {"00", "01", "02"} and same_prefix:
            confidence = "ready" if description_score >= 1 else "medium"
            message = "Candidato preparabile" if confidence == "ready" else "Candidato probabile"
        elif candidate_count <= 10 and raw_suffix in {"00", "01", "02"} and same_prefix and description_score >= 2:
            confidence = "medium"
            message = "Candidato probabile"
        elif candidate_count > 10:
            message = "Troppi candidati: attendere DDT o cercare manualmente"

        result.append(
            QuartaTaglioCodF3CandidateResponse(
                cod_f3_odp=raw_cod_f3,
                cod_f3=cod_f3,
                des_f3=_clean_text(row.des_f3),
                rag_soc=_clean_text(row.rag_soc),
                cod_cli=_clean_text(row.cod_cli),
                relation="raw" if is_raw else "candidate",
                confidence=confidence,
                message=message,
                reasons=reasons,
                has_ddt=key in ddt_cod_f3_keys,
                blocked_reason=blocked_reason,
            )
        )
    return result


def _is_old_certiol_codification(value: str | None) -> bool:
    digits = re.sub(r"\D", "", _clean_text(value) or "")
    return bool(digits and len(digits) < 9)


def _is_old_certiol_child(raw_cod_f3: str | None, cod_f3: str | None) -> bool:
    raw_digits = re.sub(r"\D", "", _clean_text(raw_cod_f3) or "")
    cod_digits = re.sub(r"\D", "", _clean_text(cod_f3) or "")
    if not raw_digits or not cod_digits:
        return False
    return cod_digits == raw_digits or (len(cod_digits) > len(raw_digits) and cod_digits.startswith(raw_digits))


def _cod_f3_prefix(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", _clean_text(value) or "")
    return digits[:-2] if len(digits) > 2 else None


def _cod_f3_last_two(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", _clean_text(value) or "")
    return digits[-2:] if len(digits) >= 2 else None


def _description_similarity_score(left: str | None, right: str | None) -> int:
    left_tokens = _description_tokens(left)
    right_tokens = _description_tokens(right)
    if not left_tokens or not right_tokens:
        return 0
    return len(left_tokens.intersection(right_tokens))


def _description_tokens(value: str | None) -> set[str]:
    text = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", " ", _clean_text(value) or "").upper()
    ignored = {"DI", "DEL", "DELLA", "DELLO", "THE", "AND", "FOR", "CON", "SENZA", "GREZZO", "GREZZA"}
    return {token for token in text.split() if len(token) >= 3 and token not in ignored}


def _candidate_by_cod_f3(
    candidates: list[QuartaTaglioCodF3CandidateResponse],
    cod_f3: str | None,
) -> QuartaTaglioCodF3CandidateResponse | None:
    target = _norm(cod_f3)
    if not target:
        return None
    return next((candidate for candidate in candidates if _norm(candidate.cod_f3) == target), None)


def _build_certifiable_units(
    *,
    cod_odp: str,
    esolver_rows: list[QuartaTaglioEsolverDdtRowResponse],
    quarta_rows: list[QuartaTaglioRow],
) -> list[QuartaTaglioCertifiableUnitResponse]:
    units: list[QuartaTaglioCertifiableUnitResponse] = []
    if esolver_rows:
        grouped: dict[tuple[str, str, str, str], list[QuartaTaglioEsolverDdtRowResponse]] = defaultdict(list)
        for row in esolver_rows:
            grouped[
                (
                    _clean_text(row.cod_f3) or "",
                    _clean_text(row.ddt) or "",
                    _clean_text(row.odv_cli) or "",
                    _clean_text(row.odv_f3) or "",
                )
            ].append(row)
        quarta_keys = {_norm(row.cod_art) for row in quarta_rows if _norm(row.cod_art)}
        for (cod_f3, ddt, ordine_cliente, conferma_ordine), group_rows in sorted(
            grouped.items(),
            key=lambda item: (_norm(item[0][0]) not in quarta_keys, item[0][0], item[0][1], item[0][2], item[0][3]),
        ):
            status_value = "ready" if cod_f3 and ddt else "incomplete"
            units.append(
                QuartaTaglioCertifiableUnitResponse(
                    unit_key=_certifiable_unit_key(
                        cod_odp=cod_odp,
                        cod_f3=cod_f3,
                        ddt=ddt,
                        ordine_cliente=ordine_cliente,
                        conferma_ordine=conferma_ordine,
                    ),
                    cod_odp=cod_odp,
                    cod_f3=cod_f3 or None,
                    ddt=ddt or None,
                    cliente=_join_unique(row.rag_soc for row in group_rows) or None,
                    ordine_cliente=ordine_cliente or None,
                    conferma_ordine=conferma_ordine or None,
                    quantita=_sum_optional(row.qta_um_mag for row in group_rows),
                    certificato_presente=_all_same_bool(row.certificato_presente for row in group_rows),
                    source="esolver",
                    status=status_value,
                    message=None if status_value == "ready" else "Cod. F3 o DDT mancante dalla riga eSolver",
                    rows_count=len(group_rows),
                )
            )
    if not units:
        quarta_cod_f3 = _join_unique(row.cod_art for row in quarta_rows) or None
        units.append(
            QuartaTaglioCertifiableUnitResponse(
                unit_key=_certifiable_unit_key(cod_odp=cod_odp, cod_f3=quarta_cod_f3, ddt=None),
                cod_odp=cod_odp,
                cod_f3=quarta_cod_f3,
                ddt=None,
                quantita=_sum_optional(row.qta_totale for row in quarta_rows),
                source="quarta",
                status="incomplete",
                message="DDT eSolver non ancora disponibile",
                rows_count=len(quarta_rows),
            )
        )
    primary = _select_primary_unit(units=units, quarta_rows=quarta_rows)
    return [unit.model_copy(update={"is_primary": unit.unit_key == primary.unit_key}) for unit in units]


def _certifiable_unit_key(
    *,
    cod_odp: str,
    cod_f3: str | None,
    ddt: str | None,
    ordine_cliente: str | None = None,
    conferma_ordine: str | None = None,
) -> str:
    return "|".join(
        [
            _clean_text(cod_odp) or "-",
            _clean_text(cod_f3) or "-",
            _clean_text(ddt) or "-",
            _clean_text(ordine_cliente) or "-",
            _clean_text(conferma_ordine) or "-",
        ]
    )


def _primary_certifiable_unit(units: list[QuartaTaglioCertifiableUnitResponse]) -> QuartaTaglioCertifiableUnitResponse | None:
    return next((unit for unit in units if unit.is_primary), units[0] if units else None)


def _select_primary_unit(
    *,
    units: list[QuartaTaglioCertifiableUnitResponse],
    quarta_rows: list[QuartaTaglioRow],
) -> QuartaTaglioCertifiableUnitResponse:
    quarta_keys = {_norm(row.cod_art) for row in quarta_rows if _norm(row.cod_art)}
    if quarta_keys:
        matching_unit = next((unit for unit in units if _norm(unit.cod_f3) in quarta_keys), None)
        if matching_unit:
            return matching_unit
    ready_unit = next((unit for unit in units if unit.status == "ready"), None)
    return ready_unit or units[0]


def _certificate_header_flow(
    *,
    current_unit: QuartaTaglioCertifiableUnitResponse | None,
    certifiable_units: list[QuartaTaglioCertifiableUnitResponse],
    quarta_rows: list[QuartaTaglioRow],
    raw_description: str | None,
    raw_cod_f3_override: str | None = None,
) -> dict[str, str | None]:
    raw_cod_f3 = _clean_text(raw_cod_f3_override) or _join_unique(row.cod_art for row in quarta_rows) or None
    current_cod_f3 = _clean_text(current_unit.cod_f3) if current_unit else None
    raw_unit = current_unit if _norm(current_cod_f3) == _norm(raw_cod_f3) else _unit_for_cod_f3(certifiable_units, raw_cod_f3)
    finished_unit = current_unit if _norm(current_cod_f3) and _norm(current_cod_f3) != _norm(raw_cod_f3) else None
    return {
        "raw_cod_f3": raw_cod_f3,
        "raw_description": _clean_text(raw_description),
        "raw_ddt": _clean_text(raw_unit.ddt) if raw_unit and raw_unit.ddt else None,
        "raw_quantita": _format_quantity(raw_unit.quantita) if raw_unit and raw_unit.ddt and raw_unit.quantita is not None else None,
        "finished_cod_f3": _clean_text(finished_unit.cod_f3) if finished_unit else None,
        "finished_description": None,
        "finished_ddt": _clean_text(finished_unit.ddt) if finished_unit and finished_unit.ddt else None,
        "finished_quantita": _format_quantity(finished_unit.quantita) if finished_unit and finished_unit.ddt and finished_unit.quantita is not None else None,
    }


def _unit_for_cod_f3(
    units: list[QuartaTaglioCertifiableUnitResponse],
    cod_f3: str | None,
) -> QuartaTaglioCertifiableUnitResponse | None:
    target = _norm(cod_f3)
    if not target:
        return None
    ready_match = next((unit for unit in units if _norm(unit.cod_f3) == target and unit.status == "ready"), None)
    return ready_match or next((unit for unit in units if _norm(unit.cod_f3) == target), None)


def _all_same_bool(values: Any) -> bool | None:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return all(cleaned)


def _codice_f3_from_unit_or_quarta(
    *,
    unit: QuartaTaglioCertifiableUnitResponse | None,
    quarta_rows: list[QuartaTaglioRow],
) -> dict[str, str | None]:
    if unit and unit.cod_f3:
        return _codice_f3_from_esolver_or_quarta(
            esolver_header_rows=[],
            quarta_rows=quarta_rows,
            esolver_value_fallback=unit.cod_f3,
        )
    return _codice_f3_from_esolver_or_quarta(esolver_header_rows=[], quarta_rows=quarta_rows)


def _codice_f3_from_esolver_or_quarta(
    *,
    esolver_header_rows: list[QuartaTaglioEsolverDdtRowResponse],
    quarta_rows: list[QuartaTaglioRow],
    esolver_value_fallback: str | None = None,
) -> dict[str, str | None]:
    esolver_value = _join_unique(row.cod_f3 for row in esolver_header_rows) or esolver_value_fallback or None
    quarta_value = _join_unique(row.cod_art for row in quarta_rows) or None
    if esolver_value:
        warning = None
        if quarta_value and _norm(esolver_value) != _norm(quarta_value):
            warning = f"Cod. F3 eSolver diverso da Quarta: Quarta {quarta_value}"
        return {
            "value": esolver_value,
            "origin": "esolver",
            "esolver": esolver_value,
            "quarta": quarta_value,
            "warning": warning,
        }
    if quarta_value:
        return {
            "value": quarta_value,
            "origin": "quarta_fallback",
            "esolver": None,
            "quarta": quarta_value,
            "warning": "Cod. F3 eSolver mancante: usato codice articolo Quarta",
        }
    return {
        "value": None,
        "origin": "missing",
        "esolver": None,
        "quarta": None,
        "warning": None,
    }


def _serialize_certificate(row: QuartaTaglioRow) -> QuartaTaglioCertificateResponse:
    return QuartaTaglioCertificateResponse(
        cdq=row.cdq,
        colata=row.colata,
        cod_art=row.cod_art,
        des_art=row.des_art,
        qta_totale=row.qta_totale,
        righe_materiale=row.righe_materiale,
        lotti_count=row.lotti_count,
        cod_lotti=row.cod_lotti,
        status_color=row.status_color,
        status_message=row.status_message,
        status_details=row.status_details,
        matching_row_ids=row.matching_row_ids,
    )


def _group_status_message(color: str, rows: list[QuartaTaglioRow]) -> str:
    if len(rows) == 1:
        return rows[0].status_message
    if color == "red":
        return "Uno o più CDQ bloccano la certificazione"
    if color == "yellow":
        return "Uno o più CDQ da completare"
    return "Tutti i CDQ coerenti e completi"


def _max_status_color(left: str, right: str) -> str:
    return max((left, right), key=lambda color: STATUS_SEVERITY.get(color, 0))


def _esolver_block_color(status_value: str) -> str:
    if status_value == "ok":
        return "green"
    if status_value in {"mismatch", "error"}:
        return "red"
    return "yellow"


def _group_status_details(rows: list[QuartaTaglioRow]) -> list[str]:
    details: list[str] = []
    for row in rows:
        if row.status_color == "green":
            continue
        prefix = f"CDQ {row.cdq}"
        row_details = row.status_details or [row.status_message]
        details.extend(f"{prefix}: {detail}" for detail in row_details if detail)
    return sorted(set(details))


def _unique_clean(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        key = _norm(cleaned)
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _sum_optional(values: Any) -> float | None:
    total = 0.0
    found = False
    for value in values:
        if value is None:
            continue
        total += float(value)
        found = True
    return total if found else None


def _format_quantity(value: Any) -> str | None:
    numeric_value = _as_float(value)
    if numeric_value is None:
        return _clean_text(value)
    return str(int(round(numeric_value)))


def _materiale_fornito_from_app_row(row: AcquisitionRow) -> str | None:
    return _join_unique((row.lega_designazione, row.lega_base, row.variante_lega), separator=" ")


def _materiale_raw_from_app_row(row: AcquisitionRow) -> str | None:
    raw_value = (
        _read_value(row, "ddt", "product_description_raw")
        or _read_value(row, "match", "descrizione_profilo_cliente_certificato")
        or _read_value(row, "ddt", "customer_item_description_raw")
    )
    if raw_value:
        return _clean_text(raw_value)
    composed = _join_unique(
        (
            _read_value(row, "ddt", "material_raw"),
            _read_value(row, "ddt", "diameter_raw"),
            _read_value(row, "ddt", "die_dimension_raw"),
        ),
        separator=" ",
    )
    return composed or _join_unique((_materiale_fornito_from_app_row(row), row.diametro), separator=" ")


def _certificate_datetime_from_detail(detail: QuartaTaglioDetailResponse) -> datetime | None:
    header = detail.header or {}
    return _certificate_datetime_from_ddt(header.get("ddt"))


def _certificate_datetime_from_ddt(ddt: Any) -> datetime | None:
    text = _clean_text(ddt)
    if not text:
        return None
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _format_certificate_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d/%m/%Y")


def _join_unique(values: Any, separator: str = ", ") -> str:
    return separator.join(_unique_clean(values))


def _split_des_art(value: str | None) -> tuple[str | None, str | None, str]:
    text = _clean_text(value)
    if not text:
        return None, None, "mancante"
    if "|" in text:
        return text, None, "multiplo"

    dis_match = re.search(r"\bDIS\.?\s+(.+)$", text, flags=re.IGNORECASE)
    if dis_match:
        drawing = f"DIS. {dis_match.group(1).strip()}"
        description = text[: dis_match.start()].strip()
        return description or text, drawing, "proposta"

    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        description, last_token = parts[0].strip(), parts[1].strip()
        has_digit = bool(re.search(r"\d", last_token))
        looks_like_drawing = has_digit and (
            "/" in last_token
            or "." in last_token
            or bool(re.match(r"^[A-Z]?\d{4,}[A-Z0-9.-]*$", last_token, flags=re.IGNORECASE))
            or bool(re.match(r"^[A-Z]\d{4,}[A-Z0-9.-]*/[A-Z0-9.-]+$", last_token, flags=re.IGNORECASE))
        )
        if description and looks_like_drawing:
            return description, last_token, "proposta"

    return text, None, "da_verificare"


def _sql_identifier(value: str) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", cleaned):
        return None
    return cleaned


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return bool(value)
    normalized = _norm(value)
    if normalized in {"1", "true", "si", "sì", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


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
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:[,.]\d+)?", value.strip())
        if not match:
            return None
        value = match.group(0).replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_lotti(value: Any) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
