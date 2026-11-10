"""New seven-digit numbers, immutable history and exact-workmanship reuse."""
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import os
import unittest

from fastapi import HTTPException
import pytest
from sqlalchemy import select, create_engine

from app.modules.quarta_taglio import service, ddt_shipments as shipments, word_reference
from app.modules.quarta_taglio import ddt_word_reuse as reuse
from app.modules.quarta_taglio.certificate_numbering import comparable_base, new_shipment_base
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as C
from test_quarta_taglio_ddt_queue import DdtQueueFixture, NOW
import test_quarta_taglio_ddt_word_reuse as reuse_cases


@pytest.mark.parametrize('code,expected', [
    ('0600023','00'), ('4130001','00'), ('0000000','00'), ('060002330','30'),
    ('060002340','40'), ('060002300','00'), ('600023','23'), ('06000238','38'),
    ('7','07'), (None,'00'), ('047012883','83'),
])
def test_only_seven_digits_change_the_workmanship_suffix(code, expected):
    assert service._cod_f3_certificate_suffix(code) == expected


def test_comparison_is_not_a_historical_number_rewrite_or_arbitrary_repair():
    old = SimpleNamespace(cod_f3='0600023',certificate_number='7100_02_23_03/26',shipment_context=None)
    assert shipments.base_number(old) == '7100_02_23/26'
    assert shipments.series_base_number(old) == '7100_02_00/26'
    assert old.certificate_number == '7100_02_23_03/26'
    assert comparable_base('7100_02_023/26','0600023') == '7100_02_00/26'
    assert comparable_base('7100_02_40/26','0600023') == '7100_02_40/26'
    assert comparable_base('7100_02_23/26','060002330') == '7100_02_23/26'
    with pytest.raises(ValueError): new_shipment_base('7100_02_40/26','0600023')


class SevenDigitAllocationTest(DdtQueueFixture):
    def test_new_ddt_keeps_sequence_across_old_and_new_spelling(self):
        first=self.item(CodF3='0600023')
        old=self.cert(first,pdf=True,certificate_number='7100_02_023_03/26')
        old.shipment_context={'base_number':'7100_02_023/26','sequence':3}
        second=self.item(IdDocumento='200',CodF3=first.cod_f3,DDT='2-10/11/2026')
        plan=shipments.number_plan(self.db,second,old)
        assert plan['number']=='7100_02_00_04/26'
        new=self.cert(second,certificate_number=plan['number'])
        shipments.record(self.db,new,second,plan);self.db.commit()
        third=self.item(IdDocumento='300',CodF3=first.cod_f3,DDT='3-11/11/2026')
        assert shipments.number_plan(self.db,third,old)['number']=='7100_02_00_05/26'
        assert shipments.number_plan(self.db,third,new)['number']=='7100_02_00_05/26'
        assert old.certificate_number=='7100_02_023_03/26'
        assert old.shipment_context=={'base_number':'7100_02_023/26','sequence':3}

    def test_already_numbered_open_word_and_late_share_keep_old_number(self):
        item=self.item(CodF3='0600023')
        old=self.cert(item,certificate_number='7100_00_23/26')
        peer=self.item(CodF3=item.cod_f3,IdRigaDoc='2')
        assert shipments.number_plan(self.db,peer,old)['number']==old.certificate_number
        assert shipments.number_plan(self.db,item,old,old)['number']==old.certificate_number
        later=self.item(CodF3=item.cod_f3,IdDocumento='200',DDT='2-10/11/2026')
        assert shipments.number_plan(self.db,later,old)['number']=='7100_00_00_01/26'

    def test_early_source_does_not_consume_a_sequence(self):
        item=self.item(CodF3='0600023')
        old=self.cert(item,certificate_number='7100_00_23/26',ddt=None,esolver_id_documento=None)
        assert shipments.number_plan(self.db,item,old)['number']=='7100_00_00/26'
        assert old.certificate_number=='7100_00_23/26'

    def test_same_visible_00_never_merges_different_f3(self):
        item=self.item(CodF3='0600023')
        old=self.cert(item,certificate_number='7100_00_23/26',ddt=None,esolver_id_documento=None)
        child=self.item(IdDocumento='300',CodF3='060002300')
        self.cert(child,certificate_number='7100_00_00/26')
        with pytest.raises(HTTPException) as conflict: shipments.number_plan(self.db,item,old)
        assert conflict.value.status_code==409
        assert old.certificate_number=='7100_00_23/26'


