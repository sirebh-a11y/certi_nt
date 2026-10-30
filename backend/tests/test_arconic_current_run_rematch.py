"""Current-run Arconic recovery: real row matcher, no AI or application DB."""
import unittest
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.modules.acquisition import service as s
from app.modules.acquisition.models import (
    AcquisitionRow, AutonomousProcessingRun, CertificateMatch, Document,
    DocumentAiUsage, DocumentPage, ManualMatchBlock, ReadValue,
)
from app.modules.suppliers.models import Supplier


class ArconicCurrentRunRematchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.supplier = Supplier(ragione_sociale="Arconic Extrusions Hannover GmbH")
        self.run = AutonomousProcessingRun(ddt_document_ids="[]", certificate_document_ids="[]")
        self.db.add_all([self.supplier, self.run])
        self.db.commit()
        self.db.info[s.AI_PROCESSING_SESSION_RUN_KEY] = self.run.id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def doc(self, side, supplier=None):
        doc = Document(tipo_documento=side, fornitore_id=(supplier or self.supplier).id,
                       nome_file_originale="fixture.pdf", storage_key=uuid4().hex)
        self.db.add(doc)
        self.db.flush()
        self.db.add(DocumentPage(document_id=doc.id, numero_pagina=1, testo_estratto=""))
        self.db.flush()
        return doc

    def row(self, side, diameter="98", *, document=None, supplier=None, fields=None):
        supplier = supplier or self.supplier
        document = document or self.doc(side, supplier)
        row = AcquisitionRow(fornitore_id=supplier.id, fornitore_raw=supplier.ragione_sociale,
            document_ddt_id=document.id if side == "ddt" else None,
            document_certificato_id=document.id if side == "certificato" else None,
            ai_processing_run_id=self.run.id, ai_processing_status="pronta")
        self.db.add(row)
        self.db.flush()
        values = fields if fields is not None else {
            "colata": "CAST1", "diametro": diameter, "peso": "6996", "lega": "6082 F",
            "ordine": "213", "ddt": "28209127", "arconic_item_number": "BG" + diameter,
            "customer_item_number": "A" + diameter, "sales_order_number": "7235306",
        }
        aliases = {"colata": "colata_certificato", "diametro": "diametro_certificato",
            "peso": "peso_certificato", "lega": "lega_certificato", "ordine": "ordine_cliente_certificato",
            "ddt": "ddt_certificato", "arconic_item_number": "articolo_certificato",
            "customer_item_number": "codice_cliente_certificato", "sales_order_number": "sales_order_number_certificato"}
        for field, value in values.items():
            self.db.add(ReadValue(acquisition_row_id=row.id, blocco="ddt" if side == "ddt" else "match",
                campo=field if side == "ddt" else aliases.get(field, field), valore_grezzo=value,
                valore_standardizzato=value, valore_finale=value, stato="proposto", metodo_lettura="chatgpt",
                fonte_documentale=side))
        self.db.commit()
        return s.get_acquisition_row(self.db, row.id)

    def finish(self, blocked=()):
        with patch.object(s, "_create_openai_response", side_effect=AssertionError("AI forbidden")), \
                patch.object(s, "_type_guard_blocked_row_ids", return_value=set(blocked)):
            protected = s._current_run_rematch_protected_ids(self.db, self.run.id, set())
            result = s._run_cross_run_auto_rematch(db=self.db, supplier_ids={self.supplier.id},
                actor_id=None, run_id=self.run.id, protected_row_ids=protected,
                protected_source_row_ids=set(blocked))
        self.assertEqual(self.db.query(DocumentAiUsage).count(), 0)
        return result

    def test_current_run_two_ddt_lines_select_different_material_without_extra_run(self):
        doc = self.doc("ddt")
        targets = [self.row("ddt", d, document=doc) for d in ("87", "98")]
        sources = [self.row("certificato", d) for d in ("98", "87")]
        expected = {"98": sources[0].document_certificato_id, "87": sources[1].document_certificato_id}
        self.assertEqual(self.finish(), 2)
        for row, diameter in zip(targets, ("87", "98")):
            current = s.get_acquisition_row(self.db, row.id)
            self.assertEqual(current.document_certificato_id, expected[diameter])
            self.assertEqual(current.certificate_match.stato, "proposto")
        self.assertEqual(self.db.query(AcquisitionRow).count(), 2)
        self.assertEqual(self.finish(), 0)

    def test_repeated_logical_lines_can_reuse_same_pdf_after_source_merge(self):
        doc = self.doc("ddt")
        targets = [self.row("ddt", document=doc) for _ in range(2)]
        source = self.row("certificato")
        cert_id = source.document_certificato_id
        self.assertEqual(self.finish(), 2)
        self.assertEqual(self.db.query(AcquisitionRow).count(), 2)
        for target in targets:
            self.assertEqual(s.get_acquisition_row(self.db, target.id).document_certificato_id, cert_id)

    def test_two_equally_valid_documents_are_not_chosen_arbitrarily(self):
        target = self.row("ddt")
        self.row("certificato")
        self.row("certificato")
        self.assertEqual(self.finish(), 0)
        self.assertIsNone(s.get_acquisition_row(self.db, target.id).document_certificato_id)

    def test_manual_detach_and_changed_identity_are_respected(self):
        target = self.row("ddt")
        source = self.row("certificato")
        block = ManualMatchBlock(document_ddt_id=target.document_ddt_id,
            document_certificato_id=source.document_certificato_id, source_row_id=target.id, attivo=True)
        self.db.add(block)
        self.db.commit()
        self.assertEqual(self.finish(), 0)
        block.attivo = False
        value = next(v for v in target.values if v.campo == "colata")
        value.valore_finale = "MANUAL_DIFFERENT_CAST"
        value.metodo_lettura = "utente"
        self.db.commit()
        self.assertEqual(self.finish(), 0)
        self.assertEqual(value.valore_finale, "MANUAL_DIFFERENT_CAST")

    def test_type_guard_on_either_side_and_validated_target_still_block(self):
        target = self.row("ddt")
        source = self.row("certificato")
        self.assertEqual(self.finish({target.id}), 0)
        self.assertEqual(self.finish({source.id}), 0)
        target.validata_finale = True
        self.db.commit()
        self.assertEqual(self.finish(), 0)

    def test_source_confirmed_match_is_not_absorbed(self):
        self.row("ddt")
        source = self.row("certificato")
        source.certificate_match = CertificateMatch(document_certificato_id=source.document_certificato_id,
                                                    stato="confermato", fonte_proposta="utente")
        self.db.commit()
        self.assertEqual(self.finish(), 0)
        self.assertIsNotNone(self.db.get(AcquisitionRow, source.id))

    def test_protection_change_only_unpaired_arconic_ddt(self):
        target = self.row("ddt")
        source = self.row("certificato")
        paired = self.row("ddt")
        paired.document_certificato_id = source.document_certificato_id
        manual = self.row("ddt")
        manual.certificate_match = CertificateMatch(document_certificato_id=source.document_certificato_id,
                                                    stato="confermato", fonte_proposta="utente")
        validated = self.row("ddt")
        validated.validata_finale = True
        other = Supplier(ragione_sociale="Metalba S.p.A.")
        self.db.add(other)
        self.db.flush()
        other_row = self.row("ddt", supplier=other)
        self.db.commit()
        protected = s._current_run_rematch_protected_ids(self.db, self.run.id, set())
        self.assertNotIn(target.id, protected)
        self.assertTrue({source.id, paired.id, manual.id, validated.id, other_row.id}.issubset(protected))

    def test_wrong_diameter_supplier_and_only_weak_support_do_not_match(self):
        target = self.row("ddt")
        self.row("certificato", "87")
        other = Supplier(ragione_sociale="Other supplier")
        self.db.add(other)
        self.db.flush()
        self.row("certificato", supplier=other)
        self.row("certificato", fields={"ordine": "213", "lega": "6082 F", "ddt": "28209127"})
        self.assertEqual(self.finish(), 0)
        self.assertIsNone(s.get_acquisition_row(self.db, target.id).document_certificato_id)
