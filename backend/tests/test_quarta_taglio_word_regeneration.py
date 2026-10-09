"""No company calls: explicit out-of-range consent, failure and document identity."""
from unittest.mock import patch
from io import BytesIO
from copy import deepcopy
from docx import Document
from app.modules.acquisition.models import ReadValue
from fastapi import UploadFile
from app.modules.quarta_taglio import word_standard as ws
from app.modules.quarta_taglio import ddt_queue, ddt_word_reuse
from app.modules.quarta_taglio.models import QuartaTaglioStandardSelection
from app.modules.standards.models import NormativeStandard, NormativeStandardChemistry, NormativeStandardProperty
from fastapi import HTTPException
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.schemas import QuartaTaglioConformityIssueResponse
import test_quarta_taglio_ddt_history as history


class WordRegenerationTest(history.DdtHistoryTest):
    def standard(self, alloy='6082'):
        s = NormativeStandard(code='test-'+alloy, lega_base=alloy, lega_designazione=alloy,
                              norma='EN 755-2', trattamento_termico='T6')
        s.chemistry_limits = [NormativeStandardChemistry(elemento='Si', min_value=0.6, max_value=1.2)]
        self.db.add(s); self.db.flush()
        selected = self.db.query(QuartaTaglioStandardSelection).filter_by(cod_odp='OL1').one_or_none()
        if selected is None:
            selected = QuartaTaglioStandardSelection(cod_odp='OL1')
        selected.standard_id = s.id
        self.db.add(selected); self.db.commit()
        return s

    def tracked_word(self):
        self.standard()
        item = self.item()
        self.material()
        with self.allow_word():
            result = self.create(item)
        return item, self.db.get(history.QuartaTaglioFinalCertificate, result.id)

    def test_tracking_change_same_and_return_standard(self):
        item, c = self.tracked_word()
        original = deepcopy(c.word_standard_snapshot)
        self.assertEqual(original['origin'], 'generated')
        self.assertFalse(ws.is_stale(c, self.db))
        self.standard('7075')
        self.assertTrue(ws.is_stale(c, self.db))
        self.assertEqual(c.word_standard_snapshot, original)
        selection = self.db.query(QuartaTaglioStandardSelection).one()
        selection.standard_id = original['standard']['id']; self.db.commit()
        self.assertFalse(ws.is_stale(c, self.db))

    def test_limits_edit_same_id_detected_but_note_does_not_invalidate(self):
        _, c = self.tracked_word()
        std = self.db.get(NormativeStandard, c.word_standard_snapshot['standard']['id'])
        std.notes = 'Administrative note'; self.db.commit()
        self.assertFalse(ws.is_stale(c, self.db))
        std.chemistry_limits[0].max_value = 9; self.db.commit()
        self.assertTrue(ws.is_stale(c, self.db))

    def test_stale_download_preserves_bytes_pdf_upload_and_rebuild_rejected(self):
        item, c = self.tracked_word()
        key = c.storage_key_docx
        data = service._certificate_storage_path(key).read_bytes()
        self.standard('7075')
        with patch.object(service, 'build_forgialluminio_draft_docx', side_effect=AssertionError('silent rebuild')):
            path, _ = service.get_quarta_taglio_word_draft_file(self.db, draft_id=c.id, download_token=c.download_token)
            self.assertEqual(path.read_bytes(), data)
            with self.assertRaises(HTTPException) as exc:
                service.generate_quarta_taglio_certificate_pdf(self.db, certificate_id=c.id, actor=self.actor)
            self.assertEqual(exc.exception.status_code, 409)
            with self.assertRaises(HTTPException):
                service.upload_quarta_taglio_word_file(self.db, cod_odp=c.cod_odp, certificate_id=c.id,
                    actor=self.actor, uploaded_file=UploadFile(filename='edited.docx', file=BytesIO(data)))
            with self.assertRaises(HTTPException):
                service.upload_quarta_taglio_additional_pages(self.db, cod_odp=c.cod_odp, certificate_id=c.id,
                    actor=self.actor, uploaded_file=UploadFile(filename='extra.docx', file=BytesIO(data)))
            with self.assertRaises(HTTPException):
                service._rebuild_certificate_word_after_pdf_attachment(self.db, detail=self.detail(item), certificate=c, actor=self.actor)
        self.assertEqual(c.storage_key_docx, key)
        self.assertEqual(service._certificate_storage_path(key).read_bytes(), data)

    def test_stale_is_visible_in_detail_register_queue_and_has_no_pdf_action(self):
        item, c = self.tracked_word()
        self.standard('7075')
        detail = self.detail(item)
        self.assertTrue(detail.word_info.standard_outdated)
        self.assertEqual(detail.display_status_label, 'Word da aggiornare')
        with patch.object(service, 'get_quarta_taglio_detail', return_value=detail):
            self.assertTrue(service._serialize_final_certificate_register_item(c, db=self.db).standard_outdated)
        row = ddt_queue._project(self.db, [item])[0]
        self.assertEqual(row.label, 'Word da aggiornare')
        self.assertIsNone(row.pdf_action)

    def test_regeneration_updates_snapshot_without_changing_number(self):
        item, c = self.tracked_word()
        number, old = c.certificate_number, c.storage_key_docx
        self.standard('7075')
        with self.allow_word():
            self.create(item, certificate_id=c.id, force_regenerate=True)
        self.assertFalse(ws.is_stale(c, self.db))
        self.assertEqual(c.word_standard_snapshot['standard']['lega_base'], '7075')
        self.assertEqual(c.certificate_number, number)
        self.assertTrue(service._certificate_storage_path(old).exists())

    def test_failed_or_concurrent_generation_preserves_file_and_provenance(self):
        item, c = self.tracked_word()
        old, saved = c.storage_key_docx, deepcopy(c.word_standard_snapshot)
        self.standard('7075')
        def change(**kwargs):
            # Simulate a committed selection change while the file is built.
            self.standard('7150')
        with self.allow_word(), patch.object(service, 'build_forgialluminio_draft_docx', side_effect=change):
            with self.assertRaises(HTTPException) as exc:
                self.create(item, certificate_id=c.id, force_regenerate=True)
            self.assertEqual(exc.exception.status_code, 409)
        self.db.rollback(); self.db.refresh(c)
        self.assertEqual(c.storage_key_docx, old)
        self.assertEqual(c.word_standard_snapshot, saved)

    def test_closed_pdf_is_preserved_but_cannot_be_source_after_standard_change(self):
        item, c = self.tracked_word()
        c.status='pdf_final'; self.db.commit()
        self.standard('7075')
        self.assertFalse(ws.is_stale(c, self.db))
        self.assertTrue(ws.is_stale(c, self.db, for_reuse=True))
        later = self.item(IdDocumento='200', DDT='78-02/09/2026')
        self.assertEqual(ddt_word_reuse.plan_item(self.db, later)['reason'], 'word_standard_outdated')
        c.status='draft'; self.db.commit()
        self.assertTrue(ws.is_stale(c, self.db))

    def test_legacy_baseline_idempotent_does_not_claim_original_generation(self):
        self.standard()
        c = self.cert(self.item())
        path = service._certificate_storage_path(c.storage_key_docx)
        data = path.read_bytes()
        self.assertEqual(ws.baseline_legacy(self.db), 1)
        self.db.commit()
        self.assertEqual(ws.baseline_legacy(self.db), 0)
        self.assertEqual(c.word_standard_snapshot['origin'], 'legacy_baseline')
        self.assertFalse(ws.is_stale(c, self.db))
        self.standard('7075')
        self.assertTrue(ws.is_stale(c, self.db))
        self.assertEqual(path.read_bytes(), data)

    def test_material_changes_alone_are_not_standard_changes(self):
        item, c = self.tracked_word()
        self.material(cdq='NEW', colata='NEW')
        self.assertFalse(ws.is_stale(c, self.db))

    def test_removed_selection_blocks_until_same_standard_is_restored(self):
        _, c = self.tracked_word()
        selection = self.db.query(QuartaTaglioStandardSelection).one()
        sid = selection.standard_id
        self.db.delete(selection); self.db.commit()
        self.assertTrue(ws.is_stale(c, self.db))
        with self.assertRaises(HTTPException):
            ws.require_current(self.db, c)
        self.db.add(QuartaTaglioStandardSelection(cod_odp='OL1', standard_id=sid))
        self.db.commit()
        self.assertFalse(ws.is_stale(c, self.db))

    def test_mechanical_range_change_is_detected_and_reversion_restores_alignment(self):
        _, c = self.tracked_word()
        std = self.db.get(NormativeStandard, c.word_standard_snapshot['standard']['id'])
        limit = NormativeStandardProperty(proprieta='Rm', misura_min=0, misura_max=100,
                                          min_value=300, max_value=None)
        std.property_limits.append(limit); self.db.commit()
        c.word_standard_snapshot = ws.provenance(ws.snapshot(self.db, 'OL1'), 'generated')
        self.db.commit()
        for field, changed in [('misura_max', 80), ('min_value', 310), ('max_value', 500)]:
            with self.subTest(field=field):
                original = getattr(limit, field)
                setattr(limit, field, changed); self.db.commit()
                self.assertTrue(ws.is_stale(c, self.db))
                setattr(limit, field, original); self.db.commit()
                self.assertFalse(ws.is_stale(c, self.db))

    def test_change_affects_all_open_ol_quotas_but_not_other_ol_or_closed_pdf(self):
        _, first = self.tracked_word()
        second = self.cert(self.item(IdDocumento='200', CodF3='009999'))
        closed = self.cert(self.item(IdDocumento='201'), pdf=True)
        other = self.cert(self.item(IdDocumento='300', ORP='OL2'))
        for c in (second, closed):
            ws.copy_provenance(first, c)
        other.word_standard_snapshot = ws.provenance(ws.snapshot(self.db, 'OL2'), 'generated')
        self.db.commit()
        closed_state = (closed.storage_key_docx, closed.storage_key_pdf, closed.updated_at)
        self.standard('7075')
        self.assertTrue(ws.is_stale(first, self.db))
        self.assertTrue(ws.is_stale(second, self.db))
        self.assertFalse(ws.is_stale(closed, self.db))
        self.assertTrue(ws.is_stale(closed, self.db, for_reuse=True))
        self.assertFalse(ws.is_stale(other, self.db))
        self.assertEqual((closed.storage_key_docx, closed.storage_key_pdf, closed.updated_at), closed_state)

    def test_baseline_without_standard_detects_later_selection_without_touching_tracked_word(self):
        c = self.cert(self.item())
        self.assertEqual(ws.baseline_legacy(self.db), 1)
        self.db.commit()
        saved = deepcopy(c.word_standard_snapshot)
        self.assertIsNone(saved['standard'])
        self.standard()
        self.assertTrue(ws.is_stale(c, self.db))
        self.assertEqual(ws.baseline_legacy(self.db), 0)
        self.assertEqual(c.word_standard_snapshot, saved)

    def test_limit_row_order_and_administrative_code_do_not_change_snapshot(self):
        _, c = self.tracked_word()
        std = self.db.get(NormativeStandard, c.word_standard_snapshot['standard']['id'])
        std.chemistry_limits.append(NormativeStandardChemistry(elemento='Mg', min_value=0.5, max_value=1.2))
        self.db.commit()
        saved = ws.snapshot(self.db, 'OL1')
        values = [(v.elemento, v.min_value, v.max_value) for v in std.chemistry_limits]
        std.chemistry_limits.clear(); self.db.flush()
        std.chemistry_limits = [NormativeStandardChemistry(elemento=e, min_value=lo, max_value=hi)
                                for e, lo, hi in reversed(values)]
        std.code = 'renamed-administrative-code'; std.notes = 'note only'
        self.db.commit()
        self.assertEqual(ws.snapshot(self.db, 'OL1'), saved)

    def test_register_does_not_recalculate_closed_pdf_against_new_ol_standard(self):
        item = self.item()
        cert = self.cert(item, pdf=True, conformity_status='conforme')
        with patch.object(service, 'get_quarta_taglio_detail', side_effect=AssertionError('closed PDF must not read live standard')):
            self.assertEqual(service._live_certificate_conformity_for_register(self.db, certificate=cert), ('conforme', []))
        self.assertFalse(self.db.dirty)

    def issues(self):
        return [QuartaTaglioConformityIssueResponse(block=block, field=field,
            value=value, standard_min=minimum, standard_max=maximum, message='Fuori limite')
            for block, field, value, minimum, maximum in
            [('chimica', 'Si', 2, None, 1), ('proprieta', 'Rm', 300, 320, None)]]

    def test_first_generation_nonconforming_requires_explicit_consent(self):
        item = self.item()
        self.material()
        with self.allow_word(), patch.object(service, '_build_standard_conformity', return_value=('non_conforme', self.issues())):
            with self.assertRaises(HTTPException) as caught:
                self.create(item)
            self.assertEqual(caught.exception.status_code, 409)
            result = self.create(item, force_non_conforming=True)
        cert = self.db.get(history.QuartaTaglioFinalCertificate, result.id)
        self.assertEqual(cert.conformity_status, 'non_conforme')
        self.assertIsNone(cert.storage_key_pdf)

    def test_regeneration_keeps_identity_and_requires_consent_again(self):
        item = self.item()
        self.material()
        with self.allow_word():
            result = self.create(item)
        cert = self.db.get(history.QuartaTaglioFinalCertificate, result.id)
        old_key, number = cert.storage_key_docx, cert.certificate_number
        old_content = service._certificate_storage_path(old_key).read_bytes()
        with self.allow_word(), patch.object(service, '_build_standard_conformity', return_value=('non_conforme', self.issues())):
            with self.assertRaises(HTTPException) as caught:
                self.create(item, certificate_id=cert.id, force_regenerate=True)
            self.assertEqual(caught.exception.status_code, 409)
            self.assertEqual(cert.storage_key_docx, old_key)
            updated = self.create(item, certificate_id=cert.id, force_regenerate=True, force_non_conforming=True)
        self.assertEqual(updated.id, result.id)
        self.assertEqual(cert.certificate_number, number)
        self.assertNotEqual(cert.storage_key_docx, old_key)
        self.assertEqual(service._certificate_storage_path(old_key).read_bytes(), old_content)
        self.assertEqual(cert.conformity_status, 'non_conforme')

    def test_failed_generation_does_not_replace_current_file(self):
        item = self.item()
        self.material()
        with self.allow_word():
            result = self.create(item)
        cert = self.db.get(history.QuartaTaglioFinalCertificate, result.id)
        old_key = cert.storage_key_docx
        old_content = service._certificate_storage_path(old_key).read_bytes()
        with self.allow_word(), patch.object(service, 'build_forgialluminio_draft_docx', side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError):
                self.create(item, certificate_id=cert.id, force_regenerate=True)
        self.db.rollback()
        self.db.refresh(cert)
        self.assertEqual(cert.storage_key_docx, old_key)
        self.assertEqual(service._certificate_storage_path(old_key).read_bytes(), old_content)

    def test_real_docx_regeneration_replaces_technical_limits_after_consent(self):
        # Actual document builder and actual conformity calculation; only unrelated
        # completeness gates are bypassed for this minimal, isolated fixture.
        std = self.standard()
        std.misura_tipo = 'diametro'
        std.property_limits = [NormativeStandardProperty(proprieta='Rm', misura_min=0,
                                misura_max=500, min_value=300)]
        item = self.item()
        _, incoming = self.material()
        for block, field, value in [('chimica', 'Si', '0.8'), ('proprieta', 'Rm', '350')]:
            self.db.add(ReadValue(acquisition_row_id=incoming.id, blocco=block, campo=field,
                valore_finale=value, stato='confermato', metodo_lettura='manuale', fonte_documentale='certificato'))
        self.db.commit()
        with patch.object(service, '_word_creation_blockers', return_value=[]):
            result = self.create(item)
            c = self.db.get(history.QuartaTaglioFinalCertificate, result.id)
            old_path = service._certificate_storage_path(c.storage_key_docx)
            original_bytes = old_path.read_bytes()
            std.chemistry_limits[0].max_value = 0.7
            std.property_limits[0].min_value = 400
            self.db.commit()
            with self.assertRaises(HTTPException) as exc:
                self.create(item, certificate_id=c.id, force_regenerate=True)
            self.assertEqual(exc.exception.status_code, 409)
            self.create(item, certificate_id=c.id, force_regenerate=True, force_non_conforming=True)
        new_path = service._certificate_storage_path(c.storage_key_docx)
        def rows(path):
            return [[cell.text for cell in row.cells] for table in Document(path).tables for row in table.rows]
        before, after = rows(old_path), rows(new_path)
        self.assertNotEqual(before, after)
        self.assertTrue(any(row[0] == '%\u00a0max' and '1,2' in row for row in before))
        self.assertTrue(any(row[0] == '%\u00a0max' and '0,7' in row for row in after))
        self.assertTrue(any(row[0] == 'Min.' and '300' in row for row in before))
        self.assertTrue(any(row[0] == 'Min.' and '400' in row for row in after))
        self.assertEqual(c.conformity_status, 'non_conforme')
        self.assertFalse(ws.is_stale(c, self.db))
        self.assertEqual(old_path.read_bytes(), original_bytes)

    def test_standard_change_during_pdf_conversion_does_not_publish_pdf(self):
        _, c = self.tracked_word()
        old_snapshot = deepcopy(c.word_standard_snapshot)
        def convert(word, pdf):
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(b'%PDF isolated conversion test')
            self.standard('7075')
        with self.allow_word(), patch.object(service, 'convert_docx_to_pdf', side_effect=convert) as converter:
            with self.assertRaises(HTTPException) as exc:
                service.generate_quarta_taglio_certificate_pdf(self.db, certificate_id=c.id, actor=self.actor)
        self.assertEqual(converter.call_count, 1)
        self.assertEqual(exc.exception.status_code, 409)
        self.db.rollback(); self.db.refresh(c)
        self.assertEqual(c.status, 'draft')
        self.assertIsNone(c.storage_key_pdf)
        self.assertEqual(c.word_standard_snapshot, old_snapshot)
        self.assertEqual(self.db.query(history.QuartaTaglioCertificatePdfVersion).count(), 0)
