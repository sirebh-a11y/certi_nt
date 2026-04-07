const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function apiRequest(path, options = {}, token = null) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
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
