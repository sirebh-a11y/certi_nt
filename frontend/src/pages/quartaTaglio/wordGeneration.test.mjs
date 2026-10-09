import assert from 'node:assert/strict';
import test from 'node:test';
import { wordGenerationPayload } from './wordGeneration.js';

test('first generation retains candidate and explicit non-conformity consent', () => {
  assert.deepEqual(wordGenerationPayload({ candidateCodF3: '001230', forceNonConforming: true }), {
    force_non_conforming: true, force_regenerate: false, certificate_id: null,
    candidate_cod_f3: '001230', ddt_work_item_id: null,
  });
});
test('regeneration with non-conformity targets the active document, not another URL certificate', () => {
  assert.deepEqual(wordGenerationPayload({ regenerate: true, forceNonConforming: true,
    activeCertificateId: 7, certificateId: 4, candidateCodF3: '001230', ddtWorkItemId: '9' }), {
    force_non_conforming: true, force_regenerate: true, certificate_id: 7,
    candidate_cod_f3: null, ddt_work_item_id: 9,
  });
});
test('conforming regeneration does not grant non-conformity consent', () => {
  const result = wordGenerationPayload({ regenerate: true, activeCertificateId: 7 });
  assert.equal(result.force_non_conforming, false);
  assert.equal(result.force_regenerate, true);
  assert.equal(result.certificate_id, 7);
});
test('missing regeneration identity cannot accidentally create a new raw Word', () => {
  for (const activeCertificateId of [undefined, null, '', 0, -1, 'bad', 1.5]) {
    assert.throws(() => wordGenerationPayload({ regenerate: true, activeCertificateId }), /non identificato/);
  }
});
