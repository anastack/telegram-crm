/** Главная логика Mini App */

const tg = window.Telegram?.WebApp;
const MONTHS_RU = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

let calYear, calMonth, calData = [], selectedDay = null;
let servicesCache = [], performersCache = [];

// --- Инициализация ---

document.addEventListener("DOMContentLoaded", async () => {
  // Только через Telegram Mini App
  if (!tg?.initData) {
    document.getElementById("telegram-gate").classList.remove("hidden");
    return;
  }

  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#1a1d27");
    tg.setBackgroundColor("#0f1117");

    document.getElementById("app-root").classList.remove("hidden");

    const me = await api.me();
    document.getElementById("admin-name").textContent = me.first_name || "Админ";

    const now = new Date();
    calYear = now.getFullYear();
    calMonth = now.getMonth() + 1;

    setupNavigation();
    setupCalendarControls();
    setupEditModal();
    setupFilters();

    loadPage("dashboard");
  } catch (e) {
    document.getElementById("app-root").classList.remove("hidden");
    showError(e.message);
  }
});

// --- Навигация ---

const PAGE_TITLES = {
  dashboard: "Dashboard",
  calendar: "Календарь",
  clients: "Клиенты",
  appointments: "Записи",
  statistics: "Статистика",
};

function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadPage(btn.dataset.page);
    });
  });
}

function loadPage(page) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById(`page-${page}`).classList.add("active");
  document.getElementById("page-title").textContent = PAGE_TITLES[page] || page;

  switch (page) {
    case "dashboard": loadDashboard(); break;
    case "calendar": loadCalendar(); break;
    case "clients": loadClients(); break;
    case "appointments": loadAppointments(); break;
    case "statistics": loadStatistics(); break;
  }
}

// --- Dashboard ---

async function loadDashboard() {
  const statsEl = document.getElementById("dashboard-stats");
  const listEl = document.getElementById("upcoming-list");
  statsEl.innerHTML = '<div class="loading">Загрузка...</div>';

  try {
    const data = await api.dashboard();
    hideError();
    statsEl.innerHTML = `
      <div class="stat-card purple"><div class="label">Клиентов</div><div class="value">${data.total_clients}</div></div>
      <div class="stat-card blue"><div class="label">Всего записей</div><div class="value">${data.total_appointments}</div></div>
      <div class="stat-card green"><div class="label">Сегодня</div><div class="value">${data.today_appointments}</div></div>
      <div class="stat-card orange"><div class="label">Выручка</div><div class="value">${formatMoney(data.revenue)}</div></div>
    `;

    if (!data.upcoming.length) {
      listEl.innerHTML = '<div class="list-item"><span>Нет ближайших записей (только подтверждённые)</span></div>';
      return;
    }
    listEl.innerHTML = data.upcoming.map(renderListItem).join("");
  } catch (e) {
    showError(e.message);
    statsEl.innerHTML = `<div class="error-banner">${e.message}</div>`;
    listEl.innerHTML = "";
  }
}

// --- Calendar ---

function setupCalendarControls() {
  document.getElementById("cal-prev").addEventListener("click", () => {
    calMonth--;
    if (calMonth < 1) { calMonth = 12; calYear--; }
    loadCalendar();
  });
  document.getElementById("cal-next").addEventListener("click", () => {
    calMonth++;
    if (calMonth > 12) { calMonth = 1; calYear++; }
    loadCalendar();
  });
}

async function loadCalendar() {
  document.getElementById("cal-month-label").textContent = `${MONTHS_RU[calMonth - 1]} ${calYear}`;

  try {
    calData = await api.calendar(calYear, calMonth);
    renderCalendarGrid();
  } catch (e) {
    showToast(e.message, "error");
  }
}

function renderCalendarGrid() {
  const grid = document.getElementById("calendar-grid");
  const firstDay = new Date(calYear, calMonth - 1, 1);
  const lastDay = new Date(calYear, calMonth, 0);
  let startWeekday = firstDay.getDay();
  startWeekday = startWeekday === 0 ? 6 : startWeekday - 1;

  const daysInMonth = lastDay.getDate();
  const prevMonthDays = new Date(calYear, calMonth - 1, 0).getDate();

  const eventsByDay = {};
  calData.forEach((a) => {
    const d = parseInt(a.appointment_date.split("-")[2]);
    eventsByDay[d] = (eventsByDay[d] || 0) + 1;
  });

  let html = "";
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === calYear && today.getMonth() + 1 === calMonth;

  for (let i = startWeekday - 1; i >= 0; i--) {
    html += `<div class="cal-day other-month">${prevMonthDays - i}</div>`;
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const classes = ["cal-day"];
    if (isCurrentMonth && d === today.getDate()) classes.push("today");
    if (eventsByDay[d]) classes.push("has-events");
    if (selectedDay === d) classes.push("selected");
    html += `<div class="${classes.join(" ")}" data-day="${d}">${d}</div>`;
  }

  const totalCells = startWeekday + daysInMonth;
  const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  for (let i = 1; i <= remaining; i++) {
    html += `<div class="cal-day other-month">${i}</div>`;
  }

  grid.innerHTML = html;

  grid.querySelectorAll(".cal-day[data-day]").forEach((el) => {
    el.addEventListener("click", () => {
      selectedDay = parseInt(el.dataset.day);
      renderCalendarGrid();
      showDayAppointments(selectedDay);
    });
  });
}

