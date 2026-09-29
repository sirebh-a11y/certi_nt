import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { DDT_QUEUE_REFRESH_EVENT, ddtCertificationPath } from "../../app/ddtQueue";

const STATE_OPTIONS = [
  ["", "Tutti gli stati"],
  ["ready", "Pronti lato Incoming"],
  ["word_ready", "Word pronto"],
  ["waiting_incoming", "In attesa Incoming"],
  ["quality_rejected", "Qualità respinta"],
  ["to_link", "Da collegare"],
  ["review", "Da verificare"],
  ["completed", "Completati"],
];

const STATE_CLASSES = {
  ready: "border-emerald-200 bg-emerald-50 text-emerald-800",
  word_ready: "border-sky-200 bg-sky-50 text-sky-800",
  waiting_incoming: "border-amber-200 bg-amber-50 text-amber-800",
  quality_rejected: "border-rose-200 bg-rose-50 text-rose-800",
  to_link: "border-amber-200 bg-amber-50 text-amber-800",
  review: "border-amber-200 bg-amber-50 text-amber-800",
  completed: "border-slate-200 bg-slate-50 text-slate-700",
};

const INITIAL_FILTERS = {
  query: "", ddt: "", cod_odp: "", cod_f3: "", cliente: "",
  date_from: "", date_to: "", source_present: "", scope: "active", state: "",
  sort_direction: "desc", limit: "50",
};

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("it-IT");
}

function formatTimestamp(value) {
  if (!value) return "Mai";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("it-IT");
}

function formatQuantity(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("it-IT", { maximumFractionDigits: 3 })
    : String(value);
}

function incomingPath(item, returnTo) {
  if (!item.cod_odp || !item.incoming_row_ids?.length) return null;
  const query = new URLSearchParams({
    scope: "certificazione",
    ol: item.cod_odp,
    row_ids: item.incoming_row_ids.join(","),
    returnTo,
  });
  return `/acquisition?${query.toString()}`;
}

function filterParams(filters, offset) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== "") query.set(key, value);
  }
  query.set("offset", String(offset));
  return query;
}

