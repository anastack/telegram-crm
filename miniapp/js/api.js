/** Запросы к API — только через Telegram Mini App */

const API_BASE = window.location.origin;
const tg = window.Telegram?.WebApp;

function getInitData() {
  return tg?.initData || "";
}

function getHeaders() {
  const initData = getInitData();
  if (!initData) {
    throw new Error("NO_TELEGRAM");
  }
  return { "X-Telegram-Init-Data": initData };
}

async function apiRequest(path, options = {}) {
  const headers = { ...getHeaders(), ...options.headers };

  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const detail = err.detail || `Ошибка ${response.status}`;
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

const api = {
  me: () => apiRequest("/api/me"),
  dashboard: () => apiRequest("/api/dashboard"),
  appointments: (params = "") => apiRequest(`/api/appointments${params}`),
  appointment: (id) => apiRequest(`/api/appointments/${id}`),
  updateAppointment: (id, data) =>
    apiRequest(`/api/appointments/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  updateStatus: (id, status) =>
    apiRequest(`/api/appointments/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  cancelAppointment: (id) =>
    apiRequest(`/api/appointments/${id}`, { method: "DELETE" }),
  clients: (q = "") => apiRequest(`/api/clients?q=${encodeURIComponent(q)}`),
  client: (id) => apiRequest(`/api/clients/${id}`),
  statistics: () => apiRequest("/api/statistics"),
  calendar: (year, month) =>
    apiRequest(`/api/calendar?year=${year}&month=${month}`),
  services: () => apiRequest("/api/services"),
  performers: (serviceId) =>
    apiRequest(
      serviceId ? `/api/performers?service_id=${serviceId}` : "/api/performers"
    ),
};
