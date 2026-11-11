"""Real acquisition service and isolated DB: never touch app data or call AI."""
import json
import os
import unittest
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.modules.acquisition import service as s
from app.modules.acquisition.models import (
    AcquisitionRow, AutonomousProcessingRun, Document, DocumentEvidence, DocumentPage,
    ReadValue, ManualMatchBlock, DocumentAiUsage,
)
from app.modules.suppliers.models import Supplier


class GroupWorkflowTest(unittest.TestCase):
    def make_engine(self):
        return create_engine("sqlite:///:memory:")

    def setUp(self):
        self.engine = self.make_engine()
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.supplier = Supplier(ragione_sociale="Leichtmetall Aluminium Giesserei Hannover GmbH")
        self.run = AutonomousProcessingRun(ddt_document_ids="[]", certificate_document_ids="[]")
        self.db.add_all([self.supplier, self.run]); self.db.commit()
        self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = self.run.id

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def doc(self, side):
        d = Document(tipo_documento=side, fornitore_id=self.supplier.id,
            nome_file_originale="not-an-identity.pdf", storage_key=uuid4().hex,
            hash_file=uuid4().hex, numero_pagine=2 if side=="ddt" else 1)
        self.db.add(d); self.db.flush()
        for i in range(1, d.numero_pagine+1):
            self.db.add(DocumentPage(document_id=d.id, numero_pagina=i, testo_estratto=""))
        self.db.commit()
        return d

    def row(self, doc, *, batch="95131", weight="3962", identity="95131.33", total="5047",
            alloy="7175", diameter="150", order="332.2+3"):
        ddt = doc.tipo_documento == "ddt"
        r = AcquisitionRow(fornitore_id=self.supplier.id, fornitore_raw=self.supplier.ragione_sociale,
            document_ddt_id=doc.id if ddt else None, document_certificato_id=None if ddt else doc.id,
            colata=batch if ddt else identity, cdq=batch if ddt else identity,
            peso=weight if ddt else total, lega_base=alloy, diametro=diameter, ordine=order,
            ddt="80011293" if ddt else None, ai_processing_status="pronta", ai_processing_run_id=self.run.id)
        self.db.add(r); self.db.flush()
        fields = {"colata":batch, "cdq":batch, "peso":weight, "lega":alloy,
                  "diametro":diameter, "ordine":order, "ddt":"80011293"} if ddt else {
                  "colata_certificato":identity, "numero_certificato_certificato":identity,
                  "peso_certificato":total, "lega_certificato":alloy,
                  "diametro_certificato":diameter, "ordine_cliente_certificato":order}
        for field, value in fields.items():
            self.db.add(ReadValue(acquisition_row_id=r.id, blocco="ddt" if ddt else "match",
                campo=field, valore_grezzo=value, valore_finale=value, valore_standardizzato=value,
                stato="proposto", metodo_lettura="chatgpt", fonte_documentale=doc.tipo_documento))
        self.db.flush(); self.db.expire(r, ["values"])
        if ddt:
            s._mark_ddt_group_complete(self.db, r, s._autonomous_ddt_row_signature(r), None)
        self.db.commit()
        return s.get_acquisition_row(self.db, r.id)

    def pair(self, *, three=False, first_certificate=False):
        cert = self.doc("certificato")
        identity = "95131.33.35" if three else "95131.33"
        total = "5547" if three else "5047"
        source = self.row(cert, identity=identity, total=total) if first_certificate else None
        ddt = self.doc("ddt")
        rows = [self.row(ddt), self.row(ddt, batch="95133", weight="1085")]
        if three:
            rows.append(self.row(ddt, batch="95135", weight="500"))
        source = source or self.row(cert, identity=identity, total=total)
        return rows, source

    def finish(self):
        with patch.object(s, "_create_openai_response", side_effect=AssertionError("AI forbidden")):
            protected = s._current_run_rematch_protected_ids(self.db, self.run.id, set())
            result = s._run_cross_run_auto_rematch(db=self.db, supplier_ids={self.supplier.id},
                actor_id=None, run_id=self.run.id, protected_row_ids=protected,
                protected_source_row_ids=set())
        assert self.db.query(DocumentAiUsage).count() == 0
        return result

    def check_arrival(self, first=False, three=False):
        rows, source = self.pair(three=three, first_certificate=first)
        cert_id = source.document_certificato_id
        count_before = self.db.query(AcquisitionRow).count()
        self.assertEqual(self.finish(), len(rows))
        self.assertEqual(self.db.query(AcquisitionRow).count(), count_before-1)
        for row in rows:
            r = s.get_acquisition_row(self.db, row.id)
            self.assertEqual(r.document_certificato_id, cert_id)
            self.assertEqual(r.colata, "95131.33.35" if three else "95131.33")
            self.assertEqual(r.cdq, r.colata)
            self.assertEqual(s._row_read_values(r, "ddt")["colata"],
                {"3962":"95131", "1085":"95133", "500":"95135"}[r.peso])
            self.assertEqual(s._row_read_values(r, "match")["peso_certificato"],
                "5547" if three else "5047")
        self.assertEqual(self.finish(), 0)

    def test_ddt_first_two(self):
        self.check_arrival()

    def test_certificate_first_two(self):
        self.check_arrival(first=True)

    def test_ddt_first_three(self):
        self.check_arrival(three=True)

    def test_certificate_first_three(self):
        self.check_arrival(first=True, three=True)

    def test_missing_member_bad_weight_duplicate_certificate_never_force(self):
        rows, source = self.pair()
        s._delete_evidence_records(self.db, self.db.query(DocumentEvidence).filter(
            DocumentEvidence.acquisition_row_id == rows[1].id).all())
        self.db.delete(rows[1]); self.db.commit()
        self.assertEqual(self.finish(), 0)

    def test_manual_detach_blocks_and_intentional_correction_survive(self):
        rows, source = self.pair()
        self.db.add(ManualMatchBlock(document_ddt_id=rows[0].document_ddt_id,
            document_certificato_id=source.document_certificato_id, source_row_id=rows[0].id, attivo=True))
        self.db.commit()
        self.assertEqual(self.finish(), 1)
        self.assertIsNone(s.get_acquisition_row(self.db, rows[0].id).document_certificato_id)
        r = s.get_acquisition_row(self.db, rows[1].id)
        v = next(v for v in r.values if v.blocco=="ddt" and v.campo=="colata")
        v.valore_finale="99999"; v.metodo_lettura="utente"; self.db.commit()
        self.assertNotEqual(s._leichtmetall_link_score(r).decision, s.RematchDecision.STRONG)
        self.assertEqual(v.valore_finale, "99999")

    def test_two_equivalent_certificates_are_not_chosen(self):
        rows, source = self.pair()
        self.row(self.doc("certificato"))
        self.assertEqual(self.finish(), 0)

    def test_sync_keeps_source_lots_and_certificate_total(self):
        rows, source = self.pair()
        self.assertEqual(self.finish(), 2)
        r = s.get_acquisition_row(self.db, rows[1].id)
        s._sync_ddt_values_from_row_fields(self.db, r, actor_id=None)
        s._sync_match_values_from_row_fields(self.db, r, actor_id=None,
            touched_fields={"peso", "colata", "cdq", "diametro"})
        self.db.commit(); self.db.expire_all()
        r = s.get_acquisition_row(self.db, r.id)
        self.assertEqual(s._row_read_values(r, "ddt")["colata"], "95133")
        self.assertEqual(s._row_read_values(r, "match")["peso_certificato"], "5047")
        self.assertEqual(r.peso, "1085")
        self.assertEqual(r.colata, "95131.33")

    def test_confirmation_accepts_verified_membership_not_literal_equality(self):
        rows, source = self.pair()
        self.assertEqual(self.finish(), 2)
        for row in rows:
            r = s.get_acquisition_row(self.db, row.id)
            for v in r.values:
                v.stato = "confermato"
            self.db.commit()
            self.assertEqual(s._document_side_field_conflicts(self.db, row=r), [])
            s._confirm_match_if_document_sides_are_ready(db=self.db, row=r, actor_id=None)
            self.db.commit()
            self.assertEqual(s.get_acquisition_row(self.db, r.id).certificate_match.stato, "confermato")

    def test_quarta_requires_all_lots_not_first_or_same_ol_weight(self):
        from app.modules.quarta_taglio import service as q
        rows, source = self.pair()
        self.assertEqual(self.finish(), 2)
        rows = [s.get_acquisition_row(self.db, r.id) for r in rows]
        selected, reason = q._effective_incoming_rows_for_quarta_material(self.db,
            cod_odp="OL2026001353", cdq="95131.33", colata="95131.33", qta_totale=1085,
            exact_rows=rows, article_code="A751500")
        self.assertIsNone(reason)
        self.assertEqual({r.id for r in selected}, {r.id for r in rows})
        rows[1].qualita_valutazione = "respinto"; self.db.commit()
        color, message, details, ids = q._evaluate_cdq(db=self.db, cod_odp="OL2026001353",
            cdq="95131.33", colata="95131.33", qta_totale=1085, rows_by_cdq={"95131.33":rows})
        self.assertEqual(color, "red")
        self.assertIn(rows[1].id, ids)
        # A missing member must not fall back to an arbitrary surviving row.
        self.db.delete(rows[1]); self.db.commit()
        _, reason = q._effective_incoming_rows_for_quarta_material(self.db,
            cod_odp="OL2026001353", cdq="95131.33", colata="95131.33", qta_totale=3962,
            exact_rows=[rows[0]])
        self.assertIsNotNone(reason)

    def test_initial_supplier_scorer_uses_same_proof(self):
        rows, source = self.pair()
        source_id, doc = source.id, source.certificate_document
        values = s._row_read_values(source, "match")
        cache = {doc.id:dict(match_values=values, supplier_fields={"po_no":"332.2+3"})}
        for r in rows:
            result = s._score_certificate_candidate(self.db, row=r, certificate_document=doc,
                ddt_certificate_number=r.cdq, row_ddt_values=s._row_read_values(r, "ddt"),
                certificate_ai_cache=cache, ai_only_mode=True)
            self.assertTrue(result and result["leichtmetall_group"])
        cache[doc.id]["match_values"]["diametro_certificato"] = "144"
        self.assertIsNone(s._score_certificate_candidate(self.db, row=rows[0], certificate_document=doc,
            ddt_certificate_number=rows[0].cdq, row_ddt_values=s._row_read_values(rows[0], "ddt"),
            certificate_ai_cache=cache, ai_only_mode=True))

    def test_refresh_does_not_put_displayed_compound_into_raw_ddt(self):
        rows, _ = self.pair(); self.assertEqual(self.finish(), 2)
        r = s.get_acquisition_row(self.db, rows[1].id)
        with patch.object(s, "extract_core_fields"), patch.object(s, "_process_certificate_side_blocks",
                side_effect=lambda **kw:kw["row"]):
            s.refresh_certificate_first_row(self.db, row=r, actor_id=None)
        r = s.get_acquisition_row(self.db, r.id)
        self.assertEqual(s._row_read_values(r, "ddt")["colata"], "95133")
        self.assertEqual(s._row_read_values(r, "match")["peso_certificato"], "5047")

    def check_creation_pipeline(self, certificate_first=False, same_run=False, ddt_only=False):
        from app.modules.document_reader.schemas import ReaderRowSplitCandidateResponse as C
        cert, ddt = self.doc("certificato"), self.doc("ddt")
        payload=s._normalize_leichtmetall_certificate_ai_payload({"page1":dict(page_id=cert.pages[0].id,
            page_number=1)}, {"core":dict(charge_cast_no="95131.33", po_no="332.2+3",
            alloy_raw="7175", diameter_raw="150", weight_raw="5047")})
        cache={cert.id:payload}
        candidates=[C(candidate_index=i,supplier_key="leichtmetall",ddt_number="80011293",
            customer_order_no="332, 2 + 3",colata=batch,cdq=batch,lega="7175",diametro="150.00",peso_netto=w)
            for i,(batch,w) in enumerate((("95131","3962"),("95133","1085")),1)]
        def process(**kw):
            r=kw["row"]
            for field,value in payload["match_values"].items():
                if value:
                    s._upsert_read_value_model(db=self.db,acquisition_row_id=r.id,blocco="match",campo=field,
                        valore_grezzo=value,valore_standardizzato=value,valore_finale=value,stato="proposto",
                        document_evidence_id=None,metodo_lettura="chatgpt",fonte_documentale="certificato",
                        confidenza=.9,actor_id=None)
            s._sync_row_from_match_values(self.db,r);self.db.commit()
            return s.get_acquisition_row(self.db,r.id)
        def ensure_cert():
            return s._ensure_certificate_first_rows(self.db,certificate_documents=[cert],actor_id=None,
                actor_email="qa@example.invalid",openai_api_key="unused",use_ai_intervention=True,
                run_id=self.run.id,certificate_ai_cache=cache)
        with patch.object(s,"_create_openai_response",side_effect=AssertionError("AI forbidden")), \
             patch.object(s,"prepare_document_for_reader",side_effect=lambda db,doc:doc), \
             patch.object(s,"_ensure_document_page_images",side_effect=lambda db,doc:doc), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates), \
             patch.object(s,"_get_supplier_certificate_ai_payload",return_value=payload), \
             patch.object(s,"_process_certificate_side_blocks",side_effect=process), \
             patch.object(s.log_service,"record"):
            if certificate_first:
                self.assertEqual(ensure_cert()[0],1)
            rows,created=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=ddt,actor_id=None,
                actor_email="qa@example.invalid",openai_api_key="unused",run_id=self.run.id)
            self.assertEqual((len(rows),created),(2,2))
            if ddt_only:
                return ddt, rows
            if same_run:
                for r in rows:
                    matched=s._auto_propose_certificate_match(self.db,row=r,certificate_documents=[cert],
                        actor_id=None,certificate_ai_cache=cache,ai_only_mode=True)
                    if matched:
                        process(row=s.get_acquisition_row(self.db,r.id))
            ensure_cert();self.finish()
        self.db.expire_all()
        final=self.db.query(AcquisitionRow).filter(AcquisitionRow.document_ddt_id==ddt.id).all()
        self.assertEqual(self.db.query(AcquisitionRow).count(),2)
        self.assertEqual({r.colata for r in final},{"95131.33"})
        self.assertEqual({r.peso for r in final},{"3962","1085"})
        self.assertEqual({r.document_certificato_id for r in final},{cert.id})

    def test_real_creation_certificate_then_ddt(self):
        self.check_creation_pipeline(certificate_first=True)

    def test_real_creation_ddt_then_certificate(self):
        self.check_creation_pipeline()

    def test_real_creation_together_initial_scorer_and_rematch(self):
        self.check_creation_pipeline(same_run=True)

    def test_group_does_not_outrank_an_also_valid_individual_certificate(self):
        rows, source = self.pair()
        self.row(self.doc("certificato"), identity="95131", total="3962")
        self.finish()
        self.assertIsNone(s.get_acquisition_row(self.db,rows[0].id).document_certificato_id)

    def test_shared_analysis_not_weighted_twice_against_other_certificates(self):
        from types import SimpleNamespace as NS
        from app.modules.quarta_taglio import service as q
        rows, _ = self.pair(); self.assertEqual(self.finish(),2)
        rows=[s.get_acquisition_row(self.db,r.id) for r in rows]
        other=NS(id=999,evidences=[],document_certificato_id=999)
        result,method=q._aggregate_numeric_values([(rows[0],.1,1000),(rows[1],.1,1000),(other,.3,1000)],
            block="chimica")
        self.assertAlmostEqual(result,.2)
        self.assertEqual(method,"weighted")

    def test_quarta_explicit_individual_cast_uses_only_that_lot(self):
        from app.modules.quarta_taglio import service as q
        rows,_=self.pair();self.assertEqual(self.finish(),2)
        rows=[s.get_acquisition_row(self.db,r.id) for r in rows]
        chosen=q._incoming_rows_for_quarta_cast(rows,"95133")
        self.assertEqual([r.id for r in chosen],[rows[1].id])
        selected,reason=q._effective_incoming_rows_for_quarta_material(self.db,cod_odp="OL_TEST",
            cdq="95131.33",colata="95133",qta_totale=500,exact_rows=chosen)
        self.assertIsNone(reason)
        self.assertEqual([r.id for r in selected],[rows[1].id])

    def test_same_document_two_complete_deliveries_remain_independently_verified(self):
        from app.modules.quarta_taglio import service as q
        rows,_=self.pair();self.assertEqual(self.finish(),2)
        next_ddt=self.doc("ddt")
        rows += [self.row(next_ddt),self.row(next_ddt,batch="95133",weight="1085")]
        self.assertEqual(self.finish(),2)
        rows=[s.get_acquisition_row(self.db,r.id) for r in rows]
        selected,reason=q._effective_incoming_rows_for_quarta_material(self.db,cod_odp="OL_TEST",
            cdq="95131.33",colata="95131.33",qta_totale=500,exact_rows=rows)
        self.assertIsNone(reason)
        self.assertEqual({r.id for r in selected},{r.id for r in rows})
        self.assertEqual(sum(s.leichtmetall_kg(r.peso) for r in rows),10094)

    def test_group_proof_survives_a_fresh_worker_session_without_ai(self):
        rows,_=self.pair();self.assertEqual(self.finish(),2)
        ids=[r.id for r in rows];run_id=self.run.id
        supplier_id=self.supplier.id
        self.db.close()
        self.db=sessionmaker(bind=self.engine,autoflush=False,expire_on_commit=False)()
        self.supplier=self.db.get(Supplier,supplier_id)
        self.run=self.db.get(AutonomousProcessingRun,run_id)
        self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=run_id
        self.assertTrue(s.verified_leichtmetall_group_rows([s.get_acquisition_row(self.db,i) for i in ids]))
        self.assertEqual(self.finish(),0)

    def test_interrupted_merge_rolls_back_and_retry_does_not_duplicate(self):
        rows,source=self.pair();source_id=source.id
        with patch.object(s,"_merge_certificate_only_row_into_ddt_row",side_effect=RuntimeError("save interrupted")):
            with self.assertRaisesRegex(RuntimeError,"save interrupted"):
                self.finish()
        self.db.rollback();self.db.expire_all()
        self.assertIsNotNone(self.db.get(AcquisitionRow,source_id))
        self.assertEqual(self.db.query(AcquisitionRow).count(),3)
        self.assertEqual(self.finish(),2)
        self.assertEqual(self.db.query(AcquisitionRow).count(),2)

    def test_certificate_supplier_must_be_independently_known(self):
        rows,source=self.pair()
        source.certificate_document.fornitore_id=None
        self.db.commit()
        self.assertEqual(self.finish(),0)
        self.assertTrue(all(self.db.get(AcquisitionRow,r.id).document_certificato_id is None for r in rows))

    def test_incoming_list_does_not_add_one_evidence_query_per_row(self):
        ddt=self.doc("ddt")
        for i in range(8):
            self.row(ddt,batch=str(96000+i),weight="100")
        self.db.expunge_all()
        queries=[]
        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT") and "documenti_evidenze" in statement:
                queries.append(statement)
        event.listen(self.engine,"before_cursor_execute",record)
        try:
            with patch.object(s,"_ensure_row_supplier_link"):
                result=s.list_acquisition_rows(self.db)
            self.assertEqual(len(result),8)
            self.assertLessEqual(len(queries),2)
        finally:
            event.remove(self.engine,"before_cursor_execute",record)

    def test_hidden_ddt_certificate_alias_cannot_override_an_intentional_correction(self):
        rows,_=self.pair();self.assertEqual(self.finish(),2)
        r=s.get_acquisition_row(self.db,rows[1].id)
        for v in r.values:
            v.stato="confermato"
        self.db.add(ReadValue(acquisition_row_id=r.id,blocco="ddt",campo="numero_certificato_ddt",
            valore_grezzo="99999",valore_finale="99999",valore_standardizzato="99999",stato="confermato",
            metodo_lettura="utente",fonte_documentale="ddt"))
        self.db.commit();self.db.expire_all()
        self.assertNotEqual(s._leichtmetall_link_score(s.get_acquisition_row(self.db,r.id)).decision,
                            s.RematchDecision.STRONG)

    def test_deliberately_deleted_lot_is_not_recreated_as_an_interrupted_save(self):
        ddt,rows=self.check_creation_pipeline(ddt_only=True)
        deleted_id=rows[0].id
        for row in rows:
            row.ai_processing_status="pronta"
        self.db.commit()
        self.db.expire_all()  # deletion is a new user request, not the worker's identity map
        with patch.object(s,"_delete_storage_keys_after_commit"):
            preview=s.delete_single_document_acquisition_row(self.db,row=rows[0],actor_id=None)
        self.assertFalse(preview.will_delete_document)
        self.assertEqual(self.db.query(DocumentEvidence).filter_by(
            tipo_evidenza="leichtmetall_deleted_ddt_groups_v1").count(),1)
        with patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",side_effect=AssertionError("AI forbidden")):
            current,count=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=ddt,actor_id=None,
                actor_email="qa@example.invalid",openai_api_key="unused",run_id=self.run.id)
        self.assertEqual((len(current),count),(1,0))
        self.assertIsNone(self.db.get(AcquisitionRow,deleted_id))

    def test_different_manual_analyses_are_not_invented_as_one_shared_measurement(self):
        from app.modules.quarta_taglio import service as q
        rows,_=self.pair();self.assertEqual(self.finish(),2)
        for r,value in zip(rows,(".10",".20")):
            self.db.add(ReadValue(acquisition_row_id=r.id,blocco="chimica",campo="Cu",
                valore_grezzo=value,valore_finale=value,valore_standardizzato=value,stato="confermato",
                metodo_lettura="utente",fonte_documentale="certificato"))
        self.db.commit();self.db.expire_all()
        rows=[s.get_acquisition_row(self.db,r.id) for r in rows]
        _,reason=q._effective_incoming_rows_for_quarta_material(self.db,cod_odp="OL_TEST",
            cdq="95131.33",colata="95131.33",qta_totale=500,exact_rows=rows)
        self.assertIsNotNone(reason)
        individual=q._incoming_rows_for_quarta_cast(rows,"95133")
        _,reason=q._effective_incoming_rows_for_quarta_material(self.db,cod_odp="OL_TEST",
            cdq="95131.33",colata="95133",qta_totale=500,exact_rows=individual)
        self.assertIsNone(reason)


