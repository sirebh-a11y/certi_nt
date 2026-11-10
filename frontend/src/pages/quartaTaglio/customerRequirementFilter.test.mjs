import test from "node:test";
import assert from "node:assert/strict";
import { normalizeCustomerRequirementFilter } from "./customerRequirementFilter.js";
import { hasOlCustomerRequirements, resolveOlCustomerRequirements } from "../../app/customerRequirements.js";
import { readFileSync } from "node:fs";

test("requirements selection accepts exactly three values; old session state defaults to all", () => {
  for (const value of ["all", "with", "without"]) assert.equal(normalizeCustomerRequirementFilter(value), value);
  for (const value of [undefined, null, true, "invalid", {}, "WITH"]) assert.equal(normalizeCustomerRequirementFilter(value), "all");
});

test("server snapshot drives a filtered badge; old unfiltered responses keep the resolver", () => {
  assert.equal(hasOlCustomerRequirements({ has_customer_requirements: true }, []), true);
  assert.equal(hasOlCustomerRequirements({ has_customer_requirements: false }, [{}]), false);
  assert.equal(hasOlCustomerRequirements({}, [{}]), true);
  assert.equal(hasOlCustomerRequirements({}, []), false);
});

const cases = JSON.parse(readFileSync(new URL("../../../../backend/tests/fixtures/customer_requirement_presence.json", import.meta.url), "utf8"));
for (const fixture of cases) test(`same presence contract as backend: ${fixture.name}`, () => {
  assert.equal(resolveOlCustomerRequirements(fixture.requirements, fixture.articles).length > 0, fixture.expected);
});
