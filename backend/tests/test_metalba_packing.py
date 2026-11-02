import copy
import json
import os
import unittest
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace as NS
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.core.departments.models import Department
from app.core.users.models import User
from app.modules.acquisition import service as s
from app.modules.acquisition.metalba_packing import (
    MetalbaPackingReviewRequired, number, reconstruct_rows, require_complete_pages,
)
from app.modules.acquisition.models import AcquisitionRow, Document, DocumentEvidence, DocumentPage, ReadValue
from app.modules.suppliers.models import Supplier


# Printed weights/casts/pieces of DDT26-03514, not the handwritten CDQs.
# Package IDs are anonymous fixtures; the last three packages are on page 3.
PRINTED = [
    ("26246A",545,13),("26246A",545,13),("26257A",837,20),("26257A",838,20),
    ("26257A",838,20),("26257A",837,20),("26257A",841,20),("26246A",548,13),
    ("26257A",758,18),("26258A",844,20),("26258A",844,20),("26258A",844,20),
    ("26258A",845,20),("26258A",845,20),("26258A",762,18),("26257A",840,20),
    ("26257A",842,20),("26257A",841,20),("26257A",840,20),("26258A",847,20),
    ("26258A",847,20),("26258A",847,20),("26258A",847,20),("26257A",843,20),
    ("26258A",846,20),("26257A",799,19),("26246A",505,12),("26258A",760,18),
]


def fixture():
    return dict(ddt_number_raw="DDT26-03514", pages_read=[1,2,3], packing_list_present=True,
        rows=[dict(row_index=1, vs_rif_raw="296/26", rif_ord_raw="26/1663", article_code_raw="BTE(KG)",
                   product_description_raw="ESTRUSO A.A. 2014 F BARRA TONDA DIAM 65 mm",
                   customer_code_raw="A210650", length_raw="4.500 mm", alloy_raw="2014 F", diameter_raw="65 mm",
                   net_weight_raw="22.075,00", colata_raw=None, source_crops=["page1_row_groups_page"])],
        packages=[dict(material_row_index=1, package_id_raw=f"TKTEST{i:03}", colata_raw=cast,
                       net_weight_raw=str(weight), pieces_raw=str(pieces), page_number=2 if i<=25 else 3,
                       packing_row_index=i if i<=25 else i-25)
                  for i,(cast,weight,pieces) in enumerate(PRINTED,1)],
        packing_totals=dict(net_weight_raw="22.075,00", pieces_raw="524,00", package_count_raw="28"))


def candidates(payload=None):
    ddt, rows = s._parse_openai_json_payload_for_metalba_row_groups(
        json.dumps(payload or fixture()), expected_pages={1,2,3}, packing_expected=True)
    return s._sanitize_metalba_ai_row_groups(ddt_number_raw=ddt, raw_rows=rows)


