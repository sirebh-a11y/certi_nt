const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
const AUTH_EXPIRED_EVENT = "certi_nt:auth-expired";
const INTEGRATION_WAIT_EVENT = "certi_nt:integration-wait";
const pendingIntegrations = new Map();
const fileIdentities = new WeakMap();
let nextFileIdentity = 1;
let activeSessionToken;
let sessionInitialized = false;

export function setApiSessionToken(token) {
  activeSessionToken = token;
  sessionInitialized = true;
}

export function onIntegrationWait(callback) {
  const listener = (event) => callback(Boolean(event.detail?.active));
  window.addEventListener(INTEGRATION_WAIT_EVENT, listener);
  return () => window.removeEventListener(INTEGRATION_WAIT_EVENT, listener);
}

function ownerOf(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return String(payload.sub);
  } catch {
    return token;
  }
}

function currentToken(original) {
  if (!sessionInitialized) return original;
  if (!activeSessionToken || ownerOf(activeSessionToken) !== ownerOf(original)) {
    throw new DOMException("Attesa sospesa: la sessione è cambiata. Il lavoro sul server continua.", "AbortError");
  }
  return activeSessionToken;
}

function integrationPath(path) {
  if (typeof path !== "string") return false;
  const base = new URL(API_BASE_URL, globalThis.location?.origin || "http://localhost");
  // JSON calls use /quarta-taglio; downloadable asset URLs include /api or
  // are absolute. Never add the deferred protocol to an unrelated origin.
  const asset = new URL(path, base);
  if (asset.origin !== base.origin) return false;
  const prefix = base.pathname.replace(/\/$/, "");
  const relative = asset.pathname.startsWith(`${prefix}/`)
    ? asset.pathname.slice(prefix.length) : asset.pathname;
  return /^\/(?:quarta-taglio(?:[/?]|$)|clients\/esolver(?:[/?]|$)|suppliers\/esolver(?:[/?]|$))/.test(relative);
}

function bodyIdentity(body) {
  if (!(body instanceof FormData)) return body || "";
  return JSON.stringify([...body.entries()].map(([key, value]) => {
    if (typeof value === "string") return [key, value];
    if (!fileIdentities.has(value)) fileIdentities.set(value, nextFileIdentity++);
    return [key, value.name, value.size, value.lastModified, fileIdentities.get(value)];
  }));
}

function waitSignal() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(INTEGRATION_WAIT_EVENT, {
      detail: { active: [...pendingIntegrations.values()].some((item) => item.waiting) },
    }));
  }
}

function pollPath(path, file = false) {
  const pattern = file ? /^\/integration-jobs\/[a-f0-9]{32}\/file$/ : /^\/integration-jobs\/[a-f0-9]{32}$/;
  if (typeof path !== "string" || !pattern.test(path)) throw new Error("Risposta di aggiornamento non valida");
  return path;
}

function pause(signal) {
  return new Promise((resolve, reject) => {
    const cancelled = () => { clearTimeout(timer); reject(new DOMException("Attesa sospesa", "AbortError")); };
    const timer = setTimeout(() => { signal?.removeEventListener("abort", cancelled); resolve(); }, 500);
    if (signal?.aborted) cancelled();
    else signal?.addEventListener("abort", cancelled, { once: true });
  });
}

async function receiveJson(response, token) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = createApiError(response.status, data?.detail, response.statusText);
    error.integrationTerminal = true;
    notifyAuthExpiredIfNeeded(error, token);
    throw error;
  }
  return data;
}

async function awaitIntegration(ticket, state, options, token) {
  state.pollUrl = pollPath(ticket.poll_url);
  state.waiting = true;
  waitSignal();
  for (;;) {
    const pollToken = currentToken(token);
    if (options.signal?.aborted) throw new DOMException("Attesa sospesa", "AbortError");
    const response = await fetch(`${API_BASE_URL}${state.pollUrl}`, {
      headers: { Authorization: `Bearer ${pollToken}` }, cache: "no-store", signal: options.signal,
    });
    const data = await receiveJson(response, pollToken);
    if (data?.kind !== "integration_wait") throw new Error("Stato aggiornamento non valido");
    if (data.status === "succeeded") {
      if (data.file_url) return { file: pollPath(data.file_url, true) };
      state.terminal = true;
      return { data: data.result };
    }
    if (data.status === "failed" || data.status === "interrupted") {
      state.terminal = true;
      const error = createApiError(data.response_status || 500, data.detail, "Operazione non riuscita");
      notifyAuthExpiredIfNeeded(error, pollToken);
      throw error;
    }
    if (!["queued", "running"].includes(data.status)) throw new Error("Stato aggiornamento non valido");
    // Poll cadence is not an operation deadline: wait for as long as needed.
    await pause(options.signal);
  }
}