@unittest.skipUnless(os.environ.get("CERTI_AI_REUSE_TEST_DATABASE_URL"), "isolated local PostgreSQL opt-in")
class GroupWorkflowPostgresTest(GroupWorkflowTest):
    def make_engine(self):
        url = make_url(os.environ["CERTI_AI_REUSE_TEST_DATABASE_URL"])
        if url.host not in {"127.0.0.1", "localhost"} or url.port != 55439 or url.database != "certi_ai_reuse":
            raise RuntimeError("Refusing anything except disposable local PostgreSQL")
        self.admin = create_engine(url)
        self.schema = "leichtmetall_group_" + uuid4().hex
        with self.admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        engine = create_engine(url, pool_size=8)
        @event.listens_for(engine, "connect")
        def schema(conn, _):
            cur=conn.cursor(); cur.execute(f'SET search_path TO "{self.schema}"')
            conn.commit(); cur.close()
        return engine

    def tearDown(self):
        super().tearDown()
        assert self.schema.startswith("leichtmetall_group_") and len(self.schema) == 51
        with self.admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin.dispose()

    def test_two_workers_group_merge_and_restart_are_idempotent(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        rows, source = self.pair(three=True)
        start = Barrier(2)
        supplier_id, run_id = self.supplier.id, self.run.id
        def worker():
            with sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)() as db:
                db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = run_id
                start.wait(timeout=10)
                return s._run_cross_run_auto_rematch(db=db, supplier_ids={supplier_id}, actor_id=None,
                    run_id=run_id, protected_row_ids=set(), protected_source_row_ids=set())
        with patch.object(s, "_create_openai_response", side_effect=AssertionError("AI forbidden")):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker) for _ in range(2)]
                self.assertEqual(sum(f.result(timeout=45) for f in futures), 3)
        self.db.expire_all()
        self.assertEqual(self.db.query(AcquisitionRow).count(), 3)
        self.assertEqual({r.colata for r in self.db.query(AcquisitionRow)}, {"95131.33.35"})
        self.assertEqual(self.finish(), 0)
