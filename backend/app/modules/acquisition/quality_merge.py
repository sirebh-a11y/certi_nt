"""Preserve manual quality data when two incoming rows become one."""
from fastapi import HTTPException

MANUAL_FIELDS = ('qualita_note', 'qualita_data_accettazione',
                 'qualita_data_ricezione', 'qualita_data_richiesta')


def acceptance_date_needs_choice(source, target):
    return bool(source.qualita_data_accettazione and target.qualita_data_accettazione
                and source.qualita_data_accettazione != target.qualita_data_accettazione
                and not source.qualita_valutazione and not target.qualita_valutazione)


def merge_manual_quality_values(source, target, *, acceptance_date_choice=None):
    source_date, target_date = source.qualita_data_accettazione, target.qualita_data_accettazione
    if acceptance_date_needs_choice(source, target):
        if acceptance_date_choice not in (source_date, target_date):
            raise HTTPException(status_code=409, detail={
                'code': 'merge_acceptance_date_choice',
                'message': 'Date accettazione diverse: scegli quale mantenere prima di unire le righe.',
                'source_row_id': source.id, 'target_row_id': target.id,
                'certificate_date': source_date.isoformat(), 'ddt_date': target_date.isoformat(),
            })
        acceptance_date = acceptance_date_choice
    elif not target_date:
        acceptance_date = source_date
    elif not source_date or target.qualita_valutazione:
        # The destination evaluation, when present, is retained by the existing merge.
        acceptance_date = target_date
    elif source.qualita_valutazione:
        acceptance_date = source_date
    else:
        acceptance_date = target_date

    source_note, target_note = source.qualita_note, target.qualita_note
    if not (target_note or '').strip():
        note = source_note if (source_note or '').strip() else target_note
    elif not (source_note or '').strip() or source_note.strip() == target_note.strip():
        note = target_note
    else:
        note = f'Da certificato: {source_note}\nDa riga DDT: {target_note}'

    values = {'qualita_note': note, 'qualita_data_accettazione': acceptance_date}
    for field in ('qualita_data_ricezione', 'qualita_data_richiesta'):
        # Keep existing precedence for other dates; never replace data with NULL.
        src, dst = getattr(source, field), getattr(target, field)
        values[field] = src if src and (not dst or (source.qualita_valutazione and not target.qualita_valutazione)) else dst
    return values
