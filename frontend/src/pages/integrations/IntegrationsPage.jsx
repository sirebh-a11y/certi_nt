import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

const FIELD_LABELS = {
  anagrafiche_view: "Vista anagrafiche",
  righe_ddt_view: "Vista righe DDT",
  certiol_view: "Vista OL/CodF3",
  traceability_view: "Vista tracciabilita",
};

const CONNECTION_ORDER = ["esolver", "quarta"];
const OBJECT_KEYS_BY_CODE = {
  esolver: ["anagrafiche_view", "righe_ddt_view", "certiol_view"],
  quarta: ["traceability_view"],
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
    driver_name: item.driver_name || "ODBC Driver 18 for SQL Server",
    encrypt: item.encrypt,
    trust_server_certificate: item.trust_server_certificate,
    connection_timeout: item.connection_timeout,
    query_timeout: item.query_timeout || 30,
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

function buildSqlViewDraft(item = {}) {
  return {
    enabled: item.enabled || false,
    external_host: item.external_host || "",
    external_port: item.external_port || "",
    database_name: item.database_name || "certi_nt",
    schema_name: item.schema_name || "esolver_export",
    view_name: item.view_name || "certi_certificati_pdf",
    reader_username: item.reader_username || "",
    allowed_source: item.allowed_source || "",
    ssl_mode: item.ssl_mode || "DA_FORNIRE_IT",
    notes: item.notes || "",
  };
}

export default function IntegrationsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [publication, setPublication] = useState(null);
  const [sqlViewDraft, setSqlViewDraft] = useState(buildSqlViewDraft());
  const [loading, setLoading] = useState(true);
  const [savingCode, setSavingCode] = useState("");
  const [testingCode, setTestingCode] = useState("");
  const [publicationAction, setPublicationAction] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const [data, publicationData] = await Promise.all([
      apiRequest("/integrations", {}, token),
      apiRequest("/integrations/export-publication", {}, token),
    ]);
    setItems(data.items || []);
    setDrafts(Object.fromEntries((data.items || []).map((item) => [item.code, buildDraft(item)])));
    setPublication(publicationData);
    setSqlViewDraft(buildSqlViewDraft(publicationData.sql_view));
  }

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    Promise.all([
      apiRequest("/integrations", {}, token),
      apiRequest("/integrations/export-publication", {}, token),
    ])
      .then(([data, publicationData]) => {
        if (ignore) {
          return;
        }
        setItems(data.items || []);
        setDrafts(Object.fromEntries((data.items || []).map((item) => [item.code, buildDraft(item)])));
        setPublication(publicationData);
        setSqlViewDraft(buildSqlViewDraft(publicationData.sql_view));
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
      configured:
        items.filter((item) => item.password_configured).length +
        (publication?.endpoint?.password_configured ? 1 : 0) +
        (publication?.sql_view?.reader_password_configured ? 1 : 0),
      total: 4,
    }),
    [items, publication],
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

  async function clearPassword(item) {
    setMessage("");
    setSavingCode(item.code);
    try {
      await apiRequest(
        `/integrations/${item.code}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...drafts[item.code],
            password: "",
            clear_password: true,
          }),
        },
        token,
      );
      await refresh();
      setMessage(`Password ${item.label} cancellata`);
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

  async function runPublicationAction(action, request) {
    setMessage("");
    setPublicationAction(action);
    try {
      const response = await request();
      await refresh();
      setMessage(response.message || "Configurazione vista eSolver aggiornata");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setPublicationAction("");
    }
  }

  async function saveSqlView(event) {
    event.preventDefault();
    await runPublicationAction("save", () =>
      apiRequest(
        "/integrations/export-publication/sql-view",
        {
          method: "PATCH",
          body: JSON.stringify({
            enabled: sqlViewDraft.enabled,
            external_port: sqlViewDraft.external_port ? Number(sqlViewDraft.external_port) : null,
            external_host: sqlViewDraft.external_host || null,
            reader_username: sqlViewDraft.reader_username || null,
            allowed_source: sqlViewDraft.allowed_source || null,
            ssl_mode: sqlViewDraft.ssl_mode,
            notes: sqlViewDraft.notes,
          }),
        },
        token,
      ),
    );
  }

  async function testSqlView() {
    await runPublicationAction("test-view", () =>
      apiRequest("/integrations/export-publication/sql-view/test", { method: "POST" }, token),
    );
  }

  async function testSqlViewPermissions() {
    await runPublicationAction("test-permissions", () =>
      apiRequest("/integrations/export-publication/sql-view/test-permissions", { method: "POST" }, token),
    );
  }

  async function setExternalValidation(validated) {
    await runPublicationAction("external-validation", () =>
      apiRequest(
        "/integrations/export-publication/sql-view/external-validation",
        {
          method: "POST",
          body: JSON.stringify({
            validated,
            message: validated ? "Verifica esterna confermata da IT" : "Verifica esterna da completare",
          }),
        },
        token,
      ),
    );
  }

  function renderConnection(item) {
    const draft = drafts[item.code] || buildDraft(item);
    const objectKeys = OBJECT_KEYS_BY_CODE[item.code] || Object.keys(draft.object_settings || {});
    return (
      <form className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" key={item.code} onSubmit={(event) => saveConnection(event, item)}>
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
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
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
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Viste e campi</h4>
          <div className="mt-4 grid gap-4">
            {objectKeys.map((key) => (
              <div key={key}>
                <label className="mb-2 block text-sm font-medium text-slate-700">{FIELD_LABELS[key] || key}</label>
                <input value={draft.object_settings?.[key] || ""} onChange={(event) => updateObjectSetting(item.code, key, event.target.value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 flex-1 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          <div className="font-semibold text-slate-900">Ultimo test</div>
          <div className="mt-2">{item.last_test_status || "Non eseguito"}</div>
          <div className="mt-1 text-xs">{item.last_test_message || "-"}</div>
          <div className="mt-2 text-xs">{item.last_test_at ? new Date(item.last_test_at).toLocaleString("it-IT") : "-"}</div>
        </div>

        <div className="mt-5 flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
          <button
            className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
            disabled={!item.password_configured || savingCode === item.code}
            onClick={() => clearPassword(item)}
            type="button"
          >
            Cancella password
          </button>
          <button
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={savingCode === item.code}
            type="submit"
          >
            {savingCode === item.code ? "Salvataggio..." : "Salva configurazione"}
          </button>
        </div>
      </form>
    );
  }

  function renderCertiExport() {
    const endpoint = publication?.endpoint;
    const fields = endpoint?.fields || [];
    return (
      <section className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="border-b border-slate-100 pb-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">certi export</p>
          <h3 className="mt-1 text-xl font-semibold text-slate-950">Certi verso eSolver</h3>
          <p className="mt-1 text-sm text-slate-500">PDF chiusi esposti in lettura per Nemesi/eSolver.</p>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Utente</div>
            <div className="mt-1 font-semibold text-slate-950">{endpoint?.username || "-"}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Password</div>
            <div className="mt-1 font-semibold text-slate-950">
              {endpoint?.password_configured ? "•••••••• (configurata)" : "Mancante"}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 md:col-span-2 xl:col-span-1 2xl:col-span-2">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Endpoint</div>
            <div className="mt-1 break-all font-mono text-sm text-slate-950">{endpoint?.public_url || endpoint?.path || "-"}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 md:col-span-2 xl:col-span-1 2xl:col-span-2">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Regola</div>
            <div className="mt-1 text-sm text-slate-700">Escono solo certificati con PDF chiuso. Se un PDF viene riaperto, non risulta piu valido nell'export.</div>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Campi esposti</h4>
          <div className="mt-3 flex flex-wrap gap-2">
            {fields.map((field) => (
              <span key={field} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                {field}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-5 flex-1 rounded-2xl border border-sky-100 bg-sky-50 p-4 text-sm text-sky-900">
          Modalita PDF attiva: URL. Alternativa non adottata ora: cartella condivisa UNC, se Nemesi la richiedera.
        </div>
      </section>
    );
  }

  function renderSqlView() {
    const view = publication?.sql_view;
    const busy = Boolean(publicationAction);
    return (
      <form className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={saveSqlView}>
        <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">vista PostgreSQL</p>
            <h3 className="mt-1 text-xl font-semibold text-slate-950">Vista per eSolver</h3>
            <p className="mt-1 text-sm text-slate-500">Pubblicazione di sola lettura predisposta per l’IT.</p>
          </div>
          <StatusBadge
            active={Boolean(view?.reader_password_configured)}
            trueLabel="Password configurata"
            falseLabel="Password da IT"
          />
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
            <input
              checked={sqlViewDraft.enabled}
              className="h-4 w-4 rounded border-slate-300 p-0 text-accent focus:ring-2 focus:ring-accent/20"
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, enabled: event.target.checked }))}
              type="checkbox"
            />
            Pubblicazione abilitata
          </label>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Host esterno</label>
            <input
              placeholder="DA FORNIRE IT"
              value={sqlViewDraft.external_host}
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, external_host: event.target.value }))}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Porta esterna</label>
            <input
              min="1"
              max="65535"
              placeholder="DA FORNIRE IT"
              type="number"
              value={sqlViewDraft.external_port}
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, external_port: event.target.value }))}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Database</label>
            <input
              disabled
              value={sqlViewDraft.database_name}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Schema</label>
            <input
              disabled
              value={sqlViewDraft.schema_name}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Vista</label>
            <input
              disabled
              value={sqlViewDraft.view_name}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Utente sola lettura</label>
            <input
              placeholder="DA FORNIRE IT"
              value={sqlViewDraft.reader_username}
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, reader_username: event.target.value }))}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Password</label>
            <input
              disabled
              value={view?.reader_password_configured ? "•••••••• (configurata sul server)" : "DA CONFIGURARE SUL SERVER"}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Origine autorizzata</label>
            <input
              placeholder="IP/CIDR DA FORNIRE IT"
              value={sqlViewDraft.allowed_source}
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, allowed_source: event.target.value }))}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Modalità SSL</label>
            <input
              value={sqlViewDraft.ssl_mode}
              onChange={(event) => setSqlViewDraft((current) => ({ ...current, ssl_mode: event.target.value }))}
            />
          </div>
        </div>

        <div className="mt-5">
          <label className="mb-2 block text-sm font-medium text-slate-700">Note e dati mancanti</label>
          <textarea
            className="min-h-24"
            value={sqlViewDraft.notes}
            onChange={(event) => setSqlViewDraft((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="font-semibold text-slate-900">Vista</div>
            <div className="mt-1 text-xs text-slate-600">{view?.last_view_test_status || "Non testata"}</div>
            <div className="mt-1 text-xs text-slate-500">{view?.last_view_test_message || "-"}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="font-semibold text-slate-900">Permessi</div>
            <div className="mt-1 text-xs text-slate-600">{view?.last_permissions_test_status || "Non testati"}</div>
            <div className="mt-1 text-xs text-slate-500">{view?.last_permissions_test_message || "-"}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="font-semibold text-slate-900">Verifica eSolver</div>
            <div className="mt-1 text-xs text-slate-600">{view?.external_validation_status || "pending"}</div>
            <div className="mt-1 text-xs text-slate-500">{view?.external_validation_message || "-"}</div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3 border-t border-slate-100 pt-4">
          <button className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold" disabled={busy} onClick={testSqlView} type="button">
            Test vista
          </button>
          <button className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold" disabled={busy} onClick={testSqlViewPermissions} type="button">
            Test permessi
          </button>
          <button
            className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold"
            disabled={busy}
            onClick={() => setExternalValidation(view?.external_validation_status !== "ok")}
            type="button"
          >
            {view?.external_validation_status === "ok" ? "Riapri verifica esterna" : "Conferma verifica esterna"}
          </button>
          <button className="ml-auto rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">
            {publicationAction === "save" ? "Salvataggio..." : "Salva configurazione"}
          </button>
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

      <div className="mt-8 grid items-stretch gap-6 xl:grid-cols-2">
        {[...items].sort((left, right) => CONNECTION_ORDER.indexOf(left.code) - CONNECTION_ORDER.indexOf(right.code)).map(renderConnection)}
        {renderCertiExport()}
        {renderSqlView()}
      </div>
    </section>
  );
}
