"""Filter presence across the whole OL list, never document/Incoming writes."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.modules.customer_requirements.models import CustomerRequirement
from app.modules.quarta_taglio import service as s, customer_requirement_filter as presence
from app.modules.quarta_taglio.schemas import QuartaTaglioRequirementArticleResponse as Article
import test_quarta_taglio_esolver as fixtures

CASES = json.loads((Path(__file__).parent / 'fixtures/customer_requirement_presence.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=[v['name'] for v in CASES])
def test_presence_matches_frontend_contract(case):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [(v['cod_f3'],) for v in case['requirements'] if v.get('active') is not False]
    assert presence.has_requirements([Article(**v) for v in case['articles']], presence.active_families(db)) == case['expected']


def test_reads_only_active_profiles_from_real_isolated_database():
    engine = create_engine('sqlite://')
    CustomerRequirement.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([CustomerRequirement(cod_f3='096007800', cliente='Active'),
                    CustomerRequirement(cod_f3='1142000100', cliente='Inactive', active=False)])
        db.commit()
        assert presence.active_families(db) == {'0960078'}
        assert not db.dirty and not db.new and not db.deleted
    engine.dispose()


def run_list(rows, *, families, candidates=None, cached_links=None, fresh_links=None, **options):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
    fetched = MagicMock(return_value=candidates or {})
    with ExitStack() as stack:
        for name, value in {
            '_latest_quarta_sync_run': object(), '_load_esolver_links_for_rows': cached_links or {},
            '_refresh_esolver_links_for_rows': fresh_links or {}, '_build_certification_progress_by_odp': {},
            '_serialize_run': dict(id=1, status='ok', message=None, total_ol=len(rows), total_cdq_rows=len(rows),
                                  started_at=datetime.now(timezone.utc), finished_at=None),
        }.items():
            stack.enter_context(patch.object(s, name, return_value=value))
        stack.enter_context(patch.object(s, '_fetch_certiol_rows_batch', fetched))
        active = stack.enter_context(patch.object(presence, 'active_families', return_value=families))
        sync = stack.enter_context(patch.object(s, '_sync_quarta_rows'))
        stack.enter_context(patch.object(s, '_load_final_certificates_by_odp', return_value={}))
        result = s.sync_and_list_quarta_taglio(db, sync_data=False, **options)
        sync.assert_not_called()
        return result, fetched.call_args_list, active.call_count


def test_filter_before_count_sort_offset_not_only_first_25_rows():
    factory = fixtures.QuartaTaglioEsolverTest()
    rows = [factory._quarta_row(cod_odp=f'OL{n:03}', cod_art='1142000100' if n in (28, 29) else '999999900') for n in range(30)]
    result, calls, _ = run_list(rows, families={'11420001'}, requirements_filter='with', limit=1, offset=1, sort_field='cod_odp')
    assert result.total_items == 2
    assert [r.cod_odp for r in result.items] == ['OL029']
    assert result.items[0].has_customer_requirements is True
    assert result.requirements_filter == 'with'
    assert len(calls) == 2  # one family lookup, one page-context lookup; never one per OL
    assert len(calls[0].args[1]) == 30
    without, _, _ = run_list(rows, families={'11420001'}, requirements_filter='without', limit=25)
    assert without.total_items == 28 and len(without.items) == 25
    assert all(r.has_customer_requirements is False for r in without.items)


def test_all_keeps_original_query_count_and_no_requirement_database_read():
    row = fixtures.QuartaTaglioEsolverTest()._quarta_row()
    result, calls, active_calls = run_list([row], families={'11420001'})
    assert result.total_items == 1 and result.items[0].has_customer_requirements is None
    assert active_calls == 0
    assert len(calls) == 1 and not calls[0].kwargs


def test_text_word_filters_and_empty_profiles_combine_without_reset():
    factory = fixtures.QuartaTaglioEsolverTest()
    rows = [factory._quarta_row(cod_odp='OL-A', cod_art='1142000100'), factory._quarta_row(cod_odp='OL-B', cod_art='1142000100')]
    result, _, _ = run_list(rows, families={'11420001'}, requirements_filter='with', only_word_pending=True, query_one='OL-B')
    assert result.only_word_pending and result.total_items == 1 and result.items[0].cod_odp == 'OL-B'
    result, calls, _ = run_list(rows, families=set(), requirements_filter='with')
    assert result.total_items == 0 and not result.items
    assert all(not call.kwargs for call in calls)
    result, _, _ = run_list(rows, families=set(), requirements_filter='without')
    assert result.total_items == 2


def test_legacy_raw_and_family_ambiguity_use_complete_candidate_context():
    row = fixtures.QuartaTaglioEsolverTest()._quarta_row(cod_odp='OL1', cod_art='1234')
    candidates = {'OL1': [s._CertiOlRow(orp='OL1', cod_cli='C', rag_soc='Test',
                  cod_f3_odp='1234', cod_f3=code, des_f3='Descrizione Quarta') for code in ('123400', '123401')]}
    result, _, _ = run_list([row], families={'1234'}, candidates=candidates, requirements_filter='with')
    assert result.total_items == 1 and result.items[0].has_customer_requirements
    assert {a.cod_f3 for a in result.items[0].customer_requirement_articles} >= {'123400', '123401'}
    # More than 25 children are review-only: do not invent a tag from a raw prefix.
    candidates['OL1'] = [s._CertiOlRow(orp='OL1', cod_cli='C', rag_soc='Test', cod_f3_odp='1234',
                                    cod_f3='1234' + str(n).zfill(2), des_f3='X') for n in range(26)]
    result, _, _ = run_list([row], families={'1234'}, candidates=candidates, requirements_filter='with')
    assert result.total_items == 0


def test_invalid_selection_rejected_before_sync_or_database_access():
    db = MagicMock()
    with patch.object(s, '_sync_quarta_rows') as sync, pytest.raises(HTTPException) as error:
        s.sync_and_list_quarta_taglio(db, requirements_filter='bad')
    assert error.value.status_code == 422 and not db.mock_calls
    sync.assert_not_called()


def test_cached_ddt_for_same_ol_counts_but_other_ol_does_not():
    factory = fixtures.QuartaTaglioEsolverTest()
    row = factory._quarta_row(cod_art='999999900')
    for source_ol, expected in [('OL1', 1), ('OTHER', 0)]:
        link = factory._esolver_link([dict(orp=source_ol, cod_f3='096007830', ddt='1-10/11/2026')])
        result, _, _ = run_list([row], families={'0960078'}, cached_links={'OL1': link}, requirements_filter='with')
        assert result.total_items == expected


def test_positive_quarta_keeps_additional_f3_and_ambiguity_from_certiol():
    row = fixtures.QuartaTaglioEsolverTest()._quarta_row(cod_art='1142000100')
    context = {'OL1': [s._CertiOlRow(orp='OL1', cod_cli='C', rag_soc='Test', cod_f3_odp='1142000100',
                                   cod_f3='1142000130', des_f3='Descrizione Quarta')]}
    result, _, _ = run_list([row], families={'11420001'}, candidates=context, requirements_filter='with')
    assert {a.cod_f3 for a in result.items[0].customer_requirement_articles} == {'1142000100', '1142000130'}
    assert result.items[0].has_customer_requirements


def test_page_refresh_does_not_reclassify_only_one_page_after_counting():
    factory = fixtures.QuartaTaglioEsolverTest()
    row = factory._quarta_row(cod_art='999999900')
    fresh = factory._esolver_link([dict(orp='OL1', cod_f3='096007830', ddt='1-10/11/2026')])
    result, _, _ = run_list([row], families={'0960078'}, fresh_links={'OL1': fresh}, requirements_filter='without')
    assert result.total_items == 1 and len(result.items) == 1
    assert result.items[0].has_customer_requirements is False
    assert [a.cod_f3 for a in result.items[0].customer_requirement_articles] == ['999999900']
    # The next request sees the newly saved source across ALL groups.
    result, _, _ = run_list([row], families={'0960078'}, cached_links={'OL1': fresh}, fresh_links={'OL1': fresh}, requirements_filter='without')
    assert result.total_items == 0


def test_profile_database_error_never_means_without_requirements():
    db = MagicMock()
    db.query.side_effect = RuntimeError('isolated database unavailable')
    with pytest.raises(RuntimeError):
        presence.active_families(db)


def test_family_metadata_query_is_single_and_keeps_complete_ol_rows():
    connection = SimpleNamespace(enabled=True, password_encrypted='encrypted', object_settings={}, schema_name='dbo',
        server_host='isolated-mock', port=1433, username='fake', database_name='fake', connection_timeout=1, query_timeout=1)
    db, sql = MagicMock(), MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = connection
    cursor = sql.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [dict(ORP='OL999', CodF3ODP='1234', CodF3='123400', DesF3='RAW'),
                                   dict(ORP='OTHER', CodF3ODP='1234', CodF3='123401', DesF3='IGNORE')]
    with patch.dict(sys.modules, pymssql=sql), patch.object(s, 'decrypt_secret', return_value='fake'):
        result = s._fetch_certiol_rows_batch(db, [f'OL{n}' for n in range(16000)], requirement_families=['1234'])
    assert set(result) == {'OL999'}
    assert sql.connect.call_count == 1
    query, params = cursor.execute.call_args.args
    assert 'where exists' in query.lower() and 'current_ol' in query and 'CodF3ODP' in query
    assert params == ('1234', '1234') and query.count('%s') == 2
    sql.connect.side_effect = RuntimeError('unavailable')
    with patch.dict(sys.modules, pymssql=sql), patch.object(s, 'decrypt_secret', return_value='fake'):
        with pytest.raises(HTTPException) as error:
            s._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=['1234'])
        assert error.value.status_code == 503
        assert s._fetch_certiol_rows_batch(db, ['OL1']) == {}  # unfiltered behavior preserved


@pytest.mark.parametrize('configuration', ['disabled', 'no_secret', 'bad_view'])
def test_configuration_failure_is_not_silent_absence(configuration):
    db, sql = MagicMock(), MagicMock()
    connection = SimpleNamespace(enabled=configuration != 'disabled', password_encrypted=None if configuration == 'no_secret' else 'fake',
        object_settings={'certiol_view': 'invalid;view'} if configuration == 'bad_view' else {}, schema_name='dbo')
    db.query.return_value.filter.return_value.one_or_none.return_value = connection
    with patch.dict(sys.modules, pymssql=sql):
        if configuration == 'disabled':
            assert s._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=['1234']) == {}
        else:
            with pytest.raises(HTTPException) as error:
                s._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=['1234'])
            assert error.value.status_code == 503
    sql.connect.assert_not_called()


def test_family_batches_keep_full_context_and_do_not_duplicate_rows():
    db, sql = MagicMock(), MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = SimpleNamespace(
        enabled=True, password_encrypted='encrypted', object_settings={}, schema_name='dbo', server_host='isolated-mock',
        port=1433, username='fake', database_name='fake', connection_timeout=1, query_timeout=1)
    cursor = sql.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [dict(ORP='OL1', CodF3ODP='1234', CodF3='123400', DesF3='RAW')]
    with patch.dict(sys.modules, pymssql=sql), patch.object(s, 'decrypt_secret', return_value='fake'):
        assert s._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=[]) == {}
        sql.connect.assert_not_called()
        result = s._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=[str(n) for n in range(501)])
    assert len(result['OL1']) == 1
    assert sql.connect.call_count == 2
    assert len(cursor.execute.call_args_list[0].args[1]) == 1000
    assert len(cursor.execute.call_args_list[1].args[1]) == 2


def test_route_defaults_and_validation_before_service():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_db, get_current_user
    from app.modules.quarta_taglio import router as routes
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/quarta-taglio')
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=999999)
    empty_result = dict(sync_run=dict(id=1, status='ok', message=None, total_ol=0, total_cdq_rows=0,
                                     started_at=datetime.now(timezone.utc), finished_at=None),
                        items=[], total_items=0, offset=0, limit=25, only_taglio_active=False,
                        hide_certified=False, only_word_pending=False, only_additional_words=False)
    with TestClient(app) as client, patch.object(routes, 'sync_and_list_quarta_taglio', return_value=empty_result) as read:
        for selection in ['all', 'with', 'without']:
            assert client.get('/api/quarta-taglio?requirements_filter=' + selection).status_code == 200
            assert read.call_args.kwargs['requirements_filter'] == selection
        assert client.get('/api/quarta-taglio').status_code == 200
        assert read.call_args.kwargs['requirements_filter'] == 'all'
        read.reset_mock()
        assert client.get('/api/quarta-taglio?requirements_filter=invalid').status_code == 422
        read.assert_not_called()
