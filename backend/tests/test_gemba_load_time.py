import unittest
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.startup import bootstrap
from app.modules.acquisition.load_time import (
    certificate_load_time_on_ddt_link, gemba_time_bounds, row_load_time,
)
from app.modules.acquisition.models import AcquisitionRow, Document
from app.modules.acquisition.schemas import AcquisitionRowCreateRequest, DocumentMatchDetachRequest
from app.modules.acquisition.service import (
    _create_ddt_clone_row_for_manual_link, _merge_certificate_only_row_into_ddt_row,
    create_acquisition_row, detach_document_match, get_acquisition_row,
    list_gemba_walk_rows, serialize_acquisition_row_list_item,
)


DAY = date(2026, 9, 30)


def utc(hour, minute=0, second=0):
    return datetime(2026, 9, 30, hour, minute, second, tzinfo=UTC)


class GembaLoadTimeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()
        self.logger = patch("app.modules.acquisition.service.log_service.record")
        self.logger.start()

    def tearDown(self):
        self.logger.stop()
        self.db.close()
        self.engine.dispose()

    def doc(self, kind, loaded):
        doc = Document(tipo_documento=kind, nome_file_originale=f"{kind}.pdf",
                       storage_key=f"{uuid4()}.pdf", data_upload=loaded)
        self.db.add(doc)
        self.db.commit()
        return doc

    def row(self, ddt=None, cert=None):
        result = create_acquisition_row(self.db, AcquisitionRowCreateRequest(
            document_ddt_id=ddt.id if ddt else None,
            document_certificato_id=cert.id if cert else None,
            fornitore_raw="Fornitore prova", cdq="CDQ-1",
        ), actor_id=1, actor_email="test@example.test")
        return get_acquisition_row(self.db, result.id)

    def filtered(self, start="00:00", end="23:59", **kwargs):
        return list_gemba_walk_rows(self.db, date_from=DAY, date_to=DAY,
                                    time_from=start, time_to=end, **kwargs)

    def test_trucks_filter_by_upload_not_late_ai_creation_and_keep_incoming_filters(self):
        morning = self.row(ddt=self.doc("ddt", utc(6, 30)))  # 08:30 Italy
        afternoon = self.row(cert=self.doc("certificato", utc(12, 20)))
        for row in (morning, afternoon):
            row.created_at = utc(18)
        afternoon.fornitore_raw = "Altro fornitore"
        self.db.commit()
        self.assertEqual([r.id for r in self.filtered("08:00", "09:00")], [morning.id])
        self.assertEqual([r.id for r in self.filtered("14:00", "15:00")], [afternoon.id])
        self.assertEqual(len(self.filtered()), 2)
        self.assertEqual(len(self.filtered(query_one="Altro")), 1)
        morning.validata_finale = True
        self.db.commit()
        self.assertEqual([r.id for r in self.filtered(view="confirmed")], [morning.id])
        self.assertEqual([r.id for r in self.filtered()], [afternoon.id])

    def test_simultaneous_trucks_and_last_minute_seconds_are_included(self):
        first = self.row(ddt=self.doc("ddt", utc(6, 30, 59)))
        second = self.row(cert=self.doc("certificato", utc(6, 30, 59)))
        self.row(ddt=self.doc("ddt", utc(6, 31)))
        self.assertEqual({r.id for r in self.filtered("08:30", "08:30")}, {first.id, second.id})

    def test_certificate_first_direct_ddt_link_keeps_initial_reference(self):
        cert = self.doc("certificato", utc(6, 30))
        row = self.row(cert=cert)
        ddt = self.doc("ddt", utc(12, 20))
        row.incoming_loaded_at = certificate_load_time_on_ddt_link(row, ddt)
        row.document_ddt_id = ddt.id
        self.db.commit()
        self.db.expire_all()
        response = serialize_acquisition_row_list_item(get_acquisition_row(self.db, row.id))
        self.assertEqual(response.incoming_loaded_at, utc(6, 30))
        self.assertEqual([r.id for r in self.filtered("08:00", "09:00")], [row.id])
        self.assertEqual(self.filtered("14:00", "15:00"), [])

    def test_merge_keeps_earliest_reference_in_both_orders_without_changing_siblings(self):
        for cert_hour, ddt_hour in ((6, 12), (12, 6)):
            with self.subTest(cert_hour=cert_hour):
                cert = self.doc("certificato", utc(cert_hour))
                ddt = self.doc("ddt", utc(ddt_hour))
                source = self.row(cert=cert)
                target = self.row(ddt=ddt, cert=cert)
                sibling = self.row(ddt=ddt, cert=cert)
                source_id = source.id
                self.assertTrue(_merge_certificate_only_row_into_ddt_row(
                    db=self.db, source_row_id=source_id, target_row=target, actor_id=1))
                self.assertIsNone(self.db.get(AcquisitionRow, source_id))
                self.assertEqual(row_load_time(get_acquisition_row(self.db, target.id)), utc(6))
                self.assertEqual(row_load_time(get_acquisition_row(self.db, sibling.id)), utc(ddt_hour))

    def test_reused_old_certificate_does_not_backdate_new_delivery(self):
        cert = self.doc("certificato", utc(6) - timedelta(days=30))
        old_row = self.row(ddt=self.doc("ddt", utc(6) - timedelta(days=30)), cert=cert)
        new_row = self.row(ddt=self.doc("ddt", utc(12, 20)), cert=cert)
        self.assertEqual(row_load_time(new_row), utc(12, 20))
        self.assertEqual([r.id for r in self.filtered()], [new_row.id])
        self.assertNotEqual(row_load_time(old_row), row_load_time(new_row))

    def test_detach_clone_and_relink_to_new_delivery_preserve_correct_reference(self):
        cert = self.doc("certificato", utc(6))
        original = self.row(ddt=self.doc("ddt", utc(6)), cert=cert)
        result = detach_document_match(self.db, row=original, payload=DocumentMatchDetachRequest(), actor_id=1)
        detached = get_acquisition_row(self.db, result.certificate_row.id)
        self.assertEqual(row_load_time(detached), utc(6))
        clone = _create_ddt_clone_row_for_manual_link(db=self.db, source_row=original, actor_id=1)
        self.assertEqual(row_load_time(clone), utc(6))
        new_ddt = self.doc("ddt", utc(12))
        self.assertEqual(certificate_load_time_on_ddt_link(detached, new_ddt), utc(12))
        target = self.row(ddt=new_ddt, cert=cert)
        self.assertTrue(_merge_certificate_only_row_into_ddt_row(
            db=self.db, source_row_id=detached.id, target_row=target, actor_id=1))
        self.assertEqual(row_load_time(get_acquisition_row(self.db, target.id)), utc(12))

    def test_legacy_fallback_matches_display_and_filter(self):
        cert = self.doc("certificato", utc(6))
        row = AcquisitionRow(document_certificato_id=cert.id, created_at=utc(18))
        self.db.add(row)
        self.db.commit()
        result = self.filtered("08:00", "09:00")
        self.assertEqual([r.id for r in result], [row.id])
        self.assertEqual(result[0].incoming_loaded_at, utc(6))


