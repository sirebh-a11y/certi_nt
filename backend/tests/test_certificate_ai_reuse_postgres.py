"""Opt-in PostgreSQL tests, strictly restricted to the disposable local DB."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import threading
import time
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.modules.acquisition.certificate_ai_reuse import reuse_certificate_payload
from app.modules.acquisition.models import Document, DocumentAiExtraction, DocumentPage
from app.modules.suppliers.models import Supplier
from test_certificate_ai_reuse import metalba_raw
from app.modules.acquisition import service as s

URL = os.environ.get('CERTI_AI_REUSE_TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'explicit disposable PostgreSQL URL required')
class CertificateAiReusePostgresTest(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {'127.0.0.1','localhost'} or url.port != 55439 or url.database != 'certi_ai_reuse':
            raise RuntimeError('Refusing to use anything except the disposable local test DB')
        self.admin = create_engine(URL)
        self.schema = 'ai_reuse_'+uuid4().hex
        with self.admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_engine(URL,pool_size=8,max_overflow=0)
        @event.listens_for(self.engine, 'connect')
        def schema(connection, _):
            cursor=connection.cursor()
            cursor.execute(f'SET search_path TO "{self.schema}"')
            connection.commit();cursor.close()
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine,expire_on_commit=False)
        with self.Session() as db:
            supplier=Supplier(ragione_sociale='Metalba S.p.A.')
            db.add(supplier);db.flush()
            doc=Document(tipo_documento='certificato',fornitore_id=supplier.id,
                         nome_file_originale='test.pdf',storage_key='test.pdf',hash_file=hashlib.sha256(b'fixture').hexdigest())
            db.add(doc);db.flush()
            db.add(DocumentPage(document_id=doc.id,numero_pagina=1,testo_estratto='',immagine_pagina_storage_key='unused.png'))
            db.commit();self.doc_id=doc.id

    def tearDown(self):
        self.engine.dispose()
        # The UUID schema was created by this test in the hard-checked local DB.
        if not self.schema.startswith('ai_reuse_') or len(self.schema)!=41:
            raise RuntimeError('Unsafe fixture cleanup target')
        with self.admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin.dispose()

    def reader(self, calls, guard):
        @reuse_certificate_payload('metalba')
        def read(db, *,certificate_document,openai_api_key,certificate_ai_cache=None):
            with guard:calls.append(certificate_document.id)
            time.sleep(.25)
            p=certificate_document.pages[0]
            return s._normalize_metalba_certificate_ai_payload({'page1':{'page_id':p.id,'page_number':1}},metalba_raw())
        return read

    def test_two_sessions_only_one_extraction_and_no_open_transaction_on_lock(self):
        calls=[];guard=threading.Lock();reader=self.reader(calls,guard)
        start=threading.Barrier(2)
        def worker():
            with self.Session() as db:
                doc=db.get(Document,self.doc_id)
                start.wait(timeout=5)
                return reader(db,certificate_document=doc,openai_api_key='unused',certificate_ai_cache={})
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=list(pool.map(lambda _:worker(),range(2)))
        self.assertEqual(calls,[self.doc_id])
        self.assertEqual(a['match_values'],b['match_values'])
        with self.Session() as db:
            self.assertEqual(db.query(DocumentAiExtraction).count(),1)

    def test_reading_persists_but_unrelated_edit_is_not_committed(self):
        reader=self.reader([],threading.Lock())
        with self.Session() as db:
            doc=db.get(Document,self.doc_id)
            doc.nome_file_originale='UNCOMMITTED_EDIT.pdf'
            db.flush()
            reader(db,certificate_document=doc,openai_api_key='unused')
            db.rollback()
        with self.Session() as db:
            self.assertEqual(db.get(Document,self.doc_id).nome_file_originale,'test.pdf')
            self.assertEqual(db.query(DocumentAiExtraction).count(),1)

    def test_single_business_connection_does_not_starve_lock_or_writer(self):
        self.engine.dispose()
        self.engine=create_engine(URL,pool_size=1,max_overflow=0,pool_timeout=1,
                                  connect_args={'options':f'-csearch_path={self.schema}'})
        self.Session=sessionmaker(bind=self.engine,expire_on_commit=False)
        reader=self.reader([],threading.Lock())
        with self.Session() as db:
            doc=db.get(Document,self.doc_id)
            result=reader(db,certificate_document=doc,openai_api_key='unused')
            self.assertEqual(result['match_values']['numero_certificato_certificato'],'26-1791')

    def test_prepare_preview_apply_and_changed_source_refusal(self):
        from scripts.prepare_certificate_ai_reuse import preview,apply,source_digest
        from app.modules.acquisition.models import DocumentEvidence
        import json
        with self.Session() as db:
            doc=db.get(Document,self.doc_id)
            db.add(DocumentEvidence(document_id=doc.id,document_page_id=doc.pages[0].id,blocco='match',
                tipo_evidenza='ai_payload',metodo_estrazione='chatgpt',testo_grezzo=json.dumps(metalba_raw())))
            db.commit()
            # Simulate the real old Alpha schema: the new tables do not exist.
            DocumentAiExtraction.__table__.drop(db.connection())
            from app.modules.acquisition.models import DocumentAiUsage
            DocumentAiUsage.__table__.drop(db.connection())
            db.commit()
            before=preview(db)
            self.assertFalse(before['schema_present'])
            db.rollback()
            result=apply(db,before['digest'])
            self.assertTrue(result['business_data_unchanged'])
            self.assertEqual(source_digest(db),before['digest'])
            self.assertEqual(db.query(DocumentAiExtraction).count(),1)
            db.rollback()
            doc=db.get(Document,self.doc_id);doc.nome_file_originale='changed.pdf';db.commit()
            with self.assertRaisesRegex(RuntimeError,'Source data changed'):
                apply(db,before['digest'])
            db.rollback()

    def test_network_work_holds_no_open_transaction_on_advisory_connection(self):
        @reuse_certificate_payload('metalba')
        def read(db,*,certificate_document,openai_api_key,certificate_ai_cache=None):
            states=db.execute(text("SELECT state FROM pg_stat_activity WHERE datname=current_database() "
                                   "AND pid<>pg_backend_pid() AND query LIKE '%pg_try_advisory_lock%'" )).scalars().all()
            self.assertTrue(states)
            self.assertNotIn('idle in transaction',states)
            p=certificate_document.pages[0]
            return s._normalize_metalba_certificate_ai_payload({'page1':{'page_id':p.id,'page_number':1}},metalba_raw())
        with self.Session() as db:
            read(db,certificate_document=db.get(Document,self.doc_id),openai_api_key='unused')

    def test_manual_policy_backfill_is_additive_idempotent_and_survives_cleared_fields(self):
        from fastapi import HTTPException
        from scripts.prepare_certificate_ai_reuse import preview,apply,source_digest
        from app.modules.acquisition.manual_document_protection import automatic_ai_disabled
        from app.modules.acquisition.models import AcquisitionRow, ReadValue, DocumentEvidence
        with self.Session() as db:
            doc=db.get(Document,self.doc_id)
            row=AcquisitionRow(document_certificato_id=doc.id,fornitore_id=doc.fornitore_id)
            db.add(row);db.flush();row_id=row.id
            for field,value in {'numero_certificato_certificato':'MANUAL1','colata_certificato':'CAST1','diametro_certificato':'33'}.items():
                db.add(ReadValue(acquisition_row_id=row.id,blocco='match',campo=field,valore_finale=value,
                    stato='confermato',metodo_lettura='utente',fonte_documentale='certificato'))
            db.commit()
            before=preview(db)
            self.assertEqual(before['counts'],{'manual_no_automatic_ai':1})
            db.rollback()
            result=apply(db,before['digest'])
            self.assertEqual(result['added_manual_policy_document_ids'],[doc.id])
            self.assertEqual(len(result['added_manual_policy_evidence_ids']),1)
            self.assertEqual(source_digest(db,new_manual_marker_ids=result['added_manual_policy_evidence_ids']),before['digest'])
            again=preview(db);db.rollback()
            repeat=apply(db,again['digest'])
            self.assertEqual(repeat['added_manual_policy_evidence_ids'],[])
            db.query(ReadValue).filter_by(acquisition_row_id=row_id).delete()
            db.commit()
            self.assertTrue(automatic_ai_disabled(db,doc))
            calls=[]
            with self.assertRaises(HTTPException):
                self.reader(calls,threading.Lock())(db,certificate_document=doc,openai_api_key='unused')
            self.assertEqual(calls,[])
            self.assertEqual(db.query(DocumentAiExtraction).count(),0)

    def test_two_sessions_manual_documents_never_enter_reader(self):
        from fastapi import HTTPException
        from app.modules.acquisition.manual_document_protection import mark_manual_entry
        with self.Session() as db:
            mark_manual_entry(db,db.get(Document,self.doc_id),actor_id=None);db.commit()
        calls=[];reader=self.reader(calls,threading.Lock())
        def worker():
            with self.Session() as db:
                with self.assertRaises(HTTPException):
                    reader(db,certificate_document=db.get(Document,self.doc_id),openai_api_key='unused')
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:worker(),range(2)))
        self.assertEqual(calls,[])

    def saved_rematch_fixture(self):
        from app.modules.acquisition.manual_document_protection import mark_manual_entry
        from app.modules.acquisition.models import AcquisitionRow, AutonomousProcessingRun, ReadValue
        with self.Session() as db:
            cert=db.get(Document,self.doc_id);mark_manual_entry(db,cert,actor_id=None)
            source=AcquisitionRow(document_certificato_id=cert.id,fornitore_id=cert.fornitore_id)
            db.add(source);db.flush()
            for field,value in {'numero_certificato_certificato':'26-1791','colata_certificato':'CAST1',
                    'diametro_certificato':'33','lega_certificato':'6082 F','peso_certificato':'120',
                    'ordine_cliente_certificato':'169/26'}.items():
                db.add(ReadValue(acquisition_row_id=source.id,blocco='match',campo=field,
                    valore_finale=value,metodo_lettura='utente',stato='confermato',fonte_documentale='certificato'))
            targets=[]
            for index in range(2):
                doc=Document(tipo_documento='ddt',fornitore_id=cert.fornitore_id,
                    nome_file_originale=f'ddt{index}.pdf',storage_key=f'ddt{index}.pdf')
                db.add(doc);db.flush()
                row=AcquisitionRow(document_ddt_id=doc.id,fornitore_id=cert.fornitore_id)
                db.add(row);db.flush();targets.append(row.id)
                for field,value in {'numero_certificato_ddt':'26-1791','colata':'CAST1','diametro':'33',
                                    'lega':'6082 F','peso':'120','ordine':'169/26'}.items():
                    db.add(ReadValue(acquisition_row_id=row.id,blocco='ddt',campo=field,
                        valore_finale=value,metodo_lettura='chatgpt',stato='proposto',fonte_documentale='ddt'))
            runs=[AutonomousProcessingRun() for _ in range(2)];db.add_all(runs);db.commit()
            return source.id,targets,[r.id for r in runs],cert.fornitore_id

    def test_rematch_replans_after_absorbing_a_source_without_changing_manual_provenance(self):
        from app.modules.acquisition.models import AcquisitionRow, DocumentAiUsage
        from app.modules.acquisition.manual_document_protection import automatic_ai_disabled
        source_id,targets,runs,supplier_id=self.saved_rematch_fixture()
        with self.Session() as db:
            db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=runs[0]
            self.assertEqual(s._run_cross_run_auto_rematch(db=db,supplier_ids={supplier_id},
                actor_id=None,run_id=runs[0]),2)
            self.assertIsNone(db.get(AcquisitionRow,source_id))
            self.assertEqual([db.get(AcquisitionRow,i).document_certificato_id for i in targets],
                             [self.doc_id,self.doc_id])
            self.assertTrue(automatic_ai_disabled(db,db.get(Document,self.doc_id)))
            self.assertEqual(db.query(DocumentAiUsage).count(),0)

    def test_concurrent_rematches_can_absorb_the_same_manual_source_once(self):
        from unittest.mock import patch
        from app.modules.acquisition.models import AcquisitionRow
        source_id,targets,runs,supplier_id=self.saved_rematch_fixture()
        barrier=threading.Barrier(2);local=threading.local();plan=s._plan_cross_run_auto_rematch
        def both_planned(*args,**kwargs):
            result=plan(*args,**kwargs)
            if kwargs.get('target_row_ids') and not getattr(local,'seen',False):
                local.seen=True;barrier.wait(timeout=10)
            return result
        def worker(index):
            with self.Session() as db:
                db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=runs[index]
                return s._run_cross_run_auto_rematch(db=db,supplier_ids={supplier_id},actor_id=None,
                    run_id=runs[index],protected_row_ids={targets[1-index]},protected_source_row_ids=set())
        with patch.object(s,'_plan_cross_run_auto_rematch',side_effect=both_planned):
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(worker,range(2))),[1,1])
        with self.Session() as db:
            self.assertIsNone(db.get(AcquisitionRow,source_id))
            self.assertEqual([db.get(AcquisitionRow,i).document_certificato_id for i in targets],
                             [self.doc_id,self.doc_id])
