import test from "node:test";
import assert from "node:assert/strict";
import { DDT_WORK_FILTERS, ddtQueueStatus, isClosedQueueScope, updateDdtQueueFilters } from "./ddtQueuePresentation.js";

test("only four work choices; final views do not duplicate lifecycle states", () => {
  assert.deepEqual(DDT_WORK_FILTERS, [["", "Tutti"], ["pdf_ready", "PDF da generare"],
    ["waiting_incoming", "Incoming da completare"], ["anomalies", "Anomalie"]]);
  for (const scope of ["completed", "excluded", "archived"]) {
    assert.equal(isClosedQueueScope(scope), true);
    const current = { scope: "active", state: "pdf_ready", query: "OL1", limit: "50" };
    const updated = updateDdtQueueFilters(current, "scope", scope);
    assert.deepEqual(updated, { ...current, scope, state: "" });
    assert.equal(updateDdtQueueFilters(updated, "state", "anomalies").state, "");
    assert.equal(current.state, "pdf_ready");
  }
});

test("search/presence/sort do not lose work selection; returning to open views clears it", () => {
  for (const scope of ["active", "all"]) {
    assert.equal(isClosedQueueScope(scope), false);
    const current = { scope, state: "anomalies", query: "OL1" };
    assert.equal(updateDdtQueueFilters(current, "query", "OL2").state, "anomalies");
    assert.equal(updateDdtQueueFilters(current, "source_present", "false").state, "anomalies");
    assert.equal(updateDdtQueueFilters(current, "scope", scope).state, "");
  }
});

test("a present Word does not promise a PDF; unknown labels have a visible fallback", () => {
  assert.deepEqual(ddtQueueStatus({ state: "word_ready", label: "Word pronto - completare PDF" }),
    { label: "Word da verificare", tone: "review" });
  assert.equal(ddtQueueStatus({ state: "word_ready", pdf_action: { id: 1 } }).label, "PDF da generare");
  assert.equal(ddtQueueStatus({ state: "ready" }).label, "Da certificare");
  assert.equal(ddtQueueStatus({ state: "ready", ddt_date: null }).label, "Data DDT da verificare");
  assert.equal(ddtQueueStatus({ state: "waiting_incoming" }).label, "Incoming da completare");
  assert.equal(ddtQueueStatus({ state: "review", label: "Totale DDT da verificare" }).label, "Totale DDT da verificare");
  assert.equal(ddtQueueStatus({ state: "future", label: " " }).label, "Verifica richiesta");
});
