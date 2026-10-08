import test from "node:test";
import assert from "node:assert/strict";
import { resolveCustomerRequirements } from "./customerRequirements.js";

test("exact CodF3 wins over same-family variants", () => {
  const rows = [{ id: 1, cod_f3: "811000700" }, { id: 2, cod_f3: "811000701" }];
  assert.equal(resolveCustomerRequirements(rows, "811000701").item.id, 2);
  assert.equal(resolveCustomerRequirements(rows, "811000702").ambiguous, true);
  assert.equal(resolveCustomerRequirements(rows, "811000702").item, null);
});
test("family fallback preserves leading zeroes and ignores inactive rows", () => {
  const rows = [{ id: 1, cod_f3: "096007800", active: true }, { id: 2, cod_f3: "096007801", active: false }];
  assert.equal(resolveCustomerRequirements(rows, "096007801").item.id, 1);
  assert.equal(resolveCustomerRequirements(rows, "96007801").item, null);
  assert.equal(resolveCustomerRequirements(rows, "531000300").item, null);
});
test("missing or short codes do not mark unrelated rows of the same customer", () => {
  for (const code of [null, "", "12", "none"])
    assert.equal(resolveCustomerRequirements([{ cod_f3: "322000100", cliente: "Cliente" }], code).candidates.length, 0);
});
