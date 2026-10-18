"""Isolated register projection tests; no external SQL or real documents."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.startup import bootstrap  # noqa: F401
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as Certificate, QuartaTaglioEsolverLink, QuartaTaglioDdtWorkItem


class RegisterPresentationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        patcher = patch.object(service.settings, 'document_storage_root', self.files.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cert(self, **changes):
        values = dict(cod_odp='OL1', cod_f3='096013900', certificate_number='7009_00_00/26',
                      draft_number='7009_00_00/26', unit_key='early', ddt=None, status='draft',
                      word_source='generated', storage_key_docx='base.docx', cdq_key='CDQ1',
                      cdq_signature=['CDQ1|COL1'],
                      cdq_values=[dict(cdq='CDQ1', colata='COL1', cod_art='096013900', lotti=['1','2'])])
        values.update(changes)
        c = Certificate(**values)
        self.db.add(c)
        self.db.commit()
        for key in [c.storage_key_docx, c.storage_key_pdf]:
            if key:
                Path(self.files.name, key).write_bytes(b'fixture')
        return c

    def shipment(self, **changes):
        return self.cert(**dict(dict(ddt='2457-12/10/2026', unit_key='shipment1',
                                    esolver_id_documento='100', esolver_id_riga_doc='1',
                                    storage_key_docx='shipment.docx', word_source='ddt_reused'), **changes))

    def visible(self):
        return service.list_quarta_taglio_final_certificates(self.db)

    def test_base_hidden_but_database_and_documents_unchanged(self):
        base = self.cert()
        shipped = self.shipment(status='pdf_final', storage_key_pdf='closed.pdf')
        before = deepcopy(base.cdq_values)
        statements = []
        event.listen(self.engine, 'before_cursor_execute', lambda conn,cursor,sql,*args: statements.append(sql))
        with patch.object(service, '_fetch_esolver_ddt_rows_batch', side_effect=AssertionError('remote')):
            result = self.visible()
        self.assertEqual([i.id for i in result.items], [shipped.id])
        self.assertEqual(result.total_items, 1)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in statements))
        self.assertEqual(self.db.query(Certificate).count(), 2)
        self.assertEqual(base.cdq_values, before)
        self.assertIsNone(base.ddt)
        self.assertFalse(self.db.dirty)
        self.assertEqual(Path(self.files.name, 'base.docx').read_bytes(), b'fixture')
        self.assertEqual(Path(self.files.name, 'closed.pdf').read_bytes(), b'fixture')

    def test_raw_and_other_inherited_workmanship_remain_visible_even_with_legacy_empty_key(self):
        base = self.cert(unit_key=None)
        child = self.shipment(cod_f3='096013930', certificate_number='7009_00_30/26', word_source='inherited')
        self.assertEqual({i.id for i in self.visible().items}, {base.id,child.id})
        self.assertFalse(next(i for i in self.visible().items if i.id == base.id).ddt_received)

    def test_prepared_inherited_workmanship_without_ddt_is_not_hidden(self):
        base = self.cert()
        child = self.cert(cod_f3='096013930', certificate_number='7009_00_30/26', word_source='inherited')
        self.assertEqual(len(self.visible().items), 2)

    def test_hidden_raw_remains_an_inheritance_source_for_another_workmanship(self):
        base = self.cert()
        shipped = self.shipment()
        child = self.cert(cod_f3='096013930', certificate_number='7009_00_30/26', word_source='inherited')
        self.assertEqual({i.id for i in self.visible().items}, {shipped.id, child.id})
        sources = service._ordered_inheritance_source_certificates(
            self.db.query(Certificate).order_by(Certificate.id).all(), cod_odp='OL1',
            current_cod_f3=child.cod_f3, raw_cod_f3=base.cod_f3,
            visited_numbers={child.certificate_number})
        self.assertEqual(sources[0].id, base.id)
        self.assertEqual(self.db.query(Certificate).count(), 3)

    def test_same_ddt_different_lines_and_later_ddt_never_collapsed(self):
        base = self.cert()
        a = self.shipment(quantita=167)
        b = self.shipment(unit_key='shipment2', esolver_id_riga_doc='2', quantita=106)
        c = self.shipment(unit_key='shipment3', ddt='2500-20/10/2026', esolver_id_documento='200')
        self.assertEqual({i.id for i in self.visible().items}, {a.id,b.id,c.id})

    def test_changed_material_or_number_is_not_hidden(self):
        base = self.cert()
        shipped = self.shipment(cdq_values=[dict(cdq='CDQ1',colata='COL1',cod_art='096013900',lotti=['1','2','3'])])
        self.assertEqual(len(self.visible().items), 2)
        shipped.cdq_values = deepcopy(base.cdq_values)
        shipped.certificate_number = 'OTHER'
        self.db.commit()
        self.assertEqual(len(self.visible().items), 2)

    def test_incomplete_material_evidence_does_not_hide_base(self):
        self.cert(cdq_values=[])
        self.shipment(cdq_values=[])
        self.assertEqual(len(self.visible().items), 2)

    def test_missing_shipment_file_keeps_base_visible_and_reports_ddt_received(self):
        base = self.cert()
        self.shipment(storage_key_docx='not-created.docx')
        Path(self.files.name, 'not-created.docx').unlink()
        result = self.visible()
        self.assertEqual(len(result.items), 2)
        self.assertTrue(next(i for i in result.items if i.id == base.id).ddt_received)

    def test_snapshot_outside_esolver_window_reports_ddt_received_without_assigning_it(self):
        base = self.cert()
        now = datetime.now(timezone.utc)
        self.db.add(QuartaTaglioDdtWorkItem(source_key='test', id_documento='10', id_riga_doc='1',
                    cod_odp='OL1', cod_f3='096013900', ddt_raw='1-01/09/2026',
                    certification_unit_key='snapshot', first_seen_at=now,last_seen_at=now,source_present=False))
        self.db.commit()
        result = self.visible().items[0]
        self.assertTrue(result.ddt_received)
        self.assertIsNone(result.ddt)
        self.assertIsNone(base.ddt)

    def test_cache_received_requires_same_ol_and_f3_and_actual_ddt(self):
        base = self.cert()
        link = QuartaTaglioEsolverLink(cod_odp='OL1',status='ok', rows=[
            dict(orp='OTHER',cod_f3='096013900',ddt='1'), dict(orp='OL1',cod_f3='OTHER',ddt='1'),
            dict(orp='OL1',cod_f3='096013900',ddt=None)])
        self.db.add(link); self.db.commit()
        self.assertFalse(self.visible().items[0].ddt_received)
        link.rows = [dict(orp='OL1',cod_f3='096013900',ddt='1')]
        self.db.commit()
        self.assertTrue(self.visible().items[0].ddt_received)

    def test_refresh_replaces_base_with_all_shipments_without_mutating_source(self):
        base = self.cert()
        a = self.shipment()
        b = self.shipment(unit_key='shipment2',esolver_id_riga_doc='2')
        with patch.object(service, '_stale_register_cod_odps', return_value=[]):
            result = service.refresh_quarta_taglio_visible_final_certificates(self.db, certificate_ids=[base.id,a.id])
        self.assertEqual(result.hidden_certificate_ids, [base.id])
        self.assertEqual({i.id for i in result.items}, {a.id,b.id})
        self.assertEqual(len(result.items), 2)
        self.assertIsNone(base.ddt)

    def test_reopened_pdf_keeps_shipment_and_hides_only_base(self):
        self.cert()
        reopened = self.shipment(status='draft',storage_key_pdf=None)
        self.assertEqual([i.id for i in self.visible().items], [reopened.id])

    def test_pdf_or_partial_identity_without_ddt_is_not_treated_as_an_early_base(self):
        for changes in [dict(storage_key_pdf='legacy.pdf'),dict(esolver_id_documento='100')]:
            with self.subTest(changes=changes):
                self.db.query(Certificate).delete(); self.db.commit()
                base = self.cert(**changes)
                shipped = self.shipment()
                self.assertEqual({i.id for i in self.visible().items}, {base.id,shipped.id})
