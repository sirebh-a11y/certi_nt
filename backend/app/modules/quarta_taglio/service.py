from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.integrations.models import ExternalConnection
from app.core.security.crypto import decrypt_secret
from app.modules.acquisition.models import AcquisitionRow, ReadValue
from app.modules.acquisition.service import _compute_block_states_from_db
from app.modules.quarta_taglio.models import QuartaTaglioRow, QuartaTaglioStandardSelection, QuartaTaglioSyncRun
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioAggregateValueResponse,
    QuartaTaglioCertificateResponse,
    QuartaTaglioDetailResponse,
    QuartaTaglioListResponse,
    QuartaTaglioMaterialResponse,
    QuartaTaglioMissingItemResponse,
    QuartaTaglioNoteResponse,
    QuartaTaglioRowResponse,
    QuartaTaglioStandardCandidateResponse,
    QuartaTaglioSyncRunResponse,
)
from app.modules.standards.models import NormativeStandard
from app.modules.notes.models import AcquisitionRowNoteTemplate

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

NOTE_FIELDS = [
    ("nota_rohs", "RoHS"),
    ("nota_radioactive_free", "Radioactive free"),
    ("nota_us_control_class_a", "US control Class A"),
    ("nota_us_control_class_b", "US control Class B"),
]


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

    rows = (
        db.query(QuartaTaglioRow)
        .filter(QuartaTaglioRow.seen_in_last_sync.is_(True))
        .order_by(QuartaTaglioRow.data_registro.desc(), QuartaTaglioRow.cod_odp.desc(), QuartaTaglioRow.cdq.asc())
        .all()
    )
    return QuartaTaglioListResponse(sync_run=_serialize_run(run), items=_serialize_grouped_rows(rows))


