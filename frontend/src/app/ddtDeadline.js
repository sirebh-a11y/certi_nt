const romeDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit",
});

function calendarDay(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
  const timestamp = Date.parse(`${value}T00:00:00Z`);
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString().slice(0, 10) !== value) return null;
  return timestamp / 86400000;
}

// The backend owns the deadline and configured duration. Compare calendar dates,
// not elapsed hours: weekends, daylight saving and the browser timezone do not shift it.
export function ddtDeadline(item, now = Date.now()) {
  if (item.state === "completed" || item.state === "excluded") return null;
  const dueDay = calendarDay(item.certification_due_date);
  if (!item.ddt_date || dueDay === null) {
    return { tone: "unknown", label: "Data DDT da verificare" };
  }
  const parts = Object.fromEntries(romeDate.formatToParts(now).map(({ type, value }) => [type, value]));
  const today = calendarDay(`${parts.year}-${parts.month}-${parts.day}`);
  const remaining = dueDay - today + 1; // Today counts as one available calendar day.
  if (remaining <= 0) return { tone: "overdue", label: "Termine superato" };
  if (remaining === 1) return { tone: "today", label: "Ultimo giorno" };
  if (remaining === 2) return { tone: "soon", label: "2 giorni, oggi incluso" };
  return { tone: "normal", label: "" };
}
