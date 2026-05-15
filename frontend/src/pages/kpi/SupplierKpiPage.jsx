import { useEffect, useMemo, useState } from "react";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { useAuth } from "../../app/auth";

const MONTHS = [
  { value: "", label: "Tutto anno" },
  { value: "1", label: "Gennaio" },
  { value: "2", label: "Febbraio" },
  { value: "3", label: "Marzo" },
  { value: "4", label: "Aprile" },
  { value: "5", label: "Maggio" },
  { value: "6", label: "Giugno" },
  { value: "7", label: "Luglio" },
  { value: "8", label: "Agosto" },
  { value: "9", label: "Settembre" },
  { value: "10", label: "Ottobre" },
  { value: "11", label: "Novembre" },
  { value: "12", label: "Dicembre" },
];

const QUARTERS = [
  { value: "1", label: "Q1", hint: "Gen-Mar" },
  { value: "2", label: "Q2", hint: "Apr-Giu" },
  { value: "3", label: "Q3", hint: "Lug-Set" },
  { value: "4", label: "Q4", hint: "Ott-Dic" },
];

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatInteger(value) {
  return Number(value || 0).toLocaleString("it-IT", { maximumFractionDigits: 0 });
}

function maxMetric(items, selector) {
  return Math.max(1, ...items.map((item) => Number(selector(item)) || 0));
}

function buildKpiParams({ year, month, quarter, supplierId }) {
  const params = new URLSearchParams({ year });
  if (month) {
    params.set("month", month);
  } else if (quarter) {
    params.set("quarter", quarter);
  }
  if (supplierId) {
    params.set("supplier_id", supplierId);
  }
  return params;
}

function MetricCard({ label, value, hint, tone = "slate" }) {
  const toneClasses = {
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    rose: "border-rose-200 bg-rose-50 text-rose-900",
    sky: "border-sky-200 bg-sky-50 text-sky-900",
    slate: "border-slate-200 bg-white text-slate-950",
  };
  return (
    <div className={`rounded-2xl border px-4 py-2 shadow-sm ${toneClasses[tone] || toneClasses.slate}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
      <p className="mt-1 text-xl font-semibold leading-tight">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] opacity-70">{hint}</p> : null}
    </div>
  );
}

function Bar({ value, max, className }) {
  const width = Math.max(0, Math.min(100, ((Number(value) || 0) / max) * 100));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${className}`} style={{ width: `${width}%` }} />
    </div>
  );
}

