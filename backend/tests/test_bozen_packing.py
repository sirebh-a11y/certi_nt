import copy
import json
import os
import unittest
from unittest.mock import patch

from app.startup import bootstrap  # register ORM models
from app.modules.acquisition import service as s
from app.modules.acquisition.models import AcquisitionRow, Document, DocumentPage
import test_ddt_packing_safety as safety


def row(cert="159629", package="01", net="373", **overrides):
    return dict(dict(packing_ref_raw="2611586.1", customer_order_raw="311 - 2026-10-01",
        article_code_raw="A622400", profile_code_raw="14BT307-B06", alloy_raw="6082/F",
        diameter_raw="240", cast_raw="926299A2", certificate_no_raw=cert,
        weight_components=[dict(package_id_raw=package, page_number=2,
                                physical_row_index=1, net_weight_raw=net)]), **overrides)


def parse(rows, **extra):
    payload = json.dumps(dict(ddt_number_raw="1612", pages_read=[1, 2, 3], rows=rows, **extra))
    no, raw, _ = s.read_bozen_packing_groups(payload, {1, 2, 3}, s._bozen_customer_order)
    return s._sanitize_aluminium_bozen_ai_row_groups(ddt_number_raw=no, raw_rows=raw, ai_document_payload_raw=payload)


class BozenPackingTests(unittest.TestCase):
    def test_1612_split_lengths_continuation_and_swapped_code_labels(self):
        a = row()
        b = row(package="02", net="1,716", customer_order_raw="2026-10-01 311",
                article_code_raw="14BT307-B06", profile_code_raw="A622400")
        b["weight_components"][0]["page_number"] = 3
        c, = parse([a, b, copy.deepcopy(b)], package_count=2, document_net_weight_raw="2,089")
        self.assertEqual((c.cdq, c.peso_netto, c.article_code, c.profile_code, c.customer_order_no),
                         ("159629", "2089", "14BT307-B06", "A622400", "311-2026-10-01"))

    def test_1383_identical_weight_distinct_packages(self):
        c, = parse([row(net="1,219"), row(package="02", net="1,219")], package_count=2)
        self.assertEqual(c.peso_netto, "2438")

    def test_keep_separate_for_each_material_anchor(self):
        for different in [dict(packing_ref_raw="2611586.2"), dict(customer_order_raw="312"),
                          dict(certificate_no_raw="159630"), dict(cast_raw="926299A3"), dict(diameter_raw="115"),
                          dict(alloy_raw="7075/F"), dict(profile_code_raw="14BT308-B06"), dict(article_code_raw="A622401")]:
            with self.subTest(different=different):
                self.assertEqual(len(parse([row(), row(package="02", **different)])), 2)

    def test_missing_conflicting_or_double_counted_details_refused(self):
        for rows, extra in [
            ([row(), row(cert="159630")], {}),
            ([row(), row(net="400")], {}),
            ([row(), row(package="02", cast_raw=None)], {}),
            ([row()], {"document_net_weight_raw":"400"}),
            ([row()], {"package_count":2}),
            ([row(weight_components=5)], {}),
            ([row(weight_components=[])], {}),
        ]:
            with self.subTest(extra=extra), self.assertRaises(s.DdtPackingReviewRequired):
                parse(rows, **extra)

    def test_clear_delivery_without_certificate_or_packing_does_not_invent_identity(self):
        c, = parse([row(cert=None, package=None, packing_ref_raw=None)])
        self.assertEqual((c.cdq, c.supplier_order_no, c.peso_netto), (None, None, "373"))

    def test_order_without_date_survives(self):
        c, = parse([row(customer_order_raw="Vs. Odv 312")])
        self.assertEqual(c.customer_order_no, "312")
        for raw, expected in (("312", "312"), ("Vs. Odv 312", "312"), ("Collo 312", None), (None, None)):
            parsed = s._sanitize_aluminium_bozen_vision_certificate_fields(
                {"customer_order_raw": {"value": raw, "evidence": "312"}})
            self.assertEqual(parsed["ordine_cliente_certificato"]["value"], expected)
        for other in ("313-2026-10-01", "312-2026-02-30", "312/26", "312", None):
            self.assertFalse(s.bozen_order_date_missing("312", other))

    def test_multiple_packages_in_one_ai_row_also_need_group_proof(self):
        unproven = row(cert=None)
        unproven["weight_components"] += row(package="02")["weight_components"]
        with self.assertRaises(s.DdtPackingReviewRequired):
            parse([unproven])