class MetalbaPackingTest(unittest.TestCase):
    def test_printed_three_page_case_totals(self):
        values = candidates()
        self.assertEqual({c.colata:c.peso_netto for c in values}, {"26246A":"2143","26257A":"9954","26258A":"9978"})
        self.assertEqual(sum(Decimal(c.peso_netto) for c in values), Decimal(22075))
        self.assertEqual(sum(len(json.loads(c.ai_row_payload_raw)["packing_packages"]) for c in values), 28)
        self.assertEqual({c.customer_order_no for c in values}, {"296/26"})
        self.assertTrue(all(json.loads(c.ai_row_payload_raw)["packing_cast_count"]==3 for c in values))

    def assert_bad(self, p):
        with self.assertRaises(MetalbaPackingReviewRequired):
            reconstruct_rows(p, expected_pages={1,2,3}, packing_expected=True)

    def test_missing_page_or_last_packages_never_become_one_total(self):
        for change in (lambda p:p.update(pages_read=[1,2]),
                       lambda p:p.update(packages=p["packages"][:-3]),
                       lambda p:p.update(packing_list_present=False, packages=[]),
                       lambda p:p.update(packages=[])):
            p=fixture();change(p);self.assert_bad(p)

    def test_repeated_same_package_counts_once_not_same_weight(self):
        p=fixture();p["packages"].extend(copy.deepcopy(p["packages"][:3]))
        self.assertEqual(len(reconstruct_rows(p,expected_pages={1,2,3})),3)
        # Distinct IDs with identical weight already exist: 545 + 545 stays 1090.
        result=reconstruct_rows(p)
        self.assertEqual(result[0]["net_weight_raw"],"2143")

    def test_conflicting_duplicate_is_not_resolved_arbitrarily(self):
        p=fixture();duplicate=copy.deepcopy(p["packages"][0]);duplicate["net_weight_raw"]="546"
        p["packages"].append(duplicate);self.assert_bad(p)

    def test_missing_cast_bad_weight_missing_identity_and_ambiguous_row(self):
        for fields in (dict(colata_raw=None),dict(net_weight_raw="0"),dict(net_weight_raw="NaN"),
                       dict(package_id_raw=None,packing_row_index=None),dict(material_row_index=99),
                       dict(page_number=4),dict(pieces_raw="1.5")):
            p=fixture();p["packages"][0].update(fields);self.assert_bad(p)

    def test_counts_totals_and_piece_missing_are_checked(self):
        for key,value in (("package_count_raw","29"),("pieces_raw","525"),("net_weight_raw","22.076,00")):
            p=fixture();p["packing_totals"][key]=value;self.assert_bad(p)
        p=fixture();p["packages"][0]["pieces_raw"]=None;self.assert_bad(p)

    def test_no_residual_allocation_or_material_mix(self):
        p=fixture();p["packages"][0]["net_weight_raw"]="540";self.assert_bad(p)
        p=fixture();second=copy.deepcopy(p["rows"][0]);second.update(row_index=2,customer_code_raw="AOTHER",net_weight_raw="2143")
        p["rows"][0]["net_weight_raw"]="19932";p["rows"].append(second)
        for pack in p["packages"]:
            if pack["colata_raw"]=="26246A":pack["material_row_index"]=2
        result=reconstruct_rows(p,expected_pages={1,2,3})
        self.assertEqual(len(result),3)
        self.assertEqual(next(r["customer_code_raw"] for r in result if r["colata_raw"]=="26246A"),"AOTHER")
        p["packages"][0]["material_row_index"]=None;self.assert_bad(p)

    def test_printed_material_disagreements_are_rejected(self):
        for fields in (dict(customer_code_raw="AOTHER"),dict(vs_rif_raw="999/26"),dict(alloy_raw="7075 F"),
                       dict(diameter_raw="66 mm"),dict(length_raw="4600 mm"),dict(colata_raw="TOTALI")):
            p=fixture();p["packages"][0].update(fields);self.assert_bad(p)
        p=fixture();p["packages"][0].update(customer_code_raw="A210650",alloy_raw="2014 F",
                                         diameter_raw="65.000 mm",length_raw="4500 mm",vs_rif_raw="296/26")
        self.assertEqual(len(reconstruct_rows(p,expected_pages={1,2,3})),3)

    def test_same_cast_on_distinct_material_positions_is_not_merged(self):
        p=fixture();second=copy.deepcopy(p["rows"][0]);second.update(row_index=2,customer_code_raw="AOTHER",net_weight_raw="545")
        p["rows"].append(second);p["rows"][0]["net_weight_raw"]="21530"
        p["packages"][0]["material_row_index"]=2
        rows=reconstruct_rows(p,expected_pages={1,2,3})
        same_cast=[r for r in rows if r["colata_raw"]=="26246A"]
        self.assertEqual(len(same_cast),2)
        self.assertEqual({r["net_weight_raw"] for r in same_cast},{"545","1598"})

    def test_legacy_without_packing_keeps_optional_cast(self):
        p=fixture();p.update(packing_list_present=False,packages=[],packing_totals=None,pages_read=[1])
        rows=reconstruct_rows(p,expected_pages={1})
        self.assertEqual(rows[0]["net_weight_raw"],"22.075,00")
        self.assertIsNone(rows[0]["colata_raw"])
        old={"rows":[{"net_weight_raw":"1234","colata_raw":"26257A"}]}
        self.assertEqual(reconstruct_rows(old)[0]["colata_raw"],"26257A")

    def test_ordinary_positions_keep_their_identity_even_with_equal_material_values(self):
        p=fixture();p.update(packing_list_present=False,packages=[],packing_totals=None,pages_read=[1])
        second=copy.deepcopy(p["rows"][0]);second.update(row_index=2,customer_code_raw="AOTHER")
        p["rows"].append(second)
        rows=reconstruct_rows(p,expected_pages={1})
        self.assertEqual([r["commercial_row_index"] for r in rows],[1,2])
        self.assertNotEqual(s._metalba_packing_signature(rows[0]),s._metalba_packing_signature(rows[1]))

    def test_italian_decimals_and_invalid_inputs(self):
        for raw,expected in (("22.075,00","22075"),("9.954","9954"),("545,50","545.50"),
                             ("545.5 kg","545.5"),("0","0")):
            self.assertEqual(number(raw),Decimal(expected),raw)
        for raw in (True,"-1","NaN","1,2,3","1.2.34",None):self.assertIsNone(number(raw),raw)

    def test_missing_images_stop_before_ai_and_other_page_counts_work(self):
        for count in (1,2,3,5):
            d=NS(numero_pagine=count,pages=[NS(numero_pagina=i,immagine_pagina_storage_key=f"{i}.png") for i in range(1,count+1)])
            require_complete_pages(d)
            d.pages[-1].immagine_pagina_storage_key=None
            with self.assertRaises(MetalbaPackingReviewRequired):require_complete_pages(d)

    def test_request_keeps_three_pages_and_retries_only_current_ddt_once(self):
        p=fixture();bad=copy.deepcopy(p);bad["packages"]=bad["packages"][:-3]
        crops={f"p{i}":dict(storage_key=f"p{i}.png",page_number=i) for i in (1,2,3)}
        responses=[NS(status="completed",output_text=json.dumps(value)) for value in (bad,p)]
        with patch.object(s,"_make_openai_client",return_value=NS()), \
             patch.object(s,"_resolve_storage_path",return_value=NS(read_bytes=lambda:b"fixture")), \
             patch.object(s,"_create_openai_response",side_effect=responses) as call:
            _, rows, _=s._extract_metalba_ddt_row_groups_from_openai(crops,openai_api_key="unused",packing_expected=True)
        self.assertEqual(call.call_count,2);self.assertEqual(len(rows),3)
        for args in call.call_args_list:
            self.assertEqual(sum(i["type"]=="input_image" for i in args.kwargs["input"][0]["content"]),3)

    def test_failed_semantic_retry_is_not_worker_retryable(self):
        p=fixture();p["packages"]=[]
        with patch.object(s,"_make_openai_client",return_value=NS()), \
             patch.object(s,"_resolve_storage_path",return_value=NS(read_bytes=lambda:b"fixture")), \
             patch.object(s,"_create_openai_response",return_value=NS(status="completed",output_text=json.dumps(p))) as call:
            with self.assertRaises(MetalbaPackingReviewRequired) as error:
                s._extract_metalba_ddt_row_groups_from_openai({"p1":dict(storage_key="p1",page_number=1)},openai_api_key="unused")
        self.assertEqual(call.call_count,2)
        self.assertFalse(s._is_retryable_processing_error(error.exception))


