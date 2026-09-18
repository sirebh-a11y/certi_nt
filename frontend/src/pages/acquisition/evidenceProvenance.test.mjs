import assert from 'node:assert/strict';
import test from 'node:test';
import { hasUnverifiedSourcePage } from './evidenceProvenance.js';

const row = {
  evidences: [{ id: 1, tipo_evidenza: 'testo_pagina_da_verificare' }, { id: 2, tipo_evidenza: 'testo' }],
  values: [{ blocco: 'note', stato: 'proposto', document_evidence_id: 1 }],
};
test('warning only for active uncertain evidence and requested block', () => {
  assert.equal(hasUnverifiedSourcePage(row, 'note'), true);
  assert.equal(hasUnverifiedSourcePage(row, 'requisiti'), false);
  assert.equal(hasUnverifiedSourcePage(null, 'note'), false);
});
test('confirmed values and replaced evidence do not leave stale warnings', () => {
  assert.equal(hasUnverifiedSourcePage({ ...row, values: [{ ...row.values[0], stato: 'confermato' }] }, 'note'), false);
  assert.equal(hasUnverifiedSourcePage({ ...row, values: [{ ...row.values[0], document_evidence_id: 2 }] }, 'note'), false);
});
