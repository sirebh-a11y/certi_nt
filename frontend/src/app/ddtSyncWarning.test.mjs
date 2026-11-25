import assert from "node:assert/strict";
import test from "node:test";

import { ddtSyncHasNewSuccess, ddtSyncRecovered, ddtSyncShouldReloadQueue, ddtSyncWarning } from "./ddtSyncWarning.js";

const success = { finished_at: "2026-09-29T08:00:00Z" };
const noon = Date.parse("2026-09-29T12:00:00Z");

test("the four-hour threshold uses the last completed success", () => {
  const sync = { enabled: true, last_success: success };
  assert.equal(ddtSyncWarning(sync, noon - 1).stale, false);
  assert.equal(ddtSyncWarning(sync, noon).stale, true);
  assert.equal(ddtSyncWarning({ ...sync, last_success: { finished_at: "2026-09-29T11:59:00Z" } }, noon).stale, false);
});

test("a failed attempt does not reset the last successful read", () => {
  const warning = ddtSyncWarning({ enabled: true, last_success: success, last_attempt: { status: "error" } }, noon);
  assert.equal(warning.stale, true);
  assert.equal(warning.syncFailed, true);
});

test("disabled sync has no four-hour warning; missing success is explicit", () => {
  assert.equal(ddtSyncWarning({ enabled: false, last_success: success }, noon).stale, false);
  assert.equal(ddtSyncWarning({ enabled: true, last_success: null }, noon).neverSucceeded, true);
});

test("recovery requires a new successful read after an actual warning", () => {
  const old = { enabled: true, last_success: success, last_attempt: { status: "error" } };
  const next = { enabled: true, last_success: { finished_at: "2026-09-29T12:01:00Z" }, last_attempt: { status: "success" } };
  assert.equal(ddtSyncRecovered(old, next, noon), true);
  assert.equal(ddtSyncRecovered(old, { ...next, last_success: success }, noon), false);
  assert.equal(ddtSyncRecovered({ ...old, last_attempt: { status: "success" } }, next, Date.parse("2026-09-29T09:00:00Z")), false);
  assert.equal(ddtSyncRecovered({ ...old, enabled: false }, next, noon), false);
});

test("a daily read is not considered stale four hours later, even the next afternoon", () => {
  const evening = { enabled: true, last_scheduled_at: "2026-11-24T17:00:00Z",
    next_scheduled_at: "2026-11-25T17:00:00Z", last_success: { started_at: "2026-11-24T17:00:00Z",
      finished_at: "2026-11-24T17:00:03Z" } };
  assert.equal(ddtSyncWarning(evening, Date.parse("2026-11-25T16:59:59Z")).stale, false);
  const today = { ...evening, last_scheduled_at: "2026-11-25T17:00:00Z", next_scheduled_at: "2026-11-26T17:00:00Z" };
  assert.equal(ddtSyncWarning(today, Date.parse("2026-11-25T17:04:59Z")).stale, false);
  assert.equal(ddtSyncWarning(today, Date.parse("2026-11-25T17:05:00Z")).stale, true);
  assert.equal(ddtSyncWarning({ ...today, in_progress: true }, Date.parse("2026-11-25T21:00:00Z")).stale, false);
  assert.equal(ddtSyncWarning({ ...today, last_attempt: {status: "error"}}, Date.parse("2026-11-25T17:01:00Z")).syncFailed, true);
  // Finishing an older slow read after today's scheduled time does not fill today's slot.
  const slow = { ...today, last_success: { ...evening.last_success, finished_at: "2026-11-25T17:01:00Z" } };
  assert.equal(ddtSyncWarning(slow, Date.parse("2026-11-25T17:10:00Z")).stale, true);
});

test("first installation waits for its first reading, and an open screen reloads for a genuinely new success", () => {
  const first = { enabled: true, next_scheduled_at: "2026-11-25T17:00:00Z" };
  assert.equal(ddtSyncWarning(first, Date.parse("2026-11-25T16:00:00Z")).neverSucceeded, false);
  const result = { ...first, last_success: { finished_at: "2026-11-25T17:00:02Z" } };
  assert.equal(ddtSyncHasNewSuccess(first, result), true);
  assert.equal(ddtSyncHasNewSuccess(result, result), false);
  assert.equal(ddtSyncHasNewSuccess(result, { ...first, last_success: success }), false);
  assert.equal(ddtSyncHasNewSuccess(null, result), false);
});

const dailySlot = "2026-11-25T17:00:00Z";
const dailyRead = {
  status: "success", started_at: dailySlot, finished_at: "2026-11-25T17:00:20Z",
};
const waiting = { enabled: true, last_scheduled_at: dailySlot, in_progress: true };
const readWhileWorking = { ...waiting, last_attempt: dailyRead, last_success: dailyRead };
const completed = { ...readWhileWorking, in_progress: false };

test("refreshes when DDT arrive and once more when the daily job has prepared the Word copies", () => {
  assert.equal(ddtSyncShouldReloadQueue(waiting, readWhileWorking), true);
  assert.equal(ddtSyncShouldReloadQueue(readWhileWorking, { ...readWhileWorking }), false);
  assert.equal(ddtSyncShouldReloadQueue(readWhileWorking, completed), true);
  assert.equal(ddtSyncShouldReloadQueue(completed, { ...completed }), false);
});

test("one refresh is enough if the entire job finished between two checks", () => {
  assert.equal(ddtSyncShouldReloadQueue(waiting, completed), true);
  assert.equal(ddtSyncShouldReloadQueue(completed, completed), false);
  assert.equal(ddtSyncShouldReloadQueue(null, completed), false);
});

test("errors, previous-day reads and disabled sync do not trigger an end-of-job refresh", () => {
  assert.equal(ddtSyncShouldReloadQueue(waiting, { ...waiting, in_progress: false,
    last_attempt: { status: "error" } }), false);
  const olderRead = { status: "success", ...success };
  const olderOnly = { ...waiting, last_attempt: olderRead, last_success: olderRead };
  assert.equal(ddtSyncShouldReloadQueue(olderOnly, { ...olderOnly, in_progress: false }), false);
  assert.equal(ddtSyncShouldReloadQueue(readWhileWorking, { ...completed, enabled: false }), false);
  assert.equal(ddtSyncShouldReloadQueue(readWhileWorking, { ...completed, in_progress: undefined }), false);
});