class GembaClockTest(unittest.TestCase):
    def test_api_passes_selected_hours_and_rejects_invalid_format(self):
        from app.core.deps import get_db, get_current_user
        from app.modules.acquisition import router as routes
        app = FastAPI()
        app.include_router(routes.router, prefix="/api/acquisition")
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_current_user] = lambda: object()
        with TestClient(app) as client, patch.object(routes, "list_gemba_walk_rows", return_value=[]) as read:
            base = "/api/acquisition/gemba-walk?date_from=2026-09-30&date_to=2026-09-30"
            self.assertEqual(client.get(base + "&time_from=08:00&time_to=09:00").status_code, 200)
            self.assertEqual(read.call_args.kwargs["time_from"], "08:00")
            self.assertEqual(read.call_args.kwargs["time_to"], "09:00")
            self.assertEqual(client.get(base).status_code, 200)
            self.assertEqual(read.call_args.kwargs["time_to"], "23:59")
            read.reset_mock()
            self.assertEqual(client.get(base + "&time_from=24:00").status_code, 422)
            read.assert_not_called()

    def test_full_italian_day_in_summer_winter_and_dst_days(self):
        for day, hours in ((DAY, 24), (date(2026, 1, 10), 24),
                           (date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            start, end = gemba_time_bounds(day, day, "00:00", "23:59")
            self.assertEqual((end-start).total_seconds()/3600, hours)
        start, _ = gemba_time_bounds(DAY, DAY, "00:00", "23:59")
        self.assertEqual(start, utc(22) - timedelta(days=1))

    def test_invalid_intervals_and_spring_clock_gap(self):
        for start, end in (("15:00", "08:00"), ("24:00", "23:59"), ("08:30:00", "09:00"), ("", "23:59")):
            with self.assertRaises(HTTPException):
                gemba_time_bounds(DAY, DAY, start, end)
        with self.assertRaises(HTTPException):
            gemba_time_bounds(date(2026, 3, 29), date(2026, 3, 29), "02:30", "03:30")


class GembaLoadTimeMigrationTest(unittest.TestCase):
    def test_legacy_upgrade_backfills_ddt_certificate_and_manual_rows_once(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as c:
                c.execute(text("CREATE TABLE documenti_fornitore (id INTEGER PRIMARY KEY, data_upload TIMESTAMP)"))
                c.execute(text("CREATE TABLE datimaterialeincoming (id INTEGER PRIMARY KEY, document_ddt_id INTEGER, document_certificato_id INTEGER, created_at TIMESTAMP, cdq TEXT)"))
                c.execute(text("INSERT INTO documenti_fornitore VALUES (1, '2026-09-30 06:30:00'), (2, '2026-09-29 10:00:00')"))
                c.execute(text("INSERT INTO datimaterialeincoming VALUES (1,1,2,'2026-09-30 18:00:00','keep'), (2,NULL,2,'2026-09-30 18:00:00','keep'), (3,NULL,NULL,'2026-09-30 18:00:00','keep')"))
            with patch.object(bootstrap, "engine", engine):
                bootstrap.ensure_acquisition_load_time_column()
                with engine.begin() as c:
                    c.execute(text("UPDATE documenti_fornitore SET data_upload='2026-10-01 12:00:00'"))
                bootstrap.ensure_acquisition_load_time_column()
            with engine.connect() as c:
                values = c.execute(text("SELECT incoming_loaded_at, cdq FROM datimaterialeincoming ORDER BY id")).all()
            self.assertEqual(values, [("2026-09-30 06:30:00", "keep"), ("2026-09-29 10:00:00", "keep"), ("2026-09-30 18:00:00", "keep")])
            self.assertIn("ix_datimaterialeincoming_incoming_loaded_at", [i["name"] for i in inspect(engine).get_indexes("datimaterialeincoming")])
        finally:
            engine.dispose()
