"""Queue PDF action: precise shipment, current readiness, same PDF/export flow."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_current_user
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.ddt_decisions import source_revision
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate, QuartaTaglioDdtDecision
from app.modules.quarta_taglio.router import router
import test_quarta_taglio_ddt_history as history
from test_quarta_taglio_ddt_queue import NOW


class QueuePdfActionTest(history.DdtHistoryTest):
    def prepared(self):
        item = self.item()
        self.material()
        with self.allow_word():
            word = self.create(item)
        return item, self.db.get(QuartaTaglioFinalCertificate, word.id)

    def request(self, item, cert, *, revision=None):
        return service.generate_quarta_taglio_certificate_pdf(
            self.db, certificate_id=cert.id, actor=self.actor,
            pdf_file_name="Cliente prova.pdf", ddt_work_item_id=item.id,
            ddt_source_revision=revision or source_revision(item))

    def exclude(self, item):
        from app.modules.quarta_taglio.ddt_decisions import source_facts
        self.db.add(QuartaTaglioDdtDecision(work_item_id=item.id, action="exclude",
            reason="Non richiesta", actor_name="Test", source_facts=source_facts(item), created_at=NOW))
        self.db.commit()

    def test_action_closes_only_clicked_shipment_and_uses_custom_name(self):
        item, cert = self.prepared()
        sibling = self.item(IdDocumento="101")
        row = next(r for r in self.read().items if r.id == item.id)
        self.assertEqual(row.pdf_action.id, cert.id)
        self.assertEqual(row.pdf_action.ddt, item.ddt_raw)
        def convert(word, pdf):
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(b"%PDF test converter")
        with patch.object(service, "convert_docx_to_pdf", side_effect=convert):
            result = self.request(item, cert)
        self.assertEqual(result.pdf_file_name, "Cliente prova.pdf")
        self.assertEqual([r.id for r in self.read().items], [sibling.id])
        self.assertIsNone(self.read(scope="completed").items[0].pdf_action)

    def test_rejects_other_ddt_old_revision_exclusion_and_missing_conformity(self):
        item, cert = self.prepared()
        other = self.item(IdDocumento="101")
        with patch.object(service, "convert_docx_to_pdf") as convert:
            with self.assertRaises(HTTPException): self.request(other, cert)
            old = source_revision(item)
            item.cliente = "Nome cambiato"
            self.db.commit()
            with self.assertRaises(HTTPException): self.request(item, cert, revision=old)
            cert.conformity_status = "non_conforme"
            self.db.commit()
            self.assertIsNone(next(r for r in self.read().items if r.id == item.id).pdf_action)
            with self.assertRaises(HTTPException): self.request(item, cert)
            cert.conformity_status = "conforme"
            self.db.commit()
            self.exclude(item)
            self.assertIsNone(self.read(scope="excluded").items[0].pdf_action)
            with self.assertRaises(HTTPException): self.request(item, cert)
            convert.assert_not_called()

    def test_missing_file_date_or_quantity_never_offers_action(self):
        item, cert = self.prepared()
        cert.cert_date = None
        self.db.commit()
        self.assertIsNone(self.read().items[0].pdf_action)
        cert.cert_date = NOW
        cert.quantita = 999
        self.db.commit()
        self.assertIsNone(self.read().items[0].pdf_action)
        cert.quantita = float(item.quantita)
        self.db.commit()
        Path(self.files.name, cert.storage_key_docx).unlink()
        self.assertIsNone(self.read().items[0].pdf_action)

    def test_exclusion_during_conversion_prevents_closure(self):
        item, cert = self.prepared()
        def convert(word, pdf):
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(b"%PDF mock")
            self.exclude(item)
        with patch.object(service, "convert_docx_to_pdf", side_effect=convert), self.assertRaises(HTTPException):
            self.request(item, cert)
        self.assertEqual(cert.status, "draft")
        self.assertIsNone(cert.storage_key_pdf)

    def test_route_preserves_authorization_and_rejects_wrong_share(self):
        item, cert = self.prepared()
        other = self.item(IdDocumento="101")
        app = FastAPI()
        app.include_router(router, prefix="/api/quarta-taglio")
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: self.actor
        payload = dict(pdf_file_name="prova.pdf", ddt_work_item_id=other.id, ddt_source_revision=source_revision(other))
        self.assertEqual(client.post(f"/api/quarta-taglio/certificates/{cert.id}/pdf", json=payload).status_code, 409)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(department=SimpleNamespace(name="Laboratorio"))
        self.assertEqual(client.post(f"/api/quarta-taglio/certificates/{cert.id}/pdf", json=payload).status_code, 403)


# Reuse fixture methods without repeating the inherited integration suite.
for _name in dir(history.DdtHistoryTest):
    if _name.startswith('test_'):
        setattr(QueuePdfActionTest, _name, None)
