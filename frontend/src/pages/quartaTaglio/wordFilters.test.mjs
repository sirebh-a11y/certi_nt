import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeWordFilters, toggleWordFilter } from './wordFilters.js';

test('each list filter switches off the other filters and toggles back to all', () => {
  const keys = ['hideCertified', 'onlyWordPending', 'onlyAdditionalWords'];
  for (const previous of keys) {
    for (const next of keys) {
      const result = toggleWordFilter({ [previous]: true }, next);
      assert.equal(Object.values(result).filter(Boolean).length, previous === next ? 0 : 1);
      assert.equal(result[next], previous !== next);
    }
  }
});

test('restored detail navigation preserves the selected filter and migrates older sessions', () => {
  const saved = JSON.parse(JSON.stringify({ onlyAdditionalWords: true, queryOne: 'OL123' }));
  assert.deepEqual(normalizeWordFilters(saved), {
    onlyAdditionalWords: true, onlyWordPending: false, hideCertified: false,
  });
  assert.equal(normalizeWordFilters({ onlyWordPending: true }).onlyWordPending, true);
  assert.equal(normalizeWordFilters({}).onlyAdditionalWords, false);
});

test('invalid stored combinations cannot activate both Word filters', () => {
  assert.deepEqual(normalizeWordFilters({ onlyAdditionalWords: true, onlyWordPending: true, hideCertified: true }), {
    onlyAdditionalWords: true, onlyWordPending: false, hideCertified: false,
  });
  assert.equal(normalizeWordFilters({ onlyWordPending: 'true' }).onlyWordPending, false);
});
