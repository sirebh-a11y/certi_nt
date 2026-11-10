"""Public work filters do not replace internal lifecycle or PDF authorization."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.deps import get_db, get_current_user
from app.modules.quarta_taglio import ddt_queue as queue, ddt_router as routes
from test_quarta_taglio_ddt_queue import DdtQueueFixture, NOW


@pytest.mark.parametrize('state,action,expected', [
    ('ready', None, False), ('waiting_incoming', None, False), ('review', None, True),
    ('quality_rejected', None, True), ('to_link', None, True), ('word_ready', None, True),
    ('word_ready', object(), False), ('completed', None, False), ('excluded', None, False),
    ('archived', None, False),
])
def test_anomalies_cover_open_problems_not_terminal_rows(state, action, expected):
    item = SimpleNamespace(state=state, pdf_action=action, ddt_date=date(2026, 11, 10))
    assert queue._matches_state_filter(item, 'anomalies') is expected
    assert queue._matches_state_filter(item, 'pdf_ready') is (state == 'word_ready' and action is not None)
    assert queue._matches_state_filter(item, state)  # Old API selections remain valid.


class DdtWorkFilterTest(DdtQueueFixture):
    def test_all_is_complete_and_new_filters_apply_before_pagination(self):
        self.material()
        ready_ids = []
        for n in range(32):
            item = self.item(IdDocumento=str(n+1), DDT=f'{n+1}-01/09/2026',
                             CodF3='001230' if n >= 28 else '001200')
            if n >= 28:
                self.cert(item, certificate_number=f'7100_{n}_00/26', cert_date=NOW, conformity_status='conforme')
                ready_ids.append(item.id)
        all_rows = self.read()
        filtered = self.read(state='pdf_ready', limit=2, offset=2, sort_field='ddt_raw', sort_direction='asc')
        assert all_rows.active == 32 and all_rows.total_items == 32
        assert filtered.active == 32 and filtered.total_items == 4 and len(filtered.items) == 2
        assert all(r.pdf_action for r in filtered.items)
        assert set(r.id for r in self.read(state='pdf_ready').items) == set(ready_ids)
        assert all_rows.by_state == filtered.by_state == self.read(counters_only=True).by_state
        assert self.read(state='ready').total_items == 28
        assert self.read(state='word_ready').total_items == 4

    def test_nonconforming_word_and_missing_data_are_explained_not_pdf_ready(self):
        self.material()
        item = self.item()
        cert = self.cert(item, certificate_number='7100_00_00/26', cert_date=NOW, conformity_status='non_conforme')
        row = self.read(state='anomalies').items[0]
        assert row.state == 'word_ready' and row.label == 'Word da verificare'
        assert any('non conforme' in reason for reason in row.reasons)
        assert self.read(state='pdf_ready').total_items == 0
        cert.conformity_status = 'conforme'
        cert.cert_date = None
        self.db.commit()
        row = self.read(state='anomalies').items[0]
        assert any('data del certificato' in reason for reason in row.reasons)
        cert.cert_date = NOW
        cert.quantita = 999
        self.db.commit()
        row = self.read(state='anomalies').items[0]
        assert any('Quantità diversa' in reason for reason in row.reasons)
        assert self.read(state='pdf_ready').total_items == 0
        cert.quantita = float(item.quantita)
        self.db.commit()
        row = self.read(state='pdf_ready').items[0]
        assert row.label == 'PDF da generare' and self.read(state='anomalies').total_items == 0

    def test_missing_date_is_not_lost_even_before_preparing_word(self):
        self.material()
        item = self.item(DDT='unreadable')
        row = self.read(state='anomalies').items[0]
        assert row.id == item.id and row.label == 'Data DDT da verificare'
        assert row.pdf_action is None and any('Data DDT mancante' in r for r in row.reasons)
        assert self.read().total_items == 1

    def test_waiting_can_have_a_word_but_cannot_offer_pdf(self):
        item = self.item()
        self.material(complete=False)
        self.cert(item, certificate_number='7100_00_00/26', cert_date=NOW, conformity_status='conforme')
        row = self.read(state='waiting_incoming').items[0]
        assert row.word_candidate_id and row.pdf_action is None
        assert row.label == 'Incoming da completare'
        assert self.read(state='pdf_ready').total_items == 0

    def test_closed_excluded_and_archive_views_remain_accessible(self):
        closed = self.item()
        self.cert(closed, pdf=True)
        assert self.read().total_items == 0
        assert self.read(scope='completed').items[0].id == closed.id
        assert self.read(scope='all', state='anomalies').total_items == 0
        assert self.read(scope='all', state='pdf_ready').total_items == 0
        assert self.read().by_state['completed'] == 1

    def test_alias_filters_are_validated_and_passed_by_route(self):
        app = FastAPI()
        app.include_router(routes.router, prefix='/api/quarta-taglio')
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(department=SimpleNamespace(name='Qualità'))
        response = self.read()
        with TestClient(app) as client, patch.object(routes, 'read_ddt_queue', return_value=response) as read:
            for state in ['pdf_ready', 'anomalies', 'waiting_incoming', 'ready', 'word_ready', 'completed']:
                assert client.get('/api/quarta-taglio/ddt-work-items?state=' + state).status_code == 200
                assert read.call_args.kwargs['state'] == state
            read.reset_mock()
            assert client.get('/api/quarta-taglio/ddt-work-items?state=unknown').status_code == 422
            read.assert_not_called()
