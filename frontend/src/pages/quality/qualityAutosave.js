import { qualityFieldError, qualityFieldPayloadValue } from "./qualityFieldPayload.js";

export const qualityCellKey = (rowId, field) => `${rowId}:${field}`;

// A cell has one latest intention and at most one outstanding write. A blur,
// retry or page exit flushes the same queue; it never starts a competing PATCH.
export function createQualityAutosave({ write, committed, feedback, settled }) {
  const pending = new Map();
  const busy = new Set();
  let readKeys = null;

  function edit(rowId, field, value, delay) {
    const key = qualityCellKey(rowId, field);
    readKeys?.add(key);
    clearTimeout(pending.get(key)?.timer);
    const entry = { rowId, field, value };
    pending.set(key, entry);
    const invalid = qualityFieldError(field, value);
    feedback(key, invalid ? { status: "error", message: invalid } : null);
    if (!invalid) {
      if (delay > 0) entry.timer = setTimeout(() => flush(key), delay);
      else void flush(key);
    }
  }

  async function flush(key) {
    const entry = pending.get(key);
    if (!entry) return;
    clearTimeout(entry.timer);
    if (busy.has(key) || qualityFieldError(entry.field, entry.value)) return;
    busy.add(key);
    feedback(key, { status: "saving" });
    try {
      const result = await write(entry.rowId, entry.field, qualityFieldPayloadValue(entry.field, entry.value));
      const latest = pending.get(key) === entry;
      committed(entry.rowId, entry.field, result, latest);
      if (latest) {
        pending.delete(key);
        feedback(key, { status: "saved" });
      }
    } catch (error) {
      if (pending.get(key) === entry) {
        feedback(key, { status: "error", retry: true, message: error.message || "Salvataggio non confermato." });
      }
    } finally {
      busy.delete(key);
      if (pending.has(key) && pending.get(key) !== entry) void flush(key);
      if (!pending.size) settled();
    }
  }

  return {
    edit, flush,
    flushAll() { for (const key of pending.keys()) void flush(key); },
    hasPending: () => pending.size > 0,
    beginRead() { readKeys = new Set(pending.keys()); return readKeys; },
    endRead(keys) { if (readKeys === keys) readKeys = null; },
  };
}

// A GET can predate both an edit and its successful PATCH. Use that GET for
// unaffected cells, never for a cell touched during the read (even if saved).
export function reconcileQualityRead(items, previous, drafts, protectedKeys, fields) {
  const previousById = new Map(previous.map(row => [row.id, row]));
  const nextDrafts = {};
  const seen = new Set();
  const rows = items.map(item => {
    seen.add(item.id);
    const row = { ...item };
    const draft = {};
    for (const f of fields) {
      if (protectedKeys.has(qualityCellKey(item.id, f)) && previousById.has(item.id)) {
        row[f] = previousById.get(item.id)[f];
        draft[f] = drafts[item.id]?.[f] ?? "";
      } else {
        draft[f] = item[f] ?? "";
      }
    }
    nextDrafts[item.id] = draft;
    return row;
  });
  for (const row of previous) {
    if (!seen.has(row.id) && fields.some(f => protectedKeys.has(qualityCellKey(row.id, f)))) {
      rows.push(row);
      nextDrafts[row.id] = drafts[row.id];
    }
  }
  return { rows, drafts: nextDrafts };
}
