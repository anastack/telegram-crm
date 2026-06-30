/** Запросы к API — только через Telegram Mini App */

const API_BASE = window.location.origin;
const tg = window.Telegram?.WebApp;

// Для тестирования в браузере - используем mock initData
const MOCK_INIT_DATA = "query_id=test&user=%7B%22id%22%3A123%7D&auth_date=1234567890&hash=test";

function getInitData() {
  if (tg?.initData) {
    return tg.initData;
  }
  // Fallback для тестирования в браузере
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    console.warn("[API] Using mock initData for local testing");
    return MOCK_INIT_DATA;
  }
  return "";
}

function getHeaders() {
  const initData = getInitData();
  if (!initData) {
    throw new Error("Мини-приложение должно быть открыто через Telegram");
  }
  return { "X-Telegram-Init-Data": initData };
}

async function apiRequest(path, options = {}) {
  try {
    const headers = { ...getHeaders(), ...options.headers };

    if (options.body) {
      headers["Content-Type"] = "application/json";
    }

    console.log(`[API] ${options.method || "GET"} ${path}`);
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = `Ошибка ${response.status}`;
      try {
        const err = await response.json();
        detail = err.detail || detail;
      } catch (e) {
        // Не JSON ответ
      }
      console.error(`[API] Error ${response.status}:`, detail);
      throw new Error(detail);
    }

    if (response.status === 204) return null;
    const data = await response.json();
    console.log(`[API] Success:`, data);
    return data;
  } catch (e) {
    console.error(`[API] Request failed:`, e);
    throw e;
  }
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

