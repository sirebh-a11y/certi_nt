import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// Vite injects import.meta.env in the app; no real server is contacted here.
const source = (await readFile(new URL('./api.js', import.meta.url), 'utf8'))
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
const { apiRequest } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('structured merge conflict keeps message and both dates for the choice dialog', async (t) => {
  const detail = { code: 'merge_acceptance_date_choice', message: 'Scegli la data',
    certificate_date: '2026-09-03', ddt_date: '2026-09-08' };
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail }), { status: 409 }));
  await assert.rejects(apiRequest('/test'), (error) => {
    assert.equal(error.status, 409);
    assert.equal(error.message, detail.message);
    assert.equal(error.detail, detail.message);
    assert.deepEqual(error.payload, detail);
    return true;
  });
});

test('existing plain and validation errors retain their readable messages', async (t) => {
  for (const [detail, message] of [['Not available', 'Not available'],
    [[{ msg: 'Value error, Data non valida' }], 'Data non valida']]) {
    const mock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail }), { status: 422 }));
    await assert.rejects(apiRequest('/test'), (error) => error.message === message && error.detail === message);
    mock.mock.restore();
  }
});
