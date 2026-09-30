"""Decisions on disposable data: permissions, source updates, counts and rollback."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.deps import get_current_user, get_db
from app.core.departments.models import Department
from app.core.users.models import User
from app.modules.quarta_taglio import ddt_decisions as decisions, ddt_snapshot as snapshot
from app.modules.quarta_taglio.ddt_schemas import DdtDecisionRequest
from app.modules.quarta_taglio.models import QuartaTaglioDdtDecision, QuartaTaglioDdtWorkItem
from app.modules.quarta_taglio.router import router
from test_quarta_taglio_ddt_queue import DdtQueueFixture, NOW


class DdtDecisionTest(DdtQueueFixture):
    def setUp(self):
        super().setUp()
        department = Department(name="Qualità", description="Test")
        self.db.add(department)
        self.db.flush()
        self.user = User(name="Admin Qualità test", email="decision@example.test", role="admin", department_id=department.id)
        self.db.add(self.user)
        self.db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api/quarta-taglio")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.app, self.client = app, TestClient(app)

    def payload(self, item, action="exclude", reason="Cliente non richiede certificato"):
        previous = decisions.latest_decisions(self.db, [item.id]).get(item.id)
        return DdtDecisionRequest(action=action, reason=reason,
                                  expected_decision_id=previous.id if previous else 0,
                                  source_revision=decisions.source_revision(item))

    def decide(self, item, action="exclude", reason="Cliente non richiede certificato"):
        return decisions.change_decision(self.db, item.id, self.payload(item, action, reason), self.user)

    def post(self, item, payload):
        return self.client.post(f"/api/quarta-taglio/ddt-work-items/{item.id}/decisions", json=payload.model_dump())

    def raw(self, item, **changes):
        result = dict(IdDocumento=item.id_documento, IdRigaDoc=item.id_riga_doc, RifLottoAlfanum=item.rif_lotto_alfanum,
                      ORP=item.cod_odp, CodF3=item.cod_f3, DDT=item.ddt_raw, RagSoc=item.cliente,
                      ODVCli=item.ordine_cliente, ODVF3=item.conferma_ordine, QtaUmMag=item.quantita, CertificatoPresente=0)
        result.update(changes)
        return result

    def sync(self, rows):
        snapshot._apply_snapshot(self.db, rows, now=NOW + timedelta(hours=1))
        self.db.commit()

    def test_exclude_one_share_restore_and_history_across_sessions(self):
        item = self.item()
        sibling = self.item(IdRigaDoc="2")
        self.material()
        first = self.decide(item)
        self.db.expire_all()
        result = self.read()
        self.assertEqual((result.total, result.active, result.by_state["excluded"]), (2, 1, 1))
        self.assertEqual([x.id for x in result.items], [sibling.id])
        self.assertEqual(self.read(counters_only=True).active, 1)
        excluded = self.read(scope="excluded").items[0]
        self.assertEqual(excluded.latest_decision.actor_name, self.user.name)
        self.assertEqual(excluded.state, "excluded")
        self.assertEqual(self.read(scope="completed").total_items, 0)
        self.assertEqual(self.read(scope="all").total_items, 2)
        second = self.decide(item, "restore", "Il cliente ha richiesto il certificato")
        self.assertEqual(self.read().active, 2)
        self.assertEqual(self.read(scope="excluded").total_items, 0)
        history = self.client.get(f"/api/quarta-taglio/ddt-work-items/{item.id}/decisions").json()
        self.assertEqual([e["id"] for e in history], [second["id"], first["id"]])
        self.assertEqual([e["action"] for e in history], ["restore", "exclude"])
        self.assertNotIn("source_facts", history[0])

    def test_only_quality_admin_can_write_backend_not_just_ui(self):
        item = self.item()
        payload = self.payload(item)
        for department, role in [("IT", "admin"), ("Qualità", "manager"), ("Qualità", "user"),
                                 ("Laboratorio", "admin"), ("Produzione", "admin")]:
            user = SimpleNamespace(id=self.user.id, name="Test", role=role, department=SimpleNamespace(name=department))
            self.app.dependency_overrides[get_current_user] = lambda: user
            self.assertEqual(self.post(item, payload).status_code, 403, (department, role))
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.assertEqual(self.post(item, payload).status_code, 200)

    def test_reason_required_and_stale_double_submit_rejected(self):
        item = self.item()
        payload = self.payload(item)
        path = f"/api/quarta-taglio/ddt-work-items/{item.id}/decisions"
        for reason in ["", "   ", "x" * 2001]:
            self.assertEqual(self.client.post(path, json={**payload.model_dump(), "reason": reason}).status_code, 422)
        self.assertEqual(self.post(item, payload).status_code, 200)
        self.assertEqual(self.post(item, payload).status_code, 409)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtDecision)))), 1)

    def test_changed_source_while_dialog_open_rejected(self):
        item = self.item()
        payload = self.payload(item)
        self.sync([self.raw(item, QtaUmMag=43)])
        self.assertEqual(self.post(item, payload).status_code, 409)
        self.assertEqual(self.read().active, 1)

    def test_completed_pdf_wins_and_restore_does_not_reopen_completed(self):
        item = self.item()
        self.decide(item)
        self.cert(item, pdf=True)
        self.assertEqual(self.read(scope="completed").total_items, 1)
        self.assertEqual(self.read().active, 0)
        self.assertEqual(self.read(scope="excluded").total_items, 0)
        self.decide(item, "restore", "Rettifica decisione precedente")
        self.assertEqual(self.read().active, 0)
        self.assertEqual(self.post(item, self.payload(item)).status_code, 409)

    def test_exclusion_preserves_rejected_incoming_and_existing_word(self):
        item = self.item()
        _, incoming = self.material(evaluation="respinto")
        cert = self.cert(item)
        before = (incoming.qualita_valutazione, cert.status, cert.storage_key_docx)
        self.assertEqual(self.read().items[0].state, "quality_rejected")
        self.decide(item)
        row = self.read(scope="excluded").items[0]
        self.assertEqual(row.operational_state, "quality_rejected")
        self.assertEqual((incoming.qualita_valutazione, cert.status, cert.storage_key_docx), before)
        self.decide(item, "restore", "Da riesaminare")
        self.assertEqual(self.read().items[0].state, "quality_rejected")

    def test_source_changes_reopen_and_reversion_does_not_reexclude(self):
        for field, value in [("QtaUmMag", 43), ("CodF3", "NEW"), ("DDT", "78-02/09/2026"),
                             ("ODVCli", "NEW"), ("RagSoc", "NEW")]:
            with self.subTest(field=field):
                item = self.item(IdDocumento=field)
                self.decide(item)
                original = self.raw(item)
                self.sync([{**original, field: value}])
                row = next(x for x in self.read(scope="all").items if x.id == item.id)
                self.assertEqual(row.state, "review")
                self.assertEqual(row.latest_decision.action, "review")
                self.sync([original])
                row = next(x for x in self.read(scope="all").items if x.id == item.id)
                self.assertEqual(row.state, "review")
                self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtDecision).where(
                    QuartaTaglioDdtDecision.work_item_id == item.id)))), 2)
                self.decide(item, "restore", "Dati ricontrollati, da certificare")
                row = next(x for x in self.read().items if x.id == item.id)
                self.assertNotIn(row.state, {"excluded", "review"})

    def test_normal_sync_and_leaving_source_keep_exclusion(self):
        item = self.item()
        other = self.item(IdDocumento="2")
        self.decide(item)
        self.sync([self.raw(item), self.raw(other)])
        self.sync([self.raw(other)])
        self.assertFalse(item.source_present)
        self.assertEqual(self.read(scope="excluded").total_items, 1)
        self.sync([self.raw(item), self.raw(other)])
        self.assertEqual(self.read(scope="excluded").total_items, 1)

    def test_missing_ol_promoted_and_identity_change_require_review(self):
        item = self.item(ORP=None)
        self.decide(item)
        self.sync([self.raw(item, ORP="OL1")])
        self.assertEqual(self.read().items[0].state, "review")
        self.decide(item)
        self.sync([self.raw(item, ORP="OL2")])
        self.assertEqual(self.read().active, 2)
        self.assertEqual({x.state for x in self.read().items}, {"review"})

    def test_failed_commit_rolls_back_decision(self):
        item = self.item()
        with patch.object(self.db, "commit", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                self.decide(item)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtDecision)))), 0)
        self.assertEqual(self.read().active, 1)

    def test_failed_sync_rolls_back_source_and_automatic_review(self):
        item = self.item()
        self.decide(item)
        original_quantity = item.quantita
        try:
            snapshot._apply_snapshot(self.db, [self.raw(item, QtaUmMag=99)], now=NOW)
            raise RuntimeError("test failure after invalidation")
        except RuntimeError:
            self.db.rollback()
        self.assertEqual(item.quantita, original_quantity)
        self.assertEqual(self.read(scope="excluded").total_items, 1)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtDecision)))), 1)

    def test_read_only_and_filtered_counts_do_not_write_decisions(self):
        item = self.item(RagSoc="A")
        self.item(IdDocumento="2", RagSoc="B")
        self.decide(item)
        count = len(list(self.db.scalars(select(QuartaTaglioDdtDecision))))
        self.assertEqual(self.read(cliente="A", counters_only=True).active, 0)
        self.assertEqual(self.read(cliente="B", counters_only=True).active, 1)
        self.read(scope="all", sort_field="state", limit=1)
        self.assertFalse(self.db.dirty)
        self.assertFalse(self.db.new)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtDecision)))), count)
