import assert from "node:assert/strict";
import test from "node:test";

import { ddtSyncRecovered, ddtSyncWarning } from "./ddtSyncWarning.js";

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
