"""Queue tests use SQLite and disposable files only; no Alpha/eSolver calls."""
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.deps import get_current_user, get_db
from app.modules.acquisition.models import AcquisitionRow, AcquisitionHistoryEvent, Document
from app.modules.quarta_taglio import ddt_queue as queue, ddt_snapshot as snapshot, service
from app.modules.quarta_taglio.models import (
    QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem,
    QuartaTaglioEsolverLink, QuartaTaglioFinalCertificate, QuartaTaglioIncomingRowOverride, QuartaTaglioRow,
)
from app.modules.quarta_taglio.router import router


NOW = datetime(2026, 9, 29, 9, tzinfo=timezone.utc)


class DdtQueueFixture(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.factory()
        self.files = TemporaryDirectory(prefix="certi-ddt-queue-")
        self.addCleanup(self.files.cleanup)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.storage = patch.object(service.settings, "document_storage_root", self.files.name)
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.document = Document(tipo_documento="certificato", nome_file_originale="test.pdf", storage_key="supplier.pdf")
        self.db.add(self.document)
        self.db.commit()

    def item(self, **changes):
        data = dict(IdDocumento="100", IdRigaDoc="1", RifLottoAlfanum="lot-a", ORP="OL1", CodF3="001230",
                    DDT="77-01/09/2026", RagSoc="Cliente A", ODVCli="PO", ODVF3="ORD", QtaUmMag=Decimal("42"),
                    CertificatoPresente=0)
        data.update(changes)
        item = QuartaTaglioDdtWorkItem(**snapshot._normalize(data), first_seen_at=NOW, last_seen_at=NOW)
        self.db.add(item)
        self.db.commit()
        return item

    def material(self, *, ol="OL1", cdq="CDQ1", colata="COL1", evaluation="accettato", complete=True,
                 diameter="285", article="A75285BTU", processing=None, certificate=True, current=True):
        quarta = QuartaTaglioRow(codice_registro="1", cod_odp=ol, cdq=cdq, colata=colata, cod_art="001230",
                                 cod_mp=article, qta_totale=100, seen_in_last_sync=current,
                                 status_color="red", status_message="cached stale", matching_row_ids=[])
        self.db.add(quarta)
        incoming = AcquisitionRow(cdq=cdq, colata=colata, diametro=diameter,
                                  document_certificato_id=self.document.id if certificate else None,
                                  qualita_valutazione=evaluation, ai_processing_status=processing)
        self.db.add(incoming)
        self.db.flush()
        if complete:
            self.confirm_blocks(incoming)
        self.db.commit()
        return quarta, incoming

    def confirm_blocks(self, incoming):
        for block in ("chimica", "proprieta", "note"):
            self.db.add(AcquisitionHistoryEvent(acquisition_row_id=incoming.id, blocco=block,
                                               azione="conferma_rapida_certificazione"))
        self.db.flush()

    def cert(self, item, *, pdf=False, word=True, active=True, file_exists=True, **changes):
        values = dict(cod_odp=item.cod_odp, cod_f3=item.cod_f3, ddt=item.ddt_raw,
                      esolver_id_documento=item.id_documento, esolver_id_riga_doc=item.id_riga_doc,
                      esolver_rif_lotto_alfanum=item.rif_lotto_alfanum, ordine_cliente=item.ordine_cliente,
                      quantita=float(item.quantita) if item.quantita is not None else None,
                      unit_key=item.certification_unit_key, status="pdf_final" if pdf else "draft",
                      draft_number="TEST", closed_at=NOW if pdf else None)
        values.update(changes)
        cert = QuartaTaglioFinalCertificate(**values)
        self.db.add(cert)
        self.db.flush()
        if word:
            cert.storage_key_docx = f"word-{cert.id}.docx"
            if file_exists:
                Path(self.files.name, cert.storage_key_docx).write_bytes(b"test Word fixture")
        if pdf:
            cert.storage_key_pdf = f"pdf-{cert.id}.pdf"
            if file_exists:
                Path(self.files.name, cert.storage_key_pdf).write_bytes(b"%PDF-1.4 test fixture")
            self.db.add(QuartaTaglioCertificatePdfVersion(certificate_id=cert.id, version=1,
                        status="active" if active else "reopened", storage_key_pdf=cert.storage_key_pdf,
                        annulled_at=None if active else NOW))
        self.db.commit()
        return cert

    def read(self, **kwargs):
        return queue.read_ddt_queue(self.db, **kwargs)


class DdtQueueTest(DdtQueueFixture):
    def test_empty_queue_has_zero_counts_and_uninitialized_sync(self):
        result = self.read()
        self.assertEqual((result.total, result.active, result.total_items), (0, 0, 0))
        self.assertIsNone(result.sync.last_success)
        self.assertFalse(result.sync.enabled)

    def test_missing_ol_visible_with_source_identifiers_and_no_invented_target(self):
        self.item(ORP=None)
        result = self.read().items[0]
        self.assertEqual(result.state, "to_link")
        self.assertEqual((result.id_documento, result.id_riga_doc), ("100", "1"))
        self.assertIsNone(result.cod_odp)
        self.assertIsNone(result.certification_unit_key)

    def test_missing_quarta_or_missing_incoming_stays_waiting(self):
        self.item()
        self.assertEqual(self.read().items[0].state, "waiting_incoming")
        quarta, incoming = self.material(complete=False)
        self.assertEqual(self.read().items[0].state, "waiting_incoming")
        self.db.delete(incoming)
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "waiting_incoming")

    def test_ready_uses_live_blocks_not_cached_color_and_writes_nothing(self):
        self.item()
        quarta, incoming = self.material()
        cache = QuartaTaglioEsolverLink(cod_odp="OL1", status="missing", rows=[])
        self.db.add(cache)
        self.db.commit()
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with patch.object(service, "get_quarta_taglio_detail", side_effect=AssertionError("mutating detail")), \
                 patch.object(service, "_fetch_esolver_ddt_rows_batch", side_effect=AssertionError("remote read")), \
                 patch.object(self.db, "commit", side_effect=AssertionError("commit")):
                result = self.read().items[0]
            self.assertEqual(result.state, "ready")
            self.assertEqual(result.incoming_row_ids, [incoming.id])
            self.assertTrue(result.incoming_ready)
            self.assertFalse(self.db.dirty or self.db.new or self.db.deleted)
            self.assertTrue(all(command == "SELECT" for command in statements))
            self.assertEqual(quarta.status_message, "cached stale")
            self.assertEqual(quarta.matching_row_ids, [])
            self.assertEqual(cache.rows, [])
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)

    def test_existing_quarta_refresh_still_updates_cached_status(self):
        quarta, incoming = self.material()
        service._refresh_quarta_rows_from_incoming(self.db, rows=[quarta])
        self.assertEqual(quarta.status_color, "green")
        self.assertEqual(quarta.matching_row_ids, [incoming.id])

    def test_reservation_ready_but_rejection_visible(self):
        self.item()
        _, incoming = self.material(evaluation="accettato_con_riserva")
        self.assertEqual(self.read().items[0].state, "ready")
        incoming.qualita_valutazione = "respinto"
        self.db.commit()
        result = self.read()
        self.assertEqual(result.items[0].state, "quality_rejected")
        self.assertEqual(result.active, 1)

    def test_incomplete_reservation_and_unassessed_quality_are_waiting(self):
        self.item()
        _, incoming = self.material(evaluation="accettato_con_riserva", complete=False)
        self.assertEqual(self.read().items[0].state, "waiting_incoming")
        self.confirm_blocks(incoming)
        incoming.qualita_valutazione = None
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "waiting_incoming")

    def test_all_material_rows_required_not_only_one(self):
        self.item()
        self.material()
        self.material(cdq="CDQ2", complete=False)
        self.assertEqual(self.read().items[0].state, "waiting_incoming")

    def test_ai_processing_and_ddt_only_cannot_be_ready(self):
        self.item()
        _, incoming = self.material(processing="in_lavorazione")
        self.assertEqual(self.read().items[0].state, "waiting_incoming")
        incoming.ai_processing_status = None
        incoming.document_certificato_id = None
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "waiting_incoming")

    def test_article_diameter_and_manual_override_follow_existing_rules(self):
        self.item()
        quarta, first = self.material(diameter="285")
        second = AcquisitionRow(cdq=first.cdq, colata=first.colata, diametro="295",
                                 document_certificato_id=self.document.id, qualita_valutazione="accettato")
        self.db.add(second)
        self.db.flush()
        self.confirm_blocks(second)
        self.db.commit()
        self.assertEqual(self.read().items[0].incoming_row_ids, [first.id])
        self.db.add(QuartaTaglioIncomingRowOverride(cod_odp="OL1", cdq=first.cdq, colata=first.colata,
                                                    acquisition_row_id=second.id))
        self.db.commit()
        self.assertEqual(self.read().items[0].incoming_row_ids, [second.id])

    def test_285_and_85_remain_ambiguous(self):
        self.item()
        _, incoming = self.material(diameter="285")
        self.db.add(AcquisitionRow(cdq=incoming.cdq, colata=incoming.colata, diametro="85",
                                  document_certificato_id=self.document.id, qualita_valutazione="accettato"))
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")

    def test_old_quarta_rows_are_used_only_when_no_current_rows(self):
        self.item()
        self.material(current=False)
        self.assertEqual(self.read().items[0].state, "ready")
        self.material(cdq="CDQ2", complete=False)
        self.assertEqual(self.read().items[0].state, "waiting_incoming")

    def test_word_draft_never_completes_queue(self):
        item = self.item()
        self.material()
        cert = self.cert(item)
        result = self.read()
        self.assertEqual((result.active, result.items[0].state), (1, "word_ready"))
        self.assertEqual(result.items[0].word_candidate_id, cert.id)

    def test_word_and_incomplete_incoming_remain_waiting(self):
        item = self.item()
        self.material(complete=False)
        cert = self.cert(item)
        result = self.read().items[0]
        self.assertEqual(result.state, "waiting_incoming")
        self.assertEqual(result.word_candidate_id, cert.id)

    def test_exact_pdf_closes_only_its_unit_not_sibling_ddt_ol_line_or_lot(self):
        item = self.item()
        self.cert(item, pdf=True)
        for changes in ({"ORP": "OL2"}, {"IdDocumento": "101"}, {"IdRigaDoc": "2"}, {"RifLottoAlfanum": "lot-b"}):
            self.item(**changes)
        result = self.read()
        self.assertEqual((result.total, result.active, result.total_items), (5, 4, 4))
        self.assertNotIn(item.id, [row.id for row in result.items])
        history = self.read(scope="completed")
        self.assertEqual([row.id for row in history.items], [item.id])

    def test_reopened_pdf_returns_to_active_queue_immediately(self):
        item = self.item()
        self.material()
        cert = self.cert(item, pdf=True)
        self.assertEqual(self.read().active, 0)
        cert.status = "draft"
        cert.storage_key_pdf = None
        self.db.scalar(select(QuartaTaglioCertificatePdfVersion)).status = "reopened"
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "word_ready")

    def test_annulled_version_missing_file_or_missing_version_cannot_complete(self):
        item = self.item()
        cert = self.cert(item, pdf=True, active=False)
        self.assertEqual(self.read().items[0].state, "review")
        version = self.db.scalar(select(QuartaTaglioCertificatePdfVersion))
        version.status = "active"
        version.annulled_at = None
        self.db.commit()
        Path(self.files.name, cert.storage_key_pdf).unlink()
        self.assertEqual(self.read().items[0].state, "review")
        self.db.delete(version)
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")

    def test_legacy_pdf_and_wrong_identity_never_close_by_ol_or_key_alone(self):
        item = self.item()
        cert = self.cert(item, pdf=True, esolver_id_documento=None, esolver_id_riga_doc=None, unit_key=None)
        self.assertEqual(self.read().items[0].state, "review")
        cert.unit_key = item.certification_unit_key
        cert.esolver_id_documento = "WRONG"
        self.db.commit()
        self.assertEqual(self.read().active, 1)

    def test_changed_quantity_after_final_pdf_requires_review(self):
        item = self.item()
        self.cert(item, pdf=True)
        item.quantita = Decimal("43")
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")

    def test_quantity_float_rounding_tolerated_but_nonfinite_never_matches(self):
        item = SimpleNamespace(quantita=Decimal("0.3"))
        self.assertTrue(queue._quantity_matches(item, SimpleNamespace(quantita=0.1 + 0.2)))
        self.assertFalse(queue._quantity_matches(item, SimpleNamespace(quantita=float("nan"))))
        self.assertFalse(queue._quantity_matches(item, SimpleNamespace(quantita=float("inf"))))

    def test_changed_ddt_f3_or_order_keeps_closed_pdf_unchanged_and_flags_review(self):
        item = self.item()
        cert = self.cert(item, pdf=True)
        original_key = cert.unit_key
        item.ddt_raw = "changed"
        item.certification_unit_key = "changed-key"
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")
        self.assertEqual(cert.unit_key, original_key)
        self.assertEqual(cert.status, "pdf_final")

    def test_unit_key_collision_does_not_close_different_identifiers(self):
        first = self.item(IdDocumento="a|b", IdRigaDoc="c")
        second = self.item(IdDocumento="a", IdRigaDoc="b|c")
        self.assertEqual(first.certification_unit_key, second.certification_unit_key)
        self.cert(first, pdf=True)
        result = self.read()
        self.assertEqual([item.id for item in result.items], [second.id])

    def test_duplicate_exact_certificates_require_review(self):
        item = self.item()
        self.cert(item, pdf=True)
        self.cert(item)
        self.assertEqual(self.read().items[0].state, "review")

    def test_wrong_version_file_and_invalid_storage_path_do_not_complete(self):
        item = self.item()
        cert = self.cert(item, pdf=True)
        version = self.db.scalar(select(QuartaTaglioCertificatePdfVersion))
        version.storage_key_pdf = "different.pdf"
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")
        cert.storage_key_pdf = "../outside.pdf"
        version.storage_key_pdf = cert.storage_key_pdf
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")

    def test_source_identity_review_cannot_be_hidden_by_ready_incoming(self):
        item = self.item()
        self.material()
        item.source_review_reason = "source_identity_changed"
        self.db.commit()
        self.assertEqual(self.read().items[0].state, "review")

    def test_incomplete_source_fields_do_not_become_ready(self):
        self.item(CodF3=None)
        self.material()
        self.assertEqual(self.read().items[0].state, "review")

    def test_reading_again_does_not_mark_seen_or_complete(self):
        self.item()
        first = self.read()
        self.assertEqual(self.read().model_dump(), first.model_dump())

    def test_source_disappears_but_stays_active_and_pdf_can_still_complete_it(self):
        item = self.item(DDT="1-01/01/2026")
        item.source_present = False
        item.source_disappeared_at = NOW
        self.db.commit()
        result = self.read().items[0]
        self.assertIn("riga conservata", " ".join(result.reasons))
        self.cert(item, pdf=True)
        self.assertEqual(self.read().active, 0)

    def test_esolver_certificate_flag_has_no_effect(self):
        self.item(CertificatoPresente=1)
        self.assertEqual(self.read().active, 1)

    def test_early_word_is_only_a_candidate_and_does_not_get_reassigned(self):
        item = self.item()
        self.material()
        cert = self.cert(item, ddt=None, esolver_id_documento=None, esolver_id_riga_doc=None,
                         esolver_rif_lotto_alfanum=None, unit_key="OL1|001230|-|-|-")
        result = self.read().items[0]
        self.assertEqual(result.state, "word_ready")
        self.assertIsNone(result.certificate_id)
        self.assertEqual(result.word_candidate_id, cert.id)
        self.assertIsNone(cert.ddt)

    def test_early_word_ambiguity_unchanged_by_filter_or_page_size(self):
        item = self.item()
        self.material()
        self.cert(item, ddt=None, esolver_id_documento=None, esolver_id_riga_doc=None,
                  esolver_rif_lotto_alfanum=None, unit_key="early")
        self.item(IdDocumento="200", DDT="88-02/09/2026")
        self.assertEqual({item.state for item in self.read().items}, {"review"})
        self.assertEqual(self.read(ddt="77", limit=1).items[0].state, "review")

    def test_multiple_early_words_never_choose_first(self):
        item = self.item()
        self.material()
        for index in range(2):
            self.cert(item, ddt=None, esolver_id_documento=None, esolver_id_riga_doc=None,
                      esolver_rif_lotto_alfanum=None, unit_key=f"early-{index}")
        self.assertEqual(self.read().items[0].state, "review")

    def test_read_filters_counters_pagination_and_order_agree(self):
        item = self.item()
        self.cert(item, pdf=True)
        self.item(IdDocumento="2", DDT="88-02/09/2026")
        self.item(IdDocumento="3", DDT="99-03/09/2026", RagSoc="Other")
        self.item(IdDocumento="4", DDT="without date")
        response = self.read(cliente="cliente", limit=1)
        self.assertEqual((response.total, response.active, response.total_items), (3, 2, 2))
        self.assertEqual(response.items[0].id_documento, "2")
        self.assertEqual(self.read(cliente="cliente", limit=1, offset=1).items[0].id_documento, "4")
        self.assertEqual(self.read(cliente="cliente", counters_only=True).by_state, response.by_state)
        self.assertEqual(self.read(date_from=date(2026, 9, 2), date_to=date(2026, 9, 2)).total, 1)
        self.assertEqual(self.read(query="OTHER").total, 1)
        self.assertEqual(self.read(ddt="%_").total, 0)
        self.assertEqual(self.read(state="completed", scope="all").total_items, 1)
        self.assertEqual(self.read(offset=100).total_items, 3)

    def test_more_than_500_rows_paginate_after_derivation_not_before(self):
        for index in range(510):
            self.item(IdDocumento=str(index), ORP=None)
        result = self.read(limit=50, offset=500)
        self.assertEqual((result.total_items, result.active, len(result.items)), (510, 510, 10))

    def test_last_attempt_and_last_success_remain_distinct(self):
        self.item()
        self.db.add(QuartaTaglioDdtSyncRun(status="success", started_at=NOW - timedelta(hours=2), finished_at=NOW))
        self.db.add(QuartaTaglioDdtSyncRun(status="error", started_at=NOW, finished_at=NOW, error_code="source_read_failed"))
        self.db.commit()
        result = self.read()
        self.assertEqual(result.sync.last_attempt.status, "error")
        self.assertEqual(result.sync.last_success.status, "success")
        self.assertEqual(result.active, 1)

    def test_api_authorization_validation_static_routes_and_no_secret_fields(self):
        self.item()
        app = FastAPI()
        app.include_router(router, prefix="/api/quarta-taglio")
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        path = "/api/quarta-taglio/ddt-work-items"
        self.assertEqual(client.get(path).status_code, 401)
        user = SimpleNamespace(role="operator", department=SimpleNamespace(name="Produzione"))
        app.dependency_overrides[get_current_user] = lambda: user
        self.assertEqual(client.get(path).status_code, 403)
        user.department.name = "Qualità"
        self.assertEqual(client.get(path).status_code, 200)
        self.assertEqual(client.get(path + "/counters").status_code, 200)
        for department in ("IT", "Laboratorio"):
            user.department.name = department
            self.assertEqual(client.get(path).status_code, 200)
        for params in ({"state": "wrong"}, {"scope": "wrong"}, {"limit": 201}, {"offset": -1},
                       {"date_from": "2026-09-03", "date_to": "2026-09-01"}):
            self.assertEqual(client.get(path, params=params).status_code, 422)
        payload = client.get(path).text
        for secret in ("storage_key", "download_token", "password", "encrypted"):
            self.assertNotIn(secret, payload)
        self.assertNotIn("items", client.get(path + "/counters").json())


if __name__ == "__main__":
    unittest.main()