class MetalbaPackingIntegrationTest(unittest.TestCase):
    def make_engine(self):
        return create_engine("sqlite:///:memory:")

    def setUp(self):
        self.engine=self.make_engine();Base.metadata.create_all(self.engine)
        # Mirror production SessionLocal, including relationship expiration on commit.
        self.db=sessionmaker(bind=self.engine,autoflush=False)()
        self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=101
        department=Department(name="QA",description="Isolated packing test")
        self.db.add(department);self.db.flush()
        self.db.add(User(id=1,name="QA",email="packing@example.invalid",role="admin",department_id=department.id))
        self.supplier=Supplier(ragione_sociale="Metalba S.p.A.",reader_template_key="metalba")
        self.db.add(self.supplier);self.db.flush()
        self.ddt=Document(tipo_documento="ddt",nome_file_originale="26-03514.pdf",storage_key="fixture-only.pdf",
                          fornitore_id=self.supplier.id,numero_pagine=3)
        self.db.add(self.ddt);self.db.flush()
        self.db.add_all([DocumentPage(document_id=self.ddt.id,numero_pagina=i,immagine_pagina_storage_key=f"page{i}.png") for i in (1,2,3)])
        self.db.commit()

    def tearDown(self):
        self.db.close();self.engine.dispose()

    def row(self,cast="26257A",weight="9954",cert=False):
        kwargs={"document_ddt_id":self.ddt.id}
        if cert:
            d=Document(tipo_documento="certificato",nome_file_originale="fixture-cert.pdf",
                       storage_key=f"cert-{self.db.query(Document).count()}.pdf",fornitore_id=self.supplier.id)
            self.db.add(d);self.db.flush();kwargs={"document_certificato_id":d.id}
            self.db.add(DocumentPage(document_id=d.id,numero_pagina=1))
        row=AcquisitionRow(fornitore_id=self.supplier.id,ordine="296/26",lega_base="2014 F",diametro="65",
                           peso=weight,colata=cast,ddt="26-03514",**kwargs)
        self.db.add(row);self.db.flush()
        block="match" if cert else "ddt"
        fields=({"ordine_cliente_certificato":"296/26","lega_certificato":"2014 F","diametro_certificato":"65",
                 "peso_certificato":weight,"colata_certificato":cast} if cert else
                {"ordine":"296/26","vs_rif":"296/26","lega":"2014 F","diametro":"65","peso":weight,"colata":cast})
        for field,value in fields.items():
            self.db.add(ReadValue(acquisition_row_id=row.id,blocco=block,campo=field,valore_grezzo=value,valore_finale=value,
                                  stato="proposto",metodo_lettura="chatgpt",fonte_documentale="certificato" if cert else "ddt"))
        self.db.commit();return s.get_acquisition_row(self.db,row.id)

    def test_forward_and_reverse_link_disambiguate_near_and_equal_weights(self):
        for weight in ("9978","9954"):
            a=self.row();b=self.row("26258A",weight)
            found=s._find_existing_metalba_row_for_certificate(rows=[a,b],customer_order="296/26",alloy="2014 F",diameter="65",weight="9954",cast="26257A")
            self.assertEqual(found.id,a.id)
        wrong=self.row("26258A","9978",cert=True);right=self.row(cert=True)
        c=next(c for c in candidates() if c.colata=="26257A")
        result=s._find_existing_certificate_first_row_for_split_candidate(self.db,rows=[wrong,right],document=self.ddt,
            candidate=c,fallback_ddt="26-03514",supplier_key="metalba")
        self.assertEqual(result.id,right.id)

    def test_cast_bonus_never_weakens_previous_material_requirements(self):
        row=self.row()
        self.assertIsNone(s._find_existing_metalba_row_for_certificate(rows=[row],customer_order="296/26",
            alloy=None,diameter=None,weight=None,cast="26257A"))
        cert=self.row(cert=True);candidate=candidates()[1]
        candidate.lega=None;candidate.diametro=None;candidate.peso_netto=None
        self.assertIsNone(s._find_existing_certificate_first_row_for_split_candidate(self.db,rows=[cert],
            document=self.ddt,candidate=candidate,fallback_ddt="26-03514",supplier_key="metalba"))

    def test_initial_scoring_rejects_wrong_cast_and_preview_does_too(self):
        a=self.row();b=self.row("26258A","9978",cert=True)
        cache={b.document_certificato_id:{"match_values":{"numero_certificato_certificato":"26-2729",
            "lega_certificato":"2014 F","diametro_certificato":"65","peso_certificato":"9978","colata_certificato":"26258A"},
            "supplier_fields":{"ordine_cliente":"296/26"}}}
        result=s._score_certificate_candidate(self.db,row=a,certificate_document=b.certificate_document,
            ddt_certificate_number=None,row_ddt_values={"vs_rif":"296/26"},certificate_ai_cache=cache,ai_only_mode=True)
        self.assertIsNone(result)
        self.assertIsNone(s._score_ddt_link_candidate_from_certificate_row(candidate_row=a,certificate_row=b,
            supplier_key="metalba",certificate_supplier_fields={"ordine_cliente":"296/26"}))

    def test_saved_source_cast_does_not_come_from_other_document(self):
        a=self.row();a.document_certificato_id=self.row(cert=True).document_certificato_id
        value=next(v for v in a.values if v.campo=="colata");value.metodo_lettura="sistema"
        self.db.commit();self.assertIsNone(s._metalba_source_cast(a))
        self.db.add(DocumentEvidence(document_id=self.ddt.id,acquisition_row_id=a.id,blocco="ddt",tipo_evidenza="ai_payload",
            metodo_estrazione="chatgpt",testo_grezzo=json.dumps({"colata_raw":"26257A","packing_list_present":True})))
        self.db.commit();self.db.expire(a,["evidences"])
        self.assertEqual(s._metalba_source_cast(a),"26257A")

    def test_manual_and_validated_values_are_not_overwritten(self):
        a=self.row();value=next(v for v in a.values if v.campo=="colata")
        value.stato="confermato";value.metodo_lettura="manuale";self.db.commit()
        c=next(c for c in candidates() if c.colata=="26258A")
        s._apply_metalba_ai_candidate_to_row(self.db,row=a,ai_candidate=c,actor_id=1,document_id=self.ddt.id)
        self.db.refresh(value);self.assertEqual(value.valore_finale,"26257A")
        a.validata_finale=True;self.db.commit();before=self.db.query(DocumentEvidence).count()
        self.assertFalse(s._apply_metalba_ai_candidate_to_row(self.db,row=a,ai_candidate=c,actor_id=1,document_id=self.ddt.id))
        self.assertEqual(self.db.query(DocumentEvidence).count(),before)

    def test_ambiguous_existing_siblings_are_not_reassigned_by_id(self):
        a=self.row(None,"9954");b=self.row(None,"9954")
        values=candidates()[1:];values[1].peso_netto="9954"
        with patch.object(s,"_apply_metalba_ai_candidate_to_row") as apply:
            result=s._apply_metalba_ai_row_groups_to_rows(self.db,ddt_document=self.ddt,rows=[a,b],ai_candidates=values,actor_id=1)
        self.assertEqual(result,0);apply.assert_not_called()

    def test_same_cast_and_weight_different_positions_keep_separate_signatures(self):
        a=candidates()[0];b=a.model_copy(deep=True)
        raw=json.loads(b.ai_row_payload_raw);raw["commercial_row_index"]=2;raw["customer_code_raw"]="AOTHER"
        b.ai_row_payload_raw=json.dumps(raw)
        sig=lambda c:s._split_candidate_signature_from_candidate(document=self.ddt,candidate=c,fallback_ddt=None)
        self.assertNotEqual(sig(a),sig(b))

    def test_session_reuses_only_complete_checked_reading(self):
        values=candidates()
        with patch.object(s,"_ensure_document_page_images",return_value=self.ddt), \
             patch.object(s,"_build_metalba_ddt_group_crops",return_value={"p1":{}}), \
             patch.object(s,"prepare_document_for_reader"), \
             patch.object(s,"build_document_row_split_plan",return_value=NS(row_split_candidates=[])), \
             patch.object(s,"_extract_metalba_ddt_row_groups_from_openai",return_value=("DDT26-03514",reconstruct_rows(fixture()),"{}")) as read:
            first=s._extract_metalba_ddt_row_groups_with_vision(self.db,ddt_document=self.ddt,openai_api_key="unused")
            first[0].colata="CHANGED"
            second=s._extract_metalba_ddt_row_groups_with_vision(self.db,ddt_document=self.ddt,openai_api_key="unused")
        self.assertEqual(read.call_count,1);self.assertEqual(second[0].colata,values[0].colata)

    def test_multicast_row_requires_certificate_cast_but_legacy_row_does_not(self):
        a=self.row();b=self.row(cert=True)
        payload={"match_values":{"numero_certificato_certificato":"26-2728","lega_certificato":"2014 F",
            "diametro_certificato":"65","peso_certificato":"9954"},"supplier_fields":{"ordine_cliente":"296/26"}}
        def score():return s._score_certificate_candidate(self.db,row=a,certificate_document=b.certificate_document,
            ddt_certificate_number=None,row_ddt_values={"vs_rif":"296/26"},certificate_ai_cache={b.document_certificato_id:payload},ai_only_mode=True)
        self.assertIsNotNone(score())
        self.db.add(DocumentEvidence(document_id=self.ddt.id,acquisition_row_id=a.id,blocco="ddt",tipo_evidenza="ai_payload",
            metodo_estrazione="chatgpt",testo_grezzo=json.dumps({"packing_cast_count":3,"packing_list_present":True})))
        self.db.commit();self.db.expire(a,["evidences"])
        self.assertIsNone(score())

    def test_creation_from_one_ddt_creates_three_rows_and_retry_no_duplicates(self):
        with patch.object(s,"_ensure_document_page_images",return_value=self.ddt), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates()) as read:
            rows,created=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
            self.assertEqual(created,3)
            self.assertEqual({r.colata:r.peso for r in rows},{"26246A":"2143","26257A":"9954","26258A":"9978"})
            for row in rows:
                candidate=next(c for c in candidates() if c.colata==row.colata)
                self.assertEqual(s._split_candidate_signature_from_row(row),
                    s._split_candidate_signature_from_candidate(document=self.ddt,candidate=candidate,fallback_ddt=None))
                self.assertEqual(s._metalba_packing_evidence(row)["packing_cast_count"],3)
                evidence=next(e for e in row.evidences if e.tipo_evidenza=="ai_payload")
                self.assertEqual(evidence.document_page.numero_pagina,2)
            repeated,count=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        self.assertEqual(len(repeated),3);self.assertEqual(count,0);self.assertEqual(read.call_count,1)

    def test_certificates_first_link_to_right_cast_without_new_rows(self):
        existing={cast:self.row(cast,weight,cert=True) for cast,weight in
                  (("26258A","9978"),("26246A","2143"),("26257A","9954"))}
        with patch.object(s,"_ensure_document_page_images",return_value=self.ddt), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates()):
            rows,count=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        self.assertEqual(len(rows),3)
        self.assertEqual(self.db.query(AcquisitionRow).count(),3)
        for row in rows:
            self.assertEqual(row.id,existing[row.colata].id)
            self.assertEqual(s._metalba_source_cast(row),row.colata)

    def test_ddt_first_then_three_certificates_link_without_orphan_rows(self):
        with patch.object(s,"_ensure_document_page_images",return_value=self.ddt), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates()):
            s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        docs=[];cache={}
        for i,(cast,weight) in enumerate((("26258A","9978"),("26257A","9954"),("26246A","2143"))):
            d=Document(tipo_documento="certificato",nome_file_originale=f"c{i}.pdf",storage_key=f"c{i}.pdf",fornitore_id=self.supplier.id)
            self.db.add(d);self.db.flush();docs.append(d)
            self.db.add(DocumentPage(document_id=d.id,numero_pagina=1,testo_estratto=""))
            cache[d.id]={"match_values":{"numero_certificato_certificato":f"26-272{i}","ordine_cliente_certificato":"296/26",
                "lega_certificato":"2014 F","diametro_certificato":"65","colata_certificato":cast,"peso_certificato":weight},
                "supplier_fields":{"ordine_cliente":"296/26"}}
        self.db.commit()
        with patch.object(s,"prepare_document_for_reader",side_effect=lambda db,doc:doc), \
             patch.object(s,"_get_supplier_certificate_ai_payload",side_effect=lambda **kw:cache[kw["certificate_document"].id]), \
             patch.object(s,"_process_certificate_side_blocks",side_effect=lambda **kw:kw["row"]):
            created,linked=s._ensure_certificate_first_rows(self.db,certificate_documents=docs,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",use_ai_intervention=True,
                run_id=101,certificate_ai_cache=cache)
        self.assertEqual((created,linked),(0,3));self.assertEqual(self.db.query(AcquisitionRow).count(),3)
        for row in self.db.query(AcquisitionRow).all():
            self.assertEqual(row.colata,cache[row.document_certificato_id]["match_values"]["colata_certificato"])

    def test_manual_document_is_never_reread_or_expanded(self):
        from app.modules.acquisition.manual_document_protection import mark_manual_entry
        a=self.row();mark_manual_entry(self.db,self.ddt,actor_id=1);self.db.commit()
        with patch.object(s,"_extract_supplier_ddt_row_groups_with_vision") as read:
            rows,count=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        self.assertEqual([r.id for r in rows],[a.id]);self.assertEqual(count,0);read.assert_not_called()

    def test_resume_interrupted_save_uses_saved_groups_and_repairs_partial_row(self):
        original=s._apply_supplier_ai_candidate_to_row
        calls=[]
        def fail_second(**kw):
            calls.append(kw["row"].id)
            if len(calls)==2:raise RuntimeError("simulated save interruption after row commit")
            return original(**kw)
        def ensure():return s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
            actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        with patch.object(s,"_ensure_document_page_images",return_value=self.ddt), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates()) as read:
            with patch.object(s,"_apply_supplier_ai_candidate_to_row",side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError,"save interruption"):ensure()
            self.db.rollback()
            self.assertEqual(self.db.query(AcquisitionRow).count(),2)
            rows,count=ensure()
        self.assertEqual((len(rows),count),(3,1))
        self.assertEqual(read.call_count,1)
        self.assertEqual(self.db.query(AcquisitionRow).count(),3)
        self.assertEqual({r.colata:r.peso for r in rows},{"26246A":"2143","26257A":"9954","26258A":"9978"})

    def test_reading_survives_restart_before_first_row_is_saved(self):
        with patch.object(s,"_ensure_document_page_images",side_effect=lambda db,doc:doc), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates()) as read:
            with patch.object(s,"create_acquisition_row",side_effect=RuntimeError("row store unavailable")):
                with self.assertRaises(RuntimeError):
                    s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                        actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
            self.db.rollback();self.assertEqual(self.db.query(AcquisitionRow).count(),0)
            document_id=self.ddt.id
            self.db.close()
            self.db=sessionmaker(bind=self.engine,autoflush=False)()
            self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=101
            self.ddt=self.db.get(Document,document_id)
            rows,count=s._ensure_autonomous_rows_with_ai(self.db,ddt_document=self.ddt,actor_id=1,
                actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
        self.assertEqual((len(rows),count),(3,3));self.assertEqual(read.call_count,1)

    def test_display_alloy_interpretation_does_not_change_saved_material_identity(self):
        row=self.row();candidate=candidates()[1]
        raw=json.loads(candidate.ai_row_payload_raw)
        self.db.add(DocumentEvidence(document_id=self.ddt.id,acquisition_row_id=row.id,blocco="ddt",tipo_evidenza="ai_payload",
            metodo_estrazione="chatgpt",testo_grezzo=json.dumps(raw)))
        value=next(v for v in row.values if v.campo=="lega")
        value.valore_grezzo="2014 F";value.valore_finale="DISPLAY ONLY";value.metodo_lettura=s.METALBA_LST03_METHOD
        row.lega_base="DISPLAY ONLY";self.db.commit()
        self.assertEqual(s._split_candidate_signature_from_row(row),s._split_candidate_signature_from_candidate(
            document=self.ddt,candidate=candidate,fallback_ddt=None))


@unittest.skipUnless(os.environ.get("CERTI_AI_REUSE_TEST_DATABASE_URL"), "disposable local PostgreSQL URL required")
class MetalbaPackingPostgresTest(MetalbaPackingIntegrationTest):
    def make_engine(self):
        url=make_url(os.environ["CERTI_AI_REUSE_TEST_DATABASE_URL"])
        if url.host not in {"127.0.0.1","localhost"} or url.port!=55439 or url.database!="certi_ai_reuse":
            raise RuntimeError("Refusing non-disposable database")
        self.admin=create_engine(url)
        self.schema="metalba_packing_"+uuid4().hex
        with self.admin.begin() as conn:conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        engine=create_engine(url)
        @event.listens_for(engine,"connect")
        def use_schema(connection,_):
            cursor=connection.cursor();cursor.execute(f'SET search_path TO "{self.schema}"')
            connection.commit();cursor.close()
        return engine

    def tearDown(self):
        super().tearDown()
        assert self.schema.startswith("metalba_packing_") and len(self.schema)==48
        with self.admin.begin() as conn:conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin.dispose()

    def test_two_workers_read_and_create_same_ddt_only_once(self):
        doc_id=self.ddt.id
        entered,release,second_started=Event(),Event(),Event()
        def reading(**kwargs):
            entered.set()
            if not release.wait(10):raise RuntimeError("Test reader was not released")
            return candidates()
        def worker(second=False):
            with sessionmaker(bind=self.engine,autoflush=False)() as db:
                db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=101
                doc=db.get(Document,doc_id)
                if second:second_started.set()
                return s._ensure_autonomous_rows_with_ai(db,ddt_document=doc,actor_id=1,
                    actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)[1]
        with patch.object(s,"_ensure_document_page_images",side_effect=lambda db,doc:doc), \
             patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",side_effect=reading) as read:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(worker)
                self.assertTrue(entered.wait(10))
                second=pool.submit(worker,True)
                self.assertTrue(second_started.wait(10))
                release.set()
                self.assertEqual(sorted([first.result(timeout=20),second.result(timeout=20)]),[0,3])
        self.db.expire_all()
        self.assertEqual(self.db.query(AcquisitionRow).count(),3)
        self.assertEqual(read.call_count,1)


if __name__=="__main__":unittest.main()
