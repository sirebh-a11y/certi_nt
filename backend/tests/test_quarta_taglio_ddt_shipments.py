"""Shipment numbering/total: isolated fixtures, real Word controls, no remote DB."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import os
import unittest

from fastapi import HTTPException
from sqlalchemy import select, text, create_engine

from app.modules.quarta_taglio import ddt_shipments as shipments, service, word_reference
from app.modules.quarta_taglio import ddt_word_reuse as reuse
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as C
from test_quarta_taglio_ddt_queue import DdtQueueFixture
import test_quarta_taglio_ddt_word_reuse as reuse_tests


class ShipmentFactsTest(DdtQueueFixture):
    def test_total_ignores_other_ol_f3_document_and_queue_filters(self):
        a = self.item(QtaUmMag=29)
        b = self.item(IdRigaDoc='2', ODVCli='OTHER ORDER', QtaUmMag=91)
        b.source_present = False  # The source window is NOT the lifetime of the DDT.
        self.item(IdRigaDoc='3', ORP='OL2', QtaUmMag=999)
        self.item(IdRigaDoc='4', CodF3='001260', QtaUmMag=999)
        self.item(IdDocumento='200', QtaUmMag=999)
        self.db.commit()
        self.assertEqual(shipments.quantity_text(self.db,a), '29 of 120')
        self.assertEqual(shipments.quantity_text(self.db,b), '91 of 120')
        self.assertFalse(self.db.dirty)

    def test_single_zero_and_decimal_values_are_exact(self):
        a=self.item(QtaUmMag=0)
        self.assertEqual(shipments.quantity_text(self.db,a),'0')
        self.item(IdRigaDoc='2', QtaUmMag=Decimal('23.001'))
        self.assertEqual(shipments.quantity_text(self.db,a),'0 of 23.001')

    def test_unknown_negative_or_ambiguous_peer_never_silently_omitted(self):
        a=self.item(QtaUmMag=29)
        b=self.item(IdRigaDoc='2',QtaUmMag=91)
        for quantity, reason in [(None,None),(-1,None),(91,'quantity_conflict')]:
            b.quantita=quantity; b.source_review_reason=reason; self.db.commit()
            with self.assertRaises(HTTPException): shipments.facts(self.db,a)

    def test_group_revision_changes_when_sibling_changes_not_on_last_seen(self):
        a=self.item(QtaUmMag=29)
        first=shipments.queue_revision(self.db,a)
        b=self.item(IdRigaDoc='2',QtaUmMag=91)
        second=shipments.queue_revision(self.db,a)
        self.assertNotEqual(first,second)
        b.quantita=92; self.db.commit()
        self.assertNotEqual(second,shipments.queue_revision(self.db,a))

    def test_legacy_closed_numbers_never_change_and_next_sequence_is_reserved(self):
        a=self.item()
        source=self.cert(a,pdf=True,certificate_number='7051_00_00/26')
        b=self.item(IdDocumento='200',DDT='2-01/10/2026')
        plan=shipments.number_plan(self.db,b,source)
        self.assertEqual(plan['number'],'7051_00_00_01/26')
        copy=self.cert(b,word=False,certificate_number=plan['number'])
        shipments.record(self.db,copy,b,plan); self.db.commit()
        peer=self.item(IdDocumento='200',IdRigaDoc='2',DDT=b.ddt_raw)
        self.assertEqual(shipments.number_plan(self.db,peer,source)['number'],copy.certificate_number)
        third=self.item(IdDocumento='300',DDT='3-01/10/2026')
        self.assertEqual(shipments.number_plan(self.db,third,copy)['number'],'7051_00_00_02/26')
        self.assertEqual(source.certificate_number,'7051_00_00/26')
        self.assertIsNone(source.shipment_context)

    def test_same_ddt_conflicting_numbers_refused(self):
        a=self.item()
        source=self.cert(a,certificate_number='7051_00_00/26')
        b=self.item(IdRigaDoc='2')
        self.cert(b,certificate_number='7051_00_00_01/26')
        with self.assertRaises(HTTPException): shipments.number_plan(self.db,a,source)

    def test_first_ddt_uses_early_base_number_and_old_open_number_is_preserved(self):
        a=self.item()
        early=self.cert(a,ddt=None,esolver_id_documento=None,certificate_number='7051_00_00/26')
        self.assertEqual(shipments.number_plan(self.db,a,early)['sequence'],0)
        b=self.item(IdDocumento='200',DDT='2-01/10/2026')
        old=self.cert(b,certificate_number='7051_00_00/26')
        self.assertEqual(shipments.number_plan(self.db,b,early,old)['number'],old.certificate_number)

    def test_new_number_parser_keeps_original_ol_and_workmanship_segments(self):
        c=SimpleNamespace(certificate_number='7051_12_30_99/26',shipment_context=None)
        self.assertEqual(shipments.base_number(c),'7051_12_30/26')
        self.assertEqual(service._certificate_main_number(c.certificate_number),7051)
        self.assertEqual(service._certificate_suffix_parts(c.certificate_number),(7051,12,'26'))

    def test_schema_preparation_idempotent_no_backfill(self):
        with self.engine.begin() as connection:
            self.assertFalse(shipments.ensure_schema(connection))
        self.assertEqual(self.db.query(C).count(),0)

    def test_migration_and_preview_work_on_old_schema_without_touching_records(self):
        a=self.item()
        c=self.cert(a,pdf=True,certificate_number='7051_00_00/26')
        certificate_id=c.id
        self.db.close()
        with self.engine.begin() as connection:
            connection.execute(text('ALTER TABLE quarta_taglio_final_certificates DROP COLUMN shipment_context'))
        preview=shipments.preview_legacy(self.db)
        self.assertEqual(preview['certificates'],1)
        self.assertEqual(preview['proposed_historical_renumbering'],0)
        with self.engine.begin() as connection:
            self.assertTrue(shipments.ensure_schema(connection))
            self.assertFalse(shipments.ensure_schema(connection))
        saved=self.db.get(C,certificate_id)
        self.assertEqual(saved.certificate_number,'7051_00_00/26')
        self.assertEqual(saved.status,'pdf_final')
        self.assertIsNone(saved.shipment_context)

    def test_standard_download_names_include_shipment_sequence_custom_pdf_stays(self):
        from app.modules.quarta_taglio.file_names import standard_certificate_file_name,certificate_pdf_file_name
        c=SimpleNamespace(certificate_number='7051_00_00_01/26',draft_number='',pdf_file_name=None)
        self.assertEqual(standard_certificate_file_name(c,'docx'),'7051_00_00_01_26.docx')
        self.assertEqual(certificate_pdf_file_name(c),'7051_00_00_01_26.pdf')
        c.pdf_file_name='Cliente - ordine.pdf'
        self.assertEqual(certificate_pdf_file_name(c),'Cliente - ordine.pdf')


class ShipmentWordTest(reuse_tests.DdtWordReuseTest):
    def create_real(self,item):
        with patch.object(service,'_word_creation_blockers',return_value=[]), patch.object(
                service,'_build_standard_conformity',return_value=('conforme',[])):
            return self.create(item)

    def test_real_first_word_generation_and_sibling_total(self):
        a=self.item(QtaUmMag=29)
        b=self.item(IdRigaDoc='2',QtaUmMag=91)
        self.material()
        result=self.create_real(a)
        c=self.db.get(C,result.id)
        controls,_=reuse.word_facts(c.storage_key_docx)
        self.assertEqual(controls['QUANTITY_RAW'],'29 of 120')
        self.assertEqual(c.quantita,29)
        self.assertEqual(controls['CERT_NUMBER'],c.certificate_number)
        self.assertEqual(c.shipment_context['sequence'],0)
        self.assertEqual(result.file_name,service._certificate_file_name(c))
        self.assertEqual(len(c.certificate_number.split('/')[0].split('_')),3)
        peer=self.db.scalar(select(C).where(C.unit_key==b.certification_unit_key))
        self.assertEqual(peer.certificate_number,c.certificate_number)
        self.assertEqual(reuse.word_facts(peer.storage_key_docx)[0]['QUANTITY_RAW'],'91 of 120')

    def test_new_shipment_pdf_filename_and_export_are_aligned(self):
        from app.modules.esolver_export.service import list_esolver_pdf_certificates
        self.base_word()
        a=self.later()
        self.run_worker()
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        c.conformity_status='conforme'
        self.db.commit()
        def convert(word,pdf):
            pdf.parent.mkdir(parents=True,exist_ok=True)
            pdf.write_bytes(b'%PDF isolated export fixture')
        with patch.object(service,'_build_standard_conformity',return_value=('conforme',[])),patch.object(
                service,'convert_docx_to_pdf',side_effect=convert):
            service.generate_quarta_taglio_certificate_pdf(self.db,certificate_id=c.id,actor=self.actor)
        self.assertEqual(c.pdf_file_name,'7013_00_00_01_26.pdf')
        if self.db.get_bind().dialect.name == 'postgresql':
            # Exercise the real canonical SQL view against THIS disposable
            # test schema, not an absent public/Alpha export view.
            from app.modules.esolver_export.view import ensure_esolver_export_view
            export_engine=create_engine(self.root_engine.url,connect_args={
                'options':f'-csearch_path={self.schema},public'})
            try:
                ensure_esolver_export_view(export_engine,public_base_url='http://local')
            finally:
                export_engine.dispose()
        export=next(e for e in list_esolver_pdf_certificates(self.db,public_base_url='http://local').items
                    if e.numero_certificato==c.certificate_number)
        self.assertEqual(export.nome_file_pdf,c.pdf_file_name)
        self.assertEqual(service._certificate_file_name(c),'7013_00_00_01_26.docx')

    def test_two_lines_same_ddt_keep_number_and_total_in_real_controls(self):
        _,source=self.base_word()
        a=self.later(QtaUmMag=29)
        b=self.later(IdRigaDoc='3',ODVCli='SECOND ORDER',QtaUmMag=91)
        self.assertEqual(self.run_worker()['prepared'],2)
        certs=[self.db.scalar(select(C).where(C.unit_key==i.certification_unit_key)) for i in (a,b)]
        for c,quantity in zip(certs,['29 of 120','91 of 120']):
            controls,_=reuse.word_facts(c.storage_key_docx)
            self.assertEqual(c.certificate_number,'7013_00_00_01/26')
            self.assertEqual(controls['CERT_NUMBER'],c.certificate_number)
            self.assertEqual(controls['QUANTITY_RAW'],quantity)
        self.assertEqual([c.quantita for c in certs],[29,91])
        self.assertEqual(self.run_worker()['prepared'],0)

    def test_three_shipments_reuse_template_despite_different_numbers(self):
        self.base_word()
        second=self.later()
        self.assertEqual(self.run_worker()['prepared'],1)
        third=self.later(IdDocumento='300',DDT='3-10/10/2026')
        self.assertEqual(self.run_worker()['prepared'],1)
        c=self.db.scalar(select(C).where(C.unit_key==third.certification_unit_key))
        self.assertEqual(c.certificate_number,'7013_00_00_02/26')
        self.assertEqual(reuse.word_facts(c.storage_key_docx)[0]['CERT_NUMBER'],c.certificate_number)

    def test_sibling_quantity_refresh_preserves_manual_body_and_closed_source(self):
        _,source=self.base_word()
        original_word,original_pdf=reuse.file_hash(source.storage_key_docx),reuse.file_hash(source.storage_key_pdf)
        a=self.later(QtaUmMag=29)
        self.assertEqual(self.run_worker()['prepared'],1)
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        old_number=c.certificate_number
        self.later(IdRigaDoc='3',QtaUmMag=91)
        self.assertEqual(self.run_worker()['prepared'],2)  # refresh first, prepare second
        self.assertEqual(c.certificate_number,old_number)
        self.assertEqual(reuse.word_facts(c.storage_key_docx)[0]['QUANTITY_RAW'],'29 of 120')
        self.assertEqual(reuse.file_hash(source.storage_key_docx),original_word)
        self.assertEqual(reuse.file_hash(source.storage_key_pdf),original_pdf)

    def test_closed_pdf_does_not_get_new_total_on_late_sibling(self):
        _,source=self.base_word()
        a=self.later(QtaUmMag=29)
        self.run_worker()
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        c.status='pdf_final'; c.storage_key_pdf='closed-test.pdf'
        Path(self.files.name,'closed-test.pdf').write_bytes(b'closed immutable fixture')
        self.db.commit()
        before=(reuse.file_hash(c.storage_key_docx),deepcopy(c.shipment_context),c.certificate_number)
        self.later(IdRigaDoc='3',QtaUmMag=91)
        self.run_worker()
        self.assertEqual((reuse.file_hash(c.storage_key_docx),c.shipment_context,c.certificate_number),before)

    def test_pdf_guard_detects_other_line_change(self):
        self.base_word(); a=self.later(QtaUmMag=29)
        b=self.later(IdRigaDoc='3',QtaUmMag=91)
        self.run_worker()
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        shipments.require_current(self.db,c)
        b.quantita=92; self.db.commit()
        with self.assertRaises(HTTPException): shipments.require_current(self.db,c)

    def test_sibling_change_during_pdf_conversion_does_not_publish(self):
        self.base_word()
        a=self.later(QtaUmMag=29)
        b=self.later(IdRigaDoc='3',QtaUmMag=91)
        self.run_worker()
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        c.conformity_status='conforme'; self.db.commit()
        def convert(word,pdf):
            pdf.parent.mkdir(parents=True,exist_ok=True); pdf.write_bytes(b'%PDF test')
            b.quantita=92; self.db.commit()
        with patch.object(service,'_build_standard_conformity',return_value=('conforme',[])),patch.object(
                service,'convert_docx_to_pdf',side_effect=convert),self.assertRaises(HTTPException) as caught:
            service.generate_quarta_taglio_certificate_pdf(self.db,certificate_id=c.id,actor=self.actor)
        self.assertEqual(caught.exception.status_code,409)
        self.assertIsNone(c.storage_key_pdf)
        self.assertNotEqual(c.status,'pdf_final')


# Reuse fixture methods without executing the inherited regression suites twice.
for name in list(vars(ShipmentWordTest.__mro__[1])):
    if name.startswith('test_') and name not in ShipmentWordTest.__dict__:
        setattr(ShipmentWordTest,name,None)


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'), 'isolated PostgreSQL test URL not supplied')
class ShipmentPostgresTest(ShipmentWordTest):
    setUp = reuse_tests.DdtWordReusePostgresTest.setUp

    def test_concurrent_workers_allocate_one_number_per_ddt_not_per_line(self):
        self.base_word()
        a=self.later(QtaUmMag=29)
        b=self.later(IdRigaDoc='3',QtaUmMag=91)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:reuse.sync_ddt_words(session_factory=self.factory),range(2)))
        self.assertEqual(sum(r['errors'] for r in results),0)
        self.assertEqual(sum(r['prepared'] for r in results),2)
        self.db.expire_all()
        copies=list(self.db.scalars(select(C).where(C.unit_key.in_([a.certification_unit_key,b.certification_unit_key]))))
        self.assertEqual({c.certificate_number for c in copies},{'7013_00_00_01/26'})

    def test_snapshot_busy_during_final_check_requires_retry_not_interruption(self):
        self.base_word(); a=self.later(); self.run_worker()
        c=self.db.scalar(select(C).where(C.unit_key==a.certification_unit_key))
        from app.modules.quarta_taglio.ddt_snapshot import _LOCK_NAMESPACE,_LOCK_ID
        with self.factory() as writer:
            writer.execute(text('SELECT pg_advisory_xact_lock(:namespace,:key)'),dict(namespace=_LOCK_NAMESPACE,key=_LOCK_ID))
            with self.assertRaises(HTTPException) as caught:
                shipments.lock_snapshot_for_pdf(self.db,c)
            self.assertEqual(caught.exception.status_code,409)
            writer.rollback()

    def test_simultaneous_first_numbers_on_different_ol_do_not_collide(self):
        def allocate(ol):
            with self.factory.begin() as db:
                number=service._assign_certificate_number(db,cdq_key='same-CDQ',cod_odp=ol,cod_f3='001230')
                db.add(C(cod_odp=ol,cod_f3='001230',certificate_number=number,draft_number=number,cdq_key='same-CDQ'))
                return number
        with ThreadPoolExecutor(max_workers=2) as pool:
            numbers=list(pool.map(allocate,['OL-A','OL-B']))
        self.assertEqual(len(set(numbers)),2)
