import test from "node:test";
import assert from "node:assert/strict";
import { mergeRegisterRefresh, registerDdtNotice } from "./registerPresentation.js";

test("received DDT is not described as waiting, without assigning it to the base", () => {
  assert.equal(registerDdtNotice({ddt: null, ddt_received: true}), "DDT presente — verifica richiesta");
  assert.equal(registerDdtNotice({ddt: "DDT1", ddt_received: true}), null);
  assert.equal(registerDdtNotice({ddt: null, ddt_received: false}), null);
  assert.equal(registerDdtNotice({ddt: null}), null);
});

test("refresh replaces hidden base and preserves different quotas with same number and DDT", () => {
  const current = [{id: 1}, {id: 2}, {id: 4, cod_f3: 'other'}];
  const shipments = [{id: 2, ddt: 'DDT1', certificate_number: 'N'}, {id: 3, ddt: 'DDT1', certificate_number: 'N'}];
  const response = {items: shipments, hidden_certificate_ids: [1]};
  const result = mergeRegisterRefresh(current, response);
  assert.deepEqual(result, [shipments[0], current[2], shipments[1]]);
  assert.deepEqual(mergeRegisterRefresh(result, response), result);
  assert.equal(current.length, 3);
});

test("refresh never resurrects hidden base and supports old responses", () => {
  assert.deepEqual(mergeRegisterRefresh([{id: 1}], {items:[{id:1}], hidden_certificate_ids:[1]}), []);
  assert.deepEqual(mergeRegisterRefresh([{id:1}], {items:[{id:1,has_pdf:true}]}), [{id:1,has_pdf:true}]);
  assert.deepEqual(mergeRegisterRefresh([{id:1}], {items:[]}), [{id:1}]);
});
