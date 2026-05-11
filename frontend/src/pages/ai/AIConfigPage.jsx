import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import StatusBadge from "../../components/common/StatusBadge";

const emptyProvider = {
  code: "",
  label: "",
  provider_type: "openai",
  base_url: "",
  enabled: true,
  notes: "",
};

const emptyModel = {
  provider_id: "",
  label: "",
  model_id: "",
  usage_scope: "document_vision",
  enabled: true,
  is_default: false,
  notes: "",
};

const USAGE_OPTIONS = [
  { value: "document_vision", label: "Visione documenti" },
  { value: "text", label: "Testo" },
  { value: "reasoning", label: "Ragionamento" },
];

function providerDraft(item) {
  return {
    label: item.label,
    provider_type: item.provider_type,
    base_url: item.base_url || "",
    enabled: item.enabled,
    notes: item.notes || "",
  };
}

function modelDraft(item) {
  return {
    provider_id: item.provider_id,
    label: item.label,
    model_id: item.model_id,
    usage_scope: item.usage_scope,
    enabled: item.enabled,
    is_default: item.is_default,
    notes: item.notes || "",
  };
}

export default function AIConfigPage() {
  const { token } = useAuth();
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [providerDrafts, setProviderDrafts] = useState({});
  const [modelDrafts, setModelDrafts] = useState({});
  const [newProvider, setNewProvider] = useState(emptyProvider);
  const [newModel, setNewModel] = useState(emptyModel);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const data = await apiRequest("/ai", {}, token);
    const nextProviders = data.providers || [];
    const nextModels = data.models || [];
    setProviders(nextProviders);
    setModels(nextModels);
    setProviderDrafts(Object.fromEntries(nextProviders.map((item) => [item.id, providerDraft(item)])));
    setModelDrafts(Object.fromEntries(nextModels.map((item) => [item.id, modelDraft(item)])));
    setNewModel((current) => ({
      ...current,
      provider_id: current.provider_id || nextProviders[0]?.id || "",
    }));
  }

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    apiRequest("/ai", {}, token)
      .then((data) => {
        if (ignore) {
          return;
        }
        const nextProviders = data.providers || [];
        const nextModels = data.models || [];
        setProviders(nextProviders);
        setModels(nextModels);
        setProviderDrafts(Object.fromEntries(nextProviders.map((item) => [item.id, providerDraft(item)])));
        setModelDrafts(Object.fromEntries(nextModels.map((item) => [item.id, modelDraft(item)])));
        setNewModel((current) => ({ ...current, provider_id: nextProviders[0]?.id || "" }));
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

  const defaultModel = useMemo(() => models.find((item) => item.is_default), [models]);

  function updateProviderDraft(id, patch) {
    setProviderDrafts((current) => ({
      ...current,
      [id]: {
        ...current[id],
        ...patch,
      },
    }));
  }

  function updateModelDraft(id, patch) {
    setModelDrafts((current) => ({
      ...current,
      [id]: {
        ...current[id],
        ...patch,
      },
    }));
  }

  async function saveProvider(event, item) {
    event.preventDefault();
    setMessage("");
    setSaving(`provider-${item.id}`);
    try {
      await apiRequest(
        `/ai/providers/${item.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(providerDrafts[item.id]),
        },
        token,
      );
      await refresh();
      setMessage(`${item.label} aggiornato`);
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  async function createProvider(event) {
    event.preventDefault();
    setMessage("");
    setSaving("provider-new");
    try {
      await apiRequest(
        "/ai/providers",
        {
          method: "POST",
          body: JSON.stringify(newProvider),
        },
        token,
      );
      setNewProvider(emptyProvider);
      await refresh();
      setMessage("Provider creato");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  async function saveModel(event, item) {
    event.preventDefault();
    setMessage("");
    setSaving(`model-${item.id}`);
    try {
      await apiRequest(
        `/ai/models/${item.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(modelDrafts[item.id]),
        },
        token,
      );
      await refresh();
      setMessage(`${item.label} aggiornato`);
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  async function createModel(event) {
    event.preventDefault();
    setMessage("");
    setSaving("model-new");
    try {
      await apiRequest(
        "/ai/models",
        {
          method: "POST",
          body: JSON.stringify({
            ...newModel,
            provider_id: Number(newModel.provider_id),
          }),
        },
        token,
      );
      setNewModel({ ...emptyModel, provider_id: providers[0]?.id || "" });
      await refresh();
      setMessage("Modello creato");
    } catch (requestError) {
      setMessage(requestError.message);
    } finally {
      setSaving("");
    }
  }

  function renderProvider(item) {
    const draft = providerDrafts[item.id] || providerDraft(item);
    return (
      <form className="rounded-xl border border-slate-200 bg-white p-4" key={item.id} onSubmit={(event) => saveProvider(event, item)}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{item.code}</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-950">{item.label}</h3>
          </div>
          <StatusBadge active={item.enabled} trueLabel="Attivo" falseLabel="Disattivo" />
        </div>
        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Nome
            <input value={draft.label} onChange={(event) => updateProviderDraft(item.id, { label: event.target.value })} />
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Tipo
            <input value={draft.provider_type} onChange={(event) => updateProviderDraft(item.id, { provider_type: event.target.value })} />
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Base URL
            <input placeholder="Vuoto se standard" value={draft.base_url} onChange={(event) => updateProviderDraft(item.id, { base_url: event.target.value })} />
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <input checked={draft.enabled} type="checkbox" onChange={(event) => updateProviderDraft(item.id, { enabled: event.target.checked })} />
            Attivo
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Note
            <textarea rows={2} value={draft.notes} onChange={(event) => updateProviderDraft(item.id, { notes: event.target.value })} />
          </label>
        </div>
        <button className="mt-4 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60" disabled={saving === `provider-${item.id}`} type="submit">
          {saving === `provider-${item.id}` ? "Salvataggio..." : "Salva provider"}
        </button>
      </form>
    );
  }

  function renderModel(item) {
    const draft = modelDrafts[item.id] || modelDraft(item);
    return (
      <form className="rounded-xl border border-slate-200 bg-white p-4" key={item.id} onSubmit={(event) => saveModel(event, item)}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{item.provider_label}</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-950">{item.label}</h3>
            <p className="mt-1 text-sm text-slate-500">{item.model_id}</p>
          </div>
          <StatusBadge active={item.enabled} trueLabel={item.is_default ? "Default" : "Attivo"} falseLabel="Disattivo" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Provider
            <select value={draft.provider_id} onChange={(event) => updateModelDraft(item.id, { provider_id: Number(event.target.value) })}>
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Uso
            <select value={draft.usage_scope} onChange={(event) => updateModelDraft(item.id, { usage_scope: event.target.value })}>
              {USAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Nome
            <input value={draft.label} onChange={(event) => updateModelDraft(item.id, { label: event.target.value })} />
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            Model ID
            <input value={draft.model_id} onChange={(event) => updateModelDraft(item.id, { model_id: event.target.value })} />
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <input checked={draft.enabled} type="checkbox" onChange={(event) => updateModelDraft(item.id, { enabled: event.target.checked })} />
            Attivo
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <input checked={draft.is_default} type="checkbox" onChange={(event) => updateModelDraft(item.id, { is_default: event.target.checked })} />
            Default
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700 md:col-span-2">
            Note
            <textarea rows={2} value={draft.notes} onChange={(event) => updateModelDraft(item.id, { notes: event.target.value })} />
          </label>
        </div>
        <button className="mt-4 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60" disabled={saving === `model-${item.id}`} type="submit">
          {saving === `model-${item.id}` ? "Salvataggio..." : "Salva modello"}
        </button>
      </form>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">AI</p>
          <h2 className="mt-2 text-2xl font-semibold">Collega AI</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Configura provider e modelli disponibili. Le API key restano personali nella scheda utente.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          Default: <span className="font-semibold text-ink">{defaultModel ? `${defaultModel.provider_label} · ${defaultModel.model_id}` : "Da impostare"}</span>
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento configurazione AI...</p> : null}
      {message ? <p className="mt-6 text-sm text-slate-600">{message}</p> : null}

      <div className="mt-8 grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-slate-950">Provider</h3>
          {providers.map(renderProvider)}
          <form className="rounded-xl border border-dashed border-slate-300 bg-white p-4" onSubmit={createProvider}>
            <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Nuovo provider</h4>
            <div className="mt-4 grid gap-3">
              <input placeholder="Codice, es. openai" value={newProvider.code} onChange={(event) => setNewProvider({ ...newProvider, code: event.target.value })} />
              <input placeholder="Nome, es. OpenAI" value={newProvider.label} onChange={(event) => setNewProvider({ ...newProvider, label: event.target.value })} />
              <input placeholder="Tipo provider" value={newProvider.provider_type} onChange={(event) => setNewProvider({ ...newProvider, provider_type: event.target.value })} />
              <input placeholder="Base URL opzionale" value={newProvider.base_url} onChange={(event) => setNewProvider({ ...newProvider, base_url: event.target.value })} />
            </div>
            <button className="mt-4 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={saving === "provider-new"} type="submit">
              {saving === "provider-new" ? "Creazione..." : "Aggiungi provider"}
            </button>
          </form>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-slate-950">Modelli</h3>
          {models.map(renderModel)}
          <form className="rounded-xl border border-dashed border-slate-300 bg-white p-4" onSubmit={createModel}>
            <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Nuovo modello</h4>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <select value={newModel.provider_id} onChange={(event) => setNewModel({ ...newModel, provider_id: event.target.value })}>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.label}
                  </option>
                ))}
              </select>
              <select value={newModel.usage_scope} onChange={(event) => setNewModel({ ...newModel, usage_scope: event.target.value })}>
                {USAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input placeholder="Nome visibile" value={newModel.label} onChange={(event) => setNewModel({ ...newModel, label: event.target.value })} />
              <input placeholder="Model ID reale" value={newModel.model_id} onChange={(event) => setNewModel({ ...newModel, model_id: event.target.value })} />
              <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <input checked={newModel.enabled} type="checkbox" onChange={(event) => setNewModel({ ...newModel, enabled: event.target.checked })} />
                Attivo
              </label>
              <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <input checked={newModel.is_default} type="checkbox" onChange={(event) => setNewModel({ ...newModel, is_default: event.target.checked })} />
                Default
              </label>
            </div>
            <button className="mt-4 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60" disabled={saving === "model-new" || !newModel.provider_id} type="submit">
              {saving === "model-new" ? "Creazione..." : "Aggiungi modello"}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