function StatusCard({ label, value, tone = "slate" }) {
  const tones = {
    slate: "border-slate-200 bg-white",
    green: "border-emerald-200 bg-emerald-50",
    amber: "border-amber-200 bg-amber-50",
    rose: "border-rose-200 bg-rose-50",
  };
  return (
    <div className={`min-w-28 rounded-xl border px-4 py-3 ${tones[tone]}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value ?? "-"}</div>
    </div>
  );
}

export default function DdtWorkQueuePage() {
  const { token } = useAuth();
  const [draftFilters, setDraftFilters] = useState(INITIAL_FILTERS);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const updateDraft = useCallback((field, value) => {
    setDraftFilters((current) => {
      const next = { ...current, [field]: value };
      if (field === "state" && value === "completed") next.scope = "completed";
      if (field === "state" && value && value !== "completed" && current.scope === "completed") next.scope = "active";
      if (field === "scope" && value === "completed" && current.state !== "completed") next.state = "";
      if (field === "scope" && value === "active" && current.state === "completed") next.state = "";
      return next;
    });
  }, []);

  function applyFilters(event) {
    event.preventDefault();
    if (draftFilters.date_from && draftFilters.date_to && draftFilters.date_from > draftFilters.date_to) {
      setError("La data iniziale deve precedere la data finale.");
      return;
    }
    setOffset(0);
    setFilters({ ...draftFilters });
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    apiRequest(`/quarta-taglio/ddt-work-items?${filterParams(filters, offset)}`, {}, token)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        window.dispatchEvent(new Event(DDT_QUEUE_REFRESH_EVENT));
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || "Impossibile caricare i DDT.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [filters, offset, refresh, token]);

  const returnTo = "/quarta-taglio/ddt-da-certificare";
  const pageSize = Number(filters.limit);
  const totalPages = data ? Math.max(1, Math.ceil(data.total_items / pageSize)) : 1;
  const pageNumber = Math.floor(offset / pageSize) + 1;
  const lastAttempt = data?.sync?.last_attempt;
  const lastSuccess = data?.sync?.last_success;
  const syncFailed = lastAttempt?.status === "error";

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Flusso certificazione</p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">DDT da certificare</h1>
          <p className="mt-1 text-sm text-slate-600">Una riga per ogni quota DDT. Il lavoro si chiude quando il PDF finale della quota è disponibile.</p>
        </div>
        <button type="button" onClick={() => setRefresh((current) => current + 1)}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-50">
          Aggiorna vista
        </button>
      </div>

      <div className="flex flex-wrap gap-2" aria-label="Contatori DDT">
        <StatusCard label="Attivi" value={data?.active} />
        <StatusCard label="Pronti Incoming" value={(data?.by_state?.ready || 0) + (data?.by_state?.word_ready || 0)} tone="green" />
        <StatusCard label="In attesa Incoming" value={data?.by_state?.waiting_incoming} tone="amber" />
        <StatusCard label="Da collegare" value={data?.by_state?.to_link} tone="amber" />
        <StatusCard label="Da verificare" value={(data?.by_state?.review || 0) + (data?.by_state?.quality_rejected || 0)} tone="rose" />
        <StatusCard label="Completati" value={data?.by_state?.completed} />
      </div>
      <p className="text-xs text-slate-500">I contatori seguono la ricerca e la presenza eSolver; vista, stato e pagina non li restringono.</p>

      <div className={`rounded-xl border px-4 py-3 text-sm ${syncFailed ? "border-rose-200 bg-rose-50 text-rose-800" : "border-slate-200 bg-white text-slate-700"}`}>
        <span>Ultima lettura eSolver riuscita: <strong>{formatTimestamp(lastSuccess?.finished_at)}</strong>.</span>
        {!data?.sync?.enabled ? <span className="ml-2">Sincronizzazione automatica non attiva in questo ambiente.</span> : null}
        {syncFailed ? <span className="ml-2">Ultimo tentativo non riuscito ({formatTimestamp(lastAttempt.finished_at || lastAttempt.started_at)}); i DDT già conservati restano visibili.</span> : null}
      </div>

      <form className="rounded-xl border border-slate-200 bg-white p-4" onSubmit={applyFilters}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          {[
            ["query", "Ricerca generale"], ["ddt", "DDT"], ["cod_odp", "OL"],
            ["cod_f3", "Cod. F3"], ["cliente", "Cliente"],
          ].map(([field, label]) => (
            <label key={field} className="block text-xs font-semibold text-slate-600">
              {label}
              <input value={draftFilters[field]} onChange={(event) => updateDraft(field, event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal text-slate-900" />
            </label>
          ))}
          <label className="block text-xs font-semibold text-slate-600">Vista
            <select value={draftFilters.scope} onChange={(event) => updateDraft("scope", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal">
              <option value="active">Attivi</option><option value="completed">Completati</option><option value="all">Tutti</option>
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-600">Stato
            <select value={draftFilters.state} onChange={(event) => updateDraft("state", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal">
              {STATE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-600">Data DDT da
            <input type="date" value={draftFilters.date_from} onChange={(event) => updateDraft("date_from", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" />
          </label>
          <label className="block text-xs font-semibold text-slate-600">Data DDT a
            <input type="date" value={draftFilters.date_to} onChange={(event) => updateDraft("date_to", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" />
          </label>
          <label className="block text-xs font-semibold text-slate-600">Presenza eSolver
            <select value={draftFilters.source_present} onChange={(event) => updateDraft("source_present", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal">
              <option value="">Tutti</option><option value="true">Ancora presenti</option><option value="false">Solo storico</option>
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-600">Ordine
            <select value={draftFilters.sort_direction} onChange={(event) => updateDraft("sort_direction", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal">
              <option value="desc">Più recenti</option><option value="asc">Più vecchi</option>
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-600">Righe
            <select value={draftFilters.limit} onChange={(event) => updateDraft("limit", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal">
              <option value="25">25</option><option value="50">50</option><option value="100">100</option><option value="200">200</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Applica filtri</button>
          <button type="button" onClick={() => { setDraftFilters(INITIAL_FILTERS); setFilters(INITIAL_FILTERS); setOffset(0); }} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold">Azzera</button>
        </div>
      </form>

      {error ? <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p> : null}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-[1480px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
            <tr>{["Data DDT", "DDT", "OL", "Cod. F3", "Cliente", "Qta", "Ordine cliente", "Conferma F3", "Incoming", "Certificazione", "Stato", "Ultima lettura", "Azioni"].map((label) => <th key={label} scope="col" className="whitespace-nowrap border-b border-slate-200 px-3 py-3">{label}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(data?.items || []).map((item) => {
              const certificationPath = ddtCertificationPath(item);
              const linkedPath = incomingPath(item, returnTo);
              return (
                <tr key={item.id} className="align-top hover:bg-slate-50/70">
                  <td className="whitespace-nowrap px-3 py-3">{formatDate(item.ddt_date)}</td>
                  <td className="max-w-40 break-words px-3 py-3 font-medium" title={item.ddt_raw || ""}>{item.ddt_raw || "-"}</td>
                  <td className="max-w-40 break-all px-3 py-3">{item.cod_odp || <span className="text-amber-700">Da collegare</span>}</td>
                  <td className="max-w-32 break-all px-3 py-3">{item.cod_f3 || "-"}</td>
                  <td className="max-w-52 break-words px-3 py-3">{item.cliente || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-3">{formatQuantity(item.quantita)}</td>
                  <td className="max-w-36 break-all px-3 py-3">{item.ordine_cliente || "-"}</td>
                  <td className="max-w-36 break-all px-3 py-3">{item.conferma_ordine || "-"}</td>
                  <td className="px-3 py-3 text-xs">{item.state === "quality_rejected" ? "Qualità respinta" : item.incoming_ready ? "Pronto" : "Da verificare"}</td>
                  <td className="px-3 py-3 text-xs">{item.state === "completed" ? "PDF finale" : item.word_candidate_id ? "Word presente" : item.certificate_id ? "Scheda presente" : "Da fare"}</td>
                  <td className="min-w-52 px-3 py-3">
                    <span className={`inline-block rounded-md border px-2 py-1 text-xs font-semibold ${STATE_CLASSES[item.state] || STATE_CLASSES.review}`}>{item.label}</span>
                    {item.reasons?.length ? <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-slate-600">{item.reasons.map((reason, index) => <li key={`${item.id}-${index}`}>{reason}</li>)}</ul> : null}
                    {!item.source_present ? <span className="mt-1 block text-xs font-medium text-amber-800">Conservato nello storico</span> : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs">{formatTimestamp(item.last_seen_at)}</td>
                  <td className="min-w-36 px-3 py-3">
                    <div className="flex flex-col items-start gap-2 text-xs font-semibold">
                      {certificationPath && !item.source_review_reason && item.cod_f3 && item.ddt_raw && item.ddt_date ? (
                        <Link to={certificationPath} className="text-accent hover:underline">Apri certificazione</Link>
                      ) : null}
                      {linkedPath ? <Link to={linkedPath} className="text-sky-700 hover:underline">Apri Incoming</Link> : null}
                      {!certificationPath ? <span className="font-normal text-slate-500">OL non disponibile</span> : null}
                      {certificationPath && (item.source_review_reason || !item.cod_f3 || !item.ddt_raw || !item.ddt_date) ? <span className="font-normal text-amber-700">Quota DDT da verificare</span> : null}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!loading && !error && data?.items?.length === 0 ? <tr><td colSpan={13} className="px-4 py-8 text-center text-slate-600">Nessun DDT per i filtri selezionati.</td></tr> : null}
            {loading ? <tr><td colSpan={13} className="px-4 py-8 text-center text-slate-600">Caricamento DDT...</td></tr> : null}
          </tbody>
        </table>
      </div>
      {data ? <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
        <span>{data.total_items === 0 ? "0 righe" : `${offset + 1}-${Math.min(offset + pageSize, data.total_items)} di ${data.total_items} righe`} · pagina {pageNumber} di {totalPages}</span>
        <div className="flex gap-2">
          <button type="button" disabled={loading || offset === 0} onClick={() => setOffset((current) => Math.max(0, current - pageSize))} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">Precedente</button>
          <button type="button" disabled={loading || offset + pageSize >= data.total_items} onClick={() => setOffset((current) => current + pageSize)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">Successiva</button>
        </div>
      </div> : null}
    </section>
  );
}