export default function SupplierKpiPage() {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [year, setYear] = useState("2026");
  const [month, setMonth] = useState("");
  const [quarter, setQuarter] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    apiRequest("/suppliers", {}, token)
      .then((data) => {
        if (!ignore) {
          setSuppliers(data.items || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setSuppliers([]);
        }
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    const params = buildKpiParams({ year, month, quarter, supplierId });
    apiRequest(`/supplier-kpi/summary?${params.toString()}`, {}, token)
      .then((data) => {
        if (!ignore) {
          setSummary(data);
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
  }, [month, quarter, supplierId, token, year]);

  const totals = summary?.totals;
  const supplierRows = summary?.by_supplier || [];
  const monthRows = summary?.by_month || [];
  const maxTons = useMemo(() => maxMetric(supplierRows, (item) => item.metrics.tonnellate), [supplierRows]);
  const maxLots = useMemo(() => maxMetric(monthRows, (item) => item.metrics.lotti_totali), [monthRows]);
  const maxDelay = useMemo(
    () => maxMetric(supplierRows, (item) => Math.abs(item.metrics.ritardo_medio_giorni || 0)),
    [supplierRows],
  );
  const maxControlTime = useMemo(
    () => maxMetric(supplierRows, (item) => Math.abs(item.metrics.tempo_medio_controllo_giorni || 0)),
    [supplierRows],
  );
  const selectedMonth = MONTHS.find((item) => item.value === month);
  const selectedQuarter = QUARTERS.find((item) => item.value === quarter);
  const quarterSelectValue = selectedQuarter ? `quarter:${selectedQuarter.value}` : "";
  const monthSelectValue = selectedQuarter && !month ? quarterSelectValue : month;
  const activePeriodLabel = month
    ? `${selectedMonth?.label || "Mese"} ${year}`
    : quarter
      ? `${selectedQuarter?.label || "Trimestre"} ${year}`
      : `Tutto anno ${year}`;

  const handleMonthChange = (value) => {
    if (value.startsWith("quarter:")) {
      setQuarter(value.replace("quarter:", ""));
      setMonth("");
      return;
    }
    setMonth(value);
    setQuarter("");
  };

  const handleQuarterClick = (value) => {
    setQuarter((current) => (current === value ? "" : value));
    setMonth("");
  };

  const handleExport = async () => {
    setExporting(true);
    setError("");
    try {
      const params = buildKpiParams({ year, month, quarter, supplierId });
      const blob = await fetchApiBlob(`/api/supplier-kpi/export?${params.toString()}`, token);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `kpi_fornitori_${year}_${month ? `mese_${month}` : quarter ? `q${quarter}` : "anno"}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Valutazione fornitori</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">KPI fornitori</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Indicatori ricavati dalle righe valutate: lotti, tonnellate, esiti qualità, ritardi e tempi di controllo.
          </p>
        </div>
        <div className="grid gap-3 lg:grid-cols-[120px_auto_minmax(190px,1fr)_minmax(260px,1.5fr)]">
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Anno
            <input
              className="mt-1 w-full rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-ink"
              max="2100"
              min="2000"
              onChange={(event) => setYear(event.target.value)}
              type="number"
              value={year}
            />
          </label>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Trimestre
            <div className="mt-1 flex flex-wrap gap-1.5">
              {QUARTERS.map((item) => {
                const active = quarter === item.value && !month;
                return (
                  <button
                    className={`rounded-lg border px-2.5 py-2 text-xs font-bold tracking-normal transition ${
                      active
                        ? "border-teal-500 bg-teal-50 text-teal-800 shadow-sm"
                        : "border-border bg-white text-slate-600 hover:border-teal-300 hover:text-teal-700"
                    }`}
                    key={item.value}
                    onClick={() => handleQuarterClick(item.value)}
                    title={item.hint}
                    type="button"
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Mese
            <select
              className="mt-1 w-full rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-ink"
              onChange={(event) => handleMonthChange(event.target.value)}
              value={monthSelectValue}
            >
              {selectedQuarter && !month ? (
                <option value={quarterSelectValue}>
                  {selectedQuarter.label} {selectedQuarter.hint}
                </option>
              ) : null}
              {MONTHS.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[260px] text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Fornitore
            <select
              className="mt-1 w-full rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-ink"
              onChange={(event) => setSupplierId(event.target.value)}
              value={supplierId}
            >
              <option value="">Tutti i fornitori</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.ragione_sociale}
                </option>
              ))}
            </select>
          </label>
          <p className="rounded-xl border border-sky-100 bg-sky-50 px-3 py-2 text-sm font-semibold text-sky-800 lg:col-span-4">
            Periodo attivo: {activePeriodLabel}
          </p>
        </div>
      </div>

      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento KPI...</p> : null}

      {totals ? (
        <>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-[repeat(7,minmax(120px,1fr))_220px]">
            <MetricCard label="Tonnellate" value={formatNumber(totals.tonnellate, 3)} tone="sky" />
            <MetricCard label="Lotti" value={formatInteger(totals.lotti_totali)} />
            <MetricCard label="Accettati" value={formatInteger(totals.lotti_accettati)} tone="emerald" />
            <MetricCard label="Con riserva" value={formatInteger(totals.lotti_deroga)} tone="amber" />
            <MetricCard label="Respinti" value={formatInteger(totals.lotti_scarti)} tone="rose" />
            <MetricCard label="Ritardo medio" value={formatNumber(totals.ritardo_medio_giorni, 2)} hint="giorni" />
            <MetricCard label="Tempo controllo" value={formatNumber(totals.tempo_medio_controllo_giorni, 2)} hint="giorni lav." />
            <button
              className="rounded-2xl border border-teal-200 bg-white px-4 py-2 text-left text-sm font-semibold leading-tight text-teal-800 shadow-sm transition hover:border-teal-400 hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={exporting || loading}
              onClick={handleExport}
              type="button"
            >
              <span className="block text-[10px] uppercase tracking-[0.16em] text-teal-600">Export</span>
              {exporting ? "Preparazione..." : "Scarica dati periodo"}
            </button>
          </div>

          <div className="mt-8 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-2xl border border-border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-slate-950">Andamento mensile valutazioni</h3>
                  <p className="text-sm text-slate-500">Accettati, riserve e respinti: {activePeriodLabel.toLowerCase()}.</p>
                </div>
              </div>
              <div className="mt-5 space-y-3">
                {monthRows.map((item) => (
                  <div className="grid grid-cols-[42px_1fr_72px] items-center gap-3" key={item.month}>
                    <span className="text-xs font-semibold text-slate-500">{item.label}</span>
                    <div className="flex h-4 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="bg-emerald-400"
                        style={{ width: `${((item.metrics.lotti_accettati || 0) / maxLots) * 100}%` }}
                      />
                      <div
                        className="bg-amber-400"
                        style={{ width: `${((item.metrics.lotti_deroga || 0) / maxLots) * 100}%` }}
                      />
                      <div
                        className="bg-rose-400"
                        style={{ width: `${((item.metrics.lotti_scarti || 0) / maxLots) * 100}%` }}
                      />
                    </div>
                    <span className="text-right text-xs font-semibold text-slate-600">
                      {formatInteger(item.metrics.lotti_totali)} lotti
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-400" /> Accettati</span>
                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" /> Con riserva</span>
                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-400" /> Respinti</span>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-950">Tonnellate per fornitore</h3>
              <p className="text-sm text-slate-500">Vista immediata del peso operativo.</p>
              <div className="mt-5 space-y-4">
                {supplierRows.slice(0, 10).map((item) => (
                  <div key={`${item.supplier_id || "raw"}-${item.fornitore}`}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                      <span className="truncate font-semibold text-slate-700">{item.fornitore}</span>
                      <span className="font-semibold text-slate-500">{formatNumber(item.metrics.tonnellate, 3)} t</span>
                    </div>
                    <Bar className="bg-sky-400" max={maxTons} value={item.metrics.tonnellate} />
                  </div>
                ))}
                {!supplierRows.length ? <p className="text-sm text-slate-500">Nessun dato nel periodo selezionato.</p> : null}
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-border bg-white p-5 shadow-sm">
            <h3 className="font-semibold text-slate-950">Ritardo medio per fornitore</h3>
            <p className="text-sm text-slate-500">Differenza media tra data ricezione e data richiesta consegna.</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {supplierRows.slice(0, 12).map((item) => (
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3" key={`${item.fornitore}-delay`}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                    <span className="truncate font-semibold text-slate-700">{item.fornitore}</span>
                    <span className="font-semibold text-slate-500">{formatNumber(item.metrics.ritardo_medio_giorni, 2)} gg</span>
                  </div>
                  <Bar className="bg-slate-400" max={maxDelay} value={Math.abs(item.metrics.ritardo_medio_giorni || 0)} />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-border bg-white p-5 shadow-sm">
            <h3 className="font-semibold text-slate-950">Tempo medio controllo per fornitore</h3>
            <p className="text-sm text-slate-500">Giorni lavorativi medi tra ricezione e accettazione qualità.</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {supplierRows.slice(0, 12).map((item) => (
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3" key={`${item.fornitore}-control-time`}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                    <span className="truncate font-semibold text-slate-700">{item.fornitore}</span>
                    <span className="font-semibold text-slate-500">{formatNumber(item.metrics.tempo_medio_controllo_giorni, 2)} gg</span>
                  </div>
                  <Bar className="bg-teal-400" max={maxControlTime} value={Math.abs(item.metrics.tempo_medio_controllo_giorni || 0)} />
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
