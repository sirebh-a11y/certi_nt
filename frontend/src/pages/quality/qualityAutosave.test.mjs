import assert from "node:assert/strict";
import test from "node:test";
import { createQualityAutosave, qualityCellKey, reconcileQualityRead } from "./qualityAutosave.js";

const count = "qualita_numero_colli", note = "qualita_note";
const key = qualityCellKey(1, count);
function fixture() {
  const calls = [], feedback = [], commits = [];
  const queue = createQualityAutosave({
    write: (id, field, value) => new Promise((resolve, reject) => calls.push({ value, resolve, reject })),
    committed: (...args) => commits.push(args), feedback: (...args) => feedback.push(args), settled() {},
  });
  return { queue, calls, feedback, commits };
}
const tick = () => new Promise(resolve => setTimeout(resolve, 0));

test("a read started before edits protects the edited field even after ACK, but fetches untouched fields", async () => {
  const { queue, calls } = fixture();
  const protectedKeys = queue.beginRead();
  queue.edit(1, count, "8", 0);
  calls[0].resolve({id: 1, [count]: 8}); await tick();
  assert.equal(queue.hasPending(), false);
  const result = reconcileQualityRead([{id: 1, [count]: 3, [note]: "incoming"}],
    [{id: 1, [count]: 8}], {1: {[count]: 8}}, protectedKeys, [count, note]);
  assert.equal(result.drafts[1][count], 8);
  assert.equal(result.drafts[1][note], "incoming");
  queue.endRead(protectedKeys);
  assert.equal(queue.beginRead().size, 0);
});
test("overlap, blur and exit serialize writes including a return to the original value", async () => {
  const { queue, calls, commits } = fixture();
  queue.edit(1, count, "5", 0);
  queue.edit(1, count, "7", 800);
  queue.edit(1, count, "3", 800);
  queue.flush(key); queue.flushAll();
  assert.deepEqual(calls.map(c => c.value), [5]);
  calls[0].resolve({}); await tick();
  assert.deepEqual(calls.map(c => c.value), [5, 3]);
  assert.equal(commits[0][3], false);
  calls[1].resolve({}); await tick();
  assert.equal(commits[1][3], true);
  assert.equal(queue.hasPending(), false);
});
test("failed write is retained across a refresh, retry succeeds, unedited blur sends nothing", async () => {
  const { queue, calls, feedback } = fixture();
  await queue.flush(key);
  queue.edit(1, count, "8", 0);
  calls[0].reject(Error("offline")); await tick();
  assert.equal(feedback.at(-1)[1].retry, true);
  const keys = queue.beginRead();
  const result = reconcileQualityRead([], [{id: 1, [count]: 3}], {1:{[count]:"8"}}, keys, [count]);
  assert.equal(result.drafts[1][count], "8");
  assert.equal(result.rows.length, 1);
  queue.endRead(keys);
  queue.flush(key);
  calls[1].resolve({}); await tick();
  assert.deepEqual(calls.map(c => c.value), [8, 8]);
  assert.equal(queue.hasPending(), false);
  assert.deepEqual(reconcileQualityRead([], result.rows, result.drafts, queue.beginRead(), [count]).rows, []);
});
test("invalid replacement is not sent on exit or after a successful older write", async () => {
  const { queue, calls, feedback } = fixture();
  queue.edit(1, count, "5", 0);
  queue.edit(1, count, "-1", 0);
  queue.flushAll(); calls[0].resolve({}); await tick();
  assert.deepEqual(calls.map(c => c.value), [5]);
  assert.equal(feedback.at(-1)[1].status, "error");
  assert.equal(feedback.at(-1)[1].retry, undefined);
  queue.edit(1, count, "", 0);
  assert.equal(calls[1].value, null); calls[1].resolve({}); await tick();
});
