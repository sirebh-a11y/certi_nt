"""No company network/AI: durable work, not elapsed-time retries."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest
from sqlalchemy import create_engine, select, text, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from uuid import uuid4

from app.startup import bootstrap  # noqa: F401 - all existing model declarations
from app.core.database import Base
from app.core.deps import DbSession, CurrentUser, get_db, get_current_user
from app.core.departments.models import Department
from app.core.users.models import User
from app.core.integrations import background as bg
from app.core.integrations.background_router import router as job_router
from app.core.integrations.models import IntegrationBackgroundJob as Job, IntegrationBackgroundReceipt as Receipt
from app.core.integrations.read_policy import query_timeout, connection_revision, ensure_connection_unchanged
from app.core.integrations.models import ExternalConnection
from app.core.security.crypto import decrypt_secret


class Payload(BaseModel):
    name: str | None = None
    count: int = 8


class Result(BaseModel):
    value: str


@pytest.fixture(params=['sqlite', 'postgresql'])
def qa(tmp_path, request):
    admin_engine, schema = None, None
    if request.param == 'postgresql':
        url = os.getenv('CERTI_EXTERNAL_WAIT_TEST_DATABASE_URL')
        if not url:
            pytest.skip('Isolated PostgreSQL opt-in not configured')
        target = make_url(url)
        assert target.host in {'127.0.0.1', 'localhost'} and target.port == 55440
        assert target.database == 'certi_ddt_test_external_wait', 'Never run on an application database'
        schema = 'qa_wait_' + uuid4().hex
        admin_engine = create_engine(url)
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'qa.sqlite'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        department = Department(name='Qualità', description='Isolated background QA')
        db.add(department); db.flush()
        actors = [User(name='Test', email=f'qa{i}@example.invalid', role='admin',
                       department_id=department.id, active=True) for i in range(2)]
        db.add_all(actors); db.commit()
        ids = [a.id for a in actors]
    manager = bg.BackgroundManager(engine, root=tmp_path / 'private', revision='qa')
    yield engine, manager, ids
    manager.stop()
    for thread in manager.threads:
        thread.join(timeout=3)
        assert not thread.is_alive(), 'The test must release its fake source before cleanup'
    engine.dispose()
    if admin_engine is not None:
        assert schema.startswith('qa_wait_') and len(schema) == 40
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin_engine.dispose()


def submit(qa, fn, values=None, request_id='request_one_0123456789'):
    engine, manager, ids = qa
    operation = bg.register_operation(fn)
    with Session(engine) as db:
        actor = db.get(User, ids[0])
        arguments = {'db': db, **(values or {})}
        job = manager.enqueue(db, operation, arguments, actor, request_id)
        return job.id


def loaded(qa, job_id):
    with Session(qa[0]) as db:
        job = db.get(Job, job_id)
        return job.status, json.loads(decrypt_secret(job.response_data)) if job.response_data else None


def test_duplicate_clicks_and_lost_responses_execute_once_including_second_receipt(qa):
    calls = []
    def task(db: Session):
        calls.append(1)
        return {'done': True}
    first = submit(qa, task)
    second = submit(qa, task, request_id='request_two_0123456789')
    assert first == second
    assert qa[1].run_one()
    assert loaded(qa, first) == ('succeeded', {'kind': 'json', 'value': {'done': True}})
    # A second tab's ID still replays the completed job, not another write.
    assert submit(qa, task, request_id='request_two_0123456789') == first
    assert calls == [1] and not qa[1].run_one()
    with Session(qa[0]) as db:
        assert len(list(db.scalars(select(Receipt)))) == 2


def test_request_id_cannot_be_reused_for_different_data(qa):
    def task(db: Session, value: str): return value
    submit(qa, task, {'value': 'one'})
    with pytest.raises(HTTPException) as error:
        submit(qa, task, {'value': 'different'})
    assert error.value.status_code == 409


def test_old_or_slow_job_has_no_age_deadline_and_does_not_block_other_requests(qa):
    entered, release = threading.Event(), threading.Event()
    def task(db: Session):
        entered.set()
        assert release.wait(8)
        return {'late': True}
    job_id = submit(qa, task)
    with Session(qa[0]) as db:
        job = db.get(Job, job_id)
        job.created_at = datetime(2000, 1, 1, tzinfo=timezone.utc); db.commit()
    thread = threading.Thread(target=qa[1].run_one)
    thread.start()
    try:
        assert entered.wait(3)
        other = bg.BackgroundManager(qa[0], root=qa[1].root, revision='qa')
        assert not other.run_one()  # live owner, NOT "old => interrupted"
        with Session(qa[0]) as db:
            assert db.scalar(text('SELECT 1')) == 1
            assert db.get(Job, job_id).status == 'running'
        assert submit(qa, task, request_id='second_click_0123456789') == job_id
    finally:
        release.set(); thread.join(timeout=5)
    assert not thread.is_alive() and loaded(qa, job_id)[0] == 'succeeded'


def test_orphan_running_work_is_reported_not_automatically_replayed(qa):
    calls = []
    def task(db: Session): calls.append(1)
    job_id = submit(qa, task)
    with Session(qa[0]) as db:
        job = db.get(Job, job_id); job.status = 'running'; job.worker_token = 'orphan'; db.commit()
    assert qa[1].run_one()
    assert loaded(qa, job_id)[0] == 'interrupted' and not calls


def test_code_change_and_permission_revocation_never_execute_queued_writes(qa):
    calls = []
    def task(db: Session): calls.append(1)
    job_id = submit(qa, task)
    qa[1].revision = 'new-code'
    qa[1].run_one()
    assert loaded(qa, job_id)[0] == 'failed' and not calls
    qa[1].revision = 'qa'
    next_id = submit(qa, task, request_id='next_request_0123456789')
    with Session(qa[0]) as db:
        db.get(User, qa[2][0]).active = False; db.commit()
    qa[1].run_one()
    assert loaded(qa, next_id)[0] == 'failed' and not calls


def test_pending_upload_survives_request_close_preserves_fields_set_and_is_encrypted(qa):
    def task(db: Session, payload: Payload, file: UploadFile):
        return {'fields': sorted(payload.model_fields_set), 'data': file.file.read().decode(), 'name': file.filename}
    upload = UploadFile(filename='original.docx', file=BytesIO(b'PRIVATE-UPLOAD-CONTENT'))
    job_id = submit(qa, task, {'payload': Payload(name='Only explicit field'), 'file': upload})
    upload.file.close()
    with Session(qa[0]) as db:
        stored = db.get(Job, job_id).request_data
        assert 'original.docx' not in stored and 'Only explicit field' not in stored
    qa[1].run_one()
    assert loaded(qa, job_id)[1]['value'] == {
        'fields': ['name'], 'data': 'PRIVATE-UPLOAD-CONTENT', 'name': 'original.docx'}
    assert not list(qa[1].root.rglob('input_*'))


def test_response_metadata_does_not_commit_incidental_business_changes(qa):
    def task(db: Session):
        db.get(User, qa[2][0]).name = 'Not committed by the business operation'
        return {'done': True}
    job_id = submit(qa, task); qa[1].run_one()
    with Session(qa[0]) as db:
        assert db.get(User, qa[2][0]).name == 'Test'
    assert loaded(qa, job_id)[0] == 'succeeded'


def test_structured_conflict_is_retained_and_internal_exception_is_sanitized(qa):
    def task(db: Session, fail: bool):
        if fail: raise RuntimeError('password=PRIVATE-SECRET')
        raise HTTPException(409, {'code': 'merge_acceptance_date_choice', 'message': 'Scegli la data'})
    for fail in (False, True):
        job_id = submit(qa, task, {'fail': fail}, request_id='failure_0123456789_' + str(fail))
        qa[1].run_one(); status, response = loaded(qa, job_id)
        assert status == 'failed' and 'PRIVATE-SECRET' not in json.dumps(response)
        if not fail: assert response['detail']['code'] == 'merge_acceptance_date_choice'


def app_for(qa, monkeypatch):
    monkeypatch.setattr(bg, '_manager', qa[1])
    app = FastAPI(); app.include_router(job_router, prefix='/api/integration-jobs')
    def database():
        with Session(qa[0]) as db: yield db
    current = {'id': qa[2][0]}
    def actor():
        with Session(qa[0], expire_on_commit=False) as db:
            user = db.get(User, current['id'])
            _ = user.department
            return user
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = actor
    return app, current


def test_api_ticket_poll_owner_isolation_and_legacy_response(qa, monkeypatch):
    app, current = app_for(qa, monkeypatch)
    @app.post('/api/slow', response_model=Result)
    @bg.background_response
    def route(payload: Payload, db: DbSession, current_user: CurrentUser) -> Result:
        return Result(value=payload.name)
    with TestClient(app) as client:
        legacy = client.post('/api/slow', json={'name': 'legacy'})
        assert legacy.status_code == 200 and legacy.json() == {'value': 'legacy'}
        response = client.post('/api/slow', json={'name': 'background'}, headers={
            'Prefer': 'respond-async', 'X-CERTI-Request-ID': 'api_request_0123456789'})
        assert response.status_code == 202
        url = '/api' + response.json()['poll_url']
        assert client.get(url).json()['status'] == 'queued'
        qa[1].run_one()
        assert client.get(url).json()['result'] == {'value': 'background'}
        current['id'] = qa[2][1]
        assert client.get(url).status_code == 404


def test_deferred_file_is_exact_owner_only_and_not_a_json_disguised_as_docx(qa, monkeypatch, tmp_path):
    app, current = app_for(qa, monkeypatch)
    source = tmp_path / 'source.docx'; source.write_bytes(b'ORIGINAL-DOCUMENT')
    @app.get('/api/document')
    @bg.background_response
    def route(db: DbSession, current_user: CurrentUser) -> FileResponse:
        return FileResponse(source, filename='certificate.docx')
    with TestClient(app) as client:
        response = client.get('/api/document', headers={'Prefer': 'respond-async'})
        qa[1].run_one()
        data = client.get('/api' + response.json()['poll_url']).json()
        source.write_bytes(b'LATER-CHANGE')
        download = client.get('/api' + data['file_url'])
        assert download.content == b'ORIGINAL-DOCUMENT' and 'certificate.docx' in download.headers['content-disposition']
        current['id'] = qa[2][1]
        assert client.get('/api' + data['file_url']).status_code == 404


@pytest.mark.parametrize('code', ['esolver', 'quarta'])
@pytest.mark.parametrize('stored', [0, 30, 120, 600])
def test_old_stored_settings_do_not_reintroduce_a_deadline(code, stored):
    connection = ExternalConnection(code=code, query_timeout=stored)
    assert query_timeout(connection) == 0 and connection.query_timeout == stored


def test_config_changed_during_read_is_not_silently_applied(qa):
    with Session(qa[0], expire_on_commit=False) as db:
        connection = ExternalConnection(code='esolver', label='eSolver', server_host='fake', port=1433,
            username='fake', database_name='fake', connection_timeout=10, query_timeout=30)
        db.add(connection); db.commit(); revision = connection_revision(connection)
        with Session(qa[0]) as other:
            other.get(ExternalConnection, connection.id).server_host = 'changed'; other.commit()
        with pytest.raises(HTTPException) as error:
            ensure_connection_unchanged(db, connection, revision)
        assert error.value.status_code == 409


def test_two_background_quarta_requests_share_one_completed_refresh(qa):
    from app.modules.quarta_taglio import service
    entered, release, second_waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def fetch(db):
        calls.append(1); entered.set()
        assert release.wait(15)
        return []
    def task(db: Session, distinguish: int):
        if distinguish == 2: second_waiting.set()
        return {'run': service._sync_quarta_rows(db).id}
    first = submit(qa, task, {'distinguish': 1})
    second = submit(qa, task, {'distinguish': 2}, request_id='second_refresh_0123456789')
    original_latest = service._latest_quarta_sync_run
    second_observed = threading.Event()
    def latest(db):
        result = original_latest(db)
        if second_waiting.is_set() and result is not None and result.status == 'running': second_observed.set()
        return result
    with patch.object(service, '_fetch_quarta_taglio_rows', side_effect=fetch), \
            patch.object(service, '_latest_quarta_sync_run', side_effect=latest):
        workers = [threading.Thread(target=qa[1].run_one) for _ in range(2)]
        workers[0].start()
        try:
            assert entered.wait(5)
            workers[1].start()
            assert second_observed.wait(5)
        finally:
            release.set()
            for worker in workers:
                if worker.ident: worker.join(timeout=8)
    assert not any(w.is_alive() for w in workers)
    assert calls == [1]
    assert loaded(qa, first)[0] == loaded(qa, second)[0] == 'succeeded'
    assert loaded(qa, first)[1] == loaded(qa, second)[1]


def test_database_additions_are_idempotent_and_do_not_rewrite_existing_data(qa):
    # Reproduce the previous schema, not just create_all on already-new tables.
    Receipt.__table__.drop(qa[0]); Job.__table__.drop(qa[0])
    with Session(qa[0]) as db:
        connection = ExternalConnection(code='esolver', label='Legacy', server_host='fake',
            username='fake', database_name='fake', query_timeout=30)
        db.add(connection); db.commit(); connection_id = connection.id
    Base.metadata.create_all(qa[0]); Base.metadata.create_all(qa[0])
    assert {'integration_background_jobs', 'integration_background_receipts'} <= set(inspect(qa[0]).get_table_names())
    with Session(qa[0]) as db:
        assert db.get(ExternalConnection, connection_id).query_timeout == 30


def test_connection_editor_keeps_zero_even_when_old_frontend_sends_30_and_keeps_secret(qa):
    from app.core.integrations.service import update_external_connection, serialize_connection
    from app.core.integrations.schemas import ExternalConnectionUpdateRequest
    with Session(qa[0]) as db:
        connection = ExternalConnection(code='esolver', label='Legacy', server_host='fake',
            username='fake', database_name='fake', query_timeout=30, password_encrypted='UNCHANGED-SECRET')
        db.add(connection); db.commit(); db.refresh(connection)
        data = serialize_connection(connection).model_dump()
        assert data['query_timeout'] == 0
        data['query_timeout'] = 30
        payload = ExternalConnectionUpdateRequest.model_validate(data)
        with patch('app.core.integrations.service.log_service.record'):
            result = update_external_connection(db, connection, payload, 'qa@example.invalid')
        assert result.query_timeout == connection.query_timeout == 0
        assert connection.connection_timeout == 10 and connection.password_encrypted == 'UNCHANGED-SECRET'


def test_department_permission_change_while_queued_prevents_execution(qa):
    calls = []
    def task(db: Session): calls.append(1)
    job_id = submit(qa, task)
    with Session(qa[0]) as db:
        department = db.get(User, qa[2][0]).department
        department.name = 'Produzione'; db.commit()
    qa[1].run_one()
    assert loaded(qa, job_id)[0] == 'failed' and not calls


def test_pg_simultaneous_clicks_have_one_job_and_one_receipt_per_request(qa):
    if qa[0].dialect.name != 'postgresql': pytest.skip('PostgreSQL concurrency')
    barrier = threading.Barrier(8)
    def task(db: Session): return True
    def click(i):
        barrier.wait(timeout=10)
        return submit(qa, task, request_id=f'parallel_click_0123456789_{i}')
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(click, range(8)))
    assert len(set(ids)) == 1
    with Session(qa[0]) as db:
        assert len(list(db.scalars(select(Job)))) == 1
        assert len(list(db.scalars(select(Receipt)))) == 8


def test_pg_worker_slots_are_global_and_do_not_cancel_slow_work(qa):
    if qa[0].dialect.name != 'postgresql': pytest.skip('PostgreSQL concurrency')
    entered = [threading.Event(), threading.Event()]; release = threading.Event()
    def task(db: Session, index: int):
        if index < 2:
            entered[index].set(); assert release.wait(15)
        return index
    ids = [submit(qa, task, {'index': index}, request_id=f'capacity_request_0123456789_{index}') for index in range(3)]
    workers = [threading.Thread(target=qa[1].run_one) for _ in range(2)]
    try:
        workers[0].start(); assert entered[0].wait(5)
        workers[1].start(); assert entered[1].wait(5)
        other = bg.BackgroundManager(qa[0], root=qa[1].root, revision='qa')
        assert not other.run_one()
        assert loaded(qa, ids[2])[0] == 'queued'
        with Session(qa[0]) as db: assert db.scalar(text('SELECT 1')) == 1
    finally:
        release.set()
        for worker in workers:
            if worker.ident: worker.join(timeout=8)
    assert qa[1].run_one() and loaded(qa, ids[2])[0] == 'succeeded'


def test_lost_worker_database_connection_cannot_reconnect_and_write_without_ownership(qa):
    def task(db: Session):
        owned = db.connection()
        owned.invalidate(); db.rollback()
        # Represents a business service catching an infrastructure failure and
        # trying to continue. Reconnecting would lose the ownership lock.
        db.get(User, qa[2][0]).name = 'MUST NOT BE WRITTEN'
        db.commit()
        return True
    job_id = submit(qa, task)
    with pytest.raises(RuntimeError, match='lost its owned database connection'):
        qa[1].run_one()
    assert qa[1].run_one()  # actual orphan, reported interrupted, not replayed
    assert loaded(qa, job_id)[0] == 'interrupted'
    with Session(qa[0]) as db:
        assert db.get(User, qa[2][0]).name == 'Test'


def test_short_http_proxy_deadline_does_not_terminate_the_background_operation(qa, monkeypatch):
    import httpx
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import socket
    import time
    import uvicorn
    app, _ = app_for(qa, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    @app.post('/api/slow')
    @bg.background_response
    def route(db: DbSession, current_user: CurrentUser):
        entered.set(); assert release.wait(15)
        return {'complete': True}
    @app.get('/api/health')
    def health(): return {'status': 'ok'}
    listener = socket.socket(); listener.bind(('127.0.0.1', 0))
    backend_url = f'http://127.0.0.1:{listener.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    class Proxy(BaseHTTPRequestHandler):
        def forward(self):
            body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            try:
                response = httpx.request(self.command, backend_url + self.path, content=body,
                    headers={'Prefer': self.headers.get('Prefer', '')}, timeout=0.5, trust_env=False)
                data, code = response.content, response.status_code
            except httpx.TimeoutException:
                data, code = b'Proxy deadline exceeded', 504
            self.send_response(code); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        do_GET = do_POST = forward
        def log_message(self, *args): pass
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    worker.start(); proxy_thread.start()
    qa[1].start()
    try:
        startup_deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < startup_deadline: time.sleep(0.01)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{proxy.server_port}', timeout=2, trust_env=False) as client:
            submitted = client.post('/api/slow', headers={'Prefer': 'respond-async'})
            assert submitted.status_code == 202 and entered.wait(3)
            url = '/api' + submitted.json()['poll_url']
            started = time.monotonic()
            while time.monotonic() - started < 1.2:  # longer than the proxy's deadline
                assert client.get(url).json()['status'] == 'running'
                assert client.get('/api/health').json() == {'status': 'ok'}
                time.sleep(0.1)
            release.set()
            completed = time.monotonic() + 5
            while time.monotonic() < completed:
                response = client.get(url)
                assert response.status_code == 200
                if response.json()['status'] == 'succeeded': break
                time.sleep(0.05)
            assert response.json()['result'] == {'complete': True}
    finally:
        release.set(); qa[1].stop()
        proxy.shutdown(); proxy.server_close(); server.should_exit = True
        proxy_thread.join(timeout=4); worker.join(timeout=4); listener.close()
        assert not worker.is_alive() and not proxy_thread.is_alive()


@pytest.mark.parametrize('read', ['ddt', 'certiol', 'filtered_certiol'])
def test_changed_integration_parameters_abort_instead_of_becoming_empty_cached_data(read):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import sys
    from app.modules.quarta_taglio import service
    db, sql = MagicMock(), MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = SimpleNamespace(
        code='esolver', enabled=True, password_encrypted='secret', object_settings={}, schema_name='dbo',
        server_host='fake', port=1433, username='fake', database_name='fake', connection_timeout=10, query_timeout=30)
    sql.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    with patch.dict(sys.modules, pymssql=sql), patch.object(service, 'decrypt_secret', return_value='fake'), \
            patch.object(service, 'ensure_connection_unchanged', side_effect=HTTPException(409, 'Parametri modificati')):
        with pytest.raises(HTTPException) as error:
            if read == 'ddt': service._fetch_esolver_ddt_rows_batch(db, {'OL1': []})
            else: service._fetch_certiol_rows_batch(db, ['OL1'], requirement_families=['1234'] if read == 'filtered_certiol' else None)
        assert error.value.status_code == 409


def test_periodic_child_sessions_keep_atomic_commits_and_worker_connection_fence(qa):
    from types import SimpleNamespace
    from app.modules.quarta_taglio import scheduler, ddt_word_reuse
    connections = []
    def snapshot(*, session_factory):
        with session_factory() as child:
            connections.append(child.get_bind())
            child.get(User, qa[2][0]).name = 'Snapshot committed'; child.commit()
    def quarta(db):
        connections.append(db.get_bind())
        assert db.get(User, qa[2][0]).name == 'Snapshot committed'
        db.get(User, qa[2][0]).name = 'Incidental, not committed'
    def reuse(*, session_factory):
        with session_factory() as child:
            connections.append(child.get_bind())
            assert child.get(User, qa[2][0]).name == 'Snapshot committed'
            child.get(User, qa[2][0]).name = 'Reuse committed'; child.commit()
        return {'prepared': 1, 'errors': 0}
    with patch.object(scheduler, 'settings', SimpleNamespace(ddt_snapshot_enabled=True, ddt_word_reuse_enabled=True)), \
            patch.object(scheduler, 'sync_ddt_snapshot', side_effect=snapshot), \
            patch.object(scheduler, 'sync_and_list_quarta_taglio', side_effect=quarta), \
            patch.object(ddt_word_reuse, 'sync_ddt_words', side_effect=reuse):
        job_id = submit(qa, scheduler.periodic_external_refresh)
        qa[1].run_one()
    assert loaded(qa, job_id)[0] == 'succeeded'
    assert len(connections) == 3 and all(c is connections[0] for c in connections)
    with Session(qa[0]) as db: assert db.get(User, qa[2][0]).name == 'Reuse committed'
