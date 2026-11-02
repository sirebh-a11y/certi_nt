import copy
import json
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import patch

from app.startup import bootstrap  # noqa: F401
from app.modules.acquisition import service as s
from app.modules.acquisition.ddt_packing import (
    DdtPackingReviewRequired, component_total, validate_reading_contract,
    require_complete_pages, unique_page_crops,
)
from app.modules.acquisition.models import AcquisitionRow, Document, DocumentPage, DocumentEvidence, ReadValue
from app.modules.document_reader import service as reader
from app.modules.document_reader.schemas import ReaderRowSplitCandidateResponse as C
import test_metalba_packing as metalba_tests


def doc(*texts, expected=None):
    return NS(id=999, numero_pagine=expected or len(texts), hash_file="fixture",
        pages=[NS(id=i, numero_pagina=i, testo_estratto=t, ocr_text=None,
                  immagine_pagina_storage_key=f"p{i}.png") for i, t in enumerate(texts, 1)])


def parts(*weights):
    return [dict(package_id_raw=f"HU-{i}", page_number=1, physical_row_index=i, net_weight_raw=w)
            for i, w in enumerate(weights, 1)]


def kety_row(weight="400", lot="10033541_22815", **extra):
    return dict(certificate_number_raw="10033541/25", lot_batch_raw=lot, heat_raw="25E-7871",
        alloy_raw="7150", temper_raw="F", diameter_raw="44", net_weight_raw=weight,
        customer_order_raw="296", source_crops=["page1_row_groups_page"], **extra)


def leicht(*pairs):
    return [C(candidate_index=i, supplier_key="leichtmetall", ddt_number="80008535", customer_order_no="296",
              colata=batch, cdq=batch, lega="2014", diametro="65", peso_netto=w)
            for i, (batch, w) in enumerate(pairs, 1)]