def get_quarta_taglio_detail(db: Session, *, cod_odp: str) -> QuartaTaglioDetailResponse:
    rows = (
        db.query(QuartaTaglioRow)
        .filter(QuartaTaglioRow.cod_odp == cod_odp)
        .order_by(QuartaTaglioRow.cdq.asc(), QuartaTaglioRow.colata.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OL non trovato in Certificazione")

    group = _serialize_ol_group(rows)
    app_rows = _load_matching_app_rows(db, rows)
    materials = [
        QuartaTaglioMaterialResponse(
            cdq=row.cdq,
            colata=row.colata,
            cod_art=row.cod_art,
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

    material_weights = {row.cdq: row.qta_totale for row in rows}
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
    )
    notes = _evaluate_notes(app_rows)
    ready = group.status_color == "green"

    return QuartaTaglioDetailResponse(
        cod_odp=group.cod_odp,
        ready=ready,
        status_color=group.status_color,
        status_message="Certificato pronto da preparare" if ready else "Dati ancora mancanti per creare il certificato",
        header={
            "numero_certificato": None,
            "cliente": None,
            "ordine_cliente": None,
            "ddt": None,
            "codice_f3": group.cod_art,
            "descrizione": None,
            "colata": group.colata,
            "quantita": str(group.qta_totale) if group.qta_totale is not None else None,
        },
        materials=materials,
        missing_items=missing_items,
        standard_candidates=standard_candidates,
        selected_standard=selected_standard,
        selected_standard_confirmed=selected_standard_confirmed,
        chemistry=chemistry,
        properties=properties,
        notes=notes,
    )


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
    return get_quarta_taglio_detail(db, cod_odp=cod_odp)


def _load_matching_app_rows(db: Session, rows: list[QuartaTaglioRow]) -> list[AcquisitionRow]:
    row_ids = sorted({row_id for row in rows for row_id in (row.matching_row_ids or [])})
    if not row_ids:
        return []
    return (
        db.query(AcquisitionRow)
        .options(
            selectinload(AcquisitionRow.values),
            selectinload(AcquisitionRow.certificate_match),
            selectinload(AcquisitionRow.custom_note_links).joinedload(AcquisitionRowNoteTemplate.note_template),
        )
        .filter(AcquisitionRow.id.in_(row_ids))
        .order_by(AcquisitionRow.cdq.asc(), AcquisitionRow.colata.asc(), AcquisitionRow.id.asc())
        .all()
    )


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
) -> list[QuartaTaglioAggregateValueResponse]:
    result: list[QuartaTaglioAggregateValueResponse] = []
    standard_chemistry_keys = _standard_chemistry_field_keys(standard) if block == "chimica" else set()
    for field in fields:
        values: list[tuple[float, float | None]] = []
        missing_rows: list[str] = []
        for row in app_rows:
            value = _as_float(_read_value(row, block, field))
            if value is None:
                missing_rows.append(row.cdq or f"riga #{row.id}")
                continue
            values.append((value, material_weights.get(row.cdq or "")))

        if block == "chimica" and standard is not None and _field_key(field) not in standard_chemistry_keys:
            if values:
                result.append(
                    QuartaTaglioAggregateValueResponse(
                        field=field,
                        value=round(sum(value for value, _ in values) / len(values), 4),
                        method="average" if len(values) > 1 else "single",
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

        if len(values) == len(app_rows) and all(weight is not None and weight > 0 for _, weight in values):
            total_weight = sum(float(weight or 0) for _, weight in values)
            aggregated = sum(value * float(weight or 0) for value, weight in values) / total_weight
            method = "weighted"
        elif len(values) == 1:
            aggregated = values[0][0]
            method = "single"
        else:
            aggregated = sum(value for value, _ in values) / len(values)
            method = "average"

        limit_min, limit_max = _standard_limits_for_field(standard, block=block, field=field, app_rows=app_rows)
        if block == "chimica" and standard is None:
            check_status = "not_checked"
            message = "Confermare lo standard per sapere se l'elemento va riportato"
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
                value=round(aggregated, 4),
                method=method,
                standard_min=limit_min,
                standard_max=limit_max,
                status=check_status,
                message=message,
            )
        )
    return result


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
    if limit_min is not None and value < limit_min:
        messages.append(f"sotto minimo {limit_min:g}")
    if limit_max is not None and value > limit_max:
        messages.append(f"sopra massimo {limit_max:g}")
    if messages:
        return "out_of_range" if any("minimo" in item or "massimo" in item for item in messages) else "missing", "; ".join(messages)
    return "ok", None


def _evaluate_notes(app_rows: list[AcquisitionRow]) -> list[QuartaTaglioNoteResponse]:
    notes: list[QuartaTaglioNoteResponse] = []
    for code, label in NOTE_FIELDS:
        values = [_clean_note_value(_read_value(row, "note", code)) for row in app_rows]
        filled = [value for value in values if value]
        unique_values = sorted(set(filled))
        if not filled:
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
                    value=unique_values[0],
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
            reasons.append(f"lega {standard.lega_base}")

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
        standard.lega_base,
        standard.norma,
        standard.trattamento_termico,
        standard.tipo_prodotto,
        standard.misura_tipo,
    ]
    return " · ".join(_unique_clean(parts)) or standard.code


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


def _serialize_grouped_rows(rows: list[QuartaTaglioRow]) -> list[QuartaTaglioRowResponse]:
    rows_by_ol: dict[str, list[QuartaTaglioRow]] = defaultdict(list)
    for row in rows:
        rows_by_ol[row.cod_odp].append(row)

    return [_serialize_ol_group(group_rows) for group_rows in rows_by_ol.values()]


def _serialize_ol_group(rows: list[QuartaTaglioRow]) -> QuartaTaglioRowResponse:
    primary = rows[0]
    worst_color = max((row.status_color for row in rows), key=lambda color: STATUS_SEVERITY.get(color, 0))
    status_details = _group_status_details(rows)
    return QuartaTaglioRowResponse(
        id=primary.id,
        codice_registro=primary.codice_registro,
        data_registro=primary.data_registro,
        cod_odp=primary.cod_odp,
        cod_art=", ".join(_unique_clean(row.cod_art for row in rows)) or None,
        cdq=", ".join(_unique_clean(row.cdq for row in rows)),
        colata=", ".join(_unique_clean(row.colata for row in rows)) or None,
        qta_totale=_sum_optional(row.qta_totale for row in rows),
        righe_materiale=sum(row.righe_materiale for row in rows),
        lotti_count=len(_unique_clean(lotto for row in rows for lotto in row.cod_lotti)),
        cod_lotti=_unique_clean(lotto for row in rows for lotto in row.cod_lotti),
        saldo=all(row.saldo for row in rows),
        status_color=worst_color,
        status_message=_group_status_message(worst_color, rows),
        status_details=status_details,
        matching_row_ids=sorted({row_id for row in rows for row_id in row.matching_row_ids}),
        certificates=[_serialize_certificate(row) for row in rows],
        seen_in_last_sync=all(row.seen_in_last_sync for row in rows),
        first_seen_at=min(row.first_seen_at for row in rows),
        last_seen_at=max(row.last_seen_at for row in rows),
    )


def _serialize_certificate(row: QuartaTaglioRow) -> QuartaTaglioCertificateResponse:
    return QuartaTaglioCertificateResponse(
        cdq=row.cdq,
        colata=row.colata,
        cod_art=row.cod_art,
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
