import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import { normalizeAlloyForDisplay } from "../../utils/alloyDisplay";
import { formatRowFieldDisplay } from "./fieldFormatting";

function todayDateInputValue() {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 10);
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function displaySupplierName(row) {
  return row.fornitore_nome || row.fornitore_raw || "-";
}

function composeLega(row) {
  return normalizeAlloyForDisplay(row.lega_designazione || row.lega_base || row.variante_lega || "-");
}

function matchLabel(row) {
  if (row.document_ddt_id && row.document_certificato_id) {
    return "Match";
  }
  if (row.document_certificato_id) {
    return "Solo certificato";
  }
  if (row.document_ddt_id) {
    return "Solo DDT";
  }
  return "-";
}

export default function AcquisitionGembaWalkPrintPage() {
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  const today = useMemo(() => todayDateInputValue(), []);
  const dateFrom = searchParams.get("date_from") || today;
  const dateTo = searchParams.get("date_to") || today;
  const view = searchParams.get("view") === "confirmed" ? "confirmed" : "open";
  const queryOne = searchParams.get("query_one") || "";
  const queryTwo = searchParams.get("query_two") || "";
  const queryThree = searchParams.get("query_three") || "";
  const operatorOne = searchParams.get("operator_one") === "or" ? "or" : "and";
  const operatorTwo = searchParams.get("operator_two") === "or" ? "or" : "and";
  const sortField = searchParams.get("sort_field") || "";
  const sortDirection = searchParams.get("sort_direction") === "desc" ? "desc" : "asc";
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
      view,
      query_one: queryOne,
      query_two: queryTwo,
      query_three: queryThree,
      operator_one: operatorOne,
      operator_two: operatorTwo,
    });
    if (sortField) {
      params.set("sort_field", sortField);
      params.set("sort_direction", sortDirection);
    }
    setLoading(true);
    setError("");
    apiRequest(`/acquisition/gemba-walk?${params.toString()}`, {}, token)
      .then((data) => {
        if (!ignore) {
          setRows(data.items || []);
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
  }, [dateFrom, dateTo, operatorOne, operatorTwo, queryOne, queryThree, queryTwo, sortDirection, sortField, token, view]);

  return (
    <section className="min-h-screen bg-white p-6 text-slate-950" id="gemba-print-root">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #gemba-print-root, #gemba-print-root * { visibility: visible; }
          #gemba-print-root { position: absolute; inset: 0; padding: 10mm; }
          .print-actions { display: none !important; }
          table { page-break-inside: auto; }
          tr { page-break-inside: avoid; page-break-after: auto; }
        }
      `}</style>
      <div className="print-actions mb-4 flex justify-end gap-2">
        <button
          className="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          type="button"
          onClick={() => window.close()}
        >
          Chiudi
        </button>
        <button
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-dark"
          type="button"
          onClick={() => window.print()}
        >
          Stampa
        </button>
      </div>

      <header className="mb-5 border-b-2 border-slate-900 pb-3">
        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Incoming materiale</p>
        <h1 className="mt-1 text-3xl font-bold">Gemba walk</h1>
        <p className="mt-2 text-sm font-medium">
          Periodo: {formatDate(dateFrom)} - {formatDate(dateTo)} · Vista: {view === "confirmed" ? "Valutate" : "Aperte"} · Righe: {rows.length}
        </p>
      </header>

      {loading ? <p className="text-sm text-slate-600">Caricamento righe...</p> : null}
      {error ? <p className="text-sm font-semibold text-rose-600">{error}</p> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="text-sm text-slate-600">Nessuna riga trovata nel periodo selezionato.</p>
      ) : null}

      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr className="bg-slate-100 text-left uppercase tracking-[0.12em] text-slate-700">
                <th className="border border-slate-300 px-2 py-2">N.</th>
                <th className="border border-slate-300 px-2 py-2">Fornitore</th>
                <th className="border border-slate-300 px-2 py-2">Lega</th>
                <th className="border border-slate-300 px-2 py-2">Ø</th>
                <th className="border border-slate-300 px-2 py-2">CDQ</th>
                <th className="border border-slate-300 px-2 py-2">Colata</th>
                <th className="border border-slate-300 px-2 py-2">DDT</th>
                <th className="border border-slate-300 px-2 py-2">Peso Kg</th>
                <th className="border border-slate-300 px-2 py-2">Vs. Odv</th>
                <th className="border border-slate-300 px-2 py-2">Match</th>
                <th className="border border-slate-300 px-2 py-2 text-center">Spunta</th>
                <th className="min-w-[220px] border border-slate-300 px-2 py-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="border border-slate-300 px-2 py-2 font-semibold">{row.id}</td>
                  <td className="border border-slate-300 px-2 py-2">{displaySupplierName(row)}</td>
                  <td className="border border-slate-300 px-2 py-2">{composeLega(row)}</td>
                  <td className="border border-slate-300 px-2 py-2">{formatRowFieldDisplay("diametro", row.diametro)}</td>
                  <td className="border border-slate-300 px-2 py-2">{row.cdq || "-"}</td>
                  <td className="border border-slate-300 px-2 py-2">{row.colata || "-"}</td>
                  <td className="border border-slate-300 px-2 py-2">{row.ddt || "-"}</td>
                  <td className="border border-slate-300 px-2 py-2">{formatRowFieldDisplay("peso", row.peso)}</td>
                  <td className="border border-slate-300 px-2 py-2">{row.ordine || "-"}</td>
                  <td className="border border-slate-300 px-2 py-2">{matchLabel(row)}</td>
                  <td className="border border-slate-300 px-2 py-2 text-center text-lg">□</td>
                  <td className="border border-slate-300 px-2 py-2">&nbsp;</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