class DdtPackingChecksTest(unittest.TestCase):
    def test_full_pages_and_missing_or_repeated_page_index(self):
        require_complete_pages(doc("one", "two", "three"))
        for d in (doc("one", "two", expected=3), doc("one", "two"), doc("one", "two")):
            if d.numero_pagine == 2:
                if d.pages[0].numero_pagina == 1:
                    d.pages[1].numero_pagina = 1
            with self.assertRaises(DdtPackingReviewRequired):
                require_complete_pages(d)

    def test_all_other_suppliers_stop_before_ai_if_page_missing(self):
        for supplier in s.DDT_SAFE_SUPPLIERS - {"metalba", "leichtmetall"}:
            with self.subTest(supplier=supplier), patch.object(s, "_create_openai_response", side_effect=AssertionError("AI forbidden")):
                with self.assertRaises(DdtPackingReviewRequired):
                    getattr(s, f"_extract_{supplier}_ddt_row_groups_with_vision")(
                        NS(info={}), ddt_document=doc("one", "two", expected=3), openai_api_key="unused")

    def test_page_roles_sent_once_not_pages_removed(self):
        crops = {f"p{i}_{role}": dict(page_number=i, storage_key=f"page{i}.png", role=role)
                 for i in (1, 2, 3) for role in ("header_page", "row_groups_page")}
        unique = unique_page_crops(crops)
        self.assertEqual(list(unique), ["p1_row_groups_page", "p2_row_groups_page", "p3_row_groups_page"])
        self.assertEqual(unique_page_crops(unique), unique)

    def test_actual_other_supplier_requests_send_each_page_once(self):
        crops = {f"page{i}_{role}": dict(page_number=i, storage_key=f"p{i}.png", role=role)
                 for i in (1, 2, 3) for role in ("header_page", "row_groups_page")}
        payload = dict(ddt_number_raw="1234567", pages_read=[1, 2, 3],
            document_check=dict(detected_type="ddt", matches_assigned=True, evidence=[dict(page_number=1, quote="Delivery Note")]),
            rows=[dict(batch_raw="94668", lot_raw="11111", heat_raw="25E-7871", certificate_number_raw="10033541/25",
                       net_weight_raw="400", weight_components=parts("400"))])
        for supplier in sorted(s.DDT_SAFE_SUPPLIERS - {"metalba"}):
            with self.subTest(supplier=supplier), patch.object(s, "_make_openai_client", return_value=NS()), \
                 patch.object(s, "_resolve_storage_path", return_value=NS(read_bytes=lambda: b"isolated-image-fixture")), \
                 patch.object(s, "_create_openai_response", return_value=NS(status="completed", output_text=json.dumps(payload))) as request:
                getattr(s, f"_extract_{supplier}_ddt_row_groups_from_openai")(crops, openai_api_key="unused")
                contents = request.call_args.kwargs["input"][0]["content"]
                self.assertEqual(sum(c["type"] == "input_image" for c in contents), 3)
                self.assertTrue(all(any(f"page_number: {i}" in c.get("text", "") for c in contents) for i in (1, 2, 3)))

    def test_components_deduplicate_ids_not_equal_weights(self):
        a = parts("400", "400")
        self.assertEqual(component_total([{"weight_components": a + copy.deepcopy(a)}]), "800")
        a[1].update(package_id_raw="HU-1", net_weight_raw="401")
        with self.assertRaises(DdtPackingReviewRequired):
            component_total([{"weight_components": a}])

    def test_components_positions_page_scope_and_conflicts(self):
        a = parts("400", "600")
        for row in a:
            row["package_id_raw"] = None
        a[1].update(page_number=2, physical_row_index=1)
        self.assertEqual(component_total([{"weight_components": a}]), "1000")
        a[1]["page_number"] = 1
        with self.assertRaises(DdtPackingReviewRequired):
            component_total([{"weight_components": a}])

    def test_new_live_contract_requires_coverage_and_components(self):
        p = {"pages_read": [1, 2, 3], "rows": [{"weight_components": parts("400")} ]}
        validate_reading_contract(json.dumps(p), {1, 2, 3})
        for altered in ({**p, "pages_read": [1, 2]}, {**p, "rows": []},
                        {**p, "rows": [{}]}, {**p, "rows": [{"weight_components": "bad"}]}):
            with self.assertRaises(DdtPackingReviewRequired):
                validate_reading_contract(json.dumps(altered), {1, 2, 3})
        p["document_net_weight_raw"] = "500"
        with self.assertRaises(DdtPackingReviewRequired):
            validate_reading_contract(json.dumps(p), {1, 2, 3})
        p["document_net_weight_raw"] = "400"
        validate_reading_contract(json.dumps(p), {1, 2, 3})

    def test_one_physical_package_cannot_belong_to_two_casts(self):
        p = dict(pages_read=[1], rows=[dict(batch_raw=b, weight_components=parts("400")) for b in ("94668", "94752")])
        with self.assertRaises(DdtPackingReviewRequired):
            validate_reading_contract(json.dumps(p), {1})

    def test_semantic_retry_is_bounded_and_not_worker_retryable(self):
        calls = []
        def _extract_neuman_fake(db, **kwargs):
            calls.append(1)
            raise DdtPackingReviewRequired("invalid detail")
        with self.assertRaises(DdtPackingReviewRequired) as exc:
            s._checked_supplier_ddt_read(_extract_neuman_fake)(NS(info={}), ddt_document=doc("one"), openai_api_key="unused")
        self.assertEqual(len(calls), 2)
        self.assertFalse(s._is_retryable_processing_error(exc.exception))

    def test_retry_can_succeed_without_affecting_other_documents(self):
        calls = []
        def _extract_grupa_kety_fake(db, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise DdtPackingReviewRequired("first incomplete")
            return ["checked"]
        result = s._checked_supplier_ddt_read(_extract_grupa_kety_fake)(NS(info={}), ddt_document=doc("one"), openai_api_key="unused")
        self.assertEqual((result, len(calls)), (["checked"], 2))

    def test_leichtmetall_no_residual_in_ai_or_local_reader(self):
        d = doc("Delivery Note 80008535\nQuantity: 1000 KG", "500 94668\n400 94669")
        with self.assertRaises(DdtPackingReviewRequired):
            s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=d, ai_candidates=leicht(("94668", None), ("94669", None)))
        local = reader._build_leichtmetall_row_split_candidates(d, "leichtmetall")
        self.assertEqual({c.colata: c.peso_netto for c in local}, {"94668": "500", "94669": "400"})

    def test_leichtmetall_complete_detail_repairs_split_without_last_wins(self):
        d = doc("Delivery Note 80008535\nQuantity: 300 KG", "100 94668\n200 94668")
        values = s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=d, ai_candidates=leicht(("94668", "100"), ("94668", "200")))
        self.assertEqual((len(values), values[0].peso_netto), (1, "300"))

    def test_leichtmetall_repeated_group_summary_does_not_double(self):
        values = s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=doc("Delivery Note"),
            ai_candidates=leicht(("94668", "300"), ("94668", "300")))
        self.assertEqual((len(values), values[0].peso_netto), (1, "300"))

    def test_leichtmetall_ai_complete_even_when_ocr_detail_incomplete(self):
        d = doc("Delivery Note 80008535\nQuantity: 1000 KG", "500 94668\n400 94669")
        values = s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=d, ai_candidates=leicht(("94668", "600"), ("94669", "400")))
        self.assertEqual([c.peso_netto for c in values], ["600", "400"])

    def test_leichtmetall_real_80008535_batch_totals_and_all_pages(self):
        d = doc("Delivery Note 80008535\nQuantity: 17,225 KG", "2000 94668\n6000 94752", "3014 94668\n6211 94752")
        values = s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=d, ai_candidates=leicht(("94668", None), ("94752", None)))
        self.assertEqual({c.colata: c.peso_netto for c in values}, {"94668": "5014", "94752": "12211"})

    def test_neuman_same_material_lot_sums_hus_once_across_rows(self):
        raw = [dict(lot_raw="11111", material_raw="2014", diameter_raw="65", article_number_raw="A210650",
                    customer_order_raw="296", net_weight_raw=w, weight_components=[part])
               for w, part in zip(("100", "200", "100"), parts("100", "200") + parts("100"))]
        values = s._sanitize_neuman_ai_row_groups(ddt_number_raw="1234567", raw_rows=raw, ai_document_payload_raw="{}")
        self.assertEqual((len(values), values[0].peso_netto, values[0].colata), (1, "300", "11111"))

    def test_neuman_different_material_same_lot_not_merged(self):
        raw = [dict(lot_raw="11111", material_raw="2014", diameter_raw=d, net_weight_raw="100", weight_components=parts("100")) for d in ("65", "70")]
        values = s._sanitize_neuman_ai_row_groups(ddt_number_raw="1234567", raw_rows=raw, ai_document_payload_raw="{}")
        self.assertEqual(len(values), 2)

    def test_neuman_legacy_single_group_preserved_not_reread(self):
        values = s._sanitize_neuman_ai_row_groups(ddt_number_raw="1234567", raw_rows=[dict(lot_raw="11111", net_weight_raw="300")], ai_document_payload_raw="{}")
        self.assertEqual(values[0].peso_netto, "300")
        with self.assertRaises(DdtPackingReviewRequired):
            s._sanitize_neuman_ai_row_groups(ddt_number_raw="1234567", raw_rows=[dict(lot_raw="11111", net_weight_raw=w) for w in ("100", "200")], ai_document_payload_raw="{}")

    def test_kety_repeated_same_sublot_once_equal_distinct_sublots_both(self):
        a = kety_row()
        b = kety_row(lot="10033541_22816")
        values = s._sanitize_grupa_kety_ai_row_groups(ddt_number_raw="12594", raw_rows=[a, copy.deepcopy(a), b])
        self.assertEqual((len(values), values[0].peso_netto), (1, "800"))

    def test_kety_components_and_conflicting_material_or_weight(self):
        a = kety_row(weight_components=parts("400"))
        values = s._sanitize_grupa_kety_ai_row_groups(ddt_number_raw="12594", raw_rows=[a, copy.deepcopy(a)])
        self.assertEqual(values[0].peso_netto, "400")
        for difference in (dict(diameter_raw="55"), dict(customer_order_raw="297"), dict(alloy_raw="2014")):
            b = kety_row("600", lot="10033541_22816");b.update(difference)
            with self.assertRaises(DdtPackingReviewRequired):
                s._sanitize_grupa_kety_ai_row_groups(ddt_number_raw="12594", raw_rows=[kety_row(), b])


class SupplierDdtRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = metalba_tests.MetalbaPackingIntegrationTest()
        self.fixture.setUp()
        self.db, self.ddt = self.fixture.db, self.fixture.ddt

    def tearDown(self):
        self.fixture.tearDown()

    def supplier(self, key):
        names = {"grupa_kety": "Grupa Kety S.A.", "neuman": "Neuman", "leichtmetall": "Leichtmetall", "impol": "Impol",
                 "aluminium_bozen": "Aluminium Bozen", "aww": "AWW", "arconic_hannover": "Arconic Hannover", "zalco": "Zalco"}
        self.fixture.supplier.ragione_sociale = names[key]
        self.fixture.supplier.reader_template_key = key
        self.db.commit()

    def candidates(self, key):
        # Keep each supplier's canonical fields; no matcher thresholds mocked.
        return [C(candidate_index=i, supplier_key=key, ddt_number=str(12594 + self.ddt.id * 10), customer_order_no="296",
                  lega="2014 F", diametro="65", colata=f"1234{i}", cdq=f"1234{i}", peso_netto=str(i * 100)) for i in (1, 2, 3)]

    def ensure(self, db=None):
        return s._ensure_autonomous_rows_with_ai(db or self.db, ddt_document=self.ddt, actor_id=1,
                    actor_email="packing@example.invalid", openai_api_key="unused", run_id=101)

    def test_all_other_suppliers_creation_and_retry_no_new_ai(self):
        for key in sorted(s.DDT_SAFE_SUPPLIERS - {"metalba"}):
            with self.subTest(key=key):
                self.supplier(key)
                # New isolated document per supplier, not a mutable historical one.
                d = Document(tipo_documento="ddt", nome_file_originale=f"{key}.pdf", storage_key=f"fixture-{key}.pdf",
                    fornitore_id=self.fixture.supplier.id, numero_pagine=3)
                self.db.add(d);self.db.flush()
                self.db.add_all(DocumentPage(document_id=d.id, numero_pagina=i, immagine_pagina_storage_key=f"p{i}.png") for i in (1, 2, 3))
                self.db.commit();self.ddt = d
                with patch.object(s, "_ensure_document_page_images", side_effect=lambda db, doc: doc), \
                     patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.candidates(key)) as read:
                    rows, count = self.ensure()
                    repeated, second = self.ensure()
                    self.assertEqual((len(rows), count, len(repeated), second, read.call_count), (3, 3, 3, 0, 1))
                    self.assertTrue(all(any(e.tipo_evidenza == "supplier_ddt_group_complete_v1" for e in r.evidences) for r in repeated))

    def test_partial_application_resumes_from_saved_reading_without_new_ai(self):
        self.supplier("grupa_kety")
        original = s._apply_supplier_ai_candidate_to_row
        calls = []
        def fail_second(**kwargs):
            calls.append(kwargs["row"].id)
            if len(calls) == 2:
                raise RuntimeError("save interrupted")
            return original(**kwargs)
        with patch.object(s, "_ensure_document_page_images", return_value=self.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.candidates("grupa_kety")) as read:
            with patch.object(s, "_apply_supplier_ai_candidate_to_row", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "save interrupted"):
                    self.ensure()
            self.db.rollback()
            self.assertEqual(self.db.query(AcquisitionRow).count(), 2)
            self.db.info.clear()
            self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = 101
            rows, count = self.ensure()
            self.assertEqual((len(rows), count, read.call_count), (3, 1, 1))
            self.assertTrue(all(any(e.tipo_evidenza == "supplier_ddt_group_complete_v1" for e in r.evidences) for r in rows))

    def test_reading_survives_failure_before_first_row_creation(self):
        self.supplier("neuman")
        with patch.object(s, "_ensure_document_page_images", return_value=self.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.candidates("neuman")) as read:
            with patch.object(s, "create_acquisition_row", side_effect=RuntimeError("before create")):
                with self.assertRaisesRegex(RuntimeError, "before create"):
                    self.ensure()
            self.db.rollback();self.db.info.clear()
            self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = 101
            rows, count = self.ensure()
            self.assertEqual((len(rows), count, read.call_count), (3, 3, 1))

    def test_distinct_products_same_lot_weight_and_diameter_keep_both_rows(self):
        self.supplier("neuman")
        a, b = self.candidates("neuman")[:2]
        b = a.model_copy(deep=True);b.candidate_index = 2
        a.article_code, b.article_code = "A210650", "A210651"
        with patch.object(s, "_ensure_document_page_images", return_value=self.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=[a, b]) as read:
            rows, count = self.ensure()
            again, second = self.ensure()
        self.assertEqual((len(rows), count, len(again), second, read.call_count), (2, 2, 2, 0, 1))

    def test_saved_reading_identity_changed_never_silently_reread(self):
        self.supplier("neuman")
        s._save_metalba_ddt_groups(self.db, self.ddt, self.candidates("neuman"), 1, "neuman")
        self.ddt.numero_pagine = 4;self.db.commit()
        with patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", side_effect=AssertionError("No reread")):
            with self.assertRaises(DdtPackingReviewRequired):self.ensure()

    def test_leichtmetall_preflight_persists_checked_reading_before_rows(self):
        from app.modules.acquisition import leichtmetall_type_workflow as workflow
        self.supplier("leichtmetall")
        check = dict(detected_type="ddt", matches_assigned=True, evidence=[dict(page_number=1, quote="Delivery Note")])
        raw_row = dict(batch_raw="94668", alloy_raw="2014 F", diameter_raw="65", net_weight_raw="400",
                       weight_components=parts("400"))
        raw = json.dumps(dict(document_check=check, pages_read=[1, 2, 3], rows=[raw_row]))
        with patch.object(s, "_ensure_document_page_images", return_value=self.ddt), \
             patch.object(s, "_build_leichtmetall_ddt_group_crops", return_value={"page1_row_groups_page": {}}), \
             patch.object(s, "_extract_leichtmetall_ddt_row_groups_from_openai", return_value=("80008535", [raw_row], raw)) as read:
            accepted, failed = workflow.preflight_documents(self.db, [self.ddt], explicit_ids={self.ddt.id},
                certificate_ai_cache={}, api_key="unused", actor_id=1, actor_email="packing@example.invalid")
            self.assertEqual((len(accepted), failed, read.call_count), (1, [], 1))
            self.db.info.clear()
            cached, cached_check = workflow.read_document(self.db, self.ddt, "ddt", "unused")
            self.assertEqual((cached[0].peso_netto, cached_check, read.call_count), ("400", check, 1))

    def test_legacy_existing_rows_without_manifest_not_expanded_or_reread(self):
        self.supplier("grupa_kety")
        self.fixture.row("12345", "400")
        with patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", side_effect=AssertionError("No historical AI")):
            rows, count = self.ensure()
        self.assertEqual((len(rows), count), (1, 0))
        self.assertEqual(self.db.query(DocumentEvidence).filter_by(tipo_evidenza="supplier_ddt_groups_v1").count(), 0)

    def test_manual_document_excluded_from_all_automatic_reading(self):
        from app.modules.acquisition.manual_document_protection import mark_manual_entry
        self.supplier("neuman")
        mark_manual_entry(self.db, self.ddt, actor_id=1);self.db.commit()
        with patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", side_effect=AssertionError("Manual AI forbidden")):
            self.assertEqual(self.ensure(), ([], 0))

    def test_manual_edit_protects_incomplete_automatic_rows(self):
        self.supplier("grupa_kety")
        with patch.object(s, "_ensure_document_page_images", return_value=self.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.candidates("grupa_kety")):
            original = s._apply_supplier_ai_candidate_to_row
            def fail(**kwargs):
                raise RuntimeError("incomplete")
            with patch.object(s, "_apply_supplier_ai_candidate_to_row", side_effect=fail):
                with self.assertRaises(RuntimeError):self.ensure()
            self.db.rollback()
            row = self.db.query(AcquisitionRow).first()
            row.validata_finale = True;self.db.commit()
            with self.assertRaises(DdtPackingReviewRequired):self.ensure()
            self.assertTrue(self.db.get(AcquisitionRow, row.id).validata_finale)


