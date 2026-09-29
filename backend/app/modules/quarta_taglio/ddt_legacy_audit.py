"""Read-only dry-run for DDT units retained by the old per-OL eSolver cache.

This module never imports cache rows. A current complete source snapshot is
required before it can call a missing cache unit genuinely historical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from types import SimpleNamespace

from sqlalchemy import inspect, select

from app.modules.quarta_taglio.ddt_context import exact_certificate, quantity_matches
from app.modules.quarta_taglio.ddt_queue import _pdf_valid
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _normalize, last_snapshot_runs
from app.modules.quarta_taglio.models import (
    QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtWorkItem,
    QuartaTaglioEsolverLink, QuartaTaglioFinalCertificate, QuartaTaglioRow,
)


def _source_row_from_cache(row):
    return {
        "IdDocumento": row.get("id_documento"),
        "IdRigaDoc": row.get("id_riga_doc"),
        "RifLottoAlfanum": row.get("rif_lotto_alfanum"),
        "ORP": row.get("orp"),
        "CodF3": row.get("cod_f3"),
        "DDT": row.get("ddt"),
        "RagSoc": row.get("rag_soc"),
        "ODVCli": row.get("odv_cli"),
        "ODVF3": row.get("odv_f3"),
        "QtaUmMag": row.get("qta_um_mag"),
        "CertificatoPresente": row.get("certificato_presente"),
    }


def _facts_differ(left, right):
    return not quantity_matches(left, right) or any(getattr(left, field) != getattr(right, field) for field in (
        "cod_odp", "cod_f3", "ddt_raw", "cliente", "ordine_cliente",
        "conferma_ordine",
    ))


def _related_certificate(item, cert):
    if cert.cod_odp != item.cod_odp:
        return False
    return bool(
        cert.unit_key == item.certification_unit_key
        or (cert.esolver_id_documento == item.id_documento
            and cert.esolver_id_riga_doc == item.id_riga_doc
            and (cert.esolver_rif_lotto_alfanum or None) == item.rif_lotto_alfanum)
        or (not cert.esolver_id_documento and not cert.esolver_id_riga_doc
            and cert.cod_f3 == item.cod_f3 and cert.ddt == item.ddt_raw)
    )


def classify_legacy_cache(db, *, current_rows=None):
    """Classify candidates; `current_rows` is a complete, externally read view.

    If omitted, use only an existing successful persistent snapshot. A missing
    baseline never causes an old cache row to be labelled safe to import.
    """
    tables = inspect(db.connection())
    source_basis = "unavailable"
    source_index = None
    source_by_base = defaultdict(list)
    source_duplicate_keys = set()
    source_invalid = 0

    if current_rows is not None:
        source_basis = "live_complete_view"
        source_index = {}
        for row in current_rows:
            try:
                values = _normalize(row)
            except SnapshotError:
                source_invalid += 1
                continue
            key = values["source_key"]
            if key in source_index:
                source_duplicate_keys.add(key)
            item = SimpleNamespace(**values)
            source_index[key] = item
            source_by_base[(item.id_documento, item.id_riga_doc, item.rif_lotto_alfanum)].append(item)
    elif tables.has_table(QuartaTaglioDdtWorkItem.__tablename__) and tables.has_table("quarta_taglio_ddt_sync_runs"):
        _, success = last_snapshot_runs(db)
        if success is not None:
            source_basis = "persisted_successful_snapshot"
            source_index = {item.source_key: item for item in db.scalars(select(QuartaTaglioDdtWorkItem))}
            for item in source_index.values():
                if item.source_present:
                    source_by_base[(item.id_documento, item.id_riga_doc, item.rif_lotto_alfanum)].append(item)

    counters = Counter()
    issues = Counter()
    cache_units = defaultdict(list)
    import_candidates = []
    links = list(db.scalars(select(QuartaTaglioEsolverLink)))
    counters["cache_links"] = len(links)
    for link in links:
        if link.rows:
            counters["cache_links_with_ddt"] += 1
        for row in link.rows or []:
            counters["cache_rows"] += 1
            if not isinstance(row, dict):
                issues["invalid_cache_row"] += 1
                continue
            try:
                values = _normalize(_source_row_from_cache(row))
            except SnapshotError as exc:
                issues[str(exc)] += 1
                continue
            if (values["cod_odp"] or "") != (link.cod_odp or ""):
                issues["cache_parent_ol_mismatch"] += 1
                continue
            cache_units[values["source_key"]].append(
                SimpleNamespace(**values, cache_checked_at=link.last_checked_at)
            )

    counters["distinct_cache_units"] = len(cache_units)
    cache_dates = [group[0].ddt_date for group in cache_units.values() if group[0].ddt_date]
    source_dates = [item.ddt_date for item in (source_index or {}).values()
                    if item.ddt_date and (source_basis == "live_complete_view" or item.source_present)]
    counters["duplicate_identity_units"] = sum(len(group) > 1 for group in cache_units.values())
    counters["duplicate_identity_rows"] = sum(len(group) for group in cache_units.values() if len(group) > 1)
    issues["duplicate_cache_identity"] = counters["duplicate_identity_units"]
    issues["duplicate_cache_identity_conflicting_facts"] = sum(
        any(_facts_differ(group[0], other) for other in group[1:])
        for group in cache_units.values() if len(group) > 1
    )

    certificates_by_ol = defaultdict(list)
    for cert in db.scalars(select(QuartaTaglioFinalCertificate)):
        certificates_by_ol[cert.cod_odp].append(cert)
    versions_by_cert = defaultdict(list)
    if tables.has_table(QuartaTaglioCertificatePdfVersion.__tablename__):
        for version in db.scalars(select(QuartaTaglioCertificatePdfVersion)):
            versions_by_cert[version.certificate_id].append(version)
    quarta_ols = set(db.scalars(select(QuartaTaglioRow.cod_odp).distinct()))

    empty_source_with_cache = source_index is not None and not source_index and bool(cache_units)
    baseline_valid = source_index is not None and not source_duplicate_keys and source_invalid == 0 and not empty_source_with_cache
    if source_index is not None:
        counters["source_units"] = len(source_index)
    issues["invalid_current_source_rows"] = source_invalid
    issues["duplicate_current_source_identity"] = len(source_duplicate_keys)
    issues["empty_current_source_with_cache"] = int(empty_source_with_cache)

    for key, group in cache_units.items():
        if len(group) > 1:
            counters["review_units"] += 1
            continue
        item = group[0]
        if not baseline_valid:
            counters["source_unknown_units"] += 1
            continue
        current = source_index.get(key)
        if current is not None:
            if _facts_differ(item, current):
                issues["cache_source_data_changed"] += 1
                counters["review_units"] += 1
            elif source_basis == "persisted_successful_snapshot" and not current.source_present:
                counters["already_saved_historical"] += 1
            else:
                counters["already_in_current_source"] += 1
            continue
        if source_by_base[(item.id_documento, item.id_riga_doc, item.rif_lotto_alfanum)]:
            issues["source_identity_changed"] += 1
            counters["review_units"] += 1
            continue

        counters["historical_units"] += 1
        if not item.cod_odp:
            issues["missing_ol"] += 1
        if item.cod_odp and item.cod_odp not in quarta_ols:
            issues["ol_not_in_quarta"] += 1
        if not item.cod_f3 or not item.ddt_raw or not item.ddt_date:
            issues["missing_certification_fields"] += 1
        if not item.cod_odp or item.cod_odp not in quarta_ols or not item.cod_f3 or not item.ddt_raw or not item.ddt_date:
            counters["review_units"] += 1
            continue

        certificates = certificates_by_ol[item.cod_odp]
        exact = [cert for cert in certificates if exact_certificate(item, cert)]
        if len(exact) > 1:
            issues["multiple_exact_certificates"] += 1
            counters["review_units"] += 1
        elif exact:
            cert = exact[0]
            if not quantity_matches(item, cert):
                issues["certificate_quantity_changed"] += 1
                counters["review_units"] += 1
            elif _pdf_valid(cert, versions_by_cert[cert.id]):
                counters["completed_historical"] += 1
                import_candidates.append(item)
            elif cert.status == "pdf_final":
                issues["pdf_final_not_verifiable"] += 1
                counters["review_units"] += 1
            else:
                counters["recoverable_historical"] += 1
                import_candidates.append(item)
        elif any(_related_certificate(item, cert) for cert in certificates):
            issues["certificate_identity_conflict"] += 1
            counters["review_units"] += 1
        else:
            counters["recoverable_historical"] += 1
            import_candidates.append(item)

    report = {
        "status": "classified" if baseline_valid else "source_baseline_required",
        "source_basis": source_basis,
        "cache_ddt_date_range": [min(cache_dates).isoformat(), max(cache_dates).isoformat()] if cache_dates else None,
        "source_ddt_date_range": [min(source_dates).isoformat(), max(source_dates).isoformat()] if source_dates else None,
        "counts": dict(sorted(counters.items())),
        "issues": {key: value for key, value in sorted(issues.items()) if value},
    }
    return report, import_candidates


def analyze_legacy_cache(db, *, current_rows=None):
    """Serializable read-only report, without the candidate row payloads."""
    report, _ = classify_legacy_cache(db, current_rows=current_rows)
    return report
