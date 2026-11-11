import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = (await readFile(new URL('./api.js', import.meta.url), 'utf8'))
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
let serial = 0;
const id = 'a'.repeat(32);
const token = (owner, version = 1) => `x.${Buffer.from(JSON.stringify({ sub: String(owner), version })).toString('base64url')}.x`;
const json = (value, status = 200) => new Response(JSON.stringify(value), { status });
const ticket = (status = 'running', extra = {}) => ({ kind: 'integration_wait', job_id: id,
  status, poll_url: `/integration-jobs/${id}`, ...extra });
async function setup(t) {
  const events = new EventTarget();
  t.mock.method(globalThis, 'setTimeout', (callback) => { queueMicrotask(callback); return 1; });
  const previous = globalThis.window;
  globalThis.window = events;
  t.after(() => { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; });
  return import(`data:text/javascript;base64,${Buffer.from(source + `\n// isolated ${++serial}`).toString('base64')}`);
}

test('waits past 30/120/300 seconds, keeps polling, and never repeats the POST', async (t) => {
  const api = await setup(t);
  let posts = 0, polls = 0;
  const seen = [];
  api.onIntegrationWait(active => seen.push(active));
  t.mock.method(Date, 'now', () => polls * 1000);
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/word-draft')) {
      posts++; assert.equal(options.headers.get('Prefer'), 'respond-async');
      return json(ticket('queued'), 202);
    }
    polls++;
    return json(polls <= 720 ? ticket() : ticket('succeeded', { result: { ready: true } }));
  });
  assert.deepEqual(await api.apiRequest('/quarta-taglio/OL1/word-draft', { method: 'POST' }, token(1)), { ready: true });
  assert.equal(posts, 1); assert.equal(polls, 721);
  assert.deepEqual(seen, [true, false]);
});

test('concurrent identical clicks share one job; ordinary pages are not blocked', async (t) => {
  const api = await setup(t);
  let release, posts = 0;
  const blocked = new Promise(resolve => { release = resolve; });
  t.mock.method(globalThis, 'fetch', async (url) => {
    if (url.endsWith('/health')) return json({ status: 'ok' });
    if (url.includes('/integration-jobs/')) { await blocked; return json(ticket('succeeded', { result: 7 })); }
    posts++; return json(ticket(), 202);
  });
  const first = api.apiRequest('/quarta-taglio', {}, token(1));
  const second = api.apiRequest('/quarta-taglio', {}, token(1));
  assert.deepEqual(await api.apiRequest('/health'), { status: 'ok' });
  release(); assert.deepEqual(await Promise.all([first, second]), [7, 7]); assert.equal(posts, 1);
});

test('a lost initial response reuses the request ID, then a lost poll resumes without POST', async (t) => {
  const api = await setup(t);
  let phase = 0, posts = 0;
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (!url.includes('/integration-jobs/')) {
      posts++; requests.push(options.headers.get('X-CERTI-Request-ID'));
      if (phase === 0) { phase++; throw new TypeError('Lost initial reply'); }
      return json(ticket(), 202);
    }
    if (phase === 1) { phase++; throw new TypeError('Lost poll'); }
    return json(ticket('succeeded', { result: 'done' }));
  });
  const run = () => api.apiRequest('/quarta-taglio/OL1/word-draft', { method: 'POST', body: '{}' }, token(1));
  await assert.rejects(run(), /Lost initial/);
  await assert.rejects(run(), /Lost poll/);
  assert.equal(await run(), 'done');
  assert.equal(posts, 2); assert.equal(requests[0], requests[1]);
});

test('structured date-choice conflict survives deferred response and next explicit action has a fresh ID', async (t) => {
  const api = await setup(t);
  const ids = [], detail = { code: 'merge_acceptance_date_choice', message: 'Scegli la data', ddt_date: '2026-11-11' };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.includes('/integration-jobs/')) return json(ticket('failed', { response_status: 409, detail }));
    ids.push(options.headers.get('X-CERTI-Request-ID')); return json(ticket(), 202);
  });
  for (let i = 0; i < 2; i++) await assert.rejects(api.apiRequest('/quarta-taglio', {}, token(1)), error => {
    assert.equal(error.status, 409); assert.deepEqual(error.payload, detail); return true;
  });
  assert.notEqual(ids[0], ids[1]);
});

test('polls use renewed JWT of the same owner, not an expired initial token', async (t) => {
  const api = await setup(t);
  const old = token(1), renewed = token(1, 2), authorizations = [];
  api.setApiSessionToken(old);
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (!url.includes('/integration-jobs/')) { api.setApiSessionToken(renewed); return json(ticket(), 202); }
    authorizations.push(options.headers.Authorization); return json(ticket('succeeded', { result: true }));
  });
  assert.equal(await api.apiRequest('/quarta-taglio', {}, old), true);
  assert.deepEqual(authorizations, [`Bearer ${renewed}`]);
});

test('logout/account switch never polls another owner or cancels server work', async (t) => {
  const api = await setup(t); api.setApiSessionToken(token(1));
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; api.setApiSessionToken(token(2)); return json(ticket(), 202); });
  await assert.rejects(api.apiRequest('/quarta-taglio', {}, token(1)), error => error.name === 'AbortError');
  assert.equal(calls, 1);
});

for (const asset of ['/api/quarta-taglio/word-drafts/1/file?download_token=xx',
  'http://localhost:8000/api/quarta-taglio/word-drafts/1/file?download_token=xx']) {
  test(`deferred Word download returns exact binary for ${asset}`, async (t) => {
    const api = await setup(t);
    t.mock.method(globalThis, 'fetch', async (url, options) => {
      if (url.endsWith('/file') && url.includes('/integration-jobs/')) return new Response('BINARY-DOCX');
      if (url.includes('/integration-jobs/')) return json(ticket('succeeded', { file_url: `/integration-jobs/${id}/file` }));
      assert.equal(options.headers.get('Prefer'), 'respond-async'); return json(ticket(), 202);
    });
    assert.equal(await (await api.fetchApiBlob(asset, token(1))).text(), 'BINARY-DOCX');
  });
}

test('foreign polling URL is rejected before credentials can be forwarded', async (t) => {
  const api = await setup(t); let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return json(ticket('queued', { poll_url: 'https://foreign.invalid/steal' }), 202); });
  await assert.rejects(api.apiRequest('/quarta-taglio', {}, token(1)), /non valida/);
  assert.equal(calls, 1);
});

test('FormData retains browser boundary and legacy 200 responses remain compatible', async (t) => {
  const api = await setup(t);
  const form = new FormData(); form.set('file', new Blob(['document']), 'file.docx');
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.headers.has('Content-Type'), false);
    assert.equal(options.body, form); return json({ uploaded: true });
  });
  assert.deepEqual(await api.apiRequest('/quarta-taglio/upload', { method: 'POST', body: form }, token(1)), { uploaded: true });
});