class SevenDigitWordTest(reuse_cases.DdtWordReuseTest):
    def historical_source(self, *, closed=True):
        first=self.item(CodF3='0600023',DDT='1-01/10/2026')
        material,_=self.material(); material.cod_art=first.cod_f3;self.db.commit()
        detail=self.detail(first)
        source=self.cert(first,pdf=closed,certificate_number='7100_00_23/26',draft_number='7100_00_23/26',
            word_source='generated',cdq_key=service._cdq_key_from_detail(detail),
            cdq_signature=service._cdq_signature_from_detail(detail),cdq_values=service._cdq_values_from_detail(detail),
            conformity_status='conforme')
        service.build_forgialluminio_draft_docx(detail=detail,output_path=service._certificate_storage_path(source.storage_key_docx),
            draft_number=source.certificate_number,certified_by=self.actor,quality_manager=self.actor)
        self.db.commit()
        return first,source

    def create_real(self,item,**kwargs):
        with patch.object(service,'_word_creation_blockers',return_value=[]),patch.object(
            service,'_build_standard_conformity',return_value=('conforme',[])):
            return self.create(item,**kwargs)

    def test_number_conflict_does_not_claim_the_source_word_is_corrupt(self):
        _,source=self.historical_source()
        old_hash=reuse.file_hash(source.storage_key_docx)
        later=self.later(CodF3=source.cod_f3)
        child=self.item(IdDocumento='300',CodF3='060002300')
        self.cert(child,certificate_number='7100_00_00_01/26')
        plan=reuse.plan_item(self.db,later)
        assert plan['action']=='skip' and plan['reason']=='certificate_number_conflict'
        assert 'altro OL/lavorazione' in plan['numbering_message']
        assert reuse.file_hash(source.storage_key_docx)==old_hash

    def test_explicit_regeneration_does_not_renumber_existing_open_word(self):
        item,source=self.historical_source(closed=False)
        response=self.create_real(item,force_regenerate=True,certificate_id=source.id)
        assert source.certificate_number=='7100_00_23/26'
        assert response.file_name=='7100_00_23_26.docx'
        assert reuse.word_facts(source.storage_key_docx)[0]['CERT_NUMBER']==source.certificate_number

    def test_old_closed_source_new_ddt_controls_names_export_and_following_ddt(self):
        _,source=self.historical_source()
        old_state=(source.certificate_number,reuse.file_hash(source.storage_key_docx),reuse.file_hash(source.storage_key_pdf))
        later=self.later(CodF3=source.cod_f3)
        assert self.run_worker()['prepared']==1
        target=self.db.scalar(select(C).where(C.unit_key==later.certification_unit_key))
        assert target.certificate_number=='7100_00_00_01/26'
        assert reuse.word_facts(target.storage_key_docx)[0]['CERT_NUMBER']==target.certificate_number
        assert service._certificate_file_name(target)=='7100_00_00_01_26.docx'
        assert service._certificate_pdf_file_name(target)=='7100_00_00_01_26.pdf'
        from app.modules.esolver_export.service import list_esolver_pdf_certificates
        def convert(word,pdf):
            pdf.parent.mkdir(parents=True,exist_ok=True);pdf.write_bytes(b'%PDF isolated naming fixture')
        with patch.object(service,'_build_standard_conformity',return_value=('conforme',[])),patch.object(
            service,'convert_docx_to_pdf',side_effect=convert):
            service.generate_quarta_taglio_certificate_pdf(self.db,certificate_id=target.id,actor=self.actor)
        if self.db.get_bind().dialect.name=='postgresql':
            from app.modules.esolver_export.view import ensure_esolver_export_view
            export_engine=create_engine(self.root_engine.url,connect_args={'options':f'-csearch_path={self.schema},public'})
            try: ensure_esolver_export_view(export_engine,public_base_url='http://local')
            finally: export_engine.dispose()
        exported=next(e for e in list_esolver_pdf_certificates(self.db,public_base_url='http://local').items if e.id_certi==target.id)
        assert exported.numero_certificato==target.certificate_number
        assert exported.nome_file_pdf=='7100_00_00_01_26.pdf'
        next_item=self.later(IdDocumento='300',DDT='3-11/11/2026',CodF3=source.cod_f3)
        assert self.run_worker()['prepared']==1
        next_cert=self.db.scalar(select(C).where(C.unit_key==next_item.certification_unit_key))
        assert next_cert.certificate_number=='7100_00_00_02/26'
        assert (source.certificate_number,reuse.file_hash(source.storage_key_docx),reuse.file_hash(source.storage_key_pdf))==old_state
        assert self.run_worker()['prepared']==0

    def test_old_early_word_hidden_after_new_numbered_share_without_losing_source(self):
        first,source=self.historical_source(closed=False)
        source.ddt=source.esolver_id_documento=source.esolver_id_riga_doc=source.esolver_rif_lotto_alfanum=None
        source.unit_key='early';self.db.delete(first);self.db.commit()
        old_hash=reuse.file_hash(source.storage_key_docx)
        later=self.later(CodF3=source.cod_f3)
        assert self.run_worker()['prepared']==1
        target=self.db.scalar(select(C).where(C.unit_key==later.certification_unit_key))
        assert target.certificate_number=='7100_00_00/26'
        assert [c.id for c in service.list_quarta_taglio_final_certificates(self.db).items]==[target.id]
        selected,reason=word_reference.choose(self.db,[source,target])
        assert selected is not None,reason
        assert source.certificate_number=='7100_00_23/26' and reuse.file_hash(source.storage_key_docx)==old_hash
        from docx import Document
        path=service._certificate_storage_path(target.storage_key_docx)
        changed=Document(path);changed.add_paragraph('Manual technical variation');changed.save(path)
        selected,reason=word_reference.choose(self.db,[source,target])
        assert selected is None and reason=='different_word_sources'

    def test_new_first_word_and_other_workmanship_use_own_f3(self):
        raw=self.item(CodF3='0600023')
        material,_=self.material();material.cod_art=raw.cod_f3;self.db.commit()
        raw_response=self.create_real(raw)
        source=self.db.get(C,raw_response.id)
        assert source.certificate_number.endswith('_00_00/26')
        for suffix in ('30','40'):
            item=self.later(CodF3='0600023'+suffix,IdDocumento='200'+suffix,DDT=suffix+'-10/11/2026')
            response=self.create_real(item)
            cert=self.db.get(C,response.id)
            assert cert.certificate_number.rsplit('_',1)[1]==suffix+'/26'
            controls,_=reuse.word_facts(cert.storage_key_docx)
            assert controls['CERT_NUMBER']==cert.certificate_number
            assert controls['COD_F3_FINISHED']==item.cod_f3
            assert controls['COD_F3_RAW']==raw.cod_f3


