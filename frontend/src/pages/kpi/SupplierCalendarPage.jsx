import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const MONTH_NAMES = [
  "Gennaio",
  "Febbraio",
  "Marzo",
  "Aprile",
  "Maggio",
  "Giugno",
  "Luglio",
  "Agosto",
  "Settembre",
  "Ottobre",
  "Novembre",
  "Dicembre",
];

const WEEK_DAYS = ["L", "M", "M", "G", "V", "S", "D"];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function clampYear(value) {
  const numeric = Number(value) || 2026;
  return String(Math.min(2100, Math.max(2026, numeric)));
}

function isoForYear(year) {
  const today = todayIso();
  return today.startsWith(`${year}-`) ? today : `${year}-01-01`;
}

function parseIso(value) {
  if (!value) {
    return null;
  }
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDateIt(value) {
  const date = parseIso(value);
  if (!date) {
    return "-";
  }
  return date.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

function monthDays(year, monthIndex) {
  const first = new Date(Number(year), monthIndex, 1);
  const last = new Date(Number(year), monthIndex + 1, 0);
  const leading = (first.getDay() + 6) % 7;
  const days = Array.from({ length: leading }, () => null);
  for (let day = 1; day <= last.getDate(); day += 1) {
    const iso = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    days.push({ day, iso });
  }
  return days;
}

function dayClass(kind, iso) {
  const today = todayIso();
  const todayClass = iso === today ? "ring-2 ring-accent ring-offset-1" : "";
  if (kind === "closure") {
    return `border-amber-300 bg-amber-100 text-amber-950 ${todayClass}`;
  }
  if (kind === "holiday") {
    return `border-sky-300 bg-sky-100 text-sky-950 ${todayClass}`;
  }
  if (kind === "weekend") {
    return `border-slate-200 bg-slate-100 text-slate-500 ${todayClass}`;
  }
  return `border-slate-200 bg-white text-slate-700 ${todayClass}`;
}

function SummaryCard({ label, value, tone }) {
  const tones = {
    sky: "border-sky-200 bg-sky-50 text-sky-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    slate: "border-slate-200 bg-white text-slate-900",
  };
  return (
    <div className={`rounded-2xl border px-4 py-3 shadow-sm ${tones[tone] || tones.slate}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
      <p className="mt-1 text-xl font-semibold leading-tight">{value}</p>
    </div>
  );
}

export default function SupplierCalendarPage() {
  const { token } = useAuth();
  const [year, setYear] = useState(clampYear(new Date().getFullYear()));
  const [calendar, setCalendar] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState(() => {
    const date = isoForYear(clampYear(new Date().getFullYear()));
    return { start_date: date, end_date: date, label: "" };
  });

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    apiRequest(`/supplier-calendar/${year}`, {}, token)
      .then((data) => {
        if (!ignore) {
          setCalendar(data);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [token, year]);

  useEffect(() => {
    const date = isoForYear(year);
    setForm((current) => ({ ...current, start_date: date, end_date: date }));
  }, [year]);

  const daysByIso = useMemo(() => {
    const map = new Map();
    (calendar?.days || []).forEach((day) => {
      map.set(day.date, day);
    });
    return map;
  }, [calendar]);

  function reload() {
    setLoading(true);
    setError("");
    apiRequest(`/supplier-calendar/${year}`, {}, token)
      .then(setCalendar)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest(
        "/supplier-calendar/closures",
        {
          method: "POST",
          body: JSON.stringify({
            start_date: form.start_date,
            end_date: form.end_date,
            label: form.label,
          }),
        },
        token,
      );
      setForm((current) => ({ ...current, label: "" }));
      reload();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(closureId) {
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/supplier-calendar/closures/${closureId}`, { method: "DELETE" }, token);
      reload();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-[22px] border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Valutazione fornitori</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink">Calendario KPI</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            Festivita italiane automatiche e chiusure aziendali usate solo per il Tempo medio controllo.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <button
            className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            type="button"
            onClick={() => setYear(clampYear(Number(year) - 1))}
          >
            Anno -
          </button>
          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Anno</span>
            <input
              className="h-10 w-28 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-ink outline-none transition focus:border-accent"
              min="2026"
              max="2100"
              type="number"
              value={year}
              onChange={(event) => setYear(clampYear(event.target.value))}
            />
          </label>
          <button
            className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            type="button"
            onClick={() => setYear(clampYear(Number(year) + 1))}
          >
            Anno +
          </button>
        </div>
      </div>

      {error ? <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <SummaryCard label="Festivita italiane" value={calendar?.totals?.holiday_days ?? "-"} tone="sky" />
        <SummaryCard label="Sabati e domeniche" value={calendar?.totals?.weekend_days ?? "-"} tone="slate" />
        <SummaryCard label="Giorni chiusura aziendale" value={calendar?.totals?.closure_days ?? "-"} tone="amber" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <section className="rounded-2xl border border-border bg-slate-50 p-4">
          <h2 className="text-lg font-semibold text-ink">Chiusure aziendali</h2>
          <p className="mt-1 text-sm text-slate-600">Aggiungi una o piu chiusure. Le date sono comprese.</p>
          <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Inizio</span>
              <input
                className="h-10 w-full rounded-xl border border-border bg-white px-3 text-sm outline-none transition focus:border-accent"
                min="2026-01-01"
                type="date"
                value={form.start_date}
                onChange={(event) => setForm((current) => ({ ...current, start_date: event.target.value }))}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Fine</span>
              <input
                className="h-10 w-full rounded-xl border border-border bg-white px-3 text-sm outline-none transition focus:border-accent"
                min="2026-01-01"
                type="date"
                value={form.end_date}
                onChange={(event) => setForm((current) => ({ ...current, end_date: event.target.value }))}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Motivo</span>
              <input
                className="h-10 w-full rounded-xl border border-border bg-white px-3 text-sm outline-none transition focus:border-accent"
                placeholder="Es. Chiusura estiva"
                value={form.label}
                onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))}
              />
            </label>
            <button
              className="h-10 rounded-xl bg-accent px-4 text-sm font-semibold text-white transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving || !form.label.trim()}
              type="submit"
            >
              Aggiungi chiusura
            </button>
          </form>

          <div className="mt-5 space-y-2">
            {(calendar?.closures || []).length === 0 ? (
              <p className="rounded-xl border border-dashed border-border bg-white px-3 py-3 text-sm text-slate-500">
                Nessuna chiusura aziendale inserita per questo anno.
              </p>
            ) : (
              calendar.closures.map((closure) => (
                <div className="rounded-xl border border-border bg-white px-3 py-3" key={closure.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-ink">{closure.label}</p>
                      <p className="mt-1 text-sm text-slate-600">
                        {formatDateIt(closure.start_date)} - {formatDateIt(closure.end_date)}
                      </p>
                    </div>
                    <button
                      className="rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
                      disabled={saving}
                      type="button"
                      onClick={() => handleDelete(closure.id)}
                    >
                      Elimina
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">Anno {year}</h2>
            <div className="flex flex-wrap gap-2 text-xs text-slate-600">
              <span className="rounded-full border border-slate-200 bg-white px-2 py-1">Lavorativo</span>
              <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-1">Sab/Dom</span>
              <span className="rounded-full border border-sky-300 bg-sky-100 px-2 py-1">Festivita</span>
              <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-1">Chiusura</span>
            </div>
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-slate-500">Caricamento calendario...</p>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {MONTH_NAMES.map((monthName, monthIndex) => (
                <div className="rounded-xl border border-border bg-slate-50 p-3" key={monthName}>
                  <p className="text-sm font-semibold text-ink">{monthName}</p>
                  <div className="mt-2 grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-slate-400">
                    {WEEK_DAYS.map((day, index) => (
                      <span key={`${day}-${index}`}>{day}</span>
                    ))}
                  </div>
                  <div className="mt-1 grid grid-cols-7 gap-1">
                    {monthDays(year, monthIndex).map((day, index) =>
                      day ? (
                        <span
                          className={`flex h-7 items-center justify-center rounded-lg border text-[11px] font-semibold ${dayClass(
                            daysByIso.get(day.iso)?.kind,
                            day.iso,
                          )}`}
                          key={day.iso}
                          title={daysByIso.get(day.iso)?.label || ""}
                        >
                          {day.day}
                        </span>
                      ) : (
                        <span key={`empty-${monthName}-${index}`} />
                      ),
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
