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
    const detail = data?.detail || "Request failed";
    throw new Error(detail);
  }
  return data;
}
