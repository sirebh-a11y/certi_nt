import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.startup import bootstrap  # noqa: F401 - register model relationships, no startup
from app.modules.quarta_taglio.models import QuartaTaglioEsolverLink, QuartaTaglioFinalCertificate
from app.modules.quarta_taglio.schemas import QuartaTaglioEsolverDdtRowResponse
from app.modules.quarta_taglio.service import (
    _certificate_quantity_display,
    generate_quarta_taglio_certificate_pdf,
    list_quarta_taglio_final_certificates,
    refresh_quarta_taglio_visible_final_certificates,
)


class ShipmentQuantityFixtures:
    def certificate(self, **changes):
        values = dict(
            cod_odp="OL1", cod_f3="F3", ddt="DDT1", quantita=3214,
            certificate_number="7000_00_00/26", draft_number="7000_00_00/26",
            unit_key="unit-1", esolver_id_documento="10", esolver_id_riga_doc="1",
            esolver_rif_lotto_alfanum="LOT1", ordine_cliente="ORDER", cdo_lega="CDO",
            status="draft", storage_key_docx="existing.docx",
            cdq_values=[{"cdq": "CDQ1", "qta_totale": 2}],
            cert_date=datetime.now(timezone.utc), conformity_status="conforme",
        )
        values.update(changes)
        return QuartaTaglioFinalCertificate(**values)

    def shipment(self, **changes):
        values = dict(
            orp="OL1", cod_f3="F3", ddt="DDT1", qta_um_mag=120,
            id_documento="10", id_riga_doc="1", rif_lotto_alfanum="LOT1",
            odv_cli="ORDER", odv_f3="CDO",
        )
        values.update(changes)
        return QuartaTaglioEsolverDdtRowResponse(**values)

    def quantity(self, certificate=None, rows=None):
        return _certificate_quantity_display(
            certificate if certificate is not None else self.certificate(),
            esolver_rows=rows if rows is not None else [self.shipment()],
        )


class RegisterShipmentQuantityTest(ShipmentQuantityFixtures, unittest.TestCase):
    def test_missing_ddt_or_source_never_falls_back_to_saved_material_quantity(self):
        for status in ("draft", "pdf_final"):
            for old_quantity in (None, 2, 208, 608, 1126):
                with self.subTest(status=status, old_quantity=old_quantity):
                    c = self.certificate(status=status, quantita=old_quantity, ddt=None)
                    self.assertIsNone(self.quantity(c))
                    c.ddt = "DDT1"
                    self.assertIsNone(self.quantity(c, []))
                    self.assertEqual(c.quantita, old_quantity)
                    self.assertEqual(c.cdq_values, [{"cdq": "CDQ1", "qta_totale": 2}])

    def test_only_the_exact_shipment_is_used_not_ol_total_or_other_lots(self):
        others = [
            self.shipment(orp="OTHER"), self.shipment(cod_f3="OTHER"),
            self.shipment(ddt="DDT2"), self.shipment(id_documento="11"),
            self.shipment(id_riga_doc="2"), self.shipment(rif_lotto_alfanum="LOT2"),
            self.shipment(odv_cli="OTHER"), self.shipment(odv_f3="OTHER"),
        ]
        self.assertIsNone(self.quantity(rows=others))
        self.assertEqual(self.quantity(rows=others + [self.shipment()]), 120)

    def test_two_partial_deliveries_of_same_article_keep_separate_quantities(self):
        rows = [self.shipment(), self.shipment(ddt="DDT2", id_documento="11", qta_um_mag=80)]
        self.assertEqual(self.quantity(rows=rows), 120)
        self.assertEqual(self.quantity(self.certificate(ddt="DDT2", esolver_id_documento="11"), rows), 80)

    def test_legacy_without_ids_is_allowed_only_for_a_unique_shipment(self):
        legacy = self.certificate(esolver_id_documento=None, esolver_id_riga_doc=None,
                                  esolver_rif_lotto_alfanum=None, ordine_cliente=None, cdo_lega=None)
        self.assertEqual(self.quantity(legacy), 120)
        for extra in (self.shipment(id_riga_doc="2"), self.shipment(rif_lotto_alfanum="LOT2"),
                      self.shipment(odv_cli="OTHER")):
            self.assertIsNone(self.quantity(legacy, [self.shipment(), extra]))
        # Even one candidate cannot override a conflicting stored identity.
        self.assertIsNone(self.quantity(self.certificate(esolver_id_riga_doc="99")))

    def test_duplicates_are_not_summed_and_conflicting_quantities_are_unknown(self):
        self.assertEqual(self.quantity(rows=[self.shipment(), self.shipment()]), 120)
        self.assertIsNone(self.quantity(rows=[self.shipment(), self.shipment(qta_um_mag=80)]))
        self.assertIsNone(self.quantity(rows=[self.shipment(), self.shipment(qta_um_mag=None)]))

    def test_missing_invalid_zero_and_decimal_quantities(self):
        for value in (None, -1, float("nan"), float("inf")):
            self.assertIsNone(self.quantity(rows=[self.shipment(qta_um_mag=value)]))
        self.assertEqual(self.quantity(rows=[self.shipment(qta_um_mag=0)]), 0)
        # Do not silently round an unexpected decimal supplied by eSolver.
        self.assertEqual(self.quantity(rows=[self.shipment(qta_um_mag=12.5)]), 12.5)
        for changes in ({"id_documento": None}, {"id_riga_doc": None}, {"orp": None}, {"ddt": None}):
            self.assertIsNone(self.quantity(rows=[self.shipment(**changes)]))

    def test_open_and_closed_certificate_snapshots_remain_unchanged(self):
        for status in ("draft", "pdf_final"):
            c = self.certificate(status=status, storage_key_pdf="existing.pdf" if status == "pdf_final" else None)
            before = deepcopy({k: v for k, v in vars(c).items() if k != "_sa_instance_state"})
            self.assertEqual(self.quantity(c), 120)
            self.assertEqual(before, {k: v for k, v in vars(c).items() if k != "_sa_instance_state"})


