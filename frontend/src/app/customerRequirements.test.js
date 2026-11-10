import test from "node:test";
import assert from "node:assert/strict";
import { customerRequirementBadges, pdfNameRequirement, resolveCustomerRequirements, resolveOlCustomerRequirements } from "./customerRequirements.js";

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

test("OL groups preserve exact selection per F3 and deduplicate repeated DDT", () => {
  const rows = [{ id: 1, cod_f3: "096007800" }, { id: 2, cod_f3: "096007801" }];
  const groups = resolveOlCustomerRequirements(rows, [
    { cod_f3: "096007800", needs_verification: true },
    { cod_f3: "096007800", cliente: "Cliente", needs_verification: false },
    { cod_f3: "096007801" },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].needs_verification, false);
  assert.equal(groups[0].cliente, "Cliente");
  assert.deepEqual(groups.map(group => group.match.item.id), [1, 2]);
});

test("OL missing data, joined strings, unrelated and inactive requirements never add badges", () => {
  const rows = [{ id: 1, cod_f3: "096007800" }, { id: 2, cod_f3: "322000100", active: false }];
  assert.deepEqual(resolveOlCustomerRequirements(rows), []);
  assert.deepEqual(resolveOlCustomerRequirements(rows, [
    { cod_f3: "096007800, 322000100" }, { cod_f3: "96007800" },
    { cod_f3: "322000100" }, { cliente: "Cliente" },
  ]), []);
});

test("OL family ambiguity and proposed F3 remain visible as warnings", () => {
  const groups = resolveOlCustomerRequirements([
    { id: 1, cod_f3: "811000700" }, { id: 2, cod_f3: "811000701" },
  ], [{ cod_f3: "811000702", needs_verification: true }]);
  assert.equal(groups[0].match.ambiguous, true);
  assert.equal(groups[0].match.item, null);
  assert.equal(groups[0].needs_verification, true);
});

test("name-only, other requirements, and both have distinct badges, not distinct filters", () => {
  for (const [profile, general, pdfName] of [
    [{}, true, false], // Existing blank profiles retain their badge.
    [{ note: "Seconda pagina" }, true, false],
    [{ requires_custom_pdf_name: true }, false, true],
    [{ requires_custom_pdf_name: true, note: "  " }, false, true],
    [{ requires_custom_pdf_name: true, requires_ndt: true }, true, true],
    [{ requires_custom_pdf_name: true, specific_requirements: "Allegato" }, true, true],
    [{ requires_custom_pdf_name: true, note: "Grafico" }, true, true],
  ]) {
    const match = resolveCustomerRequirements([{ cod_f3: "096007800", ...profile }], "096007830");
    assert.deepEqual(customerRequirementBadges([match]), { general, pdfName, ambiguous: false });
    assert.equal(pdfNameRequirement(match), pdfName ? "required" : "none");
  }
});

test("PDF name checks use exact article priority and do not choose ambiguous alternatives", () => {
  const profiles = [
    { cod_f3: "096007800", requires_custom_pdf_name: true },
    { cod_f3: "096007830", requires_marking: true },
    { cod_f3: "322000100", requires_custom_pdf_name: true, active: false },
  ];
  assert.equal(pdfNameRequirement(resolveCustomerRequirements(profiles, "096007830")), "none");
  assert.equal(pdfNameRequirement(resolveCustomerRequirements(profiles, "096007840")), "ambiguous");
  for (const code of ["322000100", "96007800", "", null, "999999900"])
    assert.equal(pdfNameRequirement(resolveCustomerRequirements(profiles, code)), "none");
});

test("multiple OL articles keep both badge kinds without multiplying DDTs", () => {
  const profiles = [{ cod_f3: "1142000100", note: "Grafico" }, { cod_f3: "096007800", requires_custom_pdf_name: true }];
  const groups = resolveOlCustomerRequirements(profiles, [
    { cod_f3: "1142000100" }, { cod_f3: "096007830" }, { cod_f3: "096007830" },
  ]);
  assert.equal(groups.length, 2);
  assert.deepEqual(customerRequirementBadges(groups.map(group => group.match)), { general: true, pdfName: true, ambiguous: false });
  assert.deepEqual(customerRequirementBadges([]), { general: false, pdfName: false, ambiguous: false });
});
