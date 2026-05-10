import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

const FIELD_LABELS = {
  anagrafiche_view: "Vista anagrafiche",
  righe_ddt_view: "Vista righe DDT",
  traceability_view: "Vista tracciabilita",
  company_field: "Campo azienda",
  odp_field: "Campo ODP",
  ddt_field: "Campo DDT",
  supplier_field: "Campo fornitore/cliente",
  lot_field: "Campo lotto",
  raw_lot_field: "Campo lotto MP",
  raw_material_field: "Campo materia prima",
  supplier_certificate_field: "Campo certificato fornitore",
  heat_field: "Campo colata",
  article_field: "Campo articolo",
  description_field: "Campo descrizione",
  quantity_field: "Campo quantita",
  certificate_present_field: "Campo certificato presente",
};

function buildDraft(item) {
  return {
    enabled: item.enabled,
    server_host: item.server_host,
    port: item.port,
    database_name: item.database_name,
    username: item.username,
    password: "",
    clear_password: false,
    driver_name: item.driver_name,
    encrypt: item.encrypt,
    trust_server_certificate: item.trust_server_certificate,
    connection_timeout: item.connection_timeout,
    query_timeout: item.query_timeout,
    schema_name: item.schema_name,
    object_settings: item.object_settings || {},
    notes: item.notes || "",
  };
}

function connectionStatus(item) {
  if (item.last_test_status === "ok") {
    return "Test ok";
  }
  if (item.last_test_status === "error") {
    return "Errore test";
  }
  return item.password_configured ? "Configurata" : "Password mancante";
}

