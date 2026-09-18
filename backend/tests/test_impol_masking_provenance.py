import copy
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate  # noqa: F401
from app.modules.acquisition.models import AcquisitionRow, Document, DocumentEvidence, DocumentPage, ReadValue
from app.modules.acquisition import service as s
from app.modules.acquisition.impol_evidence import locate_quote, assign_note_pages, PAGE_REVIEW_EVIDENCE
from app.modules.acquisition.impol_masking import mask_certificate, ImpolMaskReviewRequired

US_B = "BILLETS 100% US TESTED ACCORDING TO AMS STD 2154 CLASS B"
ROHS = "Directive 2011/65/EU RoHS with all amendment"


class ImpolProvenanceTest(unittest.TestCase):
    def pages(self, first=US_B, second=ROHS):
        return {'p1': {'page_id': 11, 'page_number': 1, 'source_text': first},
                'p2': {'page_id': 22, 'page_number': 2, 'source_text': second}}

    def test_each_note_keeps_its_own_page(self):
        payload = {'notes': {'b': {'snippet': US_B, 'final': 'true'}, 'r': {'snippet': ROHS, 'final': 'true'}}}
        assign_note_pages(payload,self.pages())
        self.assertEqual(payload['notes']['b']['page_id'],11)
        self.assertEqual(payload['notes']['r']['page_id'],22)
        self.assertEqual(payload['notes']['b']['final'],'true')

    def test_repeated_missing_boolean_or_unavailable_text_never_guesses_page(self):
        for quote,pages in [(US_B,self.pages(US_B,US_B)),('true',self.pages()),
                            ('A sentence absent from the PDF',self.pages()),(US_B,{'p1':{'page_id':11}})]:
            self.assertIsNone(locate_quote(quote,pages)[0])

    def test_multi_quote_requires_all_parts_on_same_page(self):
        self.assertEqual(locate_quote(US_B+' | '+ROHS,self.pages(US_B+'\n'+ROHS,ROHS))[0],11)
        self.assertIsNone(locate_quote(US_B+' | '+ROHS,self.pages())[0])

    def test_duplicate_crop_roles_do_not_create_false_ambiguity(self):
        pages=self.pages()
        pages['p1_copy']=dict(pages['p1'])
        self.assertEqual(locate_quote(US_B,pages)[0],11)

    def test_only_minor_ocr_letter_error_allowed_not_class_or_number(self):
        self.assertEqual(locate_quote(US_B,self.pages(US_B.replace('STD','STO')))[0],11)
        self.assertIsNone(locate_quote(US_B,self.pages(US_B.replace('CLASS B','CLASS A')))[0])
        self.assertIsNone(locate_quote(US_B,self.pages(US_B.replace('2154','2155')))[0])

    def test_normalizer_preserves_values_and_scope(self):
        raw={'core':{'numero_certificato':'1505/a','supplier_order_no':'49072/2'},
             'chemistry_raw':{'Si':'1,1','Fe':'0,23'},
             'mechanical_raw':{'measured_rows':[{'Rm':'396','Rp0.2':'380','A%':'12,5','HB':'111,8'}]},
             'notes_raw':{'nota_us_control_class_b_raw':US_B,'nota_rohs_raw':ROHS,
                          'nota_us_control_class_a_raw':'100% ULTRASONIC INSPECTION ENDS OF BARS AMS STD 2154 CLASS A'},
             'mechanical_requirement_raw':{'customer_requirement_quote_raw':'BARS EXTRUDED ON TECHNICAL SPECIFICATION LST00'}}
        original=copy.deepcopy(raw)
        pages=self.pages(US_B+' BARS EXTRUDED ON TECHNICAL SPECIFICATION LST00',ROHS)
        result=s._normalize_impol_certificate_ai_payload(pages,raw)
        self.assertEqual(raw,original)
        self.assertEqual(result['match_values']['numero_certificato_certificato'],'1505/a')
        self.assertEqual(result['supplier_fields']['supplier_order_no'],'49072/2')
        self.assertNotIn('nota_us_control_class_a',result['notes'])
        self.assertEqual(result['notes']['nota_us_control_class_b']['page_id'],11)
        self.assertEqual(result['notes']['nota_rohs']['page_id'],22)
        self.assertEqual(result['mechanical_requirement']['customer_requirement_quote']['page_id'],11)
        self.assertEqual(len(result['chemistry']),2)
        self.assertEqual(len(result['properties']),4)

    def test_lst00_enrichment_is_located_before_downstream_fallback(self):
        raw={'mechanical_requirement_raw':{'customer_requirement_quote_raw':'BARS EXTRUDED ON TECHNICAL SPECIFICATION LST00'}}
        result=s._normalize_impol_certificate_ai_payload(self.pages('unrelated','unrelated'),raw)
        self.assertIn('nota_us_control_class_b',result['notes'])
        self.assertIsNone(result['notes']['nota_us_control_class_b']['page_id'])
        s._enrich_notes_with_lst_00_class_b(result,fallback_page_id=11)
        self.assertIsNone(result['notes']['nota_us_control_class_b']['page_id'])


