import { useEffect, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function LogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/logs", {}, token)
      .then((data) => setLogs(data.items))
      .catch((requestError) => setError(requestError.message));
  }, [token]);

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Log</p>
      <h2 className="mt-2 text-2xl font-semibold">Runtime Logs</h2>
      {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      <div className="mt-6 space-y-3">
        {logs.map((entry, index) => (
          <article className="rounded-2xl border border-border bg-slate-50 p-4" key={`${entry.timestamp}-${index}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-semibold">{entry.event_type}</p>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                {new Date(entry.timestamp).toLocaleString()}
              </p>
            </div>
            <p className="mt-2 text-sm text-slate-700">{entry.message}</p>
            {entry.actor_email ? <p className="mt-1 text-xs text-slate-500">{entry.actor_email}</p> : null}
          </article>
        ))}
        {!logs.length && !error ? <p className="text-sm text-slate-500">Nessun log disponibile.</p> : null}
      </div>
    </section>
  );
}
