import json
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import patch

from app.modules.acquisition import service as s
from app.modules.acquisition.metalba_packing import MetalbaPackingReviewRequired, number, reconstruct_rows
from app.modules.acquisition.metalba_packing_review import printed_packages, printed_summary, zoom_box
from app.modules.document_reader.service import _extract_metalba_candidate_weight
from app.modules.acquisition.models import Document, DocumentPage
import test_metalba_packing as packing_tests


def doc(weights=("1.071,00", "540,00", "272,00"), casts=("26268A",) * 3):
    return dict(ddt_number_raw="DDT26-03804", rows=[dict(row_index=1, net_weight_raw="1.883")],
                pages_read=[1, 2], packing_list_present=True, packing_totals=dict(
                    net_weight_raw="1.883,00", package_count_raw="3", pieces_raw="21"),
                packages=[dict(page_number=2, packing_row_index=i, material_row_index=1,
                               package_id_raw=f"TK262123{i}", pieces_raw=pieces,
                               net_weight_raw=w, colata_raw=c) for i, (w, c, pieces)
                          in enumerate(zip(weights, casts, (14, 7, 7)), 1)])


class MetalbaFocusedReviewTest(TestCase):
    def run_reader(self, first, second=None, witness=None):
        values = [NS(status="completed", output_text=json.dumps(v)) for v in (first, second) if v]
        crops = {str(i): dict(page_number=i, storage_key=f"p{i}") for i in (1, 2)}
        with patch.object(s, "_make_openai_client", return_value=NS()), \
             patch.object(s, "_resolve_storage_path", return_value=NS(read_bytes=lambda:b"fixture")), \
             patch.object(s, "_create_openai_response", side_effect=values) as self.call:
            return s._extract_metalba_ddt_row_groups_from_openai(crops, openai_api_key="unused",
                       packing_expected=True, printed_packages=witness)[1]

    def test_nonblocking_pieces_no_retry(self):
        r = self.run_reader(doc())
        self.assertEqual([(x["colata_raw"], x["net_weight_raw"], x["packing_piece_discrepancy"]) for x in r],
                         [("26268A","1883",True)])
        self.assertEqual(self.call.call_count, 1)

    def test_annotated_ocr_uses_right_columns_not_gross_or_pieces(self):
        line = "TK2621231 stuff 2944 1.071,00 1.080,00 14,00 26268A"
        key = (2,"TK2621231")
        self.assertEqual(printed_packages([(2,[line, line, "TOTALI: 1.883,00", "TK12345 partial"])]),
                         {key: (Decimal(1071),"26268A")})
        self.assertEqual(printed_packages([(2,[line,line.replace("26268A","262688")])]), {})
        for v in ("2944 540,00","540 00","2944 1.071,00","14 pezzi","540,00 547,00"):
            self.assertIsNone(number(v),v)
        self.assertEqual(number("1 071,00 kg"), 1071)

    def test_fallback_weight_after_label_not_number_of_packages(self):
        self.assertEqual(_extract_metalba_candidate_weight(["NR. COLLI : 3 TOTALI: 1.883,00 1.902,00 21,00"]), "1883")
        self.assertEqual(_extract_metalba_candidate_weight(["PESO NETTO KG 5466"]), "5466")
        self.assertIsNone(_extract_metalba_candidate_weight(["NR. COLLI: 3 TOTALI:"]))
        self.assertIsNone(_extract_metalba_candidate_weight(["PESO NETTO KG 2944 540,00"]))

    def test_ambiguous_ai_separator_needs_independent_count_and_weight(self):
        source="NR. COLLI: 3 TOTALI: 1.883,00 1.902,00 21,00"
        summary=printed_summary([(2,[source,source])])
        self.assertEqual(summary,(3,1883))
        self.assertIsNone(printed_summary([(2,[source,source.replace("1.883","1.882")])]))
        p=doc()
        for value in ("1,883","1,883.00"):
            p["rows"][0]["net_weight_raw"]=p["packing_totals"]["net_weight_raw"]=value
            self.assertEqual(reconstruct_rows(p,printed_summary=summary)[0]["net_weight_raw"],"1883")
        p["rows"][0]["net_weight_raw"]="1,883"
        for wrong in (None,(2,1883),(3,1882)):
            with self.assertRaises(MetalbaPackingReviewRequired): reconstruct_rows(p,printed_summary=wrong)
        p["rows"][0]["net_weight_raw"]="1,882"
        with self.assertRaises(MetalbaPackingReviewRequired): reconstruct_rows(p,printed_summary=summary)
        self.assertEqual(number("1,883"),Decimal("1.883"))  # No global reinterpretation.

    def test_single_ocr_error_triggers_blind_retry_not_automatic_cast_change(self):
        w = {(2,"TK2621231"): (Decimal(1071),"262688")}
        r = self.run_reader(doc(),doc(),w)
        self.assertEqual([(v["colata_raw"],v["net_weight_raw"]) for v in r],[("26268A","1883")])
        second = self.call.call_args.kwargs["input"][0]["content"][-1]["text"]
        self.assertIn("TK2621231", second); self.assertIn("colata", second)
        self.assertNotIn("262688", second); self.assertNotIn("26268A", second)
        self.assertEqual(self.call.call_count,2)
        third = doc(casts=("26268X","26268A","26268A"))
        with self.assertRaises(MetalbaPackingReviewRequired): self.run_reader(doc(),third,w)
        lost = doc(); lost["packages"][0]["package_id_raw"]="TK2629999"
        with self.assertRaises(MetalbaPackingReviewRequired): self.run_reader(doc(),lost,w)

    def test_agreement_on_two_real_casts_never_merges_their_weights(self):
        second=doc(casts=("262688","26268A","26268A"))
        w = {(2,"TK2621231"): (Decimal(1071),"262688")}
        r=self.run_reader(doc(),second,w)
        self.assertEqual({x["colata_raw"]:x["net_weight_raw"] for x in r},{"262688":"1071","26268A":"812"})

    def test_sum_failure_with_bad_ocr_on_an_independent_cast(self):
        first=doc(weights=("1.071,00","541,00","272,00"))
        w={(2,"TK2621231"):(Decimal(1071),"262688")}
        self.assertEqual(self.run_reader(first,doc(),w)[0]["net_weight_raw"],"1883")
        reason=self.call.call_args.kwargs["input"][0]["content"][-1]["text"]
        self.assertIn("1884",reason); self.assertIn("1883",reason)

    def test_specific_missing_field_and_unresolved_case_stops_after_two_calls(self):
        for field, val, message in [("colata_raw",None,"colata"),("net_weight_raw","2944 540,00","peso netto")]:
            bad=doc(); bad["packages"][1][field]=val
            with self.assertRaises(MetalbaPackingReviewRequired) as failure: self.run_reader(bad,bad)
            self.assertIn("TK2621232",failure.exception.detail); self.assertIn(message,failure.exception.detail)
            self.assertEqual(self.call.call_count,2)
        w={(2,"TK2621232"):(Decimal(540),"26268A")}
        bad=doc(); bad["packages"][1]["colata_raw"]=None
        swapped=doc(); swapped["packages"][1]["package_id_raw"]="TK2629999"
        with self.assertRaises(MetalbaPackingReviewRequired): self.run_reader(bad,swapped,w)

    def test_zoom_keeps_entire_width_and_uses_real_row_position(self):
        words=[dict(text=t,top=y,bottom=y+10) for t,y in
               [("NETTO",100),("TK2621231",400),("TK2621232",440),("TOTALI",500)]]
        self.assertEqual(zoom_box(words,1300,700,"TK2621231"),(0,380,1300,430))
        self.assertEqual(zoom_box(words,1300,700),(0,80,1300,530))
        self.assertIsNone(zoom_box([],1300,700))

    def test_reported_case_rows_and_competing_certificates_in_isolated_db(self):
        # Production grouping + Incoming creation + match scoring. No pen-written CDQ
        # or certificate number is supplied by the DDT. Same-cast alternatives exist.
        cases = [("26-03705", "305/26", "58", "26281B", [879,879,880,879,879,1070],
                  "5,466", "5.466,00", ["26-2864", "26-2867", "320/26", "57", "3267"]),
                 ("26-03804", "308/26", "78", "26268A", [1071,540,272],
                  "1.883", "1.883,00", ["26-2944", "26-2943", "307/26", "50", "2645"])]
        for ddt, order, dia, heat, weights, header, net, (right, wrong, order2, dia2, kg2) in cases:
            f = packing_tests.MetalbaPackingIntegrationTest()
            f.setUp()
            try:
                kg = str(sum(weights))
                p = doc(tuple(str(x) for x in weights), (heat,)*len(weights))
                p["packages"] = [dict(p["packages"][0], package_id_raw=f"TK262000{i}",
                    packing_row_index=i, net_weight_raw=str(w)) for i,w in enumerate(weights,1)]
                p["packing_totals"].update(net_weight_raw=net,package_count_raw=len(weights))
                p["rows"][0].update(net_weight_raw=header,vs_rif_raw=order,diameter_raw=dia,alloy_raw="6082F F")
                p["ddt_number_raw"]="DDT"+ddt
                d,raw=s._parse_openai_json_payload_for_metalba_row_groups(json.dumps(p),expected_pages={1,2},
                    packing_expected=True,printed_summary=(len(weights),Decimal(kg)))
                candidates=s._sanitize_metalba_ai_row_groups(ddt_number_raw=d,raw_rows=raw)
                with patch.object(s,"_ensure_document_page_images",return_value=f.ddt), \
                     patch.object(s,"_extract_supplier_ddt_row_groups_with_vision",return_value=candidates):
                    rows,created=s._ensure_autonomous_rows_with_ai(f.db,ddt_document=f.ddt,actor_id=1,
                        actor_email="packing@example.invalid",openai_api_key="unused",run_id=101)
                    self.assertEqual((created,len(rows),rows[0].peso,rows[0].colata),(1,1,kg,heat))
                for cdq,ord_,di,weight in [(right,order,dia,kg),(wrong,order2,dia2,kg2)]:
                    cert=Document(tipo_documento="certificato",nome_file_originale=cdq+".pdf",
                                  storage_key=cdq+".pdf",fornitore_id=f.supplier.id)
                    f.db.add(cert);f.db.flush()
                    f.db.add(DocumentPage(document_id=cert.id, numero_pagina=1))
                    f.db.commit()
                    cache={cert.id:dict(supplier_fields={"ordine_cliente":ord_},match_values=dict(
                        lega_certificato="6082F F",diametro_certificato=di,colata_certificato=heat,
                        peso_certificato=weight,numero_certificato_certificato=cdq))}
                    score=s._score_certificate_candidate(f.db,row=rows[0],certificate_document=cert,
                        ddt_certificate_number=None,row_ddt_values={"vs_rif":order},certificate_ai_cache=cache,ai_only_mode=True)
                    self.assertEqual(score is not None,cdq==right,(ddt,cdq))
            finally:
                f.tearDown()