function showDayAppointments(day) {
  const dateStr = `${calYear}-${String(calMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const dayAppts = calData.filter((a) => a.appointment_date === dateStr);

  document.getElementById("cal-day-title").textContent =
    `Записи на ${day}.${String(calMonth).padStart(2, "0")}.${calYear}`;

  const list = document.getElementById("cal-day-list");
  if (!dayAppts.length) {
    list.innerHTML = '<div class="list-item"><span>Нет записей</span></div>';
    return;
  }
  list.innerHTML = dayAppts.map((a) => `
    <div class="list-item">
      <div>
        <div>${a.appointment_time} — ${a.client_name}</div>
        <div class="meta">${a.service_name} · ${a.performer_name}</div>
      </div>
      ${statusBadge(a.status)}
      <button class="btn btn-sm btn-ghost" onclick="openEditModal(${a.id})">✏️</button>
    </div>
  `).join("");
}

// --- Clients ---

let searchTimeout;
function setupFilters() {
  document.getElementById("client-search").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadClients(e.target.value), 300);
  });

  document.getElementById("filter-status").addEventListener("change", (e) => {
    loadAppointments(e.target.value);
  });
}

async function loadClients(query = "") {
  try {
    const clients = await api.clients(query);
    const wrap = document.getElementById("clients-list");

    if (!clients.length) {
      wrap.innerHTML = "<p style='color:var(--text-muted)'>Клиенты не найдены</p>";
      return;
    }

    wrap.innerHTML = `<table>
      <thead><tr>
        <th>Имя</th><th>Username</th><th>Телефон</th><th>Записей</th><th>Дата рег.</th>
      </tr></thead>
      <tbody>${clients.map((c) => `
        <tr>
          <td>${c.first_name} ${c.last_name || ""}</td>
          <td>${c.username ? "@" + c.username : "—"}</td>
          <td>${c.phone || "—"}</td>
          <td>${c.appointments_count}</td>
          <td>${formatDate(c.created_at)}</td>
        </tr>
      `).join("")}</tbody>
    </table>`;
  } catch (e) {
    showToast(e.message, "error");
  }
}

// --- Appointments ---

async function loadAppointments(status = "") {
  try {
    const params = status ? `?status=${status}` : "";
    const appointments = await api.appointments(params);
    const wrap = document.getElementById("appointments-list");

    if (!appointments.length) {
      wrap.innerHTML = "<p style='color:var(--text-muted)'>Записей нет</p>";
      return;
    }

    wrap.innerHTML = `<table>
      <thead><tr>
        <th>Дата</th><th>Время</th><th>Клиент</th><th>Услуга</th><th>Мастер</th><th>Статус</th><th></th>
      </tr></thead>
      <tbody>${appointments.map((a) => `
        <tr>
          <td>${formatDateShort(a.appointment_date)}</td>
          <td>${a.appointment_time}</td>
          <td>${a.client_name}</td>
          <td>${a.service_name}</td>
          <td>${a.performer_name}</td>
          <td>${statusBadge(a.status)}</td>
          <td>
            <button class="btn btn-sm btn-ghost" onclick="openEditModal(${a.id})">✏️</button>
            <select class="status-select" onchange="quickStatus(${a.id}, this.value)">
              <option value="">Статус...</option>
              <option value="confirmed">Подтверждена</option>
              <option value="pending">Ожидает</option>
              <option value="completed">Завершена</option>
              <option value="cancelled">Отменена</option>
            </select>
          </td>
        </tr>
      `).join("")}</tbody>
    </table>`;
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function quickStatus(id, status) {
  if (!status) return;
  try {
    await api.updateStatus(id, status);
    showToast("Статус обновлён", "success");
    loadAppointments(document.getElementById("filter-status").value);
  } catch (e) {
    showToast(e.message, "error");
  }
}

// --- Statistics ---

async function loadStatistics() {
  try {
    const data = await api.statistics();

    document.getElementById("stats-cards").innerHTML = `
      <div class="stat-card purple"><div class="label">Клиентов</div><div class="value">${data.total_clients}</div></div>
      <div class="stat-card blue"><div class="label">Записей</div><div class="value">${data.total_appointments}</div></div>
      <div class="stat-card green"><div class="label">Выручка</div><div class="value">${formatMoney(data.total_revenue)}</div></div>
    `;

    renderBarChart("chart-status", data.by_status);
    renderBarChart("chart-services", data.by_service);
    renderBarChart("chart-performers", data.by_performer);
  } catch (e) {
    showToast(e.message, "error");
  }
}

function renderBarChart(containerId, dataObj) {
  const container = document.getElementById(containerId);
  const entries = Object.entries(dataObj || {});
  if (!entries.length) {
    container.innerHTML = "<p style='color:var(--text-muted)'>Нет данных</p>";
    return;
  }
  const max = Math.max(...entries.map(([, v]) => v));
  container.innerHTML = entries.map(([label, value]) => `
    <div class="bar-row">
      <span class="bar-label" title="${label}">${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(value / max) * 100}%"></div></div>
      <span class="bar-value">${value}</span>
    </div>
  `).join("");
}

// --- Edit Modal ---

function setupEditModal() {
  document.getElementById("btn-close-modal").addEventListener("click", closeModal);
  document.querySelector(".modal-backdrop").addEventListener("click", closeModal);

  document.getElementById("edit-service").addEventListener("change", async (e) => {
    await loadPerformersForService(e.target.value);
  });

  document.getElementById("edit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("edit-id").value;
    try {
      await api.updateAppointment(id, {
        service_id: parseInt(document.getElementById("edit-service").value),
        performer_id: parseInt(document.getElementById("edit-performer").value),
        appointment_date: document.getElementById("edit-date").value,
        appointment_time: document.getElementById("edit-time").value.slice(0, 5),
        status: document.getElementById("edit-status").value,
      });
      showToast("Запись сохранена", "success");
      closeModal();
      reloadCurrentPage();
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  document.getElementById("btn-cancel-appt").addEventListener("click", async () => {
    const id = document.getElementById("edit-id").value;
    if (!confirm("Отменить эту запись?")) return;
    try {
      await api.cancelAppointment(id);
      showToast("Запись отменена", "success");
      closeModal();
      reloadCurrentPage();
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

async function openEditModal(id) {
  try {
    const [appt, services] = await Promise.all([api.appointment(id), api.services()]);
    servicesCache = services;

    document.getElementById("edit-id").value = id;
    document.getElementById("edit-date").value = appt.appointment_date;
    document.getElementById("edit-time").value = appt.appointment_time;
    document.getElementById("edit-status").value = appt.status;

    const serviceSelect = document.getElementById("edit-service");
    serviceSelect.innerHTML = services.map((s) =>
      `<option value="${s.id}" ${s.id === appt.service_id ? "selected" : ""}>${s.name} — ${s.price} ₽</option>`
    ).join("");

    await loadPerformersForService(appt.service_id, appt.performer_id);

    document.getElementById("modal").classList.remove("hidden");
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function loadPerformersForService(serviceId, selectedId = null) {
  const performers = await api.performers(serviceId);
  performersCache = performers;
  const select = document.getElementById("edit-performer");
  select.innerHTML = performers.map((p) =>
    `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${p.name}</option>`
  ).join("");
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
}

function reloadCurrentPage() {
  const active = document.querySelector(".nav-item.active");
  if (active) loadPage(active.dataset.page);
}

// --- Helpers ---

function statusBadge(status) {
  const labels = {
    confirmed: "Подтверждена",
    pending: "Ожидает",
    completed: "Завершена",
    cancelled: "Отменена",
  };
  return `<span class="status status-${status}">${labels[status] || status}</span>`;
}

function renderListItem(a) {
  return `<div class="list-item">
    <div>
      <div>${formatDateShort(a.appointment_date)} в ${a.appointment_time}</div>
      <div class="meta">${a.client_name} · ${a.service_name}</div>
    </div>
    ${statusBadge(a.status)}
  </div>`;
}

function formatMoney(n) {
  return new Intl.NumberFormat("ru-RU").format(n) + " ₽";
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU");
}

function formatDateShort(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function showToast(msg, type = "") {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  setTimeout(() => toast.classList.add("hidden"), 4000);
}

function showError(msg) {
  const banner = document.getElementById("error-banner");
  if (banner) {
    banner.textContent = "⚠️ " + msg;
    banner.classList.remove("hidden");
  } else {
    alert(msg);
  }
}

function hideError() {
  const banner = document.getElementById("error-banner");
  if (banner) banner.classList.add("hidden");
}

function showPageError(page, msg) {
  const el = document.querySelector(`#page-${page} .card, #page-${page}`);
  if (el) {
    el.insertAdjacentHTML(
      "afterbegin",
      `<div class="error-banner">⚠️ ${msg}</div>`
    );
  }
}

// Глобальные функции для onclick в HTML
window.openEditModal = openEditModal;
window.quickStatus = quickStatus;
