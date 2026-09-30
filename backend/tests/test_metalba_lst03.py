import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.startup import bootstrap  # noqa: F401
from app.modules.acquisition import service as s
from app.modules.acquisition.metalba_alloy import lst03_material_quote
from app.modules.acquisition.models import AcquisitionRow, Document, DocumentPage, DocumentEvidence, ReadValue, CertificateMatch
from app.modules.acquisition.schemas import DocumentMatchDetachRequest
from app.modules.suppliers.models import Supplier


class MetalbaLST03Test(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()
        self.supplier = Supplier(ragione_sociale="Metalba S.p.A.", reader_template_key="metalba")
        self.db.add(self.supplier)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def value(self, row, block, field, text, **kw):
        value = ReadValue(acquisition_row_id=row.id, blocco=block, campo=field,
                          valore_grezzo=text, valore_standardizzato=text, valore_finale=text,
                          stato=kw.pop("stato", "proposto"), metodo_lettura=kw.pop("metodo_lettura", "chatgpt"),
                          fonte_documentale="ddt" if block == "ddt" else "certificato", **kw)
        self.db.add(value)
        self.db.flush()
        return value

    def pair(self, quote="MATERIALE SECONDO SPECIFICA LST 03-A", **changes):
        docs = [Document(tipo_documento=side, nome_file_originale=f"{side}.pdf", storage_key=str(uuid4()),
                         fornitore_id=self.supplier.id) for side in ("ddt", "certificato")]
        self.db.add_all(docs)
        self.db.flush()
        row = AcquisitionRow(fornitore_id=self.supplier.id, document_ddt_id=docs[0].id,
                             document_certificato_id=docs[1].id, lega_base="6082F F",
                             diametro="60", peso="2317", ordine="232/26", cdq="26-2220")
        self.db.add(row)
        self.db.flush()
        for block, entries in {
            "ddt": {"lega": "6082F F", "diametro": "60", "peso": "2317", "ordine": "232/26"},
            "match": {"lega_certificato": "6082F F", "diametro_certificato": "60",
                      "peso_certificato": "2317", "ordine_cliente_certificato": "232/26", "numero_certificato_certificato": "26-2220"},
        }.items():
            for field, text in entries.items():
                self.value(row, block, field, changes.get(field, text))
        evidence = DocumentEvidence(document_id=docs[1].id, acquisition_row_id=row.id,
                                    blocco="requisiti", tipo_evidenza="testo", testo_grezzo=quote,
                                    metodo_estrazione="chatgpt")
        self.db.add(evidence)
        self.db.flush()
        self.value(row, "requisiti", "customer_requirement_quote", quote, document_evidence_id=evidence.id)
        self.db.commit()
        return s.get_acquisition_row(self.db, row.id)

    def apply(self, row):
        return s._apply_metalba_lst03_alloy(self.db, row, actor_id=1)

    def test_exact_phrases_and_other_specifications(self):
        for code in ("LST 03", "LST03", "LST 03-A", "LST03A", "LST-03"):
            self.assertTrue(lst03_material_quote(f"MATERIALE SECONDO SPECIFICA {code}"), code)
        for text in ("LST03", "MATERIALE SECONDO SPECIFICA LST00",
                     "MATERIALE SECONDO SPECIFICA LST030", "MATERIALE SECONDO SPECIFICA LST03-B",
                     "MATERIALE SECONDO SPECIFICA LST03-A1", "MATERIALE SECONDO SPECIFICA LST03/02",
                     "MATERIALE SECONDO SPECIFICA LST 03 B",
                     "NON MATERIALE SECONDO SPECIFICA LST03", "DEROGA MATERIALE SECONDO SPECIFICA LST03",
                     "MATERIALE SECONDO SPECIFICA LST03 | MATERIALE SECONDO SPECIFICA LST05"):
            self.assertIsNone(lst03_material_quote(text), text)
        self.assertTrue(lst03_material_quote("Materiale secondo specifica LST00 Rev.1 | MATERIALE SECONDO SPECIFICA LST 03-A | Prove meccaniche su stato fisico T62"))

    def test_alpha_167_shape_preserves_raw_and_unrelated_values(self):
        row = self.pair()
        chemical = self.value(row, "chimica", "Si", "1.1976", stato="confermato")
        row.qualita_note = "Nota manuale"
        row.qualita_tipo_controllo = "inversa"
        self.assertTrue(self.apply(row))
        self.assertEqual(row.lega_base, "6082H F")
        for block, field in (("ddt", "lega"), ("match", "lega_certificato")):
            value = self.db.query(ReadValue).filter_by(acquisition_row_id=row.id, blocco=block, campo=field).one()
            self.assertEqual(value.valore_finale, "6082H F")
            self.assertEqual(value.valore_grezzo, "6082F F")
            self.assertEqual(value.metodo_lettura, s.METALBA_LST03_METHOD)
        self.assertEqual(s._build_row_ddt_bridge(row).value("lega"), "6082F F")
        self.assertEqual(s._build_row_certificate_bridge(row).value("lega"), "6082F F")
        self.assertEqual(chemical.valore_finale, "1.1976")
        self.assertEqual(chemical.stato, "confermato")
        self.assertEqual(row.qualita_note, "Nota manuale")
        self.assertEqual(row.qualita_tipo_controllo, "inversa")
        self.assertFalse(row.validata_finale)
        self.assertFalse(self.apply(row))

    def test_source_only_waits_and_later_pair_can_be_classified(self):
        row = self.pair()
        ddt_id = row.document_ddt_id
        row.document_ddt_id = None
        self.assertFalse(self.apply(row))
        self.assertEqual(row.lega_base, "6082F F")
        row.document_ddt_id = ddt_id
        self.assertTrue(self.apply(row))

    def test_other_supplier_closed_row_confirmed_match_and_manual_values_are_protected(self):
        for index, guard in enumerate(("supplier", "closed", "match", "confirmed", "manual"), start=1):
            with self.subTest(guard=guard):
                row = self.pair(ordine=f"{index}/26", ordine_cliente_certificato=f"{index}/26")
                if guard == "supplier":
                    row.supplier = Supplier(ragione_sociale=str(uuid4()), reader_template_key="impol")
                elif guard == "closed":
                    row.validata_finale = True
                elif guard == "match":
                    row.certificate_match = CertificateMatch(document_certificato_id=row.document_certificato_id, stato="confermato")
                else:
                    alloy = next(v for v in row.values if v.blocco == "ddt" and v.campo == "lega")
                    if guard == "confirmed":
                        alloy.stato = "confermato"
                    else:
                        alloy.metodo_lettura = "utente"
                self.assertFalse(self.apply(row))
                self.assertEqual(row.lega_base, "6082F F")

    def test_mismatching_material_and_identifiers_cannot_trigger_conversion(self):
        for index, change in enumerate(({"lega": "6082L F"}, {"lega_certificato": "7075 F"}, {"diametro_certificato": "55"},
                       {"peso_certificato": "1200"}, {"ordine_cliente_certificato": "233/26"}, {"peso": None}), start=1):
            with self.subTest(change=change):
                row = self.pair(**{"ordine": f"{index}/26", "ordine_cliente_certificato": f"{index}/26", **change})
                self.assertFalse(self.apply(row))
                self.assertEqual(row.lega_base, "6082F F")

    def test_ambiguous_second_ddt_is_not_classified_or_auto_selected(self):
        row = self.pair()
        other = self.pair()
        self.assertFalse(self.apply(row))
        self.assertIsNone(s._find_existing_metalba_row_for_certificate(
            rows=[row, other], customer_order="232/26", alloy="6082F F", diameter="60", weight="2317"))

    def test_confirmation_keeps_source_and_detach_restores_original(self):
        row = self.pair()
        self.assertTrue(self.apply(row))
        s._upsert_read_value_model(db=self.db, acquisition_row_id=row.id, blocco="ddt", campo="lega",
                                  valore_grezzo="6082H", valore_standardizzato="6082H", valore_finale="6082H",
                                  stato="confermato", document_evidence_id=None, metodo_lettura="utente",
                                  fonte_documentale="ddt", confidenza=1, actor_id=1)
        self.db.expire(row, ["values"])
        alloy = next(v for v in row.values if v.blocco == "ddt" and v.campo == "lega")
        self.assertEqual(alloy.valore_grezzo, "6082F F")
        self.assertEqual(alloy.metodo_lettura, s.METALBA_LST03_METHOD)
        s._restore_metalba_document_alloys(self.db, row, actor_id=1)
        self.assertEqual(row.lega_base, "6082F F")
        self.assertEqual(alloy.valore_finale, "6082F F")

    def test_display_confirmation_preserves_original_temper_and_manual_other_alloy_is_allowed(self):
        row = self.pair(lega="6082 T62", lega_certificato="6082 T62")
        self.assertTrue(self.apply(row))
        self.assertEqual(row.lega_base, "6082H T62")
        for new_value, raw_expected, method_expected in (("6082H", "6082 T62", s.METALBA_LST03_METHOD),
                                                       ("6082L", "6082L", "utente")):
            result = s._upsert_read_value_model(db=self.db, acquisition_row_id=row.id, blocco="ddt", campo="lega",
                                               valore_grezzo=new_value, valore_standardizzato=new_value, valore_finale=new_value,
                                               stato="proposto", document_evidence_id=None, metodo_lettura="utente",
                                               fonte_documentale="ddt", confidenza=1, actor_id=1)
            self.assertEqual(result.valore_grezzo, raw_expected)
            self.assertEqual(result.metodo_lettura, method_expected)

    def test_old_document_quote_cannot_change_new_certificate(self):
        row = self.pair()
        evidence = self.db.query(DocumentEvidence).filter_by(acquisition_row_id=row.id).one()
        evidence.document_id = row.document_ddt_id
        self.assertFalse(self.apply(row))

    def test_lst00_alone_does_not_change_alloy(self):
        self.assertFalse(self.apply(self.pair("Materiale secondo specifica LST00 Rev.1")))

    def test_real_shape_ai_payload_keeps_source_alloy_until_pair_application(self):
        row = self.pair()
        raw = {
            "core": {"numero_certificato": "26-2220", "ordine_cliente": "232/26", "lega": "6082F F",
                     "product_description_raw": "ESTRUSO A.A. 6082F F BARRA TONDA DIAM 60 mm", "peso_netto": "2317"},
            "chemistry_raw": {"Si": "1.0426", "Cr": "0.1311"},
            "mechanical_raw": {"measured_rows": [{"Rm": "405", "Rp0.2": "370", "A%": "10.9", "HB": "112"}]},
            "mechanical_requirement_raw": {"customer_requirement_quote_raw": "Materiale secondo specifica LST00 Rev.1 | MATERIALE SECONDO SPECIFICA LST 03-A | Prove meccaniche su stato fisico T62"},
        }
        page = DocumentPage(document_id=row.document_certificato_id, numero_pagina=1, testo_estratto="Test")
        self.db.add(page)
        self.db.flush()
        payload = s._normalize_metalba_certificate_ai_payload({"page1": {"page_id": page.id, "page_number": 1}}, raw)
        self.assertEqual(payload["match_values"]["lega_certificato"], "6082F F")
        s._apply_supplier_certificate_ai_payload(self.db, row=row, payload=payload, actor_id=1)
        self.assertEqual(row.lega_base, "6082H F")
        self.assertEqual(self.db.query(ReadValue).filter_by(acquisition_row_id=row.id, blocco="chimica", campo="Si").one().valore_finale, "1.0426")

    def test_certificate_first_merge_preserves_confirmed_chemistry_and_notes(self):
        target = self.pair()
        source = AcquisitionRow(fornitore_id=self.supplier.id, document_certificato_id=target.document_certificato_id,
                                lega_base="6082F F", diametro="60", peso="2317", ordine="232/26", qualita_note="Gia controllato")
        self.db.add(source)
        self.db.flush()
        for value in target.values:
            if value.blocco != "ddt":
                value.acquisition_row_id = source.id
        for evidence in self.db.query(DocumentEvidence).filter_by(acquisition_row_id=target.id).all():
            evidence.acquisition_row_id = source.id
        self.value(source, "chimica", "Si", "1.04", stato="confermato")
        self.db.commit()
        source_id = source.id
        target = s.get_acquisition_row(self.db, target.id)
        self.assertTrue(s._merge_certificate_only_row_into_ddt_row(db=self.db, target_row=target, source_row_id=source_id, actor_id=1))
        target = s.get_acquisition_row(self.db, target.id)
        self.assertEqual(target.lega_base, "6082H F")
        self.assertEqual(target.qualita_note, "Gia controllato")
        self.assertEqual(next(v for v in target.values if v.blocco == "chimica").stato, "confermato")

    def test_real_detach_does_not_leave_a_false_h_on_the_ddt(self):
        row = self.pair()
        self.assertTrue(self.apply(row))
        self.db.commit()
        s.detach_document_match(self.db, row=row, payload=DocumentMatchDetachRequest(), actor_id=1)
        result = s.get_acquisition_row(self.db, row.id)
        self.assertEqual(result.lega_base, "6082F F")
        self.assertIsNone(result.document_certificato_id)

    def test_same_document_with_other_material_is_not_classified(self):
        row = self.pair()
        sibling = AcquisitionRow(fornitore_id=self.supplier.id, document_certificato_id=row.document_certificato_id)
        self.db.add(sibling)
        self.db.flush()
        self.value(sibling, "match", "diametro_certificato", "80")
        self.assertFalse(self.apply(row))


if __name__ == "__main__":
    unittest.main()