class ImpolMaskTest(unittest.TestCase):
    def sample(self, scale=1, shift=0):
        def word(text,x,y,width=90,height=15):
            return {'text':text,'left':round((x+shift)*scale),'right':round((x+width+shift)*scale),
                    'top':round((y+shift)*scale),'bottom':round((y+height+shift)*scale)}
        words=[word('INSPECTION',200,100),word('CERTIFICATE',300,100),word('NO.',405,140,25),
               word('CUSTOMER',60,355),word('SUPPLIER',610,355),word('ORDER',610,385),
               word('49072/2',790,385),word('PRODUCT',60,530),word('CHEMICAL',60,660),
               word('MECHANICAL',60,800),word('REQUIREMENTS',230,1510),word('ORDER',600,1510),
               word('DRUZBA',60,1540),word('REGISTER',190,1540),word('DAVCNA',450,1560),
               word('45197687',550,1560),word('2',480,1595,8)]
        im=Image.new('RGB',(round(1000*scale),round(1684*scale)),'white')
        draw=ImageDraw.Draw(im)
        for v in words:
            draw.rectangle((v['left'],v['top'],v['right'],v['bottom']),fill='gray')
        # Names and logo ink need not be OCR-readable to be fully covered.
        for box in [(660,100,910,330),(60,205,300,300)]:
            draw.rectangle(tuple(round((n+shift)*scale) for n in box),fill='gray')
        return im,words

    def test_ink_boundaries_keep_order_and_technical_data_at_multiple_scales(self):
        for scale,shift in [(1,0),(.75,0),(1.5,0),(1,12)]:
            im,words=self.sample(scale,shift)
            original=im.tobytes()
            masked=mask_certificate(im,words)
            self.assertEqual(im.tobytes(),original)
            for v in words:
                if v['text'] in {'ORDER','49072/2','PRODUCT','CHEMICAL','MECHANICAL','REQUIREMENTS','2','INSPECTION','CERTIFICATE'}:
                    box=(v['left'],v['top'],v['right'],v['bottom'])
                    self.assertEqual(im.crop(box).tobytes(),masked.crop(box).tobytes(),v['text'])
            self.assertEqual(masked.getpixel((round((800+shift)*scale),round((200+shift)*scale))),(0,0,0))
            self.assertEqual(masked.getpixel((round((200+shift)*scale),round((250+shift)*scale))),(0,0,0))

    def test_missing_or_unreliable_anchors_stop(self):
        im,words=self.sample()
        for invalid in [[],[v for v in words if v['text'] not in {'CUSTOMER','SUPPLIER'}],
                        [v for v in words if v['text']!='DAVCNA']]:
            with self.assertRaises(ImpolMaskReviewRequired) as caught:
                mask_certificate(im,invalid)
            self.assertFalse(s._is_retryable_processing_error(caught.exception))

    def test_high_header_and_low_signature_panel_preserve_conformity(self):
        im,words=self.sample()
        draw=ImageDraw.Draw(im)
        # Higher scanned header: number at y=97, customer name at y=166.
        for v in words:
            if v['text']=='NO.':
                v['top'],v['bottom']=97,112
            if v['text'] in {'DRUZBA','REGISTER'}:
                v['top'],v['bottom']=1584,1601
            if v['text'] in {'DAVCNA','45197687'}:
                v['top'],v['bottom']=1605,1618
        draw.rectangle((800,45,920,60),fill='gray')
        draw.rectangle((60,166,260,184),fill='gray')
        for text,x,y in [('GROUP',60,1317),('QUALITY',120,1360),('DIRECTOR',620,1360),('ORGANIZATION',260,1537)]:
            v={'text':text,'left':x,'right':x+80,'top':y,'bottom':y+15}
            words.append(v)
            draw.rectangle((x,y,x+80,y+15),fill='gray')
        masked=mask_certificate(im,words)
        self.assertEqual(masked.getpixel((850,50)),(0,0,0))
        self.assertEqual(masked.getpixel((100,170)),(0,0,0))
        self.assertEqual(masked.getpixel((300,1540)),im.getpixel((300,1540)))


class ImpolPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        self.doc=Document(tipo_documento='certificato',nome_file_originale='sample.pdf',storage_key='sample.pdf')
        self.db.add(self.doc)
        self.db.flush()
        self.page=DocumentPage(document_id=self.doc.id,numero_pagina=1)
        self.row=AcquisitionRow(document_certificato_id=self.doc.id)
        self.db.add_all([self.page,self.row])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def apply(self,payload,protected=None):
        with patch.object(s,'_sync_row_from_match_values'),patch.object(s,'_sync_row_statuses'):
            s._apply_aluminium_bozen_certificate_ai_payload(self.db,row=self.row,payload=payload,actor_id=None,confirmed_blocks=protected)
        self.db.commit()

    def test_unknown_page_persists_value_and_review_evidence_without_invalid_fk(self):
        payload={'notes':{'nota_rohs':{'page_id':None,'source_page_status':'ambigua','snippet':ROHS,'final':'true','standardized':'true'}}}
        self.apply(payload)
        value=self.db.query(ReadValue).one()
        self.assertEqual(value.valore_finale,'true')
        evidence=self.db.get(DocumentEvidence,value.document_evidence_id)
        self.assertIsNone(evidence.document_page_id)
        self.assertEqual(evidence.tipo_evidenza,PAGE_REVIEW_EVIDENCE)
        self.assertEqual(evidence.testo_grezzo,ROHS)

    def test_confirmed_notes_untouched(self):
        value=ReadValue(acquisition_row_id=self.row.id,blocco='note',campo='nota_rohs',valore_finale='true',stato='confermato',metodo_lettura='manuale',fonte_documentale='certificato')
        self.db.add(value)
        self.db.commit()
        self.apply({'notes':{'nota_rohs':{'page_id':None,'source_page_status':'da_verificare','snippet':'new','final':'false'}}})
        self.db.refresh(value)
        self.assertEqual(value.valore_finale,'true')
        self.assertEqual(value.stato,'confermato')
        self.assertEqual(self.db.query(DocumentEvidence).count(),0)


if __name__ == '__main__':
    unittest.main()