class BozenFlowTests(unittest.TestCase):
    fixture_type = safety.SupplierDdtRecoveryTest

    def setUp(self):
        self.fx = self.fixture_type()
        self.fx.setUp()
        self.addCleanup(self.fx.tearDown)
        self.fx.supplier("aluminium_bozen")
        self.db = self.fx.db
        # Different certificates, identical remaining anchors and net weights:
        # historically the generic DDT row signature would drop one group.
        self.cs = parse([row(), row(cert="159630", package="02")])
        self.docs, self.cache = [], {}
        for c in reversed(self.cs):
            d = Document(tipo_documento="certificato", nome_file_originale=c.cdq+".pdf", storage_key=c.cdq+".pdf",
                         fornitore_id=self.fx.ddt.fornitore_id)
            self.db.add(d)
            self.db.flush()
            self.db.add(DocumentPage(document_id=d.id, numero_pagina=1, testo_estratto=""))
            self.docs.append(d)
            self.cache[d.id] = {"match_values": {"numero_certificato_certificato": c.cdq,
                "colata_certificato": c.colata, "peso_certificato": c.peso_netto,
                "diametro_certificato": c.diametro, "lega_certificato": c.lega,
                "ordine_cliente_certificato": c.customer_order_no}, "supplier_fields": {
                    "article": c.article_code, "profile_code": c.profile_code,
                    "customer_order_normalized": c.customer_order_no}}
        self.db.commit()

    def certs(self, docs):
        with patch.object(s, "prepare_document_for_reader", side_effect=lambda db, doc: doc), \
             patch.object(s, "_get_supplier_certificate_ai_payload", side_effect=lambda **kw:self.cache[kw["certificate_document"].id]), \
             patch.object(s, "_process_certificate_side_blocks", side_effect=lambda **kw:kw["row"]):
            return s._ensure_certificate_first_rows(self.db, certificate_documents=docs, actor_id=1,
                actor_email="packing@example.invalid", openai_api_key="unused", use_ai_intervention=True,
                run_id=101, certificate_ai_cache=self.cache)

    def check_order(self, before):
        with patch.object(s, "_ensure_document_page_images", return_value=self.fx.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs) as read:
            if before:
                self.certs(self.docs[:before])
            self.fx.ensure()
            if before < 2:
                self.certs(self.docs[before:])
            rows, new = self.fx.ensure()
        self.assertEqual((len(rows), new, read.call_count, self.db.query(AcquisitionRow).count()), (2, 0, 1, 2))
        self.assertEqual({r.cdq:r.document_certificato_id for r in rows},
                         {c["match_values"]["numero_certificato_certificato"]:doc for doc,c in self.cache.items()})
        for r in rows:
            c = next(c for c in self.cs if c.cdq == r.cdq)
            self.assertEqual(s._autonomous_ddt_row_signature(r), s._autonomous_ddt_candidate_signature(
                document=self.fx.ddt, candidate=c, fallback_ddt=None))

    def test_ddt_first(self):
        self.check_order(0)

    def test_certificates_first(self):
        self.check_order(2)

    def test_interleaved_same_run(self):
        self.check_order(1)

    def order_flow(self, *, ddt_orders=("312",), cert_orders=("312-2026-10-01",),
                   certificate_first=False, expected=1, current_run=True, detach=False, cert_fields=None,
                   separate_deliveries=False):
        from app.modules.acquisition.models import ManualMatchBlock
        self.cs = parse([row(package=str(i+1), customer_order_raw=o, packing_ref_raw=f"2611586.{i+1}")
                         for i, o in enumerate(ddt_orders)])
        certs = self.docs[:len(cert_orders)]
        for doc, order in zip(certs, cert_orders):
            c = self.cs[0]
            values = dict(numero_certificato_certificato=c.cdq, colata_certificato=c.colata,
                lega_certificato=c.lega, diametro_certificato=c.diametro, peso_certificato=c.peso_netto,
                articolo_certificato=c.article_code, codice_cliente_certificato=c.profile_code,
                ordine_cliente_certificato=order)
            values.update(cert_fields or {})
            self.cache[doc.id] = {"match_values": values,
                "core_fields": {k: {"value": v, "evidence": v} for k,v in values.items()},
                "supplier_fields": {"customer_order_normalized": order, "article": values["articolo_certificato"],
                                    "profile_code": values["codice_cliente_certificato"]}}
        def read_certs():
            return s._ensure_certificate_first_rows(self.db, certificate_documents=certs, actor_id=1,
                actor_email="packing@example.invalid", openai_api_key="stub", use_ai_intervention=True,
                run_id=101, certificate_ai_cache=self.cache)
        with patch.object(s, "prepare_document_for_reader", side_effect=lambda db, doc: doc), \
             patch.object(s, "_get_supplier_certificate_ai_payload", side_effect=lambda **kw:self.cache[kw["certificate_document"].id]), \
             patch.object(s, "_ensure_document_page_images", side_effect=lambda db, doc:doc), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs) as read_groups:
            if certificate_first:
                read_certs()
            if separate_deliveries:
                read_groups.return_value = [self.cs[0]]
            ddt_rows, _ = self.fx.ensure()
            if separate_deliveries:
                second_ddt = Document(tipo_documento="ddt", nome_file_originale="1613.pdf", storage_key="1613.pdf",
                                      fornitore_id=self.fx.ddt.fornitore_id, numero_pagine=1)
                self.db.add(second_ddt)
                self.db.flush()
                self.db.add(DocumentPage(document_id=second_ddt.id,numero_pagina=1,immagine_pagina_storage_key="p.png"))
                self.db.commit()
                read_groups.return_value = [self.cs[1].model_copy(update={"ddt_number":"1613"})]
                extra, _ = s._ensure_autonomous_rows_with_ai(self.db,ddt_document=second_ddt,actor_id=1,
                    actor_email="packing@example.invalid",openai_api_key="stub",run_id=101)
                ddt_rows = [*ddt_rows,*extra]
            for r in ddt_rows:
                self.assertFalse(s._auto_propose_certificate_match(self.db, row=r,
                    certificate_documents=certs, actor_id=1, certificate_ai_cache=self.cache, ai_only_mode=True))
            if not certificate_first:
                read_certs()
            for r in ddt_rows:
                r.ai_processing_run_id, r.ai_processing_status = 101, "pronta"
            if detach:
                self.db.add(ManualMatchBlock(document_ddt_id=self.fx.ddt.id,document_certificato_id=certs[0].id))
            self.db.commit()
            fresh = set()
            run_id = 101 if current_run else 102
            protected = s._current_run_rematch_protected_ids(self.db,run_id,set(),fresh_bozen_targets=fresh)
            if current_run:
                self.assertTrue({r.id for r in ddt_rows}.issubset(protected & fresh))
            else:
                self.assertFalse(fresh)
            kwargs = dict(db=self.db,supplier_ids={self.fx.ddt.fornitore_id},actor_id=1,run_id=run_id,
                          protected_row_ids=protected,protected_source_row_ids=set(),fresh_bozen_targets=fresh)
            self.assertEqual(s._run_cross_run_auto_rematch(**kwargs), expected)
            self.assertEqual(s._run_cross_run_auto_rematch(**kwargs), 0)
            self.db.expire_all()
            records = self.db.query(AcquisitionRow).all()
            linked = [r for r in records if r.document_ddt_id and r.document_certificato_id]
            self.assertEqual(len(linked), expected)
            self.assertEqual(len(records), len(ddt_orders)+len(cert_orders)-expected)
            if linked:
                self.assertEqual(linked[0].document_certificato_id,certs[0].id)
                self.assertEqual(s._row_read_values(linked[0], "ddt")["customer_order_no"],ddt_orders[0])
                self.assertEqual(s._row_read_values(linked[0], "match")["ordine_cliente_certificato"],cert_orders[0])

    def test_undated_ddt_then_dated_certificate(self):
        self.order_flow()

    def test_dated_certificate_then_undated_ddt(self):
        self.order_flow(certificate_first=True)

    def test_date_only_on_ddt(self):
        self.order_flow(ddt_orders=("312-2026-10-01",),cert_orders=("312",))

    def test_persisted_order_pair_can_merge_in_a_later_run(self):
        self.order_flow(current_run=False)

    def test_two_certificates_for_undated_order(self):
        self.order_flow(cert_orders=("312-2026-10-01","312-2026-11-01"),expected=0)

    def test_two_earlier_certificates_for_undated_order(self):
        self.order_flow(cert_orders=("312-2026-10-01","312-2026-11-01"),certificate_first=True,expected=0)

    def test_two_indistinguishable_certificates_do_not_allocate_undated_order(self):
        self.order_flow(cert_orders=("312-2026-10-01","312-2026-10-01"),expected=0)

    def test_two_packing_groups_for_undated_order(self):
        self.order_flow(ddt_orders=("312","312"),expected=0,certificate_first=True)

    def test_two_open_ddts_do_not_race_for_one_certificate(self):
        self.order_flow(ddt_orders=("312","312"),separate_deliveries=True,expected=0)

    def test_different_order_number_blocks_all_paths(self):
        self.order_flow(cert_orders=("313-2026-10-01",),expected=0)

    def test_two_different_dates_block_all_paths(self):
        self.order_flow(ddt_orders=("312-2026-10-02",),expected=0)

    def test_partial_order_cannot_override_different_weight(self):
        self.order_flow(cert_fields={"peso_certificato":"375"},expected=0)

    def test_partial_order_requires_independent_article(self):
        self.order_flow(cert_fields={"articolo_certificato":None},expected=0)

    def test_partial_order_honours_manual_detach(self):
        self.order_flow(detach=True,expected=0)

    def test_same_anchors_and_cdq_but_two_distinct_packing_orders_never_pick_first(self):
        self.cs = parse([row(), row(package="02", packing_ref_raw="2611586.2")])
        with patch.object(s, "_ensure_document_page_images", return_value=self.fx.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs):
            rows, _ = self.fx.ensure()
        c = self.cs[0]
        found = s._find_existing_aluminium_bozen_row_for_certificate(rows=rows, certificate_number=c.cdq,
            article=c.article_code, profile_code=c.profile_code, customer_order=c.customer_order_no,
            alloy=c.lega, diameter=c.diametro, cast=c.colata, weight=c.peso_netto)
        self.assertIsNone(found)

    def test_old_manifests_keep_the_old_identity(self):
        legacy = self.cs[0].model_copy(update={"ai_row_payload_raw": '{"certificate_no_raw":"159629"}'})
        sig = s._autonomous_ddt_candidate_signature(document=self.fx.ddt, candidate=legacy, fallback_ddt=None)
        self.assertNotIn("bozen-v2", sig)

    def test_cert_first_two_equally_compatible_groups_stay_unattached_on_rematch(self):
        self.cs = parse([row(), row(package="02", packing_ref_raw="2611586.2")])
        self.certs([self.docs[1]])  # CDQ 159629
        with patch.object(s, "_ensure_document_page_images", return_value=self.fx.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs):
            rows, _ = self.fx.ensure()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r.document_certificato_id is None for r in rows))
        plans = s._plan_cross_run_auto_rematch(db=self.db, supplier_ids={self.fx.ddt.fornitore_id})
        self.assertEqual(plans, [])

    def test_shared_certificate_total_does_not_override_one_delivery_in_auto_rematch(self):
        self.cs = parse([row(cert="159233", net="2438", diameter_raw="98", cast_raw="526246A4",
                             article_code_raw="14BT147-B03", profile_code_raw="A62098020")])
        c = self.cs[0]
        cert = self.docs[0]
        self.cache[cert.id]["match_values"].update(numero_certificato_certificato=c.cdq, peso_certificato="10971",
                    colata_certificato=c.colata, diametro_certificato=c.diametro)
        self.cache[cert.id]["supplier_fields"].update(article=c.article_code, profile_code=c.profile_code)
        with patch.object(s, "_ensure_document_page_images", return_value=self.fx.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs):
            rows, _ = self.fx.ensure()
        self.certs([cert])
        self.assertIsNone(rows[0].document_certificato_id)
        self.assertEqual(s._plan_cross_run_auto_rematch(db=self.db, supplier_ids={self.fx.ddt.fornitore_id}), [])

    def test_reread_cannot_reassign_group_weights_by_score(self):
        with patch.object(s, "_ensure_document_page_images", return_value=self.fx.ddt), \
             patch.object(s, "_extract_supplier_ddt_row_groups_with_vision", return_value=self.cs):
            rows, _ = self.fx.ensure()
        mapping = s._match_aluminium_bozen_ai_groups_to_rows(self.db, rows=rows, ai_candidates=list(reversed(self.cs)))
        self.assertTrue(all(mapping[r.id].cdq == r.cdq for r in rows))
        changed = [self.cs[0].model_copy(update={"peso_netto":"999"}), self.cs[1]]
        with self.assertRaises(s.DdtPackingReviewRequired):
            s._apply_aluminium_bozen_ai_row_groups_to_rows(self.db, ddt_document=self.fx.ddt, rows=rows,
                                                           ai_candidates=changed, actor_id=1)
        self.assertEqual([r.peso for r in rows], ["373", "373"])


@unittest.skipUnless(os.environ.get("CERTI_AI_REUSE_TEST_DATABASE_URL"), "isolated PostgreSQL opt-in")
class BozenPostgresTests(BozenFlowTests):
    fixture_type = safety.SupplierDdtRecoveryPostgresTest
