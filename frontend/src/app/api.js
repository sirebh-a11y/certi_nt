const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function apiRequest(path, options = {}, token = null) {
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
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = formatErrorDetail(data?.detail);
    throw new Error(detail);
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
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(resolveApiAssetUrl(path), { headers });
  if (!response.ok) {
    let detail = "Request failed";
    try {
      const data = await response.json();
      detail = formatErrorDetail(data?.detail);
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.blob();
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
