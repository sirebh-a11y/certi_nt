import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition.models import (
    AcquisitionHistoryEvent,
    AcquisitionRow,
    AutonomousProcessingRun,
    CertificateMatch,
    Document,
    DocumentEvidence,
    DocumentPage,
    ManualMatchBlock,
    ReadValue,
)
from app.modules.acquisition.schemas import DocumentMatchDetachRequest
from app.modules.acquisition.schemas import AcquisitionRowUpdateRequest
from app.modules.acquisition.schemas import AcquisitionQualityUpdateRequest
from app.modules.acquisition.schemas import AcquisitionFinalValidationRequest
from app.modules.acquisition.schemas import AcquisitionQualityControlTypeUpdateRequest
from app.modules.acquisition.schemas import AcquisitionQualityNoteUpdateRequest
from app.modules.acquisition.schemas import DocumentSideFieldsConfirmRequest
from app.modules.acquisition.schemas import MatchUpsertRequest
from app.modules.acquisition.schemas import ReadValueUpsertRequest
from app.modules.acquisition.service import (
    _ensure_proposed_match_for_coupled_row,
    _manual_match_block_exists,
    _merge_certificate_only_row_into_ddt_row,
    _plan_cross_run_auto_rematch,
    _run_cross_run_auto_rematch,
    _score_certificate_candidate,
    confirm_document_side_fields,
    delete_single_document_acquisition_row,
    detach_document_match,
    get_acquisition_row,
    list_quality_rows,
    reopen_final_validation,
    save_quality_control_type,
    save_quality_evaluation_note,
    preview_acquisition_row_delete,
    update_quality_row,
    update_acquisition_row,
    upsert_read_value,
    validate_final_row,
)
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate
from app.modules.supplier_kpi.service import build_supplier_kpi_summary
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

    def test_match_confirmation_uses_combined_ddt_and_certificate_fields(self):
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
            lega_base=None,
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
        partial_ddt_fields = dict(complete_fields)
        partial_ddt_fields["lega_base"] = None
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=partial_ddt_fields),
            actor_id=1,
        )
        after_ddt = get_acquisition_row(self.db, row.id)
        self.assertIsNone(after_ddt.certificate_match)
        self.assertIsNone(after_ddt.lega_base)
        self.assertEqual(after_ddt.diametro, "35")

        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=complete_fields),
            actor_id=1,
        )
        confirmed = get_acquisition_row(self.db, row.id).certificate_match
        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed.stato, "confermato")
        synced_row = get_acquisition_row(self.db, row.id)
        self.assertEqual(synced_row.lega_base, "7150 T76")
        self.assertEqual(synced_row.diametro, "35")

    def test_validated_row_blocks_technical_edits_until_forced_reopen(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt-validated.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="cert.pdf",
            storage_key="cert-validated.pdf",
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
        )
        self.db.add(row)
        self.db.commit()

        original_fields = {
            "lega_base": "7150 F",
            "diametro": "44",
            "cdq": "10033539/25",
            "colata": "25E-7870",
            "ddt": "12594",
            "peso": "1331",
            "ordine": "154",
        }
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=original_fields),
            actor_id=1,
        )
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=original_fields),
            actor_id=1,
        )
        validated = get_acquisition_row(self.db, row.id)
        validated.validata_finale = True
        validated.qualita_valutazione = "accettato"
        validated.stato_workflow = "validata_quality"
        self.db.add(validated)
        self.db.commit()

        changed_ddt_fields = dict(original_fields)
        changed_ddt_fields.update({"cdq": "999999/25", "colata": "99E-9999", "peso": "1999"})

        with self.assertRaises(HTTPException) as document_side_error:
            confirm_document_side_fields(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=changed_ddt_fields),
                actor_id=1,
            )
        self.assertEqual(document_side_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as value_error:
            upsert_read_value(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=ReadValueUpsertRequest(
                    blocco="chimica",
                    campo="Si",
                    valore_grezzo="0,91",
                    valore_standardizzato="0,91",
                    valore_finale="0,91",
                    stato="confermato",
                    metodo_lettura="utente",
                    fonte_documentale="utente",
                ),
                actor_id=1,
            )
        self.assertEqual(value_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as row_update_error:
            update_acquisition_row(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=AcquisitionRowUpdateRequest(cdq="999999/25"),
                actor_id=1,
                actor_email="admin@certi.local",
            )
        self.assertEqual(row_update_error.exception.status_code, 409)

        still_locked = get_acquisition_row(self.db, row.id)
        self.assertTrue(still_locked.validata_finale)
        self.assertEqual(still_locked.qualita_valutazione, "accettato")
        self.assertEqual(still_locked.stato_workflow, "validata_quality")
        self.assertEqual(still_locked.cdq, "10033539/25")
        self.assertEqual(still_locked.colata, "25E-7870")
        self.assertEqual(still_locked.peso, "1331")
        self.assertIsNotNone(still_locked.certificate_match)
        self.assertEqual(still_locked.certificate_match.stato, "confermato")
        ddt_cdq_value = next(value for value in still_locked.values if value.blocco == "ddt" and value.campo == "cdq")
        self.assertEqual(ddt_cdq_value.valore_finale, "10033539/25")

        reopen_final_validation(self.db, row=get_acquisition_row(self.db, row.id), actor_id=1)
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=changed_ddt_fields),
            actor_id=1,
        )

        reopened_and_changed = get_acquisition_row(self.db, row.id)
        self.assertFalse(reopened_and_changed.validata_finale)
        self.assertIsNone(reopened_and_changed.qualita_valutazione)
        self.assertEqual(reopened_and_changed.stato_workflow, "riaperta")
        self.assertEqual(reopened_and_changed.cdq, "999999/25")
        self.assertEqual(reopened_and_changed.colata, "99E-9999")
        self.assertEqual(reopened_and_changed.peso, "1999")

    def test_validated_row_blocks_detach_and_match_change_until_reopened(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt-locked.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="cert.pdf",
            storage_key="cert-locked.pdf",
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
            colata="25E-7870",
            validata_finale=True,
            qualita_valutazione="accettato",
            stato_workflow="validata_quality",
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(
            CertificateMatch(
                acquisition_row_id=row.id,
                document_certificato_id=certificate_document.id,
                stato="confermato",
                motivo_breve="test",
                fonte_proposta="utente",
            )
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as detach_error:
            detach_document_match(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=DocumentMatchDetachRequest(motivo_breve="test detach"),
                actor_id=1,
            )
        self.assertEqual(detach_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as match_error:
            from app.modules.acquisition.service import upsert_match

            upsert_match(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=MatchUpsertRequest(
                    document_certificato_id=certificate_document.id,
                    stato="confermato",
                    motivo_breve="test cambio",
                    fonte_proposta="utente",
                    candidates=[],
                ),
                actor_id=1,
            )
        self.assertEqual(match_error.exception.status_code, 409)

    def test_grupa_kety_match_confirmation_accepts_cdq_year_suffix_when_bridge_is_strong(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt-suffix.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="cert.pdf",
            storage_key="cert-suffix.pdf",
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
            cdq="750027617",
            lega_base="7150 F",
            diametro="44",
            colata="H6245",
            ddt="201149900",
            peso="1721",
            ordine="110",
        )
        self.db.add(row)
        self.db.commit()

        ddt_fields = {
            "lega_base": "7150 F",
            "diametro": "44",
            "cdq": "750027617",
            "colata": "H6245",
            "ddt": "201149900",
            "peso": "1721",
            "ordine": "110",
        }
        certificate_fields = {
            "lega_base": "7150 F",
            "diametro": "",
            "cdq": "750027617/23",
            "colata": "H6245",
            "ddt": "201149900",
            "peso": "",
            "ordine": "110",
        }

        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=ddt_fields),
            actor_id=1,
        )
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=certificate_fields),
            actor_id=1,
        )

        confirmed = get_acquisition_row(self.db, row.id).certificate_match
        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed.stato, "confermato")

    def test_match_confirmation_reports_missing_final_field_before_match(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt-missing.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="cert.pdf",
            storage_key="cert-missing.pdf",
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
            cdq="750027617",
            lega_base=None,
            diametro="44",
            colata="H6245",
            ddt="201149900",
            peso="1721",
            ordine="110",
        )
        self.db.add(row)
        self.db.commit()

        ddt_fields = {
            "lega_base": "",
            "diametro": "44",
            "cdq": "750027617",
            "colata": "H6245",
            "ddt": "201149900",
            "peso": "1721",
            "ordine": "110",
        }
        certificate_fields = {
            "lega_base": "",
            "diametro": "",
            "cdq": "750027617/23",
            "colata": "H6245",
            "ddt": "201149900",
            "peso": "",
            "ordine": "110",
        }

        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="ddt", fields=ddt_fields),
            actor_id=1,
        )
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=certificate_fields),
            actor_id=1,
        )

        not_confirmed = get_acquisition_row(self.db, row.id).certificate_match
        self.assertIsNotNone(not_confirmed)
        self.assertEqual(not_confirmed.stato, "proposto")
        self.assertIn("Manca Lega", not_confirmed.motivo_breve)

    def test_confirmed_match_is_reopened_when_document_side_fields_conflict(self):
        supplier = Supplier(ragione_sociale="Grupa Kety S.A.")
        ddt_document = Document(tipo_documento="ddt", fornitore_id=None, nome_file_originale="ddt.pdf", storage_key="ddt-conflict.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            fornitore_id=None,
            nome_file_originale="cert.pdf",
            storage_key="cert-conflict.pdf",
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
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=complete_fields),
            actor_id=1,
        )
        self.assertEqual(get_acquisition_row(self.db, row.id).certificate_match.stato, "confermato")

        conflicting_certificate_fields = dict(complete_fields)
        conflicting_certificate_fields["lega_base"] = "6082 T6"
        confirm_document_side_fields(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=DocumentSideFieldsConfirmRequest(side="certificato", fields=conflicting_certificate_fields),
            actor_id=1,
        )
        conflicted_row = get_acquisition_row(self.db, row.id)
        self.assertEqual(conflicted_row.certificate_match.stato, "proposto")
        self.assertIn("Lega diversa", conflicted_row.certificate_match.motivo_breve)
        self.assertEqual(conflicted_row.lega_base, "7150 T76")

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
        row.validata_finale = True
        row.stato_workflow = "validata_quality"
        row.qualita_valutazione = "accettato_con_riserva"
        row.qualita_note = "Accettato con riserva"
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
            ),
            actor_id=1,
        )

        self.assertEqual(updated.qualita_numero_analisi, "206")
        self.assertEqual(updated.qualita_valutazione, "accettato_con_riserva")
        self.assertFalse(updated.qualita_numero_analisi_da_ricontrollare)
        self.assertTrue(updated.qualita_note_da_ricontrollare)

    def test_quality_register_starts_at_user_confirmed_match_and_stays_out_of_kpi_until_closed(self):
        supplier = Supplier(ragione_sociale="Early Quality Supplier")
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="early-ddt.pdf", storage_key="early-ddt.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="early-cert.pdf",
            storage_key="early-cert.pdf",
        )
        proposed_certificate = Document(
            tipo_documento="certificato",
            nome_file_originale="proposed-cert.pdf",
            storage_key="proposed-cert.pdf",
        )
        self.db.add_all([supplier, ddt_document, certificate_document, proposed_certificate])
        self.db.flush()
        ddt_document.fornitore_id = supplier.id
        certificate_document.fornitore_id = supplier.id
        proposed_certificate.fornitore_id = supplier.id

        matched_row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="EARLY-1",
            qualita_note="Nota iniziale",
            validata_finale=False,
            stato_workflow="in_lavorazione",
        )
        proposed_row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=proposed_certificate.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="PROPOSED-1",
            validata_finale=False,
        )
        self.db.add_all([matched_row, proposed_row])
        self.db.flush()
        self.db.add_all(
            [
                CertificateMatch(
                    acquisition_row_id=matched_row.id,
                    document_certificato_id=certificate_document.id,
                    stato="confermato",
                    utente_conferma_id=1,
                ),
                CertificateMatch(
                    acquisition_row_id=proposed_row.id,
                    document_certificato_id=proposed_certificate.id,
                    stato="proposto",
                ),
            ]
        )
        self.db.commit()

        quality_rows = list_quality_rows(self.db).items
        self.assertEqual([item.id for item in quality_rows], [matched_row.id])
        self.assertIsNone(quality_rows[0].qualita_valutazione)
        self.assertEqual(quality_rows[0].qualita_note, "Nota iniziale")

        updated_quality = update_quality_row(
            self.db,
            row=get_acquisition_row(self.db, matched_row.id),
            payload=AcquisitionQualityUpdateRequest(
                qualita_data_ricezione=date(2026, 7, 20),
                qualita_data_accettazione=date(2026, 7, 21),
                qualita_data_richiesta=date(2026, 7, 18),
                qualita_numero_analisi="EARLY-ANALYSIS",
            ),
            actor_id=1,
        )
        self.assertEqual(updated_quality.qualita_numero_analisi, "EARLY-ANALYSIS")
        self.assertFalse(get_acquisition_row(self.db, matched_row.id).validata_finale)

        save_quality_evaluation_note(
            self.db,
            row=get_acquisition_row(self.db, matched_row.id),
            payload=AcquisitionQualityNoteUpdateRequest(qualita_note="Nota aggiornata prima della chiusura"),
        )
        refreshed_quality_rows = list_quality_rows(self.db).items
        self.assertEqual([item.id for item in refreshed_quality_rows], [matched_row.id])
        self.assertEqual(refreshed_quality_rows[0].qualita_note, "Nota aggiornata prima della chiusura")
        self.assertIsNone(refreshed_quality_rows[0].qualita_valutazione)

        kpi_summary = build_supplier_kpi_summary(self.db, year=2026)
        self.assertEqual(kpi_summary.totals.lotti_totali, 0)
        self.assertEqual(kpi_summary.totals.lotti_non_valutati, 0)

        with self.assertRaises(HTTPException) as proposed_error:
            update_quality_row(
                self.db,
                row=get_acquisition_row(self.db, proposed_row.id),
                payload=AcquisitionQualityUpdateRequest(qualita_data_ricezione=date(2026, 7, 20)),
                actor_id=1,
            )
        self.assertEqual(proposed_error.exception.status_code, 400)

        persisted_match = get_acquisition_row(self.db, matched_row.id).certificate_match
        persisted_match.stato = "proposto"
        persisted_match.utente_conferma_id = None
        self.db.commit()
        self.assertEqual(list_quality_rows(self.db).items, [])

    def test_quality_evaluation_can_wait_for_ddt_when_certificate_blocks_are_green(self):
        supplier = Supplier(ragione_sociale="Test Supplier")
        certificate_document = Document(tipo_documento="certificato", nome_file_originale="cert.pdf", storage_key="cert-only.pdf")
        self.db.add_all([supplier, certificate_document])
        self.db.flush()
        certificate_document.fornitore_id = supplier.id
        row = AcquisitionRow(
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="CERT-1",
            colata="CAST-1",
        )
        self.db.add(row)
        self.db.flush()
        for block, field, value in [
            ("chimica", "Si", "0,9"),
            ("proprieta", "Rm", "350"),
            ("note", "nota_radioactive_free", "true"),
            ("requisiti", "customer_requirement_quote", "WITH PROOF OF TEMPER T62; VALUES SPECIALLY AGREED"),
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

        with patch(
            "app.modules.acquisition.service._current_quality_acceptance_date",
            return_value=date(2026, 7, 20),
        ):
            validated = validate_final_row(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=AcquisitionFinalValidationRequest(
                    qualita_tipo_controllo="diretta",
                    qualita_valutazione="accettato",
                    qualita_note=None,
                ),
                actor_id=1,
            )

        self.assertEqual(validated.qualita_valutazione, "accettato")
        self.assertEqual(validated.qualita_tipo_controllo, "diretta")
        self.assertEqual(
            get_acquisition_row(self.db, row.id).qualita_data_accettazione,
            date(2026, 7, 20),
        )
        self.assertFalse(validated.validata_finale)
        self.assertEqual(validated.stato_workflow, "attesa_ddt")

        with self.assertRaises(HTTPException) as locked_error:
            validate_final_row(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=AcquisitionFinalValidationRequest(
                    qualita_tipo_controllo="inversa",
                    qualita_valutazione="accettato",
                    qualita_note=None,
                ),
                actor_id=1,
            )
        self.assertEqual(locked_error.exception.status_code, 409)
        self.assertEqual(get_acquisition_row(self.db, row.id).qualita_tipo_controllo, "diretta")

        reopen_final_validation(self.db, row=get_acquisition_row(self.db, row.id), actor_id=1)
        reopened = save_quality_control_type(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=AcquisitionQualityControlTypeUpdateRequest(qualita_tipo_controllo="inversa"),
            actor_id=1,
        )
        self.assertEqual(reopened.qualita_tipo_controllo, "inversa")
        self.assertIsNone(reopened.qualita_valutazione)

    def test_quality_evaluation_sets_acceptance_date_for_every_outcome(self):
        expected_date = date(2026, 7, 20)

        for evaluation in ("accettato", "accettato_con_riserva", "respinto"):
            with self.subTest(evaluation=evaluation):
                row = AcquisitionRow(
                    cdq=f"ACCEPTANCE-DATE-{evaluation}",
                    qualita_data_accettazione=date(2026, 7, 1),
                )
                self.db.add(row)
                self.db.flush()
                for block, field, value in [
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

                with patch(
                    "app.modules.acquisition.service._current_quality_acceptance_date",
                    return_value=expected_date,
                ):
                    validated = validate_final_row(
                        self.db,
                        row=get_acquisition_row(self.db, row.id),
                        payload=AcquisitionFinalValidationRequest(
                            qualita_tipo_controllo="inversa",
                            qualita_valutazione=evaluation,
                            qualita_note="Motivazione" if evaluation != "accettato" else None,
                        ),
                        actor_id=1,
                    )

                self.assertEqual(
                    get_acquisition_row(self.db, row.id).qualita_data_accettazione,
                    expected_date,
                )

    def test_quality_note_autosave_only_changes_the_note(self):
        row = AcquisitionRow(
            cdq="AUTOSAVE-1",
            qualita_note="Nota iniziale",
            qualita_note_da_ricontrollare=True,
            stato_tecnico="giallo",
            stato_workflow="in_lavorazione",
            priorita_operativa="media",
            validata_finale=False,
        )
        self.db.add(row)
        self.db.commit()

        updated = save_quality_evaluation_note(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=AcquisitionQualityNoteUpdateRequest(qualita_note="  Ultima nota scritta  "),
        )

        persisted = get_acquisition_row(self.db, row.id)
        self.assertEqual(updated.qualita_note, "Ultima nota scritta")
        self.assertIsNone(updated.qualita_valutazione)
        self.assertTrue(persisted.qualita_note_da_ricontrollare)
        self.assertEqual(updated.stato_tecnico, "giallo")
        self.assertEqual(updated.stato_workflow, "in_lavorazione")
        self.assertEqual(updated.priorita_operativa, "media")
        self.assertFalse(updated.validata_finale)
        self.assertEqual(updated.history_events, [])

    def test_quality_note_autosave_is_locked_after_quality_evaluation(self):
        row = AcquisitionRow(
            cdq="AUTOSAVE-LOCKED",
            qualita_note="Nota chiusa",
            qualita_valutazione="accettato",
            stato_workflow="attesa_ddt",
            validata_finale=False,
        )
        self.db.add(row)
        self.db.commit()

        with self.assertRaises(HTTPException) as locked_error:
            save_quality_evaluation_note(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=AcquisitionQualityNoteUpdateRequest(qualita_note="Tentativo modifica"),
            )

        self.assertEqual(locked_error.exception.status_code, 409)
        self.assertEqual(get_acquisition_row(self.db, row.id).qualita_note, "Nota chiusa")

    def test_quality_control_type_is_saved_without_changing_quality_state(self):
        row = AcquisitionRow(cdq="CONTROL-TYPE", stato_workflow="in_lavorazione", validata_finale=False)
        self.db.add(row)
        self.db.commit()

        updated = save_quality_control_type(
            self.db,
            row=get_acquisition_row(self.db, row.id),
            payload=AcquisitionQualityControlTypeUpdateRequest(qualita_tipo_controllo="diretta"),
            actor_id=1,
        )

        self.assertEqual(updated.qualita_tipo_controllo, "diretta")
        self.assertIsNone(updated.qualita_valutazione)
        self.assertFalse(updated.validata_finale)
        self.assertEqual(updated.stato_workflow, "in_lavorazione")
        self.assertIn(
            ("quality", "tipo_controllo_qualita_aggiornato"),
            {(event.blocco, event.azione) for event in updated.history_events},
        )

    def test_quality_control_type_is_locked_after_quality_evaluation(self):
        row = AcquisitionRow(
            cdq="CONTROL-TYPE-LOCKED",
            qualita_tipo_controllo="diretta",
            qualita_valutazione="accettato",
            stato_workflow="attesa_ddt",
            validata_finale=False,
        )
        self.db.add(row)
        self.db.commit()

        with self.assertRaises(HTTPException) as locked_error:
            save_quality_control_type(
                self.db,
                row=get_acquisition_row(self.db, row.id),
                payload=AcquisitionQualityControlTypeUpdateRequest(qualita_tipo_controllo="inversa"),
                actor_id=1,
            )

        self.assertEqual(locked_error.exception.status_code, 409)
        self.assertEqual(get_acquisition_row(self.db, row.id).qualita_tipo_controllo, "diretta")

    def test_reserve_and_rejection_still_require_a_quality_note(self):
        original_acceptance_date = date(2026, 7, 1)
        row = AcquisitionRow(cdq="MANDATORY-NOTE", qualita_data_accettazione=original_acceptance_date)
        self.db.add(row)
        self.db.flush()
        for block, field, value in [
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

        for evaluation in ("accettato_con_riserva", "respinto"):
            with self.subTest(evaluation=evaluation):
                with self.assertRaises(HTTPException) as missing_note_error:
                    validate_final_row(
                        self.db,
                        row=get_acquisition_row(self.db, row.id),
                        payload=AcquisitionFinalValidationRequest(
                            qualita_tipo_controllo="diretta",
                            qualita_valutazione=evaluation,
                            qualita_note=None,
                        ),
                        actor_id=1,
                    )
                self.assertEqual(missing_note_error.exception.status_code, 400)
                self.assertIsNone(get_acquisition_row(self.db, row.id).qualita_valutazione)
                self.assertEqual(
                    get_acquisition_row(self.db, row.id).qualita_data_accettazione,
                    original_acceptance_date,
                )

    def test_certificate_first_merge_preserves_quality_evaluation_waiting_for_ddt(self):
        supplier = Supplier(ragione_sociale="Arconic Extrusions Hannover GmbH")
        certificate_document = Document(tipo_documento="certificato", nome_file_originale="cert.pdf", storage_key="cert-merge.pdf")
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key="ddt-merge.pdf")
        self.db.add_all([supplier, certificate_document, ddt_document])
        self.db.flush()
        certificate_document.fornitore_id = supplier.id
        ddt_document.fornitore_id = supplier.id
        source = AcquisitionRow(
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="EEP73062",
            colata="C70025341313",
            qualita_valutazione="accettato_con_riserva",
            qualita_tipo_controllo="inversa",
            qualita_note="Da usare con riserva",
            stato_workflow="attesa_ddt",
            validata_finale=False,
        )
        target = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="EEP73062",
            colata="C70025341313",
            ddt="28209127",
        )
        self.db.add_all([source, target])
        self.db.flush()
        for block, field, value in [
            ("chimica", "Si", "0,9"),
            ("proprieta", "Rm", "350"),
            ("note", "nota_radioactive_free", "true"),
            ("requisiti", "customer_requirement_quote", "WITH PROOF OF TEMPER T62; VALUES SPECIALLY AGREED"),
        ]:
            self.db.add(
                ReadValue(
                    acquisition_row_id=source.id,
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

        source_only_note = NoteTemplate(
            code="merge_source_only_note",
            text="Nota presente solo sul certificato",
            is_system=False,
        )
        shared_note = NoteTemplate(
            code="merge_shared_note",
            text="Nota gia presente anche sul DDT",
            is_system=False,
        )
        self.db.add_all([source_only_note, shared_note])
        self.db.flush()
        self.db.add_all(
            [
                AcquisitionHistoryEvent(
                    acquisition_row_id=source.id,
                    blocco="chimica",
                    azione="conferma_rapida_certificazione",
                ),
                AcquisitionHistoryEvent(
                    acquisition_row_id=source.id,
                    blocco="proprieta",
                    azione="conferma_blocco",
                ),
                AcquisitionHistoryEvent(
                    acquisition_row_id=source.id,
                    blocco="note",
                    azione="conferma_rapida_certificazione",
                ),
                AcquisitionHistoryEvent(
                    acquisition_row_id=target.id,
                    blocco="chimica",
                    azione="evento_target_pre_esistente",
                ),
                AcquisitionRowNoteTemplate(
                    acquisition_row_id=source.id,
                    note_template_id=source_only_note.id,
                ),
                AcquisitionRowNoteTemplate(
                    acquisition_row_id=source.id,
                    note_template_id=shared_note.id,
                ),
                AcquisitionRowNoteTemplate(
                    acquisition_row_id=target.id,
                    note_template_id=shared_note.id,
                ),
            ]
        )
        self.db.commit()

        merged = _merge_certificate_only_row_into_ddt_row(
            db=self.db,
            target_row=get_acquisition_row(self.db, target.id),
            source_row_id=source.id,
            actor_id=1,
        )

        self.assertTrue(merged)
        merged_row = get_acquisition_row(self.db, target.id)
        requirement_value = next(
            value
            for value in merged_row.values
            if value.blocco == "requisiti" and value.campo == "customer_requirement_quote"
        )
        self.assertEqual(requirement_value.valore_finale, "WITH PROOF OF TEMPER T62; VALUES SPECIALLY AGREED")
        self.assertEqual(merged_row.qualita_valutazione, "accettato_con_riserva")
        self.assertEqual(merged_row.qualita_tipo_controllo, "inversa")
        self.assertEqual(merged_row.qualita_note, "Da usare con riserva")
        self.assertIsNone(self.db.get(AcquisitionRow, source.id))

        merged_events = (
            self.db.query(AcquisitionHistoryEvent)
            .filter(AcquisitionHistoryEvent.acquisition_row_id == target.id)
            .all()
        )
        event_pairs = {(event.blocco, event.azione) for event in merged_events}
        self.assertIn(("chimica", "conferma_rapida_certificazione"), event_pairs)
        self.assertIn(("proprieta", "conferma_blocco"), event_pairs)
        self.assertIn(("note", "conferma_rapida_certificazione"), event_pairs)
        self.assertIn(("chimica", "evento_target_pre_esistente"), event_pairs)
        quick_confirmed_blocks = {
            event.blocco
            for event in merged_events
            if event.azione == "conferma_rapida_certificazione"
        }
        self.assertEqual(quick_confirmed_blocks, {"chimica", "note"})

        merged_note_template_ids = [
            note_template_id
            for (note_template_id,) in (
                self.db.query(AcquisitionRowNoteTemplate.note_template_id)
                .filter(AcquisitionRowNoteTemplate.acquisition_row_id == target.id)
                .order_by(AcquisitionRowNoteTemplate.note_template_id)
                .all()
            )
        ]
        self.assertEqual(
            merged_note_template_ids,
            sorted([source_only_note.id, shared_note.id]),
        )

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

    def test_coupled_row_without_match_record_gets_system_proposal(self):
        supplier = Supplier(ragione_sociale="Metalba S.p.A.")
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="26-00961.pdf", storage_key="ddt-metalba.pdf")
        certificate_document = Document(tipo_documento="certificato", nome_file_originale="CQF_26-0747.pdf", storage_key="cert-metalba.pdf")
        self.db.add_all([supplier, ddt_document, certificate_document])
        self.db.flush()
        ddt_document.fornitore_id = supplier.id
        certificate_document.fornitore_id = supplier.id

        row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            fornitore_id=supplier.id,
            fornitore_raw=supplier.ragione_sociale,
            cdq="26-0747",
            lega_base="6082F F",
            diametro="90",
            colata="25350C",
            ddt="26-00961",
            peso="2334",
            ordine="86/26",
        )
        self.db.add(row)
        self.db.flush()

        for block, field, value, source in [
            ("ddt", "numero_certificato_ddt", "26-0747", "ddt"),
            ("ddt", "colata", "25350C", "ddt"),
            ("ddt", "diametro", "90", "ddt"),
            ("ddt", "peso", "2334", "ddt"),
            ("ddt", "ddt", "26-00961", "ddt"),
            ("ddt", "customer_order_no", "86/26", "ddt"),
            ("match", "numero_certificato_certificato", "26-0747", "certificato"),
            ("match", "colata_certificato", "25350C", "certificato"),
            ("match", "diametro_certificato", "90", "certificato"),
            ("match", "peso_certificato", "2334", "certificato"),
            ("match", "ddt_certificato", "26-00961", "certificato"),
            ("match", "ordine_cliente_certificato", "86/26", "certificato"),
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
                    metodo_lettura="chatgpt" if source == "certificato" else "sistema",
                    fonte_documentale=source,
                )
            )
        self.db.commit()

        created = _ensure_proposed_match_for_coupled_row(db=self.db, row=get_acquisition_row(self.db, row.id), actor_id=1)

        self.assertTrue(created)
        self.db.expire_all()
        matched_row = get_acquisition_row(self.db, row.id)
        self.assertIsNotNone(matched_row.certificate_match)
        self.assertEqual(matched_row.certificate_match.stato, "proposto")
        self.assertEqual(matched_row.certificate_match.fonte_proposta, "sistema")
        self.assertEqual(matched_row.certificate_match.document_certificato_id, certificate_document.id)
        self.assertEqual(len(matched_row.certificate_match.candidates), 1)
        self.assertEqual(matched_row.certificate_match.candidates[0].stato, "scelto")

    def test_delete_single_document_row_removes_unique_document_and_frees_hash(self):
        document = Document(
            tipo_documento="ddt",
            nome_file_originale="ddt-unico.pdf",
            storage_key="ddt-unico.pdf",
            hash_file="hash-unico",
            stato_upload="persistente",
        )
        self.db.add(document)
        self.db.flush()
        page = DocumentPage(document_id=document.id, numero_pagina=1, immagine_pagina_storage_key="page-unico.png")
        self.db.add(page)
        self.db.flush()
        row = AcquisitionRow(document_ddt_id=document.id, cdq="1001", colata="C1001")
        self.db.add(row)
        self.db.flush()
        evidence = DocumentEvidence(
            document_id=document.id,
            document_page_id=page.id,
            acquisition_row_id=row.id,
            blocco="ddt",
            tipo_evidenza="text",
            testo_grezzo="test",
            metodo_estrazione="utente",
        )
        self.db.add(evidence)
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, row.id))
        self.assertTrue(preview.can_delete)
        self.assertTrue(preview.will_delete_document)
        self.assertTrue(preview.normal_reload_available)

        delete_single_document_acquisition_row(self.db, row=get_acquisition_row(self.db, row.id), actor_id=1)

        self.assertIsNone(self.db.get(AcquisitionRow, row.id))
        self.assertIsNone(self.db.get(Document, document.id))
        self.assertEqual(self.db.query(Document).filter(Document.hash_file == "hash-unico").count(), 0)
        self.assertEqual(self.db.query(DocumentEvidence).count(), 0)
        self.assertEqual(self.db.query(DocumentPage).count(), 0)

    def test_delete_single_document_row_keeps_shared_document_for_manual_fallback(self):
        document = Document(
            tipo_documento="certificato",
            nome_file_originale="cert-condiviso.pdf",
            storage_key="cert-condiviso.pdf",
            hash_file="hash-condiviso",
            stato_upload="persistente",
        )
        self.db.add(document)
        self.db.flush()
        first_row = AcquisitionRow(document_certificato_id=document.id, cdq="1001", colata="C1001")
        second_row = AcquisitionRow(document_certificato_id=document.id, cdq="1002", colata="C1002")
        self.db.add_all([first_row, second_row])
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, first_row.id))
        self.assertTrue(preview.can_delete)
        self.assertTrue(preview.shared_document)
        self.assertFalse(preview.will_delete_document)
        self.assertTrue(preview.fallback_required)

        delete_single_document_acquisition_row(self.db, row=get_acquisition_row(self.db, first_row.id), actor_id=1)

        self.assertIsNone(self.db.get(AcquisitionRow, first_row.id))
        self.assertIsNotNone(self.db.get(AcquisitionRow, second_row.id))
        self.assertIsNotNone(self.db.get(Document, document.id))
        self.assertEqual(self.db.query(Document).filter(Document.hash_file == "hash-condiviso").count(), 1)

    def test_delete_detached_certificate_row_removes_manual_block_and_keeps_ddt(self):
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key="ddt.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="cert.pdf",
            storage_key="cert.pdf",
        )
        self.db.add_all([ddt_document, certificate_document])
        self.db.flush()
        matched_row = AcquisitionRow(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            cdq="26-1820",
        )
        self.db.add(matched_row)
        self.db.commit()

        detached = detach_document_match(
            self.db,
            row=get_acquisition_row(self.db, matched_row.id),
            payload=DocumentMatchDetachRequest(motivo_breve="Separazione di prova"),
            actor_id=1,
        )
        certificate_row_id = detached.certificate_row.id
        preview = preview_acquisition_row_delete(
            self.db,
            row=get_acquisition_row(self.db, certificate_row_id),
        )

        self.assertTrue(preview.will_delete_document)
        self.assertEqual(preview.manual_blocks_cleanup_count, 1)

        delete_single_document_acquisition_row(
            self.db,
            row=get_acquisition_row(self.db, certificate_row_id),
            actor_id=1,
        )

        self.assertIsNone(self.db.get(AcquisitionRow, certificate_row_id))
        self.assertIsNone(self.db.get(Document, certificate_document.id))
        self.assertIsNotNone(self.db.get(AcquisitionRow, matched_row.id))
        self.assertIsNotNone(self.db.get(Document, ddt_document.id))
        self.assertEqual(self.db.query(ManualMatchBlock).count(), 0)

    def test_delete_single_ddt_row_keeps_ddt_shared_with_another_row(self):
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt-shared.pdf", storage_key="ddt-shared.pdf")
        self.db.add(ddt_document)
        self.db.flush()
        first_row = AcquisitionRow(document_ddt_id=ddt_document.id, cdq="1001")
        second_row = AcquisitionRow(document_ddt_id=ddt_document.id, cdq="1002")
        self.db.add_all([first_row, second_row])
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, first_row.id))

        self.assertTrue(preview.shared_document)
        self.assertEqual(preview.other_rows_count, 1)
        self.assertFalse(preview.will_delete_document)

        delete_single_document_acquisition_row(
            self.db,
            row=get_acquisition_row(self.db, first_row.id),
            actor_id=1,
        )

        self.assertIsNone(self.db.get(AcquisitionRow, first_row.id))
        self.assertIsNotNone(self.db.get(AcquisitionRow, second_row.id))
        self.assertIsNotNone(self.db.get(Document, ddt_document.id))

    def test_delete_shared_certificate_row_deactivates_its_block_but_keeps_document(self):
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt-block.pdf", storage_key="ddt-block.pdf")
        certificate_document = Document(
            tipo_documento="certificato",
            nome_file_originale="cert-shared.pdf",
            storage_key="cert-shared.pdf",
        )
        self.db.add_all([ddt_document, certificate_document])
        self.db.flush()
        first_row = AcquisitionRow(document_certificato_id=certificate_document.id, cdq="1001")
        second_row = AcquisitionRow(document_certificato_id=certificate_document.id, cdq="1002")
        self.db.add_all([first_row, second_row])
        self.db.flush()
        block = ManualMatchBlock(
            document_ddt_id=ddt_document.id,
            document_certificato_id=certificate_document.id,
            certificate_row_id=first_row.id,
            motivo_breve="Blocco di prova",
            attivo=True,
        )
        self.db.add(block)
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, first_row.id))

        self.assertTrue(preview.shared_document)
        self.assertFalse(preview.will_delete_document)
        self.assertEqual(preview.manual_blocks_cleanup_count, 1)

        delete_single_document_acquisition_row(
            self.db,
            row=get_acquisition_row(self.db, first_row.id),
            actor_id=1,
        )

        self.db.refresh(block)
        self.assertFalse(block.attivo)
        self.assertIsNone(block.certificate_row_id)
        self.assertIsNotNone(self.db.get(Document, certificate_document.id))
        self.assertIsNotNone(self.db.get(AcquisitionRow, second_row.id))

    def test_delete_row_keeps_parent_document_when_it_has_children(self):
        parent = Document(tipo_documento="certificato", nome_file_originale="parent.pdf", storage_key="parent.pdf")
        self.db.add(parent)
        self.db.flush()
        child = Document(
            tipo_documento="certificato",
            nome_file_originale="child.pdf",
            storage_key="child.pdf",
            documento_padre_id=parent.id,
        )
        row = AcquisitionRow(document_certificato_id=parent.id, cdq="parent")
        self.db.add_all([child, row])
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, row.id))

        self.assertTrue(preview.shared_document)
        self.assertEqual(preview.child_documents_count, 1)
        self.assertFalse(preview.will_delete_document)

        delete_single_document_acquisition_row(self.db, row=get_acquisition_row(self.db, row.id), actor_id=1)

        self.assertIsNotNone(self.db.get(Document, parent.id))
        self.assertIsNotNone(self.db.get(Document, child.id))

    def test_delete_row_is_blocked_while_ai_run_uses_it(self):
        document = Document(tipo_documento="ddt", nome_file_originale="active.pdf", storage_key="active.pdf")
        self.db.add(document)
        self.db.flush()
        row = AcquisitionRow(document_ddt_id=document.id, cdq="active")
        self.db.add(row)
        self.db.flush()
        run = AutonomousProcessingRun(
            current_row_id=row.id,
            stato="in_esecuzione",
            fase_corrente="ddt",
        )
        self.db.add(run)
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, row.id))

        self.assertFalse(preview.can_delete)
        self.assertIn("elaborazione AI attiva", preview.blocked_reason)

    def test_delete_row_is_blocked_when_document_is_queued_for_ai(self):
        document = Document(
            tipo_documento="certificato",
            nome_file_originale="queued.pdf",
            storage_key="queued.pdf",
        )
        self.db.add(document)
        self.db.flush()
        row = AcquisitionRow(document_certificato_id=document.id, cdq="queued")
        self.db.add(row)
        self.db.flush()
        run = AutonomousProcessingRun(
            certificate_document_ids=f"[{document.id}]",
            stato="in_coda",
            fase_corrente="avvio",
        )
        self.db.add(run)
        self.db.commit()

        preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, row.id))

        self.assertFalse(preview.can_delete)
        self.assertIn("elaborazione AI attiva", preview.blocked_reason)

    def test_storage_files_are_deleted_only_after_successful_database_commit(self):
        document = Document(
            tipo_documento="ddt",
            nome_file_originale="ordered.pdf",
            storage_key="ordered.pdf",
        )
        self.db.add(document)
        self.db.flush()
        page = DocumentPage(
            document_id=document.id,
            numero_pagina=1,
            immagine_pagina_storage_key="ordered-page.png",
        )
        row = AcquisitionRow(document_ddt_id=document.id, cdq="ordered")
        self.db.add_all([page, row])
        self.db.commit()

        original_commit = self.db.commit
        with patch("app.modules.acquisition.service._delete_storage_key_if_present") as delete_storage_file:
            def commit_after_file_safety_check():
                delete_storage_file.assert_not_called()
                original_commit()

            with patch.object(self.db, "commit", side_effect=commit_after_file_safety_check):
                delete_single_document_acquisition_row(
                    self.db,
                    row=get_acquisition_row(self.db, row.id),
                    actor_id=1,
                )

        self.assertEqual(delete_storage_file.call_count, 2)
        delete_storage_file.assert_any_call("ordered.pdf")
        delete_storage_file.assert_any_call("ordered-page.png")

    def test_database_failure_rolls_back_without_deleting_files(self):
        document = Document(tipo_documento="certificato", nome_file_originale="rollback.pdf", storage_key="rollback.pdf")
        self.db.add(document)
        self.db.flush()
        page = DocumentPage(document_id=document.id, numero_pagina=1, immagine_pagina_storage_key="rollback-page.png")
        row = AcquisitionRow(document_certificato_id=document.id, cdq="rollback")
        self.db.add_all([page, row])
        self.db.commit()

        with (
            patch.object(self.db, "commit", side_effect=IntegrityError("DELETE", {}, Exception("vincolo"))),
            patch("app.modules.acquisition.service._delete_storage_key_if_present") as delete_storage_file,
        ):
            with self.assertRaises(HTTPException) as raised:
                delete_single_document_acquisition_row(
                    self.db,
                    row=get_acquisition_row(self.db, row.id),
                    actor_id=1,
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("Nessun file e stato eliminato", raised.exception.detail)
        delete_storage_file.assert_not_called()
        self.assertIsNotNone(self.db.get(AcquisitionRow, row.id))
        self.assertIsNotNone(self.db.get(Document, document.id))

    def test_delete_single_document_row_blocks_matched_and_quality_rows(self):
        ddt_document = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key="ddt.pdf")
        certificate_document = Document(tipo_documento="certificato", nome_file_originale="cert.pdf", storage_key="cert.pdf")
        self.db.add_all([ddt_document, certificate_document])
        self.db.flush()
        matched_row = AcquisitionRow(document_ddt_id=ddt_document.id, document_certificato_id=certificate_document.id)
        quality_document = Document(tipo_documento="ddt", nome_file_originale="ddt-quality.pdf", storage_key="ddt-quality.pdf")
        self.db.add(quality_document)
        self.db.flush()
        quality_row = AcquisitionRow(
            document_ddt_id=quality_document.id,
            validata_finale=True,
            qualita_valutazione="accettato",
            stato_workflow="validata_quality",
        )
        self.db.add_all([matched_row, quality_row])
        self.db.commit()

        matched_preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, matched_row.id))
        quality_preview = preview_acquisition_row_delete(self.db, row=get_acquisition_row(self.db, quality_row.id))

        self.assertFalse(matched_preview.can_delete)
        self.assertFalse(quality_preview.can_delete)
        with self.assertRaises(HTTPException):
            delete_single_document_acquisition_row(self.db, row=get_acquisition_row(self.db, matched_row.id), actor_id=1)
        with self.assertRaises(HTTPException):
            delete_single_document_acquisition_row(self.db, row=get_acquisition_row(self.db, quality_row.id), actor_id=1)


if __name__ == "__main__":
    unittest.main()
