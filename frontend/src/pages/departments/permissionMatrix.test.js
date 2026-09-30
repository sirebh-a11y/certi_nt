import assert from "node:assert/strict";
import test from "node:test";

import { DEPARTMENT_ORDER, PERMISSION_GROUPS, ROLE_OPTIONS, permissionLevel, sortDepartments } from "./permissionMatrix.js";

const rows = PERMISSION_GROUPS.flatMap((group) => group.rows);
const row = (id) => rows.find((item) => item.id === id);
const level = (id, department, role) => permissionLevel(row(id), { department, role });

test("all seven departments and all three user roles are represented", () => {
  assert.equal(DEPARTMENT_ORDER.length, 7);
  assert.equal(ROLE_OPTIONS.length, 3);
  assert.equal(new Set(rows.map((item) => item.id)).size, rows.length);
  for (const department of DEPARTMENT_ORDER) {
    for (const role of ROLE_OPTIONS) {
      for (const item of rows) {
        assert.ok(["opera", "consulta", "no"].includes(permissionLevel(item, { department, role: role.value })));
      }
    }
  }
});

test("actual page and action distinctions replace the old fixed matrix", () => {
  assert.equal(level("ddt-list", "Qualità", "user"), "consulta");
  assert.equal(level("ddt-decide", "Qualità", "admin"), "opera");
  assert.equal(level("ddt-decide", "Qualità", "manager"), "no");
  assert.equal(level("ddt-decide", "Laboratorio", "admin"), "no");
  assert.equal(level("register", "Produzione", "user"), "consulta");
  assert.equal(level("register", "Incoming", "user"), "consulta");
  assert.equal(level("incoming-list", "Incoming", "admin"), "no");
  assert.equal(level("standards", "Laboratorio", "user"), "opera");
  assert.equal(level("quality-evaluation", "Direzione", "user"), "opera");
  assert.equal(level("customer-requirements", "Qualità", "user"), "consulta");
  assert.equal(level("customer-requirements", "Qualità", "admin"), "opera");
  assert.equal(level("pdf-generate", "Qualità", "user"), "opera");
  assert.equal(level("pdf-generate", "Laboratorio", "admin"), "no");
  assert.equal(level("pdf-reopen", "Qualità", "manager"), "opera");
  assert.equal(level("pdf-reopen", "Qualità", "user"), "no");
  assert.equal(level("users", "IT", "admin"), "opera");
  assert.equal(level("users", "IT", "manager"), "no");
});

test("departments follow the intended screen order without losing unknown ones", () => {
  const input = ["Direzione", "Incoming", "IT", "Altro"].map((name, id) => ({ id, name }));
  assert.deepEqual(sortDepartments(input).map((item) => item.name), ["IT", "Incoming", "Direzione", "Altro"]);
});
