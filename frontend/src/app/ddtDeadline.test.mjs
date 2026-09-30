import assert from "node:assert/strict";
import test from "node:test";
import { ddtDeadline } from "./ddtDeadline.js";

const item = { ddt_date: "2026-09-30", certification_due_date: "2026-10-06", state: "ready" };
const at = (iso) => Date.parse(iso);

test("seven calendar days include the DDT date and weekends", () => {
  assert.equal(ddtDeadline(item, at("2026-09-30T23:59:00+02:00")).tone, "normal");
  assert.equal(ddtDeadline(item, at("2026-10-04T12:00:00+02:00")).tone, "normal");
  assert.deepEqual(ddtDeadline(item, at("2026-10-05T00:00:00+02:00")),
    { tone: "soon", label: "2 giorni, oggi incluso" });
  assert.equal(ddtDeadline(item, at("2026-10-06T00:00:00+02:00")).tone, "today");
  assert.equal(ddtDeadline(item, at("2026-10-06T23:59:59+02:00")).tone, "today");
  assert.equal(ddtDeadline(item, at("2026-10-07T00:00:00+02:00")).tone, "overdue");
});

test("uses Rome midnight even for browsers elsewhere and across daylight saving", () => {
  assert.equal(ddtDeadline(item, at("2026-10-06T17:59:00-04:00")).tone, "today");
  assert.equal(ddtDeadline(item, at("2026-10-06T18:00:00-04:00")).tone, "overdue");
  for (const [due, before, after] of [
    ["2026-03-29", "2026-03-29T23:59:59+02:00", "2026-03-30T00:00:00+02:00"],
    ["2026-10-25", "2026-10-25T23:59:59+01:00", "2026-10-26T00:00:00+01:00"],
  ]) {
    assert.equal(ddtDeadline({ ...item, certification_due_date: due }, at(before)).tone, "today");
    assert.equal(ddtDeadline({ ...item, certification_due_date: due }, at(after)).tone, "overdue");
  }
});

test("missing or malformed dates never invent a deadline", () => {
  for (const value of [null, undefined, "", "2026-02-30", "not-a-date"]) {
    assert.deepEqual(ddtDeadline({ ...item, certification_due_date: value }),
      { tone: "unknown", label: "Data DDT da verificare" });
  }
  assert.equal(ddtDeadline({ ...item, ddt_date: null }).tone, "unknown");
});

test("completed PDFs have no warning; other operational states and history keep their deadline", () => {
  const now = at("2026-10-10T12:00:00Z");
  assert.equal(ddtDeadline({ ...item, state: "completed" }, now), null);
  for (const state of ["ready", "review", "waiting_incoming", "quality_rejected", "word_ready", "to_link"]) {
    const original = { ...item, state, source_present: false, first_seen_at: "2026-10-10T11:59:00Z" };
    const copy = { ...original };
    assert.equal(ddtDeadline(copy, now).tone, "overdue");
    assert.deepEqual(copy, original);
  }
});
