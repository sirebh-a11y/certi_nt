import unittest
from datetime import date

from fastapi import HTTPException
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
    DocumentPage,
    ManualMatchBlock,
    ReadValue,
)
from app.modules.acquisition.schemas import DocumentMatchDetachRequest
from app.modules.acquisition.schemas import AcquisitionQualityUpdateRequest
from app.modules.acquisition.schemas import DocumentSideFieldsConfirmRequest
from app.modules.acquisition.service import (
    _manual_match_block_exists,
    _plan_cross_run_auto_rematch,
    _run_cross_run_auto_rematch,
    _score_certificate_candidate,
    confirm_document_side_fields,
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

    def test_match_confirmation_requires_all_visible_row_fields(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
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
            cdq="740083448/23",
            lega_base="7150 T76",
            diametro="35",
            colata="H6216",
            ddt="201138817",
            peso="2006",
            ordine="100",
        )
        self.db.add(row)
        self.db.commit()

        complete_fields = {
            "lega_base": "7150 T76",
            "diametro": "35",
            "cdq": "740083448/23",
            "colata": "H6216",
            "ddt": "201138817",
            "peso": "2006",
            "ordine": "100",
        }
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=complete_fields),
            actor_id=1,
        )

        incomplete_certificate_fields = dict(complete_fields)
        incomplete_certificate_fields["lega_base"] = None
        with self.assertRaises(HTTPException) as exc:
            confirm_document_side_fields(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=incomplete_certificate_fields),
                actor_id=1,
            )
        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Manca Lega")
        self.assertIsNone(get_acquisition_row(self.db, row.id).certificate_match)

        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=complete_fields),
            actor_id=1,
        )
        confirmed = get_acquisition_row(self.db, row.id).certificate_match
        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed.stato, "confermato")

    def test_grupa_kety_score_rejects_certificate_for_different_heat(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="201138817.pdf", storage_key="ddt.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="CQF_740083448_23.pdf",
            storage_key="cert.pdf",
        )
        self.db.add_all([supplier, ddt_document, certificate_document])
        self.db.flush()
        ddt_document.fornitore_id = supplier.id
        certificate_document.fornitore_id = supplier.id
        self.db.add_all(
            [
                DocumentPage(document_id=ddt_document.id, numero_pagina=1, testo_estratto=""),
                DocumentPage(document_id=certificate_document.id, numero_pagina=1, testo_estratto=""),
            ]
        )
        row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="740083449/23",
            lega_base="7150 T76",
            diametro="35",
            colata="H6216",
            ddt="201138817",
            peso="2006",
            ordine="100",
        )
        self.db.add(row)
        self.db.flush()

        candidate = _score_certificate_candidate(
            self.db,
            row=row,
            certificate_document=certificate_document,
            ddt_certificate_number="740083449/23",
            row_ddt_values={"lot_batch_no": "740083449", "heat_no": "H6216", "ddt": "201138817", "ordine": "100"},
            certificate_ai_cache={
                certificate_document.id: {
                    "match_values": {
                        "numero_certificato_certificato": "740083448/23",
                        "colata_certificato": "H6215",
                        "ddt_certificato": "201138817",
                        "ordine_cliente_certificato": "100",
                        "lega_certificato": "7150 T76",
                    },
                    "supplier_fields": {
                        "delivery_note_no": "201138817",
                        "lot_number": "740083448",
                        "order_no": "100",
                        "heat": "H6215",
                        "certificate_number": "740083448/23",
                    },
                }
            },
            ai_only_mode=True,
        )

        self.assertIsNone(candidate)

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

    def test_certificate_first_arconic_row_merges_when_matching_ddt_arrives_later(self):
        supplier = Supplier(ragione_sociale="Arconic Extrusions Hannover GmbH")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="CQF_EEP66506-43440412_6111A68_2023.pdf",
            storage_key="cert-arconic.pdf",
        )
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="27697432.pdf", storage_key="ddt-arconic.pdf")
        self.db.add_all([supplier, certificate_document, ddt_document])
        self.db.flush()
        certificate_document.fornitore_id = supplier.id
        ddt_document.fornitore_id = supplier.id
        self.db.add(
            DocumentPage(
                document_id=certificate_document.id,
                numero_pagina=1,
                ocr_text=(
                    "Certificate EEP66506 Cast Job C3802220451 / 43440412 "
                    "Delivery note 27697432 Arconic Item Number BG5203862"
                ),
                stato_estrazione="completata",
            )
        )

        certificate_row = AcquisitionRow(
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="EEP66506-43440412",
            colata="C3802220451",
            ddt="27697432",
            ordine="318",
        )
        ddt_row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            colata="C3802220451",
            ddt="27697432",
            diametro="68",
            peso="7656",
            ordine="318",
        )
        self.db.add_all([certificate_row, ddt_row])
        self.db.flush()

        for block, field, value, row in [
            ("match", "numero_certificato_certificato", "EEP66506-43440412", certificate_row),
            ("match", "colata_certificato", "C3802220451", certificate_row),
            ("match", "ddt_certificato", "27697432", certificate_row),
            ("match", "ordine_cliente_certificato", "318", certificate_row),
            ("match", "articolo_certificato", "BG5203862", certificate_row),
            ("ddt", "colata", "C3802220451", ddt_row),
            ("ddt", "ddt", "27697432", ddt_row),
            ("ddt", "ordine", "318", ddt_row),
            ("ddt", "article_code", "BG5203862", ddt_row),
            ("ddt", "arconic_item_number", "BG5203862", ddt_row),
        ]:
            self.db.add(
                ReadValue(
                    acquisition_row_id=row.id,
                    blocco=block,
                    campo=field,
                    valore_grezzo=value,
                    valore_standardizzato=value,
                    valore_finale=value,
                    stato="proposto",
                    metodo_lettura="chatgpt" if block == "match" else "sistema",
                    fonte_documentale="certificato" if block == "match" else "ddt",
                )
            )
        self.db.commit()

        plans = _plan_cross_run_auto_rematch(db=self.db, supplier_ids={supplier.id})

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].row_id, ddt_row.id)
        self.assertEqual(plans[0].document_id, certificate_document.id)

        applied = _run_cross_run_auto_rematch(db=self.db, supplier_ids={supplier.id}, actor_id=1)

        self.assertEqual(applied, 1)
        rows = self.db.query(AcquisitionRow).filter(AcquisitionRow.fornitore_id == supplier.id).all()
        self.assertEqual(len(rows), 1)
        merged = rows[0]
        self.assertEqual(merged.document_ddt_id, ddt_document.id)
        self.assertEqual(merged.document_certificato_id, certificate_document.id)
        self.assertEqual(merged.cdq, "EEP66506-43440412")
        self.assertIsNotNone(merged.certificate_match)
        self.assertEqual(merged.certificate_match.document_certificato_id, certificate_document.id)


if __name__ == "__main__":
    unittest.main()