for name in dir(reuse_cases.DdtWordReuseTest):
    if name.startswith('test_') and name not in SevenDigitWordTest.__dict__:
        setattr(SevenDigitWordTest,name,None)


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'),'isolated PostgreSQL URL not supplied')
class SevenDigitPostgresTest(SevenDigitWordTest):
    setUp=reuse_cases.DdtWordReusePostgresTest.setUp

    def test_concurrent_new_shares_get_one_number_without_touching_old_source(self):
        _,source=self.historical_source()
        source_hash=reuse.file_hash(source.storage_key_docx)
        a=self.later(CodF3=source.cod_f3,QtaUmMag=29)
        b=self.later(CodF3=source.cod_f3,IdRigaDoc='3',QtaUmMag=91)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:reuse.sync_ddt_words(session_factory=self.factory),range(2)))
        self.db.expire_all()
        copies=list(self.db.scalars(select(C).where(C.unit_key.in_([a.certification_unit_key,b.certification_unit_key]))))
        assert sum(r['prepared'] for r in outcomes)==2 and sum(r['errors'] for r in outcomes)==0
        assert {c.certificate_number for c in copies}=={'7100_00_00_01/26'}
        assert reuse.file_hash(source.storage_key_docx)==source_hash
        assert source.certificate_number=='7100_00_23/26'

    def test_concurrent_first_seven_digit_numbers_keep_cdq_ol_segment(self):
        def allocate(ol):
            with self.factory.begin() as db:
                number=service._assign_certificate_number(db,cdq_key='SAME-CDQ',cod_odp=ol,cod_f3='0600023',now=NOW)
                db.add(C(cod_odp=ol,cod_f3='0600023',certificate_number=number,draft_number=number,cdq_key='SAME-CDQ'))
                return number
        with ThreadPoolExecutor(max_workers=2) as pool:
            numbers=list(pool.map(allocate,['OL-A','OL-B']))
        assert len(set(numbers))==2 and all(n.endswith('_00/26') for n in numbers)
        assert {n.split('_')[1] for n in numbers}=={'00','01'}