class RegisterShipmentQuantityDatabaseTest(ShipmentQuantityFixtures, unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_list_loads_cache_in_one_query_and_does_not_write_or_generate_documents(self):
        first = self.certificate()
        second = self.certificate(cod_odp="OL2", unit_key="unit-2", ddt=None,
                                  certificate_number="7001_00_00/26", quantita=2)
        closed = self.certificate(cod_odp="OL3", unit_key="unit-3", status="pdf_final",
                                  certificate_number="7002_00_00/26", storage_key_pdf="existing.pdf")
        self.db.add_all([first, second, closed])
        self.db.add_all([
            QuartaTaglioEsolverLink(cod_odp="OL1", status="ok", rows=[self.shipment().model_dump()]),
            QuartaTaglioEsolverLink(cod_odp="OL3", status="ok", rows=[self.shipment(orp="OL3", qta_um_mag=50).model_dump()]),
        ])
        self.db.commit()
        statements = []
        event.listen(self.engine, "before_cursor_execute", lambda conn, cursor, statement, *args: statements.append(statement))
        with patch("app.modules.quarta_taglio.service._fetch_esolver_ddt_rows_batch", side_effect=AssertionError("external sync")), \
             patch("app.modules.quarta_taglio.service._ensure_register_word_current", side_effect=AssertionError("Word changed")):
            result = list_quarta_taglio_final_certificates(self.db)
        self.assertEqual({item.cod_odp: item.quantita for item in result.items}, {"OL1": 120, "OL2": None, "OL3": 50})
        self.assertEqual(sum("FROM quarta_taglio_esolver_links" in sql for sql in statements), 1)
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        self.assertFalse(self.db.dirty)
        self.assertEqual((first.quantita, second.quantita, closed.quantita), (3214, 2, 3214))
        self.assertEqual(closed.storage_key_pdf, "existing.pdf")

    def test_existing_refresh_response_uses_same_display_rule_and_keeps_requested_order(self):
        first = self.certificate()
        second = self.certificate(cod_odp="OL2", unit_key="unit-2", ddt=None,
                                  certificate_number="7001_00_00/26", quantita=2)
        self.db.add_all([first, second])
        self.db.commit()
        self.assertTrue(all(item.quantita is None for item in list_quarta_taglio_final_certificates(self.db).items))
        # Simulate the existing eSolver cache refresh, without an external connection.
        self.db.add(QuartaTaglioEsolverLink(cod_odp="OL1", status="ok", rows=[self.shipment().model_dump()]))
        self.db.commit()
        with patch("app.modules.quarta_taglio.service._stale_register_cod_odps", return_value=[]):
            result = refresh_quarta_taglio_visible_final_certificates(self.db, certificate_ids=[second.id, first.id])
        self.assertEqual([item.id for item in result.items], [second.id, first.id])
        self.assertEqual([item.quantita for item in result.items], [None, 120])
        self.assertEqual((first.quantita, second.quantita), (3214, 2))

    def test_already_closed_pdf_action_returns_same_quantity_without_recreating_pdf(self):
        certificate = self.certificate(status="pdf_final", storage_key_pdf="existing.pdf")
        self.db.add(certificate)
        self.db.add(QuartaTaglioEsolverLink(cod_odp="OL1", status="ok", rows=[self.shipment().model_dump()]))
        self.db.commit()
        with patch("app.modules.quarta_taglio.service.is_quality_area_user", return_value=True), \
             patch("app.modules.quarta_taglio.service.convert_docx_to_pdf", side_effect=AssertionError("PDF changed")):
            result = generate_quarta_taglio_certificate_pdf(self.db, certificate_id=certificate.id, actor=None)
        self.assertEqual(result.quantita, 120)
        self.assertEqual((certificate.status, certificate.quantita, certificate.storage_key_pdf), ("pdf_final", 3214, "existing.pdf"))


if __name__ == "__main__":
    unittest.main()