export default function IntegrationsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingCode, setSavingCode] = useState("");
  const [testingCode, setTestingCode] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const data = await apiRequest("/integrations", {}, token);
    setItems(data.items || []);
    setDrafts(Object.fromEntries((data.items || []).map((item) => [item.code, buildDraft(item)])));
  }

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    apiRequest("/integrations", {}, token)
      .then((data) => {
        if (ignore) {
          return;
        }
        setItems(data.items || []);
        setDrafts(Object.fromEntries((data.items || []).map((item) => [item.code, buildDraft(item)])));
      })
      .catch((requestError) => {
        if (!ignore) {
          setMessage(requestError.message);
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
  }, [token]);

  const summary = useMemo(
    () => ({
      configured: items.filter((item) => item.password_configured).length,
      total: items.length,
    }),
    [items],
  );

  function updateDraft(code, patch) {
    setDrafts((current) => ({
      ...current,
      [code]: {
        ...current[code],
        ...patch,
      },
    }));
  }

  function updateObjectSetting(code, key, value) {
    const draft = drafts[code];
    updateDraft(code, {
      object_settings: {
        ...(draft?.object_settings || {}),
        [key]: value,
      },
    });
  }

  async function saveConnection(event, item) {
    event.preventDefault();
    setMessage("");
    setSavingCode(item.code);
    try {
      await apiRequest(
        `/integrations/${item.code}`,
        {
          method: "PATCH",
          body: JSON.stringify(drafts[item.code]),
        },
        token,
      );
      await refresh();
      setMessage(`${item.label} aggiornata`);
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSavingCode("");
    }
  }

  async function testConnection(item) {
    setMessage("");
    setTestingCode(item.code);
    try {
      const response = await apiRequest(
        `/integrations/${item.code}/test-network`,
        {
          method: "POST",
        },
        token,
      );
      await refresh();
      setMessage(response.message);
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setTestingCode("");
    }
  }

  function renderConnection(item) {
    const draft = drafts[item.code] || buildDraft(item);
    return (
      <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" key={item.code} onSubmit={(event) => saveConnection(event, item)}>
        <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{item.code}</p>
            <h3 className="mt-1 text-xl font-semibold text-slate-950">{item.label}</h3>
            <p className="mt-1 text-sm text-slate-500">{connectionStatus(item)}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge active={item.password_configured} trueLabel="Password configurata" falseLabel="Password mancante" />
            <button
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              disabled={testingCode === item.code}
              onClick={() => testConnection(item)}
              type="button"
            >
              {testingCode === item.code ? "Test..." : "Test rete"}
            </button>
            <button
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              disabled={savingCode === item.code}
              type="submit"
            >
              {savingCode === item.code ? "Salvataggio..." : "Salva"}
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
            <input
              checked={draft.enabled}
              className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
              onChange={(event) => updateDraft(item.code, { enabled: event.target.checked })}
              type="checkbox"
            />
            Abilitata
          </label>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Server</label>
            <input value={draft.server_host} onChange={(event) => updateDraft(item.code, { server_host: event.target.value })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Porta</label>
            <input type="number" value={draft.port} onChange={(event) => updateDraft(item.code, { port: Number(event.target.value) })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Database</label>
            <input value={draft.database_name} onChange={(event) => updateDraft(item.code, { database_name: event.target.value })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Utente</label>
            <input value={draft.username} onChange={(event) => updateDraft(item.code, { username: event.target.value })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Nuova password</label>
            <input
              autoComplete="new-password"
              placeholder={item.password_configured ? "Lascia vuoto per mantenere" : "Inserisci password"}
              type="password"
              value={draft.password}
              onChange={(event) => updateDraft(item.code, { password: event.target.value, clear_password: false })}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Driver</label>
            <input value={draft.driver_name} onChange={(event) => updateDraft(item.code, { driver_name: event.target.value })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Schema</label>
            <input value={draft.schema_name} onChange={(event) => updateDraft(item.code, { schema_name: event.target.value })} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Timeout connessione</label>
            <input
              type="number"
              value={draft.connection_timeout}
              onChange={(event) => updateDraft(item.code, { connection_timeout: Number(event.target.value) })}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Timeout query</label>
            <input type="number" value={draft.query_timeout} onChange={(event) => updateDraft(item.code, { query_timeout: Number(event.target.value) })} />
          </div>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
            <input
              checked={draft.encrypt}
              className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
              onChange={(event) => updateDraft(item.code, { encrypt: event.target.checked })}
              type="checkbox"
            />
            Encrypt
          </label>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
            <input
              checked={draft.trust_server_certificate}
              className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
              onChange={(event) => updateDraft(item.code, { trust_server_certificate: event.target.checked })}
              type="checkbox"
            />
            Trust certificate
          </label>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
            <input
              checked={draft.clear_password}
              className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
              onChange={(event) => updateDraft(item.code, { clear_password: event.target.checked, password: "" })}
              type="checkbox"
            />
            Rimuovi password
          </label>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Viste e campi</h4>
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(draft.object_settings || {}).map(([key, value]) => (
              <div key={key}>
                <label className="mb-2 block text-sm font-medium text-slate-700">{FIELD_LABELS[key] || key}</label>
                <input value={value || ""} onChange={(event) => updateObjectSetting(item.code, key, event.target.value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr),minmax(280px,0.45fr)]">
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Note interne</label>
            <textarea
              className="min-h-24 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-ink"
              value={draft.notes}
              onChange={(event) => updateDraft(item.code, { notes: event.target.value })}
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div className="font-semibold text-slate-900">Ultimo test</div>
            <div className="mt-2">{item.last_test_status || "Non eseguito"}</div>
            <div className="mt-1 text-xs">{item.last_test_message || "-"}</div>
            <div className="mt-2 text-xs">{item.last_test_at ? new Date(item.last_test_at).toLocaleString("it-IT") : "-"}</div>
          </div>
        </div>
      </form>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Integrazioni</p>
          <h2 className="mt-2 text-2xl font-semibold">Collegamenti eSolver e QuartaEVO</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Parametri di lettura per ERP e tracciabilita. I valori sensibili restano cifrati e non vengono restituiti in chiaro.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-ink">{summary.configured}</span> / {summary.total} password configurate
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento integrazioni...</p> : null}
      {message ? <p className="mt-6 text-sm text-slate-600">{message}</p> : null}

      <div className="mt-8 grid gap-6">{items.map(renderConnection)}</div>
    </section>
  );
}