@unittest.skipUnless(os.environ.get("CERTI_AI_REUSE_TEST_DATABASE_URL"), "isolated PostgreSQL opt-in")
class SupplierDdtRecoveryPostgresTest(SupplierDdtRecoveryTest):
    def setUp(self):
        # Reuse the existing strict localhost:55439 allowlist and UUID schema.
        self.fixture = metalba_tests.MetalbaPackingPostgresTest()
        self.fixture.setUp()
        self.db, self.ddt = self.fixture.db, self.fixture.ddt

    def test_two_workers_one_read_per_non_metalba_ddt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from sqlalchemy.orm import sessionmaker
        self.supplier("grupa_kety")
        document_id = self.ddt.id
        entered, release, second_started = Event(), Event(), Event()
        def reading(**kwargs):
            entered.set()
            if not release.wait(10):raise RuntimeError("test release timeout")
            return self.candidates("grupa_kety")
        def worker(second=False):
            with sessionmaker(bind=self.fixture.engine, autoflush=False)() as db:
                db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = 101
                d = db.get(Document, document_id)
                if second:second_started.set()
                return s._ensure_autonomous_rows_with_ai(db, ddt_document=d, actor_id=1,
                    actor_email="packing@example.invalid", openai_api_key="unused", run_id=101)[1]
        with patch.object(s, "_ensure_document_page_images", side_effect=lambda db, doc: doc), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", side_effect=reading) as read:
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(worker);self.assertTrue(entered.wait(10))
                b = pool.submit(worker, True);self.assertTrue(second_started.wait(10));release.set()
                self.assertEqual(sorted([a.result(20), b.result(20)]), [0, 3])
            self.assertEqual(read.call_count, 1)
