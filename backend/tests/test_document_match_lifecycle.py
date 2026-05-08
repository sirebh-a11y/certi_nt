import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition.models import (
    AcquisitionRow,
    CertificateMatch,
    Document,
    DocumentEvidence,
    ManualMatchBlock,
    ReadValue,
)
from app.modules.acquisition.schemas import DocumentMatchDetachRequest
from app.modules.acquisition.schemas import AcquisitionQualityUpdateRequest
from app.modules.acquisition.service import (
    _manual_match_block_exists,
    _plan_cross_run_auto_rematch,
    detach_document_match,
    get_acquisition_row,
    list_quality_rows,
    update_quality_row,
)
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate
from app.modules.suppliers.models import Supplier


class DocumentMatchLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_detach_moves_certificate_blocks_and_blocks_immediate_auto_rematch(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(
            tipo_documento="ddt",
            fornitore_id=None,
            nome_file_originale="12594.pdf",
            storage_key="ddt-12594.pdf",
        )
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="CQF_10033539_25.pdf",
            storage_key="cert-10033539.pdf",
        )
        self.db.add_all([supplier, ddt_document, certificate_document])
        self.db.flush()
        ddt_document.fornitore_id = supplier.id
        certificate_document.fornitore_id = supplier.id

        row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="10033539/25",
            lega_base="7150 F",
            diametro="44",
            colata="25E-7870",
            ddt="12594",
            peso="1331",
            ordine="154",
            qualita_numero_analisi="205",
            qualita_valutazione="accettato",
            qualita_note="Accettato",
        )
        self.db.add(row)
        self.db.flush()

        evidence = DocumentEvidence(
            document_id=certificate_document.id,
            acquisition_row_id=row.id,
            blocco="chimica",
            tipo_evidenza="text",
            bbox="10,10,20,20",
            testo_grezzo="Cu 2,16",
            metodo_estrazione="chatgpt",
            mascherato=True,
        )
        note_template = NoteTemplate(code="radio-free", note_key="radioactive_free", text="Material free from radioactive contamination")
        self.db.add_all([evidence, note_template])
        self.db.flush()

        values = [
            ("ddt", "lega", "7150 F", "ddt", None),
            ("ddt", "diametro", "44", "ddt", None),
            ("ddt", "numero_certificato_ddt", "10033539/25", "ddt", None),
            ("ddt", "colata", "25E-7870", "ddt", None),
            ("ddt", "ddt", "12594", "ddt", None),
            ("ddt", "peso", "1331", "ddt", None),
            ("ddt", "customer_order_no", "154", "ddt", None),
            ("match", "numero_certificato_certificato", "10033539/25", "certificato", None),
            ("match", "lega_certificato", "7150 F", "certificato", None),
            ("match", "diametro_certificato", "44", "certificato", None),
            ("match", "colata_certificato", "25E-7870", "certificato", None),
            ("match", "ddt_certificato", "12594", "certificato", None),
            ("match", "peso_certificato", "1331", "certificato", None),
            ("match", "ordine_cliente_certificato", "154", "certificato", None),
            ("chimica", "Cu", "2,16", "certificato", evidence.id),
            ("proprieta", "Rm", "599", "certificato", None),
            ("note", "nota_radioactive_free", "true", "certificato", None),
        ]
        for block, field, value, source, evidence_id in values:
            self.db.add(
                ReadValue(
                    acquisition_row_id=row.id,
                    blocco=block,
                    campo=field,
                    valore_grezzo=value,
                    valore_standardizzato=value,
                    valore_finale=value,
                    stato="proposto",
                    document_evidence_id=evidence_id,
                    metodo_lettura="chatgpt" if source == "certificato" else "sistema",
                    fonte_documentale=source,
                )
            )
        self.db.add(AcquisitionRowNoteTemplate(acquisition_row_id=row.id, note_template_id=note_template.id))
        self.db.commit()

        response = detach_document_match(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentMatchDetachRequest(motivo_breve="test detach"),
            actor_id=1,
        )

        ddt_row = get_acquisition_row(self.db, response.ddt_row.id)
        certificate_row = get_acquisition_row(self.db, response.certificate_row.id)

        self.assertIsNotNone(ddt_row.document_ddt_id)
        self.assertIsNone(ddt_row.document_certificato_id)
        self.assertEqual(ddt_row.cdq, "10033539/25")
        self.assertEqual(ddt_row.ddt, "12594")
        self.assertEqual(ddt_row.qualita_numero_analisi, "205")
        self.assertIsNone(ddt_row.qualita_valutazione)
        self.assertEqual(ddt_row.qualita_note, "Accettato")
        self.assertTrue(ddt_row.qualita_numero_analisi_da_ricontrollare)
        self.assertTrue(ddt_row.qualita_note_da_ricontrollare)
        self.assertEqual({value.blocco for value in ddt_row.values}, {"ddt"})

        self.assertIsNone(certificate_row.document_ddt_id)
        self.assertIsNotNone(certificate_row.document_certificato_id)
        self.assertEqual(certificate_row.cdq, "10033539/25")
        self.assertTrue({"match", "chimica", "proprieta", "note"}.issubset({value.blocco for value in certificate_row.values}))
        self.assertEqual(certificate_row.evidences[0].acquisition_row_id, certificate_row.id)
        self.assertEqual(certificate_row.custom_note_links[0].acquisition_row_id, certificate_row.id)

        self.assertTrue(
            _manual_match_block_exists(
                self.db,
                ddt_document_id=ddt_document.id,
                certificate_document_id=certificate_document.id,
                ddt_row_id=ddt_row.id,
                certificate_row_id=certificate_row.id,
            )
        )
        self.assertEqual(
            _plan_cross_run_auto_rematch(db=self.db, supplier_ids={supplier.id}),
            [],
        )
        self.assertEqual(self.db.query(ManualMatchBlock).filter(ManualMatchBlock.attivo.is_(True)).count(), 1)

    def test_quality_rows_include_only_fully_confirmed_rows_and_clear_review_flags_on_update(self):
        supplier = Supplier(ragione_sociale="Test Supplier")
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key="ddt.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="cert.pdf",
            storage_key="cert.pdf",
        )
        self.db.add_all([supplier, ddt_document, certificate_document])
        self.db.flush()
        ddt_document.fornitore_id = supplier.id
        certificate_document.fornitore_id = supplier.id

        row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="1001",
            lega_base="6082",
            diametro="100",
            colata="C1001",
            ddt="D1001",
            peso="1200",
            ordine="333",
            qualita_numero_analisi="205",
            qualita_note="Da ricontrollare",
            qualita_numero_analisi_da_ricontrollare=True,
            qualita_note_da_ricontrollare=True,
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(
            CertificateMatch(
                acquisition_row_id=row.id,
                document_certificato_id=certificate_document.id,
                stato="confermato",
            )
        )

        for block, field, value in [
            ("ddt", "ddt", "D1001"),
            ("ddt", "lega", "6082"),
            ("ddt", "cdq", "1001"),
            ("ddt", "numero_certificato_ddt", "1001"),
            ("ddt", "colata", "C1001"),
            ("ddt", "diametro", "100"),
            ("ddt", "peso", "1200"),
            ("ddt", "customer_order_no", "333"),
            ("chimica", "Si", "0,9"),
            ("proprieta", "Rm", "350"),
            ("note", "nota_radioactive_free", "true"),
        ]:
            self.db.add(
                ReadValue(
                    acquisition_row_id=row.id,
                    blocco=block,
                    campo=field,
                    valore_grezzo=value,
                    valore_standardizzato=value,
                    valore_finale=value,
                    stato="confermato",
                    metodo_lettura="sistema",
                    fonte_documentale="sistema",
                )
            )
        self.db.commit()

        quality_rows = list_quality_rows(self.db).items

        self.assertEqual([item.id for item in quality_rows], [row.id])

        updated = update_quality_row(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=AcquisitionQualityUpdateRequest(
                qualita_data_ricezione=date(2026, 1, 19),
                qualita_data_accettazione=date(2026, 1, 20),
                qualita_data_richiesta=date(2026, 1, 21),
                qualita_numero_analisi="206",
                qualita_valutazione="accettato_con_riserva",
                qualita_note="Accettato con riserva",
            ),
            actor_id=1,
        )

        self.assertEqual(updated.qualita_numero_analisi, "206")
        self.assertEqual(updated.qualita_valutazione, "accettato_con_riserva")
        self.assertFalse(updated.qualita_numero_analisi_da_ricontrollare)
        self.assertFalse(updated.qualita_note_da_ricontrollare)


if __name__ == "__main__":
    unittest.main()
