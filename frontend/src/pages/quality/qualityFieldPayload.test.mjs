import assert from "node:assert/strict";
import test from "node:test";
import { qualityFieldError, qualityFieldPayloadValue } from "./qualityFieldPayload.js";

const field = "qualita_numero_colli";
test("manual package count is a positive JSON integer or null", () => {
  for (const value of ["", "   ", null, undefined]) assert.equal(qualityFieldPayloadValue(field, value), null);
  for (const value of ["3", " 3 ", "003", 3]) assert.equal(qualityFieldPayloadValue(field, value), 3);
  assert.equal(qualityFieldPayloadValue(field, "2147483647"), 2147483647);
});
test("invalid counts are not converted to zero, rounded or sent", () => {
  for (const value of ["0", "-1", "1.5", "1,5", "1e2", "abc", "2147483648", "999999999999999999", true]) {
    assert.ok(qualityFieldError(field, value));
    assert.throws(() => qualityFieldPayloadValue(field, value));
  }
});
test("existing quality field payloads are unchanged", () => {
  for (const field of ["qualita_note", "qualita_tipo_controllo", "qualita_data_accettazione"]) {
    assert.equal(qualityFieldPayloadValue(field, ""), null);
    assert.equal(qualityFieldPayloadValue(field, "test"), "test");
  }
});