async function integrationRequest(path, options, token, asBlob) {
  const key = JSON.stringify([ownerOf(token), asBlob, path, options.method || "GET", bodyIdentity(options.body)]);
  let state = pendingIntegrations.get(key);
  if (state?.promise) return state.promise;
  if (!state) {
    state = { requestId: globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(16).slice(2)}` };
    pendingIntegrations.set(key, state);
  }
  state.promise = (async () => {
    try {
      let outcome;
      if (state.pollUrl) {
        outcome = await awaitIntegration({ poll_url: state.pollUrl }, state, options, token);
      } else {
        const headers = requestHeaders(options, currentToken(token));
        headers.set("Prefer", "respond-async");
        headers.set("X-CERTI-Request-ID", state.requestId);
        const response = await fetch(asBlob ? resolveApiAssetUrl(path) : `${API_BASE_URL}${path}`, {
          ...options, headers, cache: options.cache || "no-store",
        });
        if (response.status === 202) {
          const data = await receiveJson(response, token);
          if (data?.kind !== "integration_wait") throw new Error("Risposta di aggiornamento non valida");
          outcome = await awaitIntegration(data, state, options, token);
        } else {
          state.terminal = true;
          if (response.status === 204) return null;
          if (asBlob && response.ok) return response.blob();
          return await receiveJson(response, token);
        }
      }
      if (outcome.file) {
        const fileToken = currentToken(token);
        const response = await fetch(`${API_BASE_URL}${outcome.file}`, {
          headers: { Authorization: `Bearer ${fileToken}` }, cache: "no-store", signal: options.signal,
        });
        if (!response.ok) await receiveJson(response, fileToken);
        const blob = await response.blob();
        state.terminal = true;
        return blob;
      }
      return outcome.data;
    } catch (error) {
      if (error.integrationTerminal) state.terminal = true;
      throw error;
    } finally {
      state.waiting = false;
      state.promise = null;
      if (state.terminal) pendingIntegrations.delete(key);
      waitSignal();
    }
  })();
  return state.promise;
}

function requestHeaders(options, token) {
  const headers = new Headers(options.headers || {});
  if (options.body instanceof FormData) headers.delete("Content-Type");
  else if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function apiRequest(path, options = {}, token = null) {
  if (token && integrationPath(path)) return integrationRequest(path, options, token, false);
  const headers = new Headers(options.headers || {});
  if (options.body instanceof FormData) {
    headers.delete("Content-Type");
  } else if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: options.cache || "no-store",
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = createApiError(response.status, data?.detail, response.statusText);
    notifyAuthExpiredIfNeeded(error, token);
    throw error;
  }
  return data;
}

export function resolveApiAssetUrl(path) {
  if (!path) {
    return null;
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return new URL(path, API_BASE_URL).toString();
}

export async function fetchApiBlob(path, token) {
  if (token && integrationPath(path)) return integrationRequest(path, {}, token, true);
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(resolveApiAssetUrl(path), { headers, cache: "no-store" });
  if (!response.ok) {
    let error;
    try {
      const data = await response.json();
      error = createApiError(response.status, data?.detail, response.statusText);
    } catch {
      error = createApiError(response.status, response.statusText, response.statusText);
    }
    notifyAuthExpiredIfNeeded(error, token);
    throw error;
  }

  return response.blob();
}

function createApiError(status, detail, fallback = "Request failed") {
  const message = formatErrorDetail(detail) || fallback || "Request failed";
  const error = new Error(message);
  error.status = status;
  error.detail = message;
  error.payload = detail;
  return error;
}

function notifyAuthExpiredIfNeeded(error, token) {
  if (sessionInitialized && activeSessionToken !== token) return;
  if (!token || !isAuthExpiredError(error)) {
    return;
  }
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

function isAuthExpiredError(error) {
  const message = error?.message || "";
  return error?.status === 401 || /invalid token|invalid token type|user not available/i.test(message);
}

export function onAuthExpired(callback) {
  window.addEventListener(AUTH_EXPIRED_EVENT, callback);
  return () => window.removeEventListener(AUTH_EXPIRED_EVENT, callback);
}

function formatErrorDetail(detail) {
  if (!detail) {
    return "Request failed";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => cleanValidationMessage(item?.msg || item?.message || JSON.stringify(item)))
      .join(" | ");
  }

  if (typeof detail === "object") {
    return detail.message || JSON.stringify(detail);
  }

  return "Request failed";
}

function cleanValidationMessage(message) {
  if (typeof message !== "string") {
    return message;
  }

  return message.replace(/^Value error,\s*/i, "");
}
