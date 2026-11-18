/* ==========================================================================
   HỆ THỐNG QUẢN LÝ NHÀ TRỌ & THANH TOÁN TIỀN PHÒNG - FRONTEND APPLICATION JS
   Kiến trúc: Vanilla ES6+ kết nối RESTful API (FastAPI + MySQL)
   ========================================================================== */

const API_BASE =
  window.location.port === "8000"
    ? `${window.location.origin}/api`
    : "http://127.0.0.1:8000/api";

// Global State
const state = {
  token: localStorage.getItem("qlpt_token") || null,
  user: JSON.parse(localStorage.getItem("qlpt_user") || "null"),
  activeTab: "dashboard",
  notifications: [],
  seenNotificationIds: new Set(),
  initialNotifLoaded: false,

  // Data caches
  dashboardStats: null,
  revenueStats: null,
  rooms: [],
  invoices: [],
  overdueList: [],
  tenants: [],
  archivedTenants: [],
  feedbacks: [],
  contracts: [],
  myContract: null,
  emailLogs: [],

  // Filters & Pagination
  roomFloorFilter: "ALL",
  roomStatusFilter: "ALL",
  roomSearch: "",
  roomPage: 1,
  roomPageSize: 9,

  invoiceMonthFilter: "ALL",
  invoiceStatusFilter: "ALL",
  invoiceSearch: "",
  invoicePage: 1,
  invoicePageSize: 8,

  debtMonthFilter: "ALL",
  tenantSubTab: "active", // 'active' | 'archived'
};

let revenueChartInstance = null;
let roomPieChartInstance = null;
let pollTimer = null;

// ==========================================================================
// UTILITY HELPERS
// ==========================================================================

function fmtVND(amount) {
  const num = Number(amount || 0);
  return num.toLocaleString("vi-VN") + " đ";
}

function fmtDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("vi-VN");
}

function fmtDateTime(dtStr) {
  if (!dtStr) return "—";
  const d = new Date(dtStr);
  if (isNaN(d.getTime())) return dtStr;
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function apiFetch(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    let detail = "Phiên đăng nhập đã hết hạn hoặc bị thu hồi bởi Chủ trọ.";
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch (_) {}
    if (state.token && path !== "/auth/login") {
      logout(detail);
    }
    throw new Error(detail);
  }

  if (!res.ok) {
    let errMsg = `Lỗi HTTP ${res.status}`;
    try {
      const data = await res.json();
      errMsg = data.detail || errMsg;
    } catch (_) {}
    throw new Error(errMsg);
  }

  return res.json();
}

// ==========================================================================
// HỆ THỐNG TOAST NOTIFICATION 10 GIÂY -> THU NHỎ VÀO BIỂU TƯỢNG CHIẾC CHUÔNG
// ==========================================================================

function showToast10s(title, message, type = "INFO") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  let colorClass = "toast-success";
  let badgeBg = "bg-teal-100 text-teal-800";
  let badgeText = "THÔNG BÁO MỚI";

  if (type === "OVERDUE_ALERT" || type === "DANGER") {
    colorClass = "toast-danger";
    badgeBg = "bg-red-100 text-red-700";
    badgeText = "CẢNH BÁO QUÁ HẠN";
  } else if (type === "BILL_UPLOADED" || type === "FEEDBACK_NEW" || type === "WARNING") {
    colorClass = "toast-warning";
    badgeBg = "bg-amber-100 text-amber-800";
    badgeText = "CẦN XỬ LÝ";
  } else if (type === "PAYMENT_SUCCESS") {
    colorClass = "toast-success";
    badgeBg = "bg-emerald-100 text-emerald-800";
    badgeText = "THANH TOÁN THÀNH CÔNG";
  }

  const toastEl = document.createElement("div");
  toastEl.className = `toast-popup ${colorClass}`;

  let secondsLeft = 10;
  toastEl.innerHTML = `
    <div class="flex items-start justify-between gap-2 mb-1">
      <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${badgeBg}">${escapeHtml(badgeText)}</span>
      <div class="flex items-center gap-2">
        <span class="text-[11px] font-mono-code font-semibold text-slate-400" data-countdown>10s → 🔔</span>
        <button type="button" class="text-slate-400 hover:text-slate-700 text-xs font-bold cursor-pointer" data-close>✕</button>
      </div>
    </div>
    <h4 class="text-sm font-bold text-slate-900 mb-0.5">${escapeHtml(title)}</h4>
    <p class="text-xs text-slate-600 leading-relaxed">${escapeHtml(message)}</p>
    <div class="toast-progress-bar"></div>
  `;

  container.prepend(toastEl);

  const countdownSpan = toastEl.querySelector("[data-countdown]");
  const closeBtn = toastEl.querySelector("[data-close]");

  const shrinkAndAbsorbIntoBell = () => {
    clearInterval(intervalId);
    clearTimeout(timeoutId);
    if (!toastEl.isConnected) return;
    toastEl.classList.add("shrinking-to-bell");

    // Rung chiếc chuông khi Toast thu nhỏ bay vào
    const bellSvg = document.getElementById("bell-svg-icon");
    if (bellSvg) {
      bellSvg.classList.remove("bell-ringing");
      void bellSvg.offsetWidth;
      bellSvg.classList.add("bell-ringing");
    }

    setTimeout(() => {
      if (toastEl.isConnected) toastEl.remove();
    }, 550);
  };

  closeBtn.addEventListener("click", shrinkAndAbsorbIntoBell);

  const intervalId = setInterval(() => {
    secondsLeft -= 1;
    if (secondsLeft > 0 && countdownSpan) {
      countdownSpan.textContent = `${secondsLeft}s → 🔔`;
    }
  }, 1000);

  // Đúng 10 giây tự động thu nhỏ bay vào biểu tượng Chiếc chuông
  const timeoutId = setTimeout(shrinkAndAbsorbIntoBell, 10000);
}

function triggerDemoToast() {
  const roleLabel = state.user?.role === "LANDLORD" ? "Chủ trọ" : `Phòng ${state.user?.username}`;
  showToast10s(
    `Thông báo Real-time (${roleLabel})`,
    "Popup hình chữ nhật hiển thị tóm tắt trong đúng 10 giây, sau đó tự động thu nhỏ và bay vào biểu tượng Chiếc chuông góc trên bên phải!",
    "PAYMENT_SUCCESS"
  );
}

async function fetchNotifications(silent = false) {
  if (!state.token) return;
  try {
    const list = await apiFetch("/notifications?limit=40");
    state.notifications = list;

    if (!state.initialNotifLoaded) {
      list.forEach((n) => state.seenNotificationIds.add(n.id));
      state.initialNotifLoaded = true;
      // Hiển thị 1 Toast chào mừng/thông báo mới nhất chưa đọc khi vừa đăng nhập
      const latestUnread = list.find((n) => !n.is_read);
      if (latestUnread && !silent) {
        showToast10s(latestUnread.title, latestUnread.message, latestUnread.type);
      }
    } else {
      // Nếu có thông báo mới phát sinh trong phiên -> Bắn Toast 10s
      const newOnes = list.filter((n) => !state.seenNotificationIds.has(n.id));
      newOnes.forEach((n) => {
        state.seenNotificationIds.add(n.id);
        showToast10s(n.title, n.message, n.type);
      });
    }

    renderBellUI();
  } catch (_) {}
}

function renderBellUI() {
  const badge = document.getElementById("bell-badge");
  const listEl = document.getElementById("bell-list");
  if (!badge || !listEl) return;

  const unreadCount = state.notifications.filter((n) => !n.is_read).length;
  if (unreadCount > 0) {
    badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }

  if (state.notifications.length === 0) {
    listEl.innerHTML = `<div class="p-6 text-center text-xs text-slate-400">Chưa có thông báo nào.</div>`;
    return;
  }

  listEl.innerHTML = state.notifications
    .map((n) => {
      const unreadClass = !n.is_read ? "bg-teal-50/60" : "bg-white";
      const dot = !n.is_read
        ? `<span class="w-2 h-2 rounded-full bg-red-600 shrink-0 mt-1.5"></span>`
        : `<span class="w-2 h-2 rounded-full bg-slate-200 shrink-0 mt-1.5"></span>`;
      return `
        <div onclick="markOneNotifRead(${n.id})"
          class="p-3.5 hover:bg-slate-50 transition cursor-pointer flex items-start gap-2.5 ${unreadClass}">
          ${dot}
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <p class="text-xs font-bold text-slate-800 truncate">${escapeHtml(n.title)}</p>
              <span class="text-[10px] text-slate-400 shrink-0">${fmtDateTime(n.created_at)}</span>
            </div>
            <p class="text-xs text-slate-600 mt-0.5 leading-snug">${escapeHtml(n.message)}</p>
          </div>
        </div>
      `;
    })
    .join("");
}

function toggleBellDropdown() {
  const dd = document.getElementById("bell-dropdown");
  if (!dd) return;
  dd.classList.toggle("hidden");
}

async function markOneNotifRead(id) {
  try {
    await apiFetch(`/notifications/${id}/read`, { method: "PUT" });
    const item = state.notifications.find((n) => n.id === id);
    if (item) item.is_read = true;
    renderBellUI();
  } catch (_) {}
}

async function markAllNotificationsRead() {
  try {
    await apiFetch("/notifications/read-all", { method: "PUT" });
    state.notifications.forEach((n) => (n.is_read = true));
    renderBellUI();
  } catch (_) {}
}

// Close Bell Dropdown when clicking outside
document.addEventListener("click", (e) => {
  const wrapper = document.getElementById("bell-wrapper");
  const dd = document.getElementById("bell-dropdown");
  if (wrapper && dd && !wrapper.contains(e.target)) {
    dd.classList.add("hidden");
  }
});

// ==========================================================================
// AUTHENTICATION & SESSION MANAGEMENT
// ==========================================================================

async function handleLogin(username, password) {
  const errBox = document.getElementById("login-error");
  const btn = document.getElementById("login-submit-btn");
  if (errBox) errBox.classList.add("hidden");
  if (btn) btn.disabled = true;

  try {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: username.trim(), password }),
    });

    state.token = data.access_token;
    state.user = data.user;
    state.seenNotificationIds.clear();
    state.initialNotifLoaded = false;

    localStorage.setItem("qlpt_token", state.token);
    localStorage.setItem("qlpt_user", JSON.stringify(state.user));

    await initAppPortal();
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message || "Đăng nhập thất bại";
      errBox.classList.remove("hidden");
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

function quickLogin(username, password) {
  const uInput = document.getElementById("login-username");
  const pInput = document.getElementById("login-password");
  if (uInput) uInput.value = username;
  if (pInput) pInput.value = password;
  handleLogin(username, password);
}

function logout(reasonMessage = null) {
  state.token = null;
  state.user = null;
  localStorage.removeItem("qlpt_token");
  localStorage.removeItem("qlpt_user");
  if (pollTimer) clearInterval(pollTimer);

  document.getElementById("app-view").classList.add("hidden");
  document.getElementById("login-view").classList.remove("hidden");

  if (reasonMessage && typeof reasonMessage === "string") {
    const errBox = document.getElementById("login-error");
    if (errBox) {
      errBox.textContent = reasonMessage;
      errBox.classList.remove("hidden");
    }
  }
}

// ==========================================================================
// PORTAL INITIALIZATION & NAVIGATION
// ==========================================================================

async function initAppPortal() {
  if (!state.token) {
    logout();
    return;
  }

  try {
    const me = await apiFetch("/auth/me");
    state.user = me;
    localStorage.setItem("qlpt_user", JSON.stringify(me));
  } catch (_) {
    return;
  }

  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-view").classList.remove("hidden");

  const isLandlord = state.user.role === "LANDLORD";
  const badgeEl = document.getElementById("header-portal-badge");
  const titleEl = document.getElementById("header-title");
  const userNameEl = document.getElementById("header-user-name");
  const userRoleEl = document.getElementById("header-user-role");

  if (isLandlord) {
    badgeEl.textContent = "ADMIN / CHỦ TRỌ";
    badgeEl.className = "px-2.5 py-0.5 text-[11px] font-bold uppercase rounded bg-teal-700 text-white";
    titleEl.textContent = "Quản Trị Hệ Thống Nhà Trọ (3 Tầng • 15 Phòng)";
    userNameEl.textContent = state.user.full_name;
    userRoleEl.textContent = `Tài khoản: ${state.user.username}`;
    state.activeTab = "dashboard";
  } else {
    badgeEl.textContent = `PHÒNG ${state.user.username}`;
    badgeEl.className = "px-2.5 py-0.5 text-[11px] font-bold uppercase rounded bg-sky-700 text-white";
    titleEl.textContent = `Cổng Thông Tin Khách Thuê - Phòng ${state.user.username}`;
    userNameEl.textContent = state.user.full_name;
    userRoleEl.textContent = `Phòng ${state.user.username} (Phiên v${state.user.token_version || 1})`;
    state.activeTab = "my-bills";
  }

  renderNavTabs();
  await fetchNotifications(false);

  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => fetchNotifications(true), 8000);

  await switchTab(state.activeTab);

  // Nếu là Khách thuê lần đầu đăng nhập vào phòng chưa có hồ sơ -> mở Modal Khai báo thông tin lần đầu
  if (!isLandlord && !state.user.is_profile_completed) {
    openFirstTimeProfileModal();
  }
}

function renderNavTabs() {
  const nav = document.getElementById("nav-tabs");
  if (!nav) return;

  const isLandlord = state.user?.role === "LANDLORD";

  const landlordTabs = [
    { id: "dashboard", label: "📊 Tổng quan & Doanh thu" },
    { id: "rooms", label: "🏢 Quản lý 15 Phòng (3 Tầng)" },
    { id: "billing", label: "🧾 Hóa đơn, Điện Nước & Duyệt Bill" },
    { id: "debt", label: "🚨 Kiểm tra Công nợ (Quá hạn ngày 15)" },
    { id: "tenants", label: "👥 Khách thuê & Lưu trữ 30 ngày" },
    { id: "feedbacks", label: "💬 Phản ánh / Góp ý theo Phòng" },
  ];

  const tenantTabs = [
    { id: "my-bills", label: "💳 Hóa đơn & Cổng Thanh toán" },
    { id: "my-debt", label: "🚨 Thanh toán Nợ các tháng" },
    { id: "my-contract", label: "📜 Hợp đồng Thuê nhà (PDF)" },
    { id: "my-feedbacks", label: "🛠️ Gửi Feedback / Báo hỏng" },
    { id: "my-profile", label: "👤 Hồ sơ Cá nhân & Mật khẩu" },
  ];

  const tabs = isLandlord ? landlordTabs : tenantTabs;

  nav.innerHTML = tabs
    .map((t) => {
      const active = state.activeTab === t.id;
      const cls = active
        ? "bg-teal-700 text-white shadow-xs"
        : "text-slate-600 hover:bg-slate-200/70 hover:text-slate-900";
      return `
        <button type="button" onclick="switchTab('${t.id}')"
          class="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold whitespace-nowrap transition cursor-pointer ${cls}">
          ${t.label}
        </button>
      `;
    })
    .join("");
}

async function switchTab(tabId) {
  state.activeTab = tabId;
  renderNavTabs();
  const main = document.getElementById("main-content");
  if (!main) return;

  main.innerHTML = `
    <div class="py-16 flex flex-col items-center justify-center text-slate-500">
      <div class="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin mb-3"></div>
      <p class="text-sm font-medium">Đang tải dữ liệu...</p>
    </div>
  `;

  try {
    if (tabId === "dashboard") {
      await loadAndRenderAdminDashboard();
    } else if (tabId === "rooms") {
      await loadAndRenderAdminRooms();
    } else if (tabId === "billing") {
      await loadAndRenderAdminBilling();
    } else if (tabId === "debt") {
      await loadAndRenderAdminDebt();
    } else if (tabId === "tenants") {
      await loadAndRenderAdminTenants();
    } else if (tabId === "feedbacks") {
      await loadAndRenderAdminFeedbacks();
    } else if (tabId === "my-bills") {
      await loadAndRenderTenantBills();
    } else if (tabId === "my-debt") {
      await loadAndRenderTenantDebt();
    } else if (tabId === "my-contract") {
      await loadAndRenderTenantContract();
    } else if (tabId === "my-feedbacks") {
      await loadAndRenderTenantFeedbacks();
    } else if (tabId === "my-profile") {
      await renderTenantProfileTab();
    }
  } catch (err) {
    main.innerHTML = `
      <div class="p-6 rounded-2xl bg-red-50 border border-red-200 text-red-700">
        <h3 class="font-bold mb-1">Không thể tải dữ liệu</h3>
        <p class="text-sm">${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

// ==========================================================================
// ADMIN TAB 1: DASHBOARD TỔNG QUAN & BIỂU ĐỒ DOANH THU
// ==========================================================================

async function loadAndRenderAdminDashboard() {
  const [dash, rev, overdue, rooms, feedbacks] = await Promise.all([
    apiFetch("/stats/dashboard?month_year=2026-11"),
    apiFetch("/stats/revenue"),
    apiFetch("/stats/overdue"),
    apiFetch("/rooms"),
    apiFetch("/feedbacks"),
  ]);

  state.dashboardStats = dash;
  state.revenueStats = rev;
  state.overdueList = overdue;
  state.rooms = rooms;
  state.feedbacks = feedbacks;

  const main = document.getElementById("main-content");
  main.innerHTML = `
    <div class="space-y-6">
      <!-- Top Action Banner -->
      <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900">Tổng quan Vận hành & Tài chính Nhà trọ (Kỳ 11/2026)</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Theo dõi thời gian thực 15 phòng trên 3 tầng • Tự động cảnh báo nợ sau ngày 15 hằng tháng • Tự động xóa lưu trữ tạm sau 30 ngày.
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button type="button" onclick="openEmailLogsModal()"
            class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition cursor-pointer flex items-center gap-1.5">
            <span>📧 Hộp thư Gmail đã gửi</span>
          </button>
          <button type="button" onclick="runSystemCronjob()"
            class="px-3.5 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs transition cursor-pointer flex items-center gap-1.5">
            <span>⚙️ Chạy Cronjob (Quét Nợ Ngày 15 & Xóa Lưu Trữ >30 Ngày)</span>
          </button>
        </div>
      </div>

      <!-- 6 KPI Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <p class="text-xs font-semibold text-slate-500 uppercase">Tổng phải thu (T11)</p>
          <p class="text-lg font-bold text-slate-900 font-mono-code mt-1">${fmtVND(dash.monthly_expected_revenue)}</p>
          <p class="text-[11px] text-slate-500 mt-1">${dash.active_contracts} hợp đồng hiệu lực</p>
        </div>

        <div class="bg-emerald-50/70 p-4 rounded-2xl border border-emerald-200 shadow-xs">
          <p class="text-xs font-semibold text-emerald-800 uppercase">Đã thu thực tế (T11)</p>
          <p class="text-lg font-bold text-emerald-700 font-mono-code mt-1">${fmtVND(dash.monthly_actual_revenue)}</p>
          <p class="text-[11px] text-emerald-700 mt-1">✓ ${dash.paid_invoices_count} hóa đơn đã đóng</p>
        </div>

        <div onclick="switchTab('debt')" class="bg-red-50/80 p-4 rounded-2xl border border-red-200 shadow-xs cursor-pointer hover:bg-red-100/60 transition">
          <p class="text-xs font-semibold text-red-800 uppercase">Tổng công nợ chưa trả</p>
          <p class="text-lg font-bold text-red-600 font-mono-code mt-1">${fmtVND(dash.total_unpaid_amount)}</p>
          <p class="text-[11px] text-red-700 font-semibold mt-1">🚨 ${dash.overdue_invoices_count} hóa đơn quá hạn ngày 15</p>
        </div>

        <div onclick="switchTab('billing')" class="bg-amber-50/80 p-4 rounded-2xl border border-amber-200 shadow-xs cursor-pointer hover:bg-amber-100/60 transition">
          <p class="text-xs font-semibold text-amber-800 uppercase">Chờ duyệt Bill UNC</p>
          <p class="text-lg font-bold text-amber-700 font-mono-code mt-1">${dash.pending_approval_invoices_count} phòng</p>
          <p class="text-[11px] text-amber-800 font-semibold mt-1">⏳ Bấm để đối soát & duyệt</p>
        </div>

        <div onclick="switchTab('rooms')" class="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs cursor-pointer hover:bg-slate-50 transition">
          <p class="text-xs font-semibold text-slate-500 uppercase">Tỷ lệ lấp đầy</p>
          <p class="text-lg font-bold text-teal-700 font-mono-code mt-1">${dash.rented_rooms}/${dash.total_rooms} phòng</p>
          <p class="text-[11px] text-slate-500 mt-1">Trống: ${dash.available_rooms} • Bảo trì: ${dash.maintenance_rooms}</p>
        </div>

        <div onclick="switchTab('feedbacks')" class="bg-white p-4 rounded-2xl border ${dash.unread_feedbacks_count > 0 ? "border-red-400 bg-red-50/40" : "border-slate-200"} shadow-xs cursor-pointer hover:bg-slate-50 transition">
          <p class="text-xs font-semibold text-slate-600 uppercase">Feedback "Cần đọc"</p>
          <p class="text-lg font-bold ${dash.unread_feedbacks_count > 0 ? "text-red-600" : "text-slate-800"} font-mono-code mt-1">${dash.unread_feedbacks_count} mới</p>
          <p class="text-[11px] text-slate-500 mt-1">Lưu trữ 30 ngày: ${dash.archived_tenants_count} hồ sơ</p>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-8 bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-bold text-slate-900">Biểu đồ Doanh thu & Công nợ theo Tháng</h3>
              <p class="text-xs text-slate-500">So sánh Tổng tiền phải thu, Đã thu thực tế và Tổng nợ chưa trả</p>
            </div>
            <span class="px-2.5 py-1 rounded-lg bg-teal-50 text-teal-800 text-xs font-mono-code font-semibold">
              Lũy kế đã thu: ${fmtVND(rev.total_collected_revenue)}
            </span>
          </div>
          <div class="h-72">
            <canvas id="revenue-chart"></canvas>
          </div>
        </div>

        <div class="lg:col-span-4 bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div>
            <h3 class="text-base font-bold text-slate-900">Trạng thái 15 Phòng (3 Tầng)</h3>
            <p class="text-xs text-slate-500 mb-4">Tầng 1 (1.1-1.5) • Tầng 2 (2.1-2.5) • Tầng 3 (3.1-3.5)</p>
            <div class="h-56 flex items-center justify-center">
              <canvas id="room-pie-chart"></canvas>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-2 pt-4 border-t border-slate-100 text-center text-xs">
            <div class="p-2 rounded-lg bg-emerald-50 text-emerald-800 font-semibold">Đang thuê: ${dash.rented_rooms}</div>
            <div class="p-2 rounded-lg bg-sky-50 text-sky-800 font-semibold">Phòng trống: ${dash.available_rooms}</div>
            <div class="p-2 rounded-lg bg-amber-50 text-amber-800 font-semibold">Bảo trì: ${dash.maintenance_rooms}</div>
          </div>
        </div>
      </div>

      <!-- Sơ đồ trực quan 15 phòng 3 tầng -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 class="text-base font-bold text-slate-900">Sơ đồ Trực quan 15 Phòng theo 3 Tầng</h3>
            <p class="text-xs text-slate-500">Phòng quá hạn sau ngày 15 được đánh dấu đỏ nổi bật • Bấm vào phòng để xem chi tiết / Hợp đồng / Trả phòng</p>
          </div>
          <button type="button" onclick="switchTab('rooms')" class="text-xs font-bold text-teal-700 hover:underline cursor-pointer">
            Quản lý chi tiết 15 phòng →
          </button>
        </div>

        <div class="space-y-4">
          ${[1, 2, 3]
            .map((fl) => {
              const floorRooms = rooms.filter((r) => r.floor === fl);
              return `
                <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <div class="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2.5">TẦNG ${fl} (Phòng ${fl}.1 → ${fl}.5)</div>
                  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                    ${floorRooms
                      .map((r) => {
                        let cardBorder = "border-slate-200 bg-white";
                        let badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">TRỐNG</span>`;
                        if (r.has_overdue_invoice) {
                          cardBorder = "room-card-overdue";
                          badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-600 text-white badge-pulse-red">NỢ QUÁ HẠN (${r.overdue_months_count}T)</span>`;
                        } else if (r.pending_bill_count > 0) {
                          cardBorder = "border-2 border-amber-400 bg-amber-50/40";
                          badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-white">CHỜ DUYỆT BILL</span>`;
                        } else if (r.status === "RENTED") {
                          cardBorder = "border-emerald-300 bg-white";
                          badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-800">ĐANG THUÊ</span>`;
                        } else if (r.status === "MAINTENANCE") {
                          cardBorder = "border-amber-300 bg-slate-100";
                          badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-300 text-slate-800">BẢO TRÌ</span>`;
                        }
                        return `
                          <div onclick="openRoomQuickDetailModal(${r.id})"
                            class="p-3 rounded-xl border ${cardBorder} shadow-2xs hover:shadow-md transition cursor-pointer flex flex-col justify-between">
                            <div class="flex items-center justify-between gap-1 mb-1.5">
                              <span class="font-mono-code font-bold text-sm text-slate-900">P.${escapeHtml(r.room_number)}</span>
                              ${badgeHtml}
                            </div>
                            <div class="text-xs text-slate-700 font-semibold truncate">${escapeHtml(r.tenant_name || "Chưa có khách thuê")}</div>
                            <div class="text-[11px] text-slate-500 font-mono-code mt-1">${fmtVND(r.price)}/tháng</div>
                            ${
                              r.has_overdue_invoice
                                ? `<div class="mt-1.5 text-[11px] font-bold text-red-600 font-mono-code">Nợ: ${fmtVND(r.overdue_amount)}</div>`
                                : ""
                            }
                          </div>
                        `;
                      })
                      .join("")}
                  </div>
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    </div>
  `;

  renderDashboardCharts(rev, dash);
}

function renderDashboardCharts(rev, dash) {
  const ctxRev = document.getElementById("revenue-chart");
  if (ctxRev && window.Chart) {
    if (revenueChartInstance) revenueChartInstance.destroy();
    const items = (rev.monthly_breakdown || []).slice().reverse();
    const labels = items.map((i) => `Kỳ ${i.month_year}`);
    const expectedData = items.map((i) => i.expected_amount);
    const collectedData = items.map((i) => i.collected_amount);
    const unpaidData = items.map((i) => i.unpaid_amount);

    revenueChartInstance = new Chart(ctxRev, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Tổng phải thu (VNĐ)",
            data: expectedData,
            backgroundColor: "#0f766e",
            borderRadius: 6,
          },
          {
            label: "Đã thu (VNĐ)",
            data: collectedData,
            backgroundColor: "#10b981",
            borderRadius: 6,
          },
          {
            label: "Còn nợ quá hạn / Chưa thu (VNĐ)",
            data: unpaidData,
            backgroundColor: "#ef4444",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top" },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: (v) => (v / 1000000).toFixed(1) + "M",
            },
          },
        },
      },
    });
  }

  const ctxPie = document.getElementById("room-pie-chart");
  if (ctxPie && window.Chart) {
    if (roomPieChartInstance) roomPieChartInstance.destroy();
    roomPieChartInstance = new Chart(ctxPie, {
      type: "doughnut",
      data: {
        labels: ["Đang thuê", "Phòng trống", "Đang bảo trì"],
        datasets: [
          {
            data: [dash.rented_rooms, dash.available_rooms, dash.maintenance_rooms],
            backgroundColor: ["#0f766e", "#38bdf8", "#f59e0b"],
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
        },
      },
    });
  }
}

async function runSystemCronjob() {
  try {
    const res = await apiFetch("/stats/run-cron", { method: "POST" });
    showToast10s(
      "Đã thực thi Cronjob Hệ thống",
      `Đã xóa vĩnh viễn ${res.purged_archived_tenants} hồ sơ lưu trữ quá 30 ngày & đánh dấu nợ ${res.newly_marked_overdue_invoices} hóa đơn sau ngày 15.`,
      "PAYMENT_SUCCESS"
    );
    await switchTab(state.activeTab);
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// ADMIN TAB 2: QUẢN LÝ TẦNG & 15 PHÒNG (CÓ MODAL XÁC NHẬN XÓA & TRẢ PHÒNG)
// ==========================================================================

async function loadAndRenderAdminRooms() {
  state.rooms = await apiFetch("/rooms");
  renderAdminRoomsView();
}

function renderAdminRoomsView() {
  const main = document.getElementById("main-content");
  if (!main) return;

  const floors = [...new Set(state.rooms.map((r) => r.floor))].sort((a, b) => a - b);

  let filtered = state.rooms.filter((r) => {
    if (state.roomFloorFilter !== "ALL" && String(r.floor) !== String(state.roomFloorFilter)) {
      return false;
    }
    if (state.roomStatusFilter === "OVERDUE") {
      if (!r.has_overdue_invoice) return false;
    } else if (state.roomStatusFilter !== "ALL" && r.status !== state.roomStatusFilter) {
      return false;
    }
    if (state.roomSearch.trim()) {
      const q = state.roomSearch.trim().toLowerCase();
      const matchNum = r.room_number.toLowerCase().includes(q);
      const matchName = (r.tenant_name || "").toLowerCase().includes(q);
      const matchPhone = (r.tenant_phone || "").toLowerCase().includes(q);
      if (!matchNum && !matchName && !matchPhone) return false;
    }
    return true;
  });

  const totalItems = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / state.roomPageSize));
  if (state.roomPage > totalPages) state.roomPage = totalPages;
  const startIdx = (state.roomPage - 1) * state.roomPageSize;
  const pageItems = filtered.slice(startIdx, startIdx + state.roomPageSize);

  main.innerHTML = `
    <div class="space-y-5">
      <!-- Header & Add Buttons -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900">Quản lý Tầng, Phòng & Tài khoản Phòng (${state.rooms.length} Phòng)</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Mỗi phòng tự động có 1 tài khoản độc lập theo quy tắc <code class="font-mono-code font-bold text-teal-700">[Số tầng].[Thứ tự phòng]</code> • Giá mặc định 2.000.000đ/tháng (tùy chỉnh theo phòng).
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button type="button" onclick="openAddFloorModal()"
            class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition cursor-pointer">
            + Thêm Tầng mới (Tự sinh phòng)
          </button>
          <button type="button" onclick="openAddRoomModal()"
            class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs transition cursor-pointer">
            + Thêm Phòng mới
          </button>
        </div>
      </div>

      <!-- Filters Bar -->
      <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <select onchange="state.roomFloorFilter=this.value; state.roomPage=1; renderAdminRoomsView()"
            class="px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold bg-white">
            <option value="ALL" ${state.roomFloorFilter === "ALL" ? "selected" : ""}>Tất cả các tầng</option>
            ${floors
              .map(
                (f) =>
                  `<option value="${f}" ${String(state.roomFloorFilter) === String(f) ? "selected" : ""}>Tầng ${f}</option>`
              )
              .join("")}
          </select>

          <select onchange="state.roomStatusFilter=this.value; state.roomPage=1; renderAdminRoomsView()"
            class="px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold bg-white">
            <option value="ALL" ${state.roomStatusFilter === "ALL" ? "selected" : ""}>Tất cả trạng thái</option>
            <option value="RENTED" ${state.roomStatusFilter === "RENTED" ? "selected" : ""}>Đang thuê (RENTED)</option>
            <option value="AVAILABLE" ${state.roomStatusFilter === "AVAILABLE" ? "selected" : ""}>Phòng trống (AVAILABLE)</option>
            <option value="MAINTENANCE" ${state.roomStatusFilter === "MAINTENANCE" ? "selected" : ""}>Đang bảo trì (MAINTENANCE)</option>
            <option value="OVERDUE" ${state.roomStatusFilter === "OVERDUE" ? "selected" : ""}>🚨 Đang nợ quá hạn sau ngày 15</option>
          </select>

          <input type="text" value="${escapeHtml(state.roomSearch)}"
            oninput="state.roomSearch=this.value; state.roomPage=1; renderAdminRoomsView()"
            placeholder="Tìm mã phòng (1.1), tên khách, SĐT..."
            class="px-3.5 py-2 rounded-xl border border-slate-300 text-xs w-60" />
        </div>

        <div class="text-xs text-slate-500">
          Hiển thị <b>${pageItems.length}</b> / <b>${totalItems}</b> phòng (Trang ${state.roomPage}/${totalPages})
        </div>
      </div>

      <!-- Room Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        ${pageItems
          .map((r) => {
            const isOverdue = r.has_overdue_invoice;
            const statusBadge =
              r.status === "RENTED"
                ? `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-teal-100 text-teal-800">ĐANG THUÊ</span>`
                : r.status === "AVAILABLE"
                ? `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">PHÒNG TRỐNG</span>`
                : `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">ĐANG BẢO TRÌ</span>`;

            return `
              <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between ${
                isOverdue ? "room-card-overdue" : ""
              }">
                <div>
                  <div class="flex items-start justify-between gap-2 mb-3">
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="text-lg font-bold font-mono-code text-slate-900">Phòng ${escapeHtml(r.room_number)}</span>
                        <span class="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px] font-semibold">Tầng ${r.floor}</span>
                      </div>
                      <p class="text-[11px] text-slate-500 mt-0.5">Tài khoản đăng nhập: <code class="font-mono-code font-bold text-teal-700">${escapeHtml(r.account_username || r.room_number)}</code></p>
                    </div>
                    <div class="flex flex-col items-end gap-1">
                      ${statusBadge}
                      ${
                        isOverdue
                          ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-600 text-white badge-pulse-red">QUÁ HẠN (NỢ ${r.overdue_months_count} THÁNG)</span>`
                          : ""
                      }
                      ${
                        r.pending_bill_count > 0
                          ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-white">CHỜ DUYỆT BILL UNC</span>`
                          : ""
                      }
                    </div>
                  </div>

                  <!-- Giá phòng & Phụ phí cố định -->
                  <div class="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs space-y-1 mb-3">
                    <div class="flex justify-between">
                      <span class="text-slate-500">Giá thuê cơ bản:</span>
                      <span class="font-mono-code font-bold text-teal-800">${fmtVND(r.price)}/tháng</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-slate-500">Điện / Nước:</span>
                      <span class="font-mono-code text-slate-700">${fmtVND(r.electricity_rate)}/kWh • ${fmtVND(r.water_rate)}/m³</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-slate-500">Phụ phí (Xe, Wifi, Rác, Bảo trì):</span>
                      <span class="font-mono-code text-slate-700">${fmtVND(
                        (r.parking_fee || 0) + (r.wifi_fee || 0) + (r.trash_fee || 0) + (r.maintenance_fee || 0)
                      )}</span>
                    </div>
                  </div>

                  <!-- Thông tin khách thuê -->
                  ${
                    r.status === "RENTED"
                      ? `
                        <div class="text-xs space-y-1 mb-4">
                          <div class="font-bold text-slate-800">👤 Khách thuê: ${escapeHtml(r.tenant_name || "Chưa cập nhật")} (${escapeHtml(r.tenant_gender || "—")})</div>
                          <div class="text-slate-600">• CCCD: <span class="font-mono-code font-semibold">${escapeHtml(r.tenant_cccd || "Chưa khai báo")}</span> • SĐT: <span class="font-mono-code">${escapeHtml(r.tenant_phone || "—")}</span></div>
                          <div class="text-slate-600 truncate">• Gmail: ${escapeHtml(r.tenant_email || "—")}</div>
                          <div class="text-slate-600 truncate">• Quê quán: ${escapeHtml(r.tenant_hometown || "—")}</div>
                          ${
                            isOverdue
                              ? `<div class="p-2 rounded-lg bg-red-100/80 text-red-800 font-bold mt-2">🚨 Tổng nợ quá hạn: ${fmtVND(r.overdue_amount)}</div>`
                              : ""
                          }
                        </div>
                      `
                      : `
                        <div class="p-3 rounded-xl bg-emerald-50/50 border border-dashed border-emerald-200 text-xs text-slate-500 mb-4">
                          Phòng hiện đang trống (${r.area || 22}m²). Khách mới có thể đăng nhập tài khoản <b>${escapeHtml(r.room_number)}</b> để khai báo thông tin nhận phòng.
                        </div>
                      `
                  }
                </div>

                <!-- Action Buttons -->
                <div class="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-1.5">
                  <button type="button" onclick="openEditRoomModal(${r.id})"
                    class="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition cursor-pointer">
                    ✏️ Sửa giá/phí
                  </button>

                  <button type="button" onclick="openRoomContractModal(${r.id})"
                    class="px-2.5 py-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 text-xs font-semibold transition cursor-pointer">
                    📜 Hợp đồng VN
                  </button>

                  ${
                    r.status === "RENTED"
                      ? `
                        <button type="button" onclick="openCheckoutRoomModal(${r.id}, '${escapeHtml(r.room_number)}', '${escapeHtml(r.tenant_name || "")}')"
                          class="px-2.5 py-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 text-xs font-bold transition cursor-pointer">
                          🔑 Khách trả phòng / Reset TK
                        </button>
                      `
                      : `
                        <button type="button" onclick="openConfirmDeleteRoomModal(${r.id}, '${escapeHtml(r.room_number)}')"
                          class="px-2.5 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-xs font-semibold transition cursor-pointer ml-auto">
                          🗑️ Xóa phòng
                        </button>
                      `
                  }
                </div>
              </div>
            `;
          })
          .join("")}
      </div>

      <!-- Pagination Controls -->
      <div class="flex items-center justify-between bg-white px-4 py-3 rounded-2xl border border-slate-200">
        <span class="text-xs text-slate-500">Trang ${state.roomPage} / ${totalPages}</span>
        <div class="flex items-center gap-1.5">
          <button type="button" ${state.roomPage <= 1 ? "disabled" : ""}
            onclick="state.roomPage--; renderAdminRoomsView()"
            class="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold disabled:opacity-40 cursor-pointer">
            ← Trước
          </button>
          <button type="button" ${state.roomPage >= totalPages ? "disabled" : ""}
            onclick="state.roomPage++; renderAdminRoomsView()"
            class="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold disabled:opacity-40 cursor-pointer">
            Tiếp →
          </button>
        </div>
      </div>
    </div>
  `;
}

// Modal Xác nhận xóa phòng ("Bạn có chắc chắn muốn xóa phòng [Tên phòng] không?")
function openConfirmDeleteRoomModal(roomId, roomNumber) {
  openModal(
    "Xác nhận xóa phòng trọ",
    `
      <div class="space-y-4">
        <div class="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm font-medium">
          ⚠️ <b>Bạn có chắc chắn muốn xóa phòng Phòng ${escapeHtml(roomNumber)} không?</b>
        </div>
        <p class="text-xs text-slate-600">
          Hành động này sẽ xóa Phòng <b>${escapeHtml(roomNumber)}</b> và tài khoản đăng nhập tương ứng của phòng khỏi hệ thống.
        </p>
        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy bỏ</button>
          <button type="button" onclick="confirmDeleteRoom(${roomId}, '${escapeHtml(roomNumber)}')"
            class="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-bold cursor-pointer">
            Chắc chắn xóa Phòng ${escapeHtml(roomNumber)}
          </button>
        </div>
      </div>
    `
  );
}

async function confirmDeleteRoom(roomId, roomNumber) {
  try {
    await apiFetch(`/rooms/${roomId}`, { method: "DELETE" });
    closeModal();
    showToast10s(
      `Đã xóa Phòng ${roomNumber}`,
      `Phòng ${roomNumber} đã được xóa khỏi hệ thống thành công.`,
      "INFO"
    );
    await loadAndRenderAdminRooms();
  } catch (err) {
    alert(err.message);
  }
}

// Modal Quy trình Khách chuyển đi ("Khách trả phòng / Reset tài khoản")
function openCheckoutRoomModal(roomId, roomNumber, tenantName) {
  openModal(
    `Khách trả phòng & Reset tài khoản - Phòng ${roomNumber}`,
    `
      <form onsubmit="submitCheckoutRoom(event, ${roomId}, '${escapeHtml(roomNumber)}')" class="space-y-4">
        <div class="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-1.5 leading-relaxed">
          <div class="font-bold text-sm">🔒 Quy trình Bảo mật khi Khách trả phòng (Check-out):</div>
          <div>1. Hệ thống lập tức <b>đăng xuất toàn bộ các thiết bị</b> đang đăng nhập vào tài khoản Phòng <b>${escapeHtml(roomNumber)}</b> (Invalidate JWT Token Version).</div>
          <div>2. Cho phép Chủ trọ <b>đặt lại mật khẩu mới</b> để khách cũ (${escapeHtml(tenantName)}) không thể đăng nhập lại.</div>
          <div>3. Chuyển toàn bộ hồ sơ của khách thuê vừa chuyển đi sang mục <b>Lưu trữ tạm (Archived)</b> với mốc <code>deleted_at</code> và giữ đúng <b>30 ngày (1 tháng)</b> trước khi tự động xóa sạch bằng Cronjob.</div>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Đặt mật khẩu mới cho tài khoản Phòng ${escapeHtml(roomNumber)}</label>
          <input type="text" id="checkout-new-pw" required value="123456"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Ghi chú / Lý do trả phòng</label>
          <textarea id="checkout-reason" rows="2"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm">Khách thuê kết thúc hợp đồng, đã bàn giao phòng và thanh toán công nợ.</textarea>
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold cursor-pointer">
            🔑 Xác nhận Trả phòng, Thu hồi Phiên & Lưu trữ 30 ngày
          </button>
        </div>
      </form>
    `
  );
}

async function submitCheckoutRoom(e, roomId, roomNumber) {
  e.preventDefault();
  const newPassword = document.getElementById("checkout-new-pw").value.trim();
  const reason = document.getElementById("checkout-reason").value.trim();

  try {
    const res = await apiFetch(`/rooms/${roomId}/checkout`, {
      method: "POST",
      body: JSON.stringify({
        new_password: newPassword,
        checkout_reason: reason,
      }),
    });
    closeModal();
    showToast10s(
      `Đã trả phòng & Reset TK Phòng ${roomNumber}`,
      res.message,
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminRooms();
  } catch (err) {
    alert(err.message);
  }
}

function openAddRoomModal() {
  openModal(
    "Thêm Phòng Trọ Mới (Tự động sinh tài khoản [Tầng].[Thứ tự])",
    `
      <form onsubmit="submitAddRoom(event)" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Số tầng</label>
            <input type="number" id="add-room-floor" required min="1" value="3" oninput="updateAutoRoomNum()"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Số thứ tự phòng trong tầng</label>
            <input type="number" id="add-room-seq" required min="1" value="6" oninput="updateAutoRoomNum()"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Mã phòng & Tên đăng nhập</label>
            <input type="text" id="add-room-num" required value="3.6"
              class="w-full px-3 py-2 rounded-xl border border-teal-500 bg-teal-50/40 font-mono-code font-bold text-sm" />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Giá thuê cơ bản (VNĐ/tháng)</label>
            <input type="number" id="add-room-price" required min="0" step="50000" value="2000000"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Diện tích (m²)</label>
            <input type="number" id="add-room-area" required min="5" step="0.5" value="22"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Mật khẩu mặc định</label>
            <input type="text" id="add-room-pw" required value="123456"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí gửi xe (đ)</label>
            <input type="number" id="add-room-parking" value="100000" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí Wifi (đ)</label>
            <input type="number" id="add-room-wifi" value="50000" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí rác/vệ sinh (đ)</label>
            <input type="number" id="add-room-trash" value="30000" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí bảo trì ĐN (đ)</label>
            <input type="number" id="add-room-maint" value="20000" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            Tạo Phòng & Sinh Tài Khoản
          </button>
        </div>
      </form>
    `
  );
}

function updateAutoRoomNum() {
  const fl = document.getElementById("add-room-floor")?.value || 1;
  const seq = document.getElementById("add-room-seq")?.value || 1;
  const numInput = document.getElementById("add-room-num");
  if (numInput) numInput.value = `${fl}.${seq}`;
}

async function submitAddRoom(e) {
  e.preventDefault();
  try {
    const payload = {
      floor: Number(document.getElementById("add-room-floor").value),
      room_seq: Number(document.getElementById("add-room-seq").value),
      room_number: document.getElementById("add-room-num").value.trim(),
      price: Number(document.getElementById("add-room-price").value),
      area: Number(document.getElementById("add-room-area").value),
      default_password: document.getElementById("add-room-pw").value.trim(),
      parking_fee: Number(document.getElementById("add-room-parking").value),
      wifi_fee: Number(document.getElementById("add-room-wifi").value),
      trash_fee: Number(document.getElementById("add-room-trash").value),
      maintenance_fee: Number(document.getElementById("add-room-maint").value),
    };
    const r = await apiFetch("/rooms", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    closeModal();
    showToast10s(
      `Đã tạo Phòng ${r.room_number}`,
      `Hệ thống đã tự động sinh tài khoản đăng nhập '${r.room_number}' cho phòng mới.`,
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminRooms();
  } catch (err) {
    alert(err.message);
  }
}

function openAddFloorModal() {
  openModal(
    "Thêm Tầng Mới & Tự Động Sinh Tài Khoản Phòng",
    `
      <form onsubmit="submitAddFloor(event)" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Số tầng mới (VD: Tầng 4)</label>
            <input type="number" id="floor-num" required min="1" max="50" value="4"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Số lượng phòng trong tầng</label>
            <input type="number" id="floor-count" required min="1" max="20" value="5"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Giá thuê cơ bản mặc định (VNĐ)</label>
            <input type="number" id="floor-price" required value="2000000"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Mật khẩu mặc định các phòng</label>
            <input type="text" id="floor-pw" required value="123456"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            Tạo Tầng Mới
          </button>
        </div>
      </form>
    `
  );
}

async function submitAddFloor(e) {
  e.preventDefault();
  try {
    const floor = Number(document.getElementById("floor-num").value);
    const num_rooms = Number(document.getElementById("floor-count").value);
    const base_price = Number(document.getElementById("floor-price").value);
    const default_password = document.getElementById("floor-pw").value.trim();

    const created = await apiFetch("/rooms/add-floor", {
      method: "POST",
      body: JSON.stringify({ floor, num_rooms, base_price, area: 22, default_password }),
    });
    closeModal();
    showToast10s(
      `Đã thêm Tầng ${floor}`,
      `Đã khởi tạo ${created.length} phòng mới (${floor}.1 → ${floor}.${num_rooms}) kèm tài khoản đăng nhập.`,
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminRooms();
  } catch (err) {
    alert(err.message);
  }
}

function openEditRoomModal(roomId) {
  const r = state.rooms.find((x) => x.id === roomId);
  if (!r) return;

  openModal(
    `Chỉnh sửa Giá thuê & Phụ phí - Phòng ${r.room_number}`,
    `
      <form onsubmit="submitEditRoom(event, ${r.id})" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Giá thuê cơ bản (VNĐ/tháng)</label>
            <input type="number" id="edit-room-price" required value="${r.price}"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code font-bold text-teal-800" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Trạng thái phòng</label>
            <select id="edit-room-status" class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm bg-white">
              <option value="AVAILABLE" ${r.status === "AVAILABLE" ? "selected" : ""}>AVAILABLE (Phòng trống)</option>
              <option value="RENTED" ${r.status === "RENTED" ? "selected" : ""}>RENTED (Đang thuê)</option>
              <option value="MAINTENANCE" ${r.status === "MAINTENANCE" ? "selected" : ""}>MAINTENANCE (Đang bảo trì)</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Đơn giá điện (đ/kWh)</label>
            <input type="number" id="edit-room-elec" value="${r.electricity_rate}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Đơn giá nước (đ/m³)</label>
            <input type="number" id="edit-room-water" value="${r.water_rate}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí gửi xe (đ/tháng)</label>
            <input type="number" id="edit-room-parking" value="${r.parking_fee}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí Wifi (đ/tháng)</label>
            <input type="number" id="edit-room-wifi" value="${r.wifi_fee}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phí rác/vệ sinh (đ/tháng)</label>
            <input type="number" id="edit-room-trash" value="${r.trash_fee}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Bảo trì điện nước (đ)</label>
            <input type="number" id="edit-room-maint" value="${r.maintenance_fee}" class="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono-code" />
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Mô tả phòng</label>
          <input type="text" id="edit-room-desc" value="${escapeHtml(r.description || "")}"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            Lưu thay đổi
          </button>
        </div>
      </form>
    `
  );
}

async function submitEditRoom(e, roomId) {
  e.preventDefault();
  try {
    const payload = {
      price: Number(document.getElementById("edit-room-price").value),
      status: document.getElementById("edit-room-status").value,
      electricity_rate: Number(document.getElementById("edit-room-elec").value),
      water_rate: Number(document.getElementById("edit-room-water").value),
      parking_fee: Number(document.getElementById("edit-room-parking").value),
      wifi_fee: Number(document.getElementById("edit-room-wifi").value),
      trash_fee: Number(document.getElementById("edit-room-trash").value),
      maintenance_fee: Number(document.getElementById("edit-room-maint").value),
      description: document.getElementById("edit-room-desc").value,
    };
    const updated = await apiFetch(`/rooms/${roomId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    closeModal();
    showToast10s(
      `Đã cập nhật Phòng ${updated.room_number}`,
      `Giá thuê cơ bản mới: ${fmtVND(updated.price)}/tháng.`,
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminRooms();
  } catch (err) {
    alert(err.message);
  }
}

function openRoomQuickDetailModal(roomId) {
  const r = state.rooms.find((x) => x.id === roomId);
  if (!r) return;
  openEditRoomModal(roomId);
}

// ==========================================================================
// HỢP ĐỒNG THUÊ NHÀ CHUẨN PHÁP LUẬT VIỆT NAM (XEM / TẠO / IN / XUẤT PDF)
// ==========================================================================

async function openRoomContractModal(roomId) {
  const r = state.rooms.find((x) => x.id === roomId);
  try {
    const contract = await apiFetch(`/contracts/by-room/${roomId}`);
    renderLegalContractModal(contract, r);
  } catch (_) {
    // Phòng chưa có hợp đồng -> Mở form Tạo hợp đồng mới
    openCreateContractModal(r);
  }
}

function openCreateContractModal(room) {
  if (!room) return;
  openModal(
    `Tạo Hợp Đồng Thuê Nhà Pháp Lý Việt Nam - Phòng ${room.room_number}`,
    `
      <form onsubmit="submitCreateContract(event, ${room.id})" class="space-y-4">
        <div class="p-3.5 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900">
          Hệ thống tự động điền thông tin từ Chủ trọ (Bên A), Khách thuê Phòng <b>${escapeHtml(room.room_number)}</b> (Bên B: <b>${escapeHtml(room.tenant_name || "Tài khoản Phòng " + room.room_number)}</b>) và đơn giá của phòng.
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Ngày bắt đầu hợp đồng</label>
            <input type="date" id="ct-start" required value="2026-11-01"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Ngày kết thúc hợp đồng</label>
            <input type="date" id="ct-end" required value="2027-11-01"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Giá thuê phòng (VNĐ/tháng)</label>
            <input type="number" id="ct-rent" required value="${room.price}"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Tiền đặt cọc (VNĐ)</label>
            <input type="number" id="ct-deposit" required value="${room.price}"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            📜 Ký & Ban hành Hợp đồng Pháp lý VN
          </button>
        </div>
      </form>
    `
  );
}

async function submitCreateContract(e, roomId) {
  e.preventDefault();
  try {
    const payload = {
      room_id: roomId,
      start_date: document.getElementById("ct-start").value,
      end_date: document.getElementById("ct-end").value,
      monthly_rent: Number(document.getElementById("ct-rent").value),
      deposit_amount: Number(document.getElementById("ct-deposit").value),
    };
    const contract = await apiFetch("/contracts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast10s(
      `Đã tạo Hợp đồng ${contract.contract_code}`,
      "Hợp đồng thuê nhà chuẩn pháp luật Việt Nam đã được ban hành.",
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminRooms();
    renderLegalContractModal(contract);
  } catch (err) {
    alert(err.message);
  }
}

function buildVietnameseContractHtml(c) {
  const roomNum = c.room?.room_number || c.room_id;
  const floorNum = c.room?.floor || 1;
  const areaVal = c.room?.area || 22;
  const t = c.tenant || {};
  const pdfUrl = `${API_BASE}/contracts/${c.id}/pdf?token=${encodeURIComponent(state.token)}`;

  return `
    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-100 p-3 rounded-xl">
        <span class="text-xs font-bold text-slate-700">Mã hợp đồng: <code class="font-mono-code text-teal-800">${escapeHtml(c.contract_code)}</code> (${escapeHtml(c.status)})</span>
        <div class="flex items-center gap-2">
          <button type="button" onclick="window.print()"
            class="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-slate-300 text-xs font-bold text-slate-700 cursor-pointer">
            🖨️ In Hợp đồng
          </button>
          <a href="${pdfUrl}" target="_blank"
            class="px-3.5 py-1.5 rounded-lg bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer inline-flex items-center gap-1">
            <span>⬇️ Tải Hợp đồng PDF chuẩn VN</span>
          </a>
        </div>
      </div>

      <div id="printable-area" class="vn-legal-contract text-sm">
        <div class="text-center mb-5">
          <div class="font-bold text-base uppercase">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</div>
          <div class="font-bold text-sm underline underline-offset-4">Độc lập - Tự do - Hạnh phúc</div>
          <div class="mt-4 font-bold text-xl uppercase">HỢP ĐỒNG THUÊ PHÒNG TRỌ</div>
          <div class="text-xs italic mt-0.5">Số: ${escapeHtml(c.contract_code)}</div>
        </div>

        <div class="italic text-xs space-y-1 mb-4">
          <div>- Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24/11/2015 của Quốc hội nước CHXHCN Việt Nam;</div>
          <div>- Căn cứ Luật Nhà ở số 27/2023/QH15 và các văn bản hướng dẫn thi hành;</div>
          <div>- Căn cứ vào nhu cầu thực tế và sự thỏa thuận tự nguyện của hai bên.</div>
        </div>

        <div class="space-y-3 text-justify">
          <div>
            <b>I. BÊN CHO THUÊ PHÒNG TRỌ (Bên A - Chủ trọ):</b><br/>
            - Ông/Bà: <b>${escapeHtml(c.landlord_name || "Nguyễn Minh Hoàng")}</b><br/>
            - Số CCCD: <b>${escapeHtml(c.landlord_cccd || "079085001234")}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Điện thoại: <b>${escapeHtml(c.landlord_phone || "0901234567")}</b><br/>
            - Địa chỉ tòa nhà trọ: ${escapeHtml(c.landlord_address || "Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh")}
          </div>

          <div>
            <b>II. BÊN THUÊ PHÒNG TRỌ (Bên B - Khách thuê):</b><br/>
            - Ông/Bà: <b>${escapeHtml(t.full_name || "................................")}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Giới tính: ${escapeHtml(t.gender || "—")} &nbsp;&nbsp;|&nbsp;&nbsp; Ngày sinh: ${fmtDate(t.birth_date)}<br/>
            - Số CCCD/Định danh: <b>${escapeHtml(t.cccd || "........................")}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Điện thoại: <b>${escapeHtml(t.phone || "........................")}</b><br/>
            - Gmail nhận hóa đơn: <b>${escapeHtml(t.email || "........................")}</b><br/>
            - Quê quán / Thường trú: ${escapeHtml(t.hometown || "................................................")}
          </div>

          <div>
            <b>ĐIỀU 1: ĐỐI TƯỢNG VÀ THỜI HẠN THUÊ PHÒNG</b><br/>
            Bên A đồng ý cho Bên B thuê <b>Phòng số ${escapeHtml(roomNum)} (Tầng ${floorNum})</b>, diện tích <b>${areaVal} m²</b> để ở và sinh hoạt hợp pháp.<br/>
            Thời hạn thuê: Từ ngày <b>${fmtDate(c.start_date)}</b> đến ngày <b>${fmtDate(c.end_date)}</b>.
          </div>

          <div>
            <b>ĐIỀU 2: GIÁ THUÊ, ĐIỆN NƯỚC, PHỤ PHÍ VÀ HẠN THANH TOÁN (NGÀY 10 HẰNG THÁNG)</b><br/>
            - Giá thuê phòng cơ bản: <b>${fmtVND(c.monthly_rent)}/tháng</b>. Tiền đặt cọc: <b>${fmtVND(c.deposit_amount)}</b>.<br/>
            - Tiền điện: <b>${fmtVND(c.electricity_rate)}/kWh</b> (Tính theo chỉ số công tơ riêng: Số mới - Số cũ).<br/>
            - Tiền nước: <b>${fmtVND(c.water_rate)}/m³</b> (Tính theo đồng hồ nước riêng: Số mới - Số cũ).<br/>
            - Phụ phí cố định: Gửi xe <b>${fmtVND(c.parking_fee)}</b>; Wifi <b>${fmtVND(c.wifi_fee)}</b>; Rác/vệ sinh <b>${fmtVND(c.trash_fee)}</b>; Bảo trì điện nước <b>${fmtVND(c.maintenance_fee)}</b> (Tổng phụ phí: <b>${fmtVND(c.service_fee)}/tháng</b>).<br/>
            - <b>Hạn đóng tiền cố định: Ngày ${c.payment_due_day || 10} hằng tháng</b>. Sau 05 ngày kể từ hạn đóng (tức từ <b>Ngày 15 hằng tháng</b>), nếu chưa thanh toán sẽ chuyển sang trạng thái <b>Quá hạn (Nợ)</b>.
          </div>

          <div>
            <b>ĐIỀU 3: QUYỀN VÀ NGHĨA VỤ CỦA HAI BÊN & CAM KẾT CHUNG</b><br/>
            - Bên A đảm bảo bàn giao phòng tốt, tính tiền minh bạch, gửi hóa đơn PDF qua Gmail và phản hồi kịp thời các góp ý (Feedback) của Bên B.<br/>
            - Bên B cam kết khai báo trung thực thông tin CCCD phục vụ đăng ký tạm trú, đóng tiền đúng hạn ngày 10 hằng tháng, giữ gìn an ninh trật tự và vệ sinh chung.
          </div>
        </div>

        <div class="grid grid-cols-2 text-center mt-8 pt-4">
          <div>
            <div class="font-bold">ĐẠI DIỆN BÊN A (CHỦ TRỌ)</div>
            <div class="italic text-xs">(Ký, ghi rõ họ tên)</div>
            <div class="h-16"></div>
            <div class="font-bold">${escapeHtml(c.landlord_name || "Nguyễn Minh Hoàng")}</div>
          </div>
          <div>
            <div class="font-bold">ĐẠI DIỆN BÊN B (KHÁCH THUÊ)</div>
            <div class="italic text-xs">(Ký, ghi rõ họ tên)</div>
            <div class="h-16"></div>
            <div class="font-bold">${escapeHtml(t.full_name || "")}</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderLegalContractModal(contract) {
  openModal(
    `Hợp đồng Thuê nhà Pháp lý Việt Nam - ${contract.contract_code}`,
    buildVietnameseContractHtml(contract)
  );
}

// ==========================================================================
// ADMIN TAB 3: HÓA ĐƠN, GHI ĐIỆN NƯỚC & DUYỆT BILL CHUYỂN KHOẢN (UNC)
// ==========================================================================

async function loadAndRenderAdminBilling() {
  const [invoices, rooms] = await Promise.all([
    apiFetch("/invoices"),
    apiFetch("/rooms"),
  ]);
  state.invoices = invoices;
  state.rooms = rooms;
  renderAdminBillingView();
}

function renderAdminBillingView() {
  const main = document.getElementById("main-content");
  if (!main) return;

  const months = [...new Set(state.invoices.map((i) => i.month_year))].sort().reverse();

  let filtered = state.invoices.filter((inv) => {
    if (state.invoiceMonthFilter !== "ALL" && inv.month_year !== state.invoiceMonthFilter) return false;
    if (state.invoiceStatusFilter !== "ALL" && inv.status !== state.invoiceStatusFilter) return false;
    if (state.invoiceSearch.trim()) {
      const q = state.invoiceSearch.trim().toLowerCase();
      const rNum = (inv.room?.room_number || "").toLowerCase();
      const tName = (inv.tenant?.full_name || "").toLowerCase();
      const code = inv.invoice_code.toLowerCase();
      if (!rNum.includes(q) && !tName.includes(q) && !code.includes(q)) return false;
    }
    return true;
  });

  const totalItems = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / state.invoicePageSize));
  if (state.invoicePage > totalPages) state.invoicePage = totalPages;
  const startIdx = (state.invoicePage - 1) * state.invoicePageSize;
  const pageItems = filtered.slice(startIdx, startIdx + state.invoicePageSize);

  const pendingBills = state.invoices.filter((i) => i.status === "PENDING_APPROVAL");

  main.innerHTML = `
    <div class="space-y-5">
      <!-- Top Bar -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900">Ghi Chỉ số Điện Nước, Lập Hóa đơn & Duyệt Bill Chuyển khoản</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Tự động tính: Tiền phòng + Điện + Nước + Gửi xe + Bảo trì + Wifi + Rác • Gửi thông báo & Hóa đơn PDF vào đúng Gmail từng phòng.
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <button type="button" onclick="openRecordUtilityModal()"
            class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition cursor-pointer">
            ⚡ Ghi chỉ số Điện / Nước
          </button>
          <button type="button" onclick="openGenerateMonthlyModal()"
            class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs transition cursor-pointer">
            🧾 Tự động Tính tiền & Phát hành Hóa đơn Tháng
          </button>
        </div>
      </div>

      <!-- Khối nổi bật: Hóa đơn đang chờ Chủ trọ duyệt ảnh Bill UNC -->
      ${
        pendingBills.length > 0
          ? `
            <div class="bg-amber-50 border-2 border-amber-300 rounded-2xl p-4">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <span class="px-2.5 py-0.5 rounded-full bg-amber-500 text-white text-xs font-bold">CẦN DUYỆT (${pendingBills.length})</span>
                  <h3 class="text-sm font-bold text-amber-900">Danh sách Phòng vừa tải lên ảnh Bill chuyển khoản (UNC) chờ Chủ trọ đối soát</h3>
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${pendingBills
                  .map(
                    (inv) => `
                      <div class="bg-white p-3.5 rounded-xl border border-amber-200 flex items-center justify-between gap-3">
                        <div>
                          <div class="font-bold text-sm text-slate-900">Phòng ${escapeHtml(inv.room?.room_number || inv.room_id)} • ${escapeHtml(inv.tenant?.full_name || "")}</div>
                          <div class="text-xs text-slate-600">Mã HĐ: <code class="font-mono-code">${escapeHtml(inv.invoice_code)}</code> • Kỳ ${escapeHtml(inv.month_year)}</div>
                          <div class="text-sm font-bold text-teal-800 font-mono-code mt-0.5">Số tiền: ${fmtVND(inv.total_amount)}</div>
                        </div>
                        <button type="button" onclick="openReviewBillModal(${inv.id})"
                          class="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold shadow-xs cursor-pointer shrink-0">
                          🔍 Xem Bill & Đối soát
                        </button>
                      </div>
                    `
                  )
                  .join("")}
              </div>
            </div>
          `
          : ""
      }

      <!-- Filters -->
      <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <select onchange="state.invoiceMonthFilter=this.value; state.invoicePage=1; renderAdminBillingView()"
            class="px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold bg-white">
            <option value="ALL" ${state.invoiceMonthFilter === "ALL" ? "selected" : ""}>Tất cả các kỳ tháng</option>
            ${months
              .map(
                (m) =>
                  `<option value="${m}" ${state.invoiceMonthFilter === m ? "selected" : ""}>Kỳ ${m}</option>`
              )
              .join("")}
          </select>

          <select onchange="state.invoiceStatusFilter=this.value; state.invoicePage=1; renderAdminBillingView()"
            class="px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold bg-white">
            <option value="ALL" ${state.invoiceStatusFilter === "ALL" ? "selected" : ""}>Tất cả trạng thái</option>
            <option value="PAID" ${state.invoiceStatusFilter === "PAID" ? "selected" : ""}>✅ Đã đóng (PAID)</option>
            <option value="PENDING_APPROVAL" ${state.invoiceStatusFilter === "PENDING_APPROVAL" ? "selected" : ""}>⏳ Chờ duyệt Bill UNC</option>
            <option value="OVERDUE" ${state.invoiceStatusFilter === "OVERDUE" ? "selected" : ""}>🚨 Quá hạn sau ngày 15 (Nợ)</option>
            <option value="UNPAID" ${state.invoiceStatusFilter === "UNPAID" ? "selected" : ""}>🕒 Chờ thanh toán (Trong hạn)</option>
          </select>

          <input type="text" value="${escapeHtml(state.invoiceSearch)}"
            oninput="state.invoiceSearch=this.value; state.invoicePage=1; renderAdminBillingView()"
            placeholder="Tìm phòng, tên khách, mã hóa đơn..."
            class="px-3.5 py-2 rounded-xl border border-slate-300 text-xs w-64" />
        </div>
        <div class="text-xs text-slate-500">Hiển thị <b>${pageItems.length}</b> / <b>${totalItems}</b> hóa đơn</div>
      </div>

      <!-- Invoices Table -->
      <div class="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                <th class="py-3 px-4">Mã HĐ / Kỳ</th>
                <th class="py-3 px-4">Phòng / Khách thuê</th>
                <th class="py-3 px-4 text-right">Tiền phòng</th>
                <th class="py-3 px-4 text-right">Điện + Nước</th>
                <th class="py-3 px-4 text-right">Phụ phí</th>
                <th class="py-3 px-4 text-right">Tổng tiền</th>
                <th class="py-3 px-4 text-center">Hạn đóng</th>
                <th class="py-3 px-4 text-center">Trạng thái</th>
                <th class="py-3 px-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              ${pageItems
                .map((inv) => {
                  const statusBadge = renderInvoiceStatusBadge(inv.status, inv.payment_method);
                  const rowBg =
                    inv.status === "OVERDUE"
                      ? "bg-red-50/50 hover:bg-red-50"
                      : inv.status === "PENDING_APPROVAL"
                      ? "bg-amber-50/40 hover:bg-amber-50"
                      : "hover:bg-slate-50";
                  const pdfUrl = `${API_BASE}/invoices/${inv.id}/pdf?token=${encodeURIComponent(state.token)}`;

                  return `
                    <tr class="${rowBg} transition">
                      <td class="py-3 px-4">
                        <div class="font-mono-code font-bold text-slate-900">${escapeHtml(inv.invoice_code)}</div>
                        <div class="text-[11px] text-slate-500">Kỳ: ${escapeHtml(inv.month_year)}</div>
                      </td>
                      <td class="py-3 px-4">
                        <div class="font-bold text-slate-900">Phòng ${escapeHtml(inv.room?.room_number || inv.room_id)}</div>
                        <div class="text-[11px] text-slate-500">${escapeHtml(inv.tenant?.full_name || "—")}</div>
                      </td>
                      <td class="py-3 px-4 text-right font-mono-code">${fmtVND(inv.room_charge)}</td>
                      <td class="py-3 px-4 text-right font-mono-code">
                        <div>Đ: ${fmtVND(inv.electricity_charge)} (${inv.electricity_usage}kWh)</div>
                        <div class="text-[11px] text-slate-500">N: ${fmtVND(inv.water_charge)} (${inv.water_usage}m³)</div>
                      </td>
                      <td class="py-3 px-4 text-right font-mono-code">${fmtVND(inv.service_charge)}</td>
                      <td class="py-3 px-4 text-right font-mono-code font-bold text-sm text-teal-800">${fmtVND(inv.total_amount)}</td>
                      <td class="py-3 px-4 text-center">
                        <div class="font-semibold">${fmtDate(inv.due_date)}</div>
                        <div class="text-[10px] text-slate-400">Nợ từ: ${fmtDate(inv.overdue_date)}</div>
                      </td>
                      <td class="py-3 px-4 text-center">${statusBadge}</td>
                      <td class="py-3 px-4 text-right">
                        <div class="flex items-center justify-end gap-1">
                          ${
                            inv.status === "PENDING_APPROVAL"
                              ? `<button type="button" onclick="openReviewBillModal(${inv.id})"
                                  class="px-2.5 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-white font-bold cursor-pointer">
                                  Duyệt Bill
                                </button>`
                              : ""
                          }
                          <button type="button" onclick="openInvoiceDetailModal(${inv.id})"
                            class="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold cursor-pointer">
                            Chi tiết
                          </button>
                          <a href="${pdfUrl}" target="_blank"
                            class="px-2 py-1 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 font-semibold">
                            PDF
                          </a>
                          <button type="button" onclick="sendInvoiceToGmail(${inv.id})"
                            class="px-2 py-1 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200 font-semibold cursor-pointer"
                            title="Gửi Hóa đơn PDF vào Gmail của phòng">
                            Gmail
                          </button>
                        </div>
                      </td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between bg-white px-4 py-3 rounded-2xl border border-slate-200">
        <span class="text-xs text-slate-500">Trang ${state.invoicePage} / ${totalPages}</span>
        <div class="flex items-center gap-1.5">
          <button type="button" ${state.invoicePage <= 1 ? "disabled" : ""}
            onclick="state.invoicePage--; renderAdminBillingView()"
            class="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold disabled:opacity-40 cursor-pointer">
            ← Trước
          </button>
          <button type="button" ${state.invoicePage >= totalPages ? "disabled" : ""}
            onclick="state.invoicePage++; renderAdminBillingView()"
            class="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold disabled:opacity-40 cursor-pointer">
            Tiếp →
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderInvoiceStatusBadge(status, method) {
  if (status === "PAID") {
    return `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 inline-block">ĐÃ ĐÓNG (${escapeHtml(method || "ONLINE")})</span>`;
  }
  if (status === "PENDING_APPROVAL") {
    return `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300 inline-block">CHỜ DUYỆT BILL UNC</span>`;
  }
  if (status === "OVERDUE") {
    return `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-red-600 text-white badge-pulse-red inline-block">QUÁ HẠN (NỢ)</span>`;
  }
  return `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200 inline-block">CHỜ THANH TOÁN</span>`;
}

// Modal Kiểm tra / Đối soát giao dịch Demo & Xác nhận đã thu tiền (Phương thức 2)
function openReviewBillModal(invoiceId) {
  const inv = state.invoices.find((x) => x.id === invoiceId);
  if (!inv) return;

  const roomNum = inv.room?.room_number || inv.room_id;
  openModal(
    `Kiểm tra & Duyệt Bill Chuyển khoản (UNC) - Phòng ${roomNum}`,
    `
      <div class="grid grid-cols-1 md:grid-cols-12 gap-5">
        <div class="md:col-span-6 flex flex-col items-center bg-slate-50 p-4 rounded-2xl border border-slate-200">
          <p class="text-xs font-bold text-slate-600 mb-2">Ảnh chụp màn hình Bill (UNC) từ Khách thuê:</p>
          ${
            inv.bill_image_url
              ? `<img src="${inv.bill_image_url}" alt="Bill UNC" class="max-h-96 rounded-xl shadow border border-slate-200 object-contain" />`
              : `<div class="p-10 text-xs text-slate-400">Không có ảnh đính kèm</div>`
          }
        </div>

        <div class="md:col-span-6 flex flex-col justify-between space-y-4">
          <div class="space-y-3">
            <div class="p-3.5 rounded-xl bg-teal-50 border border-teal-200 text-xs space-y-1">
              <div class="font-bold text-sm text-teal-900">Thông tin Hóa đơn đối chiếu:</div>
              <div>• Mã hóa đơn: <b class="font-mono-code">${escapeHtml(inv.invoice_code)}</b> (Kỳ ${escapeHtml(inv.month_year)})</div>
              <div>• Phòng: <b>Phòng ${escapeHtml(roomNum)}</b> • Khách: <b>${escapeHtml(inv.tenant?.full_name || "")}</b></div>
              <div>• Gmail nhận biên lai PDF: <b>${escapeHtml(inv.tenant?.email || "")}</b></div>
              <div class="text-base font-bold text-teal-800 font-mono-code pt-1">Số tiền cần thu: ${fmtVND(inv.total_amount)}</div>
            </div>

            <div id="reconcile-result-box" class="p-3.5 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-600">
              Bấm nút <b>"1. Kiểm tra / Đối soát giao dịch Demo"</b> bên dưới để hệ thống tự động kiểm tra biến động số dư tài khoản ngân hàng của Chủ trọ.
            </div>

            <button type="button" onclick="runReconcileDemo(${inv.id})"
              class="w-full py-2.5 px-4 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold shadow-xs transition cursor-pointer">
              🔄 1. Kiểm tra / Đối soát giao dịch Demo (Xác nhận tiền vào TK)
            </button>
          </div>

          <div class="pt-4 border-t border-slate-200 space-y-2">
            <button type="button" onclick="confirmApproveBill(${inv.id})"
              class="w-full py-3 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold shadow-md transition cursor-pointer">
              ✅ 2. Xác nhận đã thu tiền & Gửi Biên lai PDF qua Gmail
            </button>
            <button type="button" onclick="closeModal()"
              class="w-full py-2 px-4 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">
              Đóng cửa sổ
            </button>
          </div>
        </div>
      </div>
    `
  );
}

async function runReconcileDemo(invoiceId) {
  const box = document.getElementById("reconcile-result-box");
  try {
    const res = await apiFetch(`/invoices/${invoiceId}/reconcile`, { method: "POST" });
    if (box) {
      box.className = "p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-xs text-emerald-900 space-y-1";
      box.innerHTML = `
        <div class="font-bold text-emerald-800">✓ ĐỐI SOÁT NGÂN HÀNG THÀNH CÔNG!</div>
        <div>• Ngân hàng nhận: <b>${escapeHtml(res.bank_name)}</b></div>
        <div>• Nội dung CK: <code class="font-mono-code font-bold">${escapeHtml(res.transfer_content)}</code></div>
        <div>• Mã tham chiếu: <code class="font-mono-code font-bold">${escapeHtml(res.transaction_ref)}</code></div>
        <div>• Số tiền khớp 100%: <b class="font-mono-code">${fmtVND(res.matched_amount)}</b></div>
      `;
    }
  } catch (err) {
    alert(err.message);
  }
}

async function confirmApproveBill(invoiceId) {
  try {
    const updated = await apiFetch(`/invoices/${invoiceId}/approve-bill`, {
      method: "POST",
      body: JSON.stringify({ is_reconciled: true, notes: "Đã đối soát UNC và xác nhận thu tiền" }),
    });
    closeModal();
    showToast10s(
      `Đã xác nhận thu tiền ${updated.invoice_code}`,
      `Hóa đơn đã chuyển sang ĐÃ ĐÓNG (PAID) và tự động gửi Biên lai PDF qua Gmail của phòng.`,
      "PAYMENT_SUCCESS"
    );
    await fetchNotifications(true);
    await loadAndRenderAdminBilling();
  } catch (err) {
    alert(err.message);
  }
}

function openRecordUtilityModal() {
  const rentedRooms = state.rooms.filter((r) => r.status === "RENTED");
  openModal(
    "Ghi Chỉ Số Điện / Nước Hằng Tháng",
    `
      <form onsubmit="submitRecordUtility(event)" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Chọn Phòng</label>
            <select id="util-room-id" required onchange="loadLastReadingForRoom(this.value)"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm bg-white">
              ${rentedRooms
                .map(
                  (r) =>
                    `<option value="${r.id}">Phòng ${escapeHtml(r.room_number)} - ${escapeHtml(r.tenant_name || "")}</option>`
                )
                .join("")}
            </select>
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Kỳ tháng (YYYY-MM)</label>
            <input type="text" id="util-month" required value="2026-11" pattern="\\d{4}-\\d{2}"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Điện số cũ (kWh)</label>
            <input type="number" id="util-old-e" required min="0" value="200"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-teal-800 mb-1">Điện số mới (kWh)</label>
            <input type="number" id="util-new-e" required min="0" value="285"
              class="w-full px-3 py-2 rounded-xl border border-teal-500 text-sm font-mono-code font-bold" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Nước số cũ (m³)</label>
            <input type="number" id="util-old-w" required min="0" value="19"
              class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
          </div>
          <div>
            <label class="block text-xs font-bold text-teal-800 mb-1">Nước số mới (m³)</label>
            <input type="number" id="util-new-w" required min="0" value="24"
              class="w-full px-3 py-2 rounded-xl border border-teal-500 text-sm font-mono-code font-bold" />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            Lưu chỉ số Điện Nước
          </button>
        </div>
      </form>
    `
  );
  if (rentedRooms.length > 0) {
    loadLastReadingForRoom(rentedRooms[0].id);
  }
}

async function loadLastReadingForRoom(roomId) {
  try {
    const last = await apiFetch(`/utilities/last-reading/${roomId}`);
    if (last) {
      document.getElementById("util-old-e").value = last.new_electricity;
      document.getElementById("util-new-e").value = last.new_electricity + 80;
      document.getElementById("util-old-w").value = last.new_water;
      document.getElementById("util-new-w").value = last.new_water + 4;
    }
  } catch (_) {}
}

async function submitRecordUtility(e) {
  e.preventDefault();
  try {
    const payload = {
      room_id: Number(document.getElementById("util-room-id").value),
      month_year: document.getElementById("util-month").value.trim(),
      old_electricity: Number(document.getElementById("util-old-e").value),
      new_electricity: Number(document.getElementById("util-new-e").value),
      old_water: Number(document.getElementById("util-old-w").value),
      new_water: Number(document.getElementById("util-new-w").value),
    };
    const res = await apiFetch("/utilities", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    closeModal();
    showToast10s(
      `Đã ghi Điện Nước Phòng ${res.room_number}`,
      `Kỳ ${res.month_year}: Tiêu thụ ${res.electricity_usage} kWh điện & ${res.water_usage} m³ nước.`,
      "PAYMENT_SUCCESS"
    );
  } catch (err) {
    alert(err.message);
  }
}

function openGenerateMonthlyModal() {
  openModal(
    "Tự Động Tính Tiền & Phát Hành Hóa Đơn Hằng Tháng",
    `
      <form onsubmit="submitGenerateMonthly(event)" class="space-y-4">
        <div class="p-3.5 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900 space-y-1">
          <div class="font-bold">⚡ Luồng tích hợp tự động:</div>
          <div>Lấy Hợp đồng đang hiệu lực + Chỉ số điện nước (Số mới - Số cũ) + Phụ phí phòng (Gửi xe, Rác, Wifi, Bảo trì) → Tính tổng tiền → Tạo Hóa đơn (Hạn đóng: <b>Ngày 10 hằng tháng</b>) → Gửi thông báo & Gmail kèm PDF cho đúng từng phòng!</div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Kỳ thu tiền (YYYY-MM)</label>
            <input type="text" id="gen-month" required value="2026-11" pattern="\\d{4}-\\d{2}"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code font-bold" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Hạn thanh toán cố định (Ngày 10)</label>
            <input type="date" id="gen-due" required value="2026-11-10"
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
        </div>

        <label class="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <input type="checkbox" id="gen-send-email" checked class="rounded text-teal-700" />
          <span>Tự động gửi Hóa đơn PDF vào Gmail của từng phòng sau khi lập</span>
        </label>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer">
            🚀 Phát hành Hóa đơn & Gửi Gmail
          </button>
        </div>
      </form>
    `
  );
}

async function submitGenerateMonthly(e) {
  e.preventDefault();
  try {
    const month_year = document.getElementById("gen-month").value.trim();
    const due_date = document.getElementById("gen-due").value;
    const send_email = document.getElementById("gen-send-email").checked;

    const list = await apiFetch("/invoices/generate-monthly", {
      method: "POST",
      body: JSON.stringify({ month_year, due_date, send_email }),
    });
    closeModal();
    showToast10s(
      `Đã phát hành ${list.length} hóa đơn kỳ ${month_year}`,
      "Hệ thống đã tính tiền tự động và gửi thông báo + Hóa đơn PDF vào Gmail từng phòng.",
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminBilling();
  } catch (err) {
    alert(err.message);
  }
}

async function sendInvoiceToGmail(invoiceId) {
  try {
    const res = await apiFetch(`/invoices/${invoiceId}/send-email`, { method: "POST" });
    showToast10s("Đã gửi Hóa đơn PDF qua Gmail", res.message, "PAYMENT_SUCCESS");
  } catch (err) {
    alert(err.message);
  }
}

function openInvoiceDetailModal(invoiceId) {
  const inv = state.invoices.find((x) => x.id === invoiceId);
  if (!inv) return;
  const pdfUrl = `${API_BASE}/invoices/${inv.id}/pdf?token=${encodeURIComponent(state.token)}`;
  const roomNum = inv.room?.room_number || inv.room_id;

  openModal(
    `Chi tiết Hóa đơn ${inv.invoice_code} - Phòng ${roomNum}`,
    `
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-100 p-3 rounded-xl">
          <div>${renderInvoiceStatusBadge(inv.status, inv.payment_method)}</div>
          <div class="flex items-center gap-2">
            <button type="button" onclick="window.print()"
              class="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs font-bold text-slate-700 cursor-pointer">
              🖨️ In Hóa đơn
            </button>
            <a href="${pdfUrl}" target="_blank"
              class="px-3.5 py-1.5 rounded-lg bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold">
              ⬇️ Tải Hóa đơn PDF
            </a>
          </div>
        </div>

        <div id="printable-area" class="p-6 bg-white rounded-xl border border-slate-200 space-y-4 text-xs">
          <div class="text-center border-b border-slate-200 pb-3">
            <div class="font-bold text-base text-teal-900">HỆ THỐNG NHÀ TRỌ MINH HOÀNG</div>
            <div class="text-slate-500">Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh</div>
            <div class="text-lg font-bold text-slate-900 mt-2">HÓA ĐƠN TIỀN PHÒNG & DỊCH VỤ KỲ ${escapeHtml(inv.month_year)}</div>
            <div class="font-mono-code text-slate-600">Mã HĐ: ${escapeHtml(inv.invoice_code)} • Hạn đóng cố định: ${fmtDate(inv.due_date)} (Ngày 10 hằng tháng)</div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div><b>Phòng:</b> Phòng ${escapeHtml(roomNum)}</div>
            <div><b>Khách thuê:</b> ${escapeHtml(inv.tenant?.full_name || "—")}</div>
            <div><b>Số điện thoại:</b> ${escapeHtml(inv.tenant?.phone || "—")}</div>
            <div><b>Gmail nhận PDF:</b> ${escapeHtml(inv.tenant?.email || "—")}</div>
          </div>

          <table class="w-full border-collapse border border-slate-300 text-xs">
            <thead>
              <tr class="bg-teal-700 text-white">
                <th class="p-2 border border-slate-300 text-left">STT</th>
                <th class="p-2 border border-slate-300 text-left">Khoản mục</th>
                <th class="p-2 border border-slate-300 text-left">Chi tiết cách tính</th>
                <th class="p-2 border border-slate-300 text-right">Thành tiền</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="p-2 border border-slate-200">1</td>
                <td class="p-2 border border-slate-200 font-semibold">Tiền phòng cơ bản</td>
                <td class="p-2 border border-slate-200">Tiền thuê Phòng ${escapeHtml(roomNum)} kỳ ${escapeHtml(inv.month_year)}</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.room_charge)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">2</td>
                <td class="p-2 border border-slate-200 font-semibold">Tiền điện</td>
                <td class="p-2 border border-slate-200">(${inv.new_electricity} - ${inv.old_electricity}) = ${inv.electricity_usage} kWh × ${fmtVND(inv.electricity_rate)}</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.electricity_charge)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">3</td>
                <td class="p-2 border border-slate-200 font-semibold">Tiền nước</td>
                <td class="p-2 border border-slate-200">(${inv.new_water} - ${inv.old_water}) = ${inv.water_usage} m³ × ${fmtVND(inv.water_rate)}</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.water_charge)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">4</td>
                <td class="p-2 border border-slate-200">Tiền gửi xe</td>
                <td class="p-2 border border-slate-200">Phụ phí gửi xe cố định theo phòng</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.parking_fee)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">5</td>
                <td class="p-2 border border-slate-200">Tiền bảo trì điện nước</td>
                <td class="p-2 border border-slate-200">Bảo trì hệ thống điện nước chung</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.maintenance_fee)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">6</td>
                <td class="p-2 border border-slate-200">Tiền Internet / Wifi</td>
                <td class="p-2 border border-slate-200">Cáp quang tốc độ cao theo phòng</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.wifi_fee)}</td>
              </tr>
              <tr>
                <td class="p-2 border border-slate-200">7</td>
                <td class="p-2 border border-slate-200">Tiền vệ sinh / rác</td>
                <td class="p-2 border border-slate-200">Thu gom rác sinh hoạt hằng ngày</td>
                <td class="p-2 border border-slate-200 text-right font-mono-code">${fmtVND(inv.trash_fee)}</td>
              </tr>
              <tr class="bg-teal-50 font-bold text-sm text-teal-900">
                <td colspan="3" class="p-2.5 border border-slate-300">TỔNG CỘNG PHẢI THANH TOÁN</td>
                <td class="p-2.5 border border-slate-300 text-right font-mono-code">${fmtVND(inv.total_amount)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `
  );
}

// ==========================================================================
// ADMIN TAB 4: KIỂM TRA CÔNG NỢ (QUÁ HẠN SAU NGÀY 15 HẰNG THÁNG)
// ==========================================================================

async function loadAndRenderAdminDebt() {
  const overdue = await apiFetch("/stats/overdue");
  state.overdueList = overdue;
  renderAdminDebtView();
}

function renderAdminDebtView() {
  const main = document.getElementById("main-content");
  if (!main) return;

  const months = [...new Set(state.overdueList.map((i) => i.month_year))].sort().reverse();
  const filtered = state.overdueList.filter(
    (i) => state.debtMonthFilter === "ALL" || i.month_year === state.debtMonthFilter
  );
  const totalDebt = filtered.reduce((acc, x) => acc + Number(x.total_amount || 0), 0);
  const distinctRooms = new Set(filtered.map((x) => x.room_number)).size;

  main.innerHTML = `
    <div class="space-y-5">
      <div class="bg-red-50 border-2 border-red-300 p-5 rounded-2xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <span class="px-2.5 py-0.5 rounded-full bg-red-600 text-white text-xs font-bold badge-pulse-red">CẢNH BÁO CÔNG NỢ QUÁ HẠN</span>
            <h2 class="text-lg font-bold text-red-900">Kiểm tra Công nợ theo Phòng & Tháng (Quá hạn sau ngày 15)</h2>
          </div>
          <p class="text-xs text-red-800 mt-1">
            Quy định: Hạn đóng tiền cố định là <b>Ngày 10 hằng tháng</b>. Sau 5 ngày (từ <b>Ngày 15 hằng tháng</b>), các hóa đơn chưa đóng tự động chuyển sang <b>Quá hạn (Nợ)</b> và đánh dấu đỏ.
          </p>
        </div>

        <div class="flex items-center gap-4 bg-white p-3.5 rounded-xl border border-red-200 shrink-0">
          <div>
            <div class="text-[11px] text-slate-500 uppercase font-semibold">Số phòng đang nợ</div>
            <div class="text-lg font-bold text-red-600 font-mono-code">${distinctRooms} phòng (${filtered.length} kỳ)</div>
          </div>
          <div class="border-l border-slate-200 pl-4">
            <div class="text-[11px] text-slate-500 uppercase font-semibold">Tổng tiền nợ quá hạn</div>
            <div class="text-lg font-bold text-red-600 font-mono-code">${fmtVND(totalDebt)}</div>
          </div>
        </div>
      </div>

      <!-- Filter by Month -->
      <div class="bg-white p-4 rounded-2xl border border-slate-200 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-slate-700">Lọc theo tháng nợ:</span>
          <select onchange="state.debtMonthFilter=this.value; renderAdminDebtView()"
            class="px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-semibold bg-white">
            <option value="ALL" ${state.debtMonthFilter === "ALL" ? "selected" : ""}>Tất cả các tháng đang nợ</option>
            ${months
              .map(
                (m) =>
                  `<option value="${m}" ${state.debtMonthFilter === m ? "selected" : ""}>Tháng ${m}</option>`
              )
              .join("")}
          </select>
        </div>
      </div>

      <!-- Debt Table -->
      <div class="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-red-600 text-white uppercase">
                <th class="py-3 px-4">Phòng đang nợ</th>
                <th class="py-3 px-4">Tháng nợ</th>
                <th class="py-3 px-4">Mã hóa đơn</th>
                <th class="py-3 px-4">Khách thuê & Liên hệ</th>
                <th class="py-3 px-4 text-center">Hạn đóng (Mùng 10)</th>
                <th class="py-3 px-4 text-center">Số ngày quá hạn</th>
                <th class="py-3 px-4 text-right">Số tiền nợ</th>
                <th class="py-3 px-4 text-right">Hành động</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-red-100">
              ${
                filtered.length === 0
                  ? `<tr><td colspan="8" class="p-8 text-center text-slate-400">Không có khoản nợ quá hạn nào.</td></tr>`
                  : filtered
                      .map(
                        (item) => `
                          <tr class="bg-red-50/40 hover:bg-red-50 transition">
                            <td class="py-3.5 px-4">
                              <span class="px-2.5 py-1 rounded-lg bg-red-600 text-white font-mono-code font-bold text-sm">
                                Phòng ${escapeHtml(item.room_number)}
                              </span>
                            </td>
                            <td class="py-3.5 px-4 font-mono-code font-bold text-red-700 text-sm">Kỳ ${escapeHtml(item.month_year)}</td>
                            <td class="py-3.5 px-4 font-mono-code">${escapeHtml(item.invoice_code)}</td>
                            <td class="py-3.5 px-4">
                              <div class="font-bold text-slate-900">${escapeHtml(item.tenant_name || "—")}</div>
                              <div class="text-[11px] text-slate-600">SĐT: ${escapeHtml(item.tenant_phone || "—")} • ${escapeHtml(item.tenant_email || "")}</div>
                            </td>
                            <td class="py-3.5 px-4 text-center font-mono-code">${fmtDate(item.due_date)}</td>
                            <td class="py-3.5 px-4 text-center">
                              <span class="px-2 py-0.5 rounded bg-red-100 text-red-800 font-bold">Quá hạn ${item.days_overdue} ngày</span>
                            </td>
                            <td class="py-3.5 px-4 text-right font-mono-code font-bold text-sm text-red-700">${fmtVND(item.total_amount)}</td>
                            <td class="py-3.5 px-4 text-right">
                              <div class="flex items-center justify-end gap-1.5">
                                <button type="button" onclick="remindOverdueRoom(${item.id})"
                                  class="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-bold cursor-pointer">
                                  🔔 Gửi Nhắc nợ (Toast + Gmail)
                                </button>
                                <button type="button" onclick="confirmApproveBill(${item.id})"
                                  class="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold cursor-pointer">
                                  ✓ Thu tiền
                                </button>
                              </div>
                            </td>
                          </tr>
                        `
                      )
                      .join("")
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

async function remindOverdueRoom(invoiceId) {
  try {
    const res = await apiFetch(`/stats/overdue/${invoiceId}/remind`, { method: "POST" });
    showToast10s("Đã gửi Nhắc nợ & Gmail", res.message, "OVERDUE_ALERT");
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// ADMIN TAB 5: HỒ SƠ KHÁCH THUÊ & LƯU TRỮ TẠM 30 NGÀY (SOFT DELETE / ARCHIVE)
// ==========================================================================

async function loadAndRenderAdminTenants() {
  const [tenants, archived] = await Promise.all([
    apiFetch("/tenants"),
    apiFetch("/tenants/archived"),
  ]);
  state.tenants = tenants;
  state.archivedTenants = archived;
  renderAdminTenantsView();
}

function renderAdminTenantsView() {
  const main = document.getElementById("main-content");
  if (!main) return;

  main.innerHTML = `
    <div class="space-y-5">
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900">Quản lý Hồ sơ Người thuê & Kho Lưu trữ tạm 30 Ngày</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Xem toàn bộ thông tin CCCD, Quê quán, Ngày sinh, Gmail của từng phòng • Hồ sơ khách cũ sau khi trả phòng được giữ đúng 30 ngày trước khi tự động xóa sạch.
          </p>
        </div>

        <div class="flex items-center gap-2">
          <button type="button" onclick="state.tenantSubTab='active'; renderAdminTenantsView()"
            class="px-3.5 py-2 rounded-xl text-xs font-bold cursor-pointer transition ${
              state.tenantSubTab === "active"
                ? "bg-teal-700 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }">
            👤 Tài khoản Phòng & Hồ sơ Hiện tại (${state.tenants.length})
          </button>
          <button type="button" onclick="state.tenantSubTab='archived'; renderAdminTenantsView()"
            class="px-3.5 py-2 rounded-xl text-xs font-bold cursor-pointer transition ${
              state.tenantSubTab === "archived"
                ? "bg-amber-600 text-white"
                : "bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100"
            }">
            🗄️ Lưu trữ tạm 30 ngày (${state.archivedTenants.length})
          </button>
        </div>
      </div>

      ${
        state.tenantSubTab === "active"
          ? `
            <div class="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr class="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                      <th class="py-3 px-4">Tài khoản Phòng</th>
                      <th class="py-3 px-4">Họ và tên</th>
                      <th class="py-3 px-4">Giới tính / Ngày sinh</th>
                      <th class="py-3 px-4">Số CCCD</th>
                      <th class="py-3 px-4">SĐT & Gmail</th>
                      <th class="py-3 px-4">Quê quán</th>
                      <th class="py-3 px-4 text-center">Trạng thái Hồ sơ</th>
                      <th class="py-3 px-4 text-right">Bảo mật Phiên</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100">
                    ${state.tenants
                      .map(
                        (t) => `
                          <tr class="hover:bg-slate-50">
                            <td class="py-3 px-4 font-mono-code font-bold text-teal-800">Phòng ${escapeHtml(t.username)}</td>
                            <td class="py-3 px-4 font-bold text-slate-900">${escapeHtml(t.full_name)}</td>
                            <td class="py-3 px-4">${escapeHtml(t.gender || "—")} • ${fmtDate(t.birth_date)}</td>
                            <td class="py-3 px-4 font-mono-code font-semibold">${escapeHtml(t.cccd || "—")}</td>
                            <td class="py-3 px-4">
                              <div class="font-mono-code">${escapeHtml(t.phone || "—")}</div>
                              <div class="text-[11px] text-slate-500">${escapeHtml(t.email || "—")}</div>
                            </td>
                            <td class="py-3 px-4">${escapeHtml(t.hometown || "—")}</td>
                            <td class="py-3 px-4 text-center">
                              ${
                                t.is_profile_completed
                                  ? `<span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px]">ĐÃ KHAI BÁO</span>`
                                  : `<span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-semibold text-[10px]">CHỜ KHÁCH MỚI</span>`
                              }
                            </td>
                            <td class="py-3 px-4 text-right">
                              <button type="button" onclick="revokeTenantDeviceSessions(${t.id}, '${escapeHtml(t.username)}')"
                                class="px-2.5 py-1 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 font-semibold cursor-pointer"
                                title="Đăng xuất mọi thiết bị đang đăng nhập vào tài khoản phòng này">
                                🔒 Thu hồi thiết bị (v${t.token_version})
                              </button>
                            </td>
                          </tr>
                        `
                      )
                      .join("")}
                  </tbody>
                </table>
              </div>
            </div>
          `
          : `
            <div class="bg-amber-50/60 border border-amber-200 p-4 rounded-2xl flex items-center justify-between">
              <div class="text-xs text-amber-900">
                <b>Cơ chế Soft Delete / Archive 30 ngày:</b> Hồ sơ khách thuê cũ sau khi trả phòng được lưu giữ đúng <b>30 ngày (1 tháng)</b> kể từ mốc <code>deleted_at</code> để tra cứu khi cần. Sau 30 ngày, Cronjob tự động xóa vĩnh viễn.
              </div>
              <button type="button" onclick="triggerCleanupArchived()"
                class="px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold cursor-pointer shrink-0">
                🧹 Chạy Cronjob Xóa hồ sơ >30 ngày
              </button>
            </div>

            <div class="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr class="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                      <th class="py-3 px-4">Phòng cũ</th>
                      <th class="py-3 px-4">Họ tên khách cũ</th>
                      <th class="py-3 px-4">CCCD / SĐT / Gmail</th>
                      <th class="py-3 px-4">Quê quán</th>
                      <th class="py-3 px-4">Thời điểm trả phòng (deleted_at)</th>
                      <th class="py-3 px-4 text-center">Thời hạn tự động xóa</th>
                      <th class="py-3 px-4">Lý do chuyển đi</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100">
                    ${state.archivedTenants
                      .map(
                        (a) => `
                          <tr class="hover:bg-slate-50">
                            <td class="py-3.5 px-4 font-mono-code font-bold text-amber-800">Phòng ${escapeHtml(a.room_number)}</td>
                            <td class="py-3.5 px-4">
                              <div class="font-bold text-slate-900">${escapeHtml(a.full_name)}</div>
                              <div class="text-[11px] text-slate-500">${escapeHtml(a.gender || "")} • NS: ${fmtDate(a.birth_date)}</div>
                            </td>
                            <td class="py-3.5 px-4">
                              <div class="font-mono-code font-semibold">CCCD: ${escapeHtml(a.cccd || "—")}</div>
                              <div class="text-[11px] text-slate-600">${escapeHtml(a.phone || "")} • ${escapeHtml(a.email || "")}</div>
                            </td>
                            <td class="py-3.5 px-4">${escapeHtml(a.hometown || "—")}</td>
                            <td class="py-3.5 px-4 font-mono-code">${fmtDateTime(a.deleted_at)}</td>
                            <td class="py-3.5 px-4 text-center">
                              <span class="px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-bold">
                                ⏳ Còn ${a.days_remaining} / 30 ngày
                              </span>
                            </td>
                            <td class="py-3.5 px-4 text-slate-600">${escapeHtml(a.checkout_reason || "—")}</td>
                          </tr>
                        `
                      )
                      .join("")}
                  </tbody>
                </table>
              </div>
            </div>
          `
      }
    </div>
  `;
}

async function revokeTenantDeviceSessions(userId, username) {
  try {
    const res = await apiFetch(`/auth/revoke-sessions/${userId}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    showToast10s(
      `Đã thu hồi thiết bị Phòng ${username}`,
      `Token version đã nâng lên v${res.token_version}. Mọi thiết bị đang đăng nhập vào Phòng ${username} đã bị đăng xuất ngay lập tức.`,
      "WARNING"
    );
    await loadAndRenderAdminTenants();
  } catch (err) {
    alert(err.message);
  }
}

async function triggerCleanupArchived() {
  try {
    const res = await apiFetch("/tenants/cleanup-archived", { method: "POST" });
    showToast10s("Cronjob Lưu trữ 30 ngày", res.message, "INFO");
    await loadAndRenderAdminTenants();
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// ADMIN TAB 6: QUẢN LÝ FEEDBACK THEO PHÒNG (TỰ ĐỘNG ĐẨY LÊN ĐẦU + NHÃN "CẦN ĐỌC")
// ==========================================================================

async function loadAndRenderAdminFeedbacks() {
  state.feedbacks = await apiFetch("/feedbacks");
  renderAdminFeedbacksView();
}

function renderAdminFeedbacksView() {
  const main = document.getElementById("main-content");
  if (!main) return;

  const catLabels = {
    ELECTRIC_WATER: "⚡ Điện nước",
    SECURITY: "🛡️ An ninh",
    HYGIENE: "🧹 Vệ sinh",
    GENERAL: "💬 Góp ý chung",
  };

  main.innerHTML = `
    <div class="space-y-5">
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-900">Quản lý Phản ánh / Góp ý (Feedback) theo từng Phòng</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Khi có phòng gửi Feedback mới, phòng đó <b>tự động được đẩy lên đầu danh sách</b> và gắn nhãn đỏ nổi bật <b>"Cần đọc (Chưa đọc)"</b>.
          </p>
        </div>
      </div>

      <div class="space-y-3">
        ${state.feedbacks
          .map((fb) => {
            const isUnread = !fb.is_read_by_admin;
            return `
              <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs ${
                isUnread ? "unread-feedback-card" : ""
              }">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="px-2.5 py-1 rounded-lg bg-slate-900 text-white font-mono-code font-bold text-xs">
                      Phòng ${escapeHtml(fb.room_number)} (Tầng ${fb.floor || 1})
                    </span>
                    <span class="px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 font-semibold text-xs">
                      ${catLabels[fb.category] || fb.category}
                    </span>
                    ${
                      isUnread
                        ? `<span class="px-2.5 py-0.5 rounded-full bg-red-600 text-white text-xs font-bold badge-pulse-red">🔴 CẦN ĐỌC (CHƯA ĐỌC)</span>`
                        : `<span class="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold">✓ ĐÃ XEM / PHẢN HỒI</span>`
                    }
                  </div>
                  <span class="text-xs text-slate-400">${fmtDateTime(fb.created_at)}</span>
                </div>

                <h3 class="text-sm font-bold text-slate-900 mb-1">${escapeHtml(fb.title)}</h3>
                <p class="text-xs text-slate-700 leading-relaxed mb-3">
                  <b>${escapeHtml(fb.tenant_name)} (${escapeHtml(fb.tenant_phone || "")}):</b> "${escapeHtml(fb.content)}"
                </p>

                ${
                  fb.admin_reply
                    ? `
                      <div class="p-3 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900 mb-3">
                        <b>↪ Phản hồi từ Chủ trọ (${fmtDateTime(fb.replied_at)}):</b> ${escapeHtml(fb.admin_reply)}
                      </div>
                    `
                    : ""
                }

                <div class="flex items-center gap-2 pt-2 border-t border-slate-100">
                  <input type="text" id="reply-input-${fb.id}"
                    value="${escapeHtml(fb.admin_reply || "")}"
                    placeholder="Nhập nội dung phản hồi trực tiếp cho Phòng ${escapeHtml(fb.room_number)}..."
                    class="flex-1 px-3.5 py-2 rounded-xl border border-slate-300 text-xs" />
                  <button type="button" onclick="submitAdminReplyFeedback(${fb.id}, '${escapeHtml(fb.room_number)}')"
                    class="px-4 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold cursor-pointer shrink-0">
                    📨 Gửi phản hồi cho Phòng ${escapeHtml(fb.room_number)}
                  </button>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    </div>
  `;
}

async function submitAdminReplyFeedback(feedbackId, roomNumber) {
  const input = document.getElementById(`reply-input-${feedbackId}`);
  const replyText = input ? input.value.trim() : "";
  if (!replyText) {
    alert("Vui lòng nhập nội dung phản hồi");
    return;
  }
  try {
    await apiFetch(`/feedbacks/${feedbackId}/reply`, {
      method: "POST",
      body: JSON.stringify({ admin_reply: replyText }),
    });
    showToast10s(
      `Đã phản hồi Phòng ${roomNumber}`,
      `Phản hồi của bạn đã được gửi trực tiếp tới tài khoản Phòng ${roomNumber}.`,
      "PAYMENT_SUCCESS"
    );
    await loadAndRenderAdminFeedbacks();
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// TENANT PORTAL (PORTAL KHÁCH THUÊ - TÀI KHOẢN PHÒNG 1.1 -> 3.5)
// ==========================================================================

async function loadAndRenderTenantBills() {
  const invoices = await apiFetch("/invoices/my-invoices");
  state.invoices = invoices;
  const overdueBills = invoices.filter((i) => i.status === "OVERDUE");

  const main = document.getElementById("main-content");
  main.innerHTML = `
    <div class="space-y-5">
      ${
        !state.user.is_profile_completed
          ? `
            <div class="p-4 rounded-2xl bg-purple-50 border-2 border-purple-300 flex items-center justify-between gap-4">
              <div class="text-xs text-purple-900">
                <b class="text-sm">📝 Yêu cầu Khai báo thông tin khách thuê lần đầu:</b><br/>
                Bạn đang đăng nhập vào Phòng <b>${escapeHtml(state.user.username)}</b> chưa có hồ sơ cá nhân. Vui lòng cập nhật đầy đủ Họ tên, CCCD, SĐT, Gmail, Quê quán để đồng bộ vào Hợp đồng thuê trọ.
              </div>
              <button type="button" onclick="openFirstTimeProfileModal()"
                class="px-4 py-2 rounded-xl bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold shrink-0 cursor-pointer">
                Khai báo hồ sơ ngay
              </button>
            </div>
          `
          : ""
      }

      ${
        overdueBills.length > 0
          ? `
            <div class="p-4 rounded-2xl bg-red-50 border-2 border-red-400 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="text-xs text-red-900">
                <b class="text-sm text-red-700">🚨 CẢNH BÁO CÔNG NỢ QUÁ HẠN SAU NGÀY 15:</b><br/>
                Phòng <b>${escapeHtml(state.user.username)}</b> hiện có <b>${overdueBills.length} hóa đơn quá hạn</b> chưa thanh toán. Vui lòng vào mục <b>"Thanh toán nợ"</b> để đóng tiền cho từng tháng đang nợ.
              </div>
              <button type="button" onclick="switchTab('my-debt')"
                class="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-bold shrink-0 cursor-pointer">
                Vào mục Thanh toán Nợ →
              </button>
            </div>
          `
          : ""
      }

      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <h2 class="text-lg font-bold text-slate-900">Danh sách Hóa đơn Tiền phòng & Điện nước - Phòng ${escapeHtml(state.user.username)}</h2>
        <p class="text-xs text-slate-500 mt-0.5">
          Hạn đóng cố định: <b>Ngày 10 hằng tháng</b> • Hỗ trợ thanh toán Online (MoMo, Thẻ Visa, Ngân hàng liên kết) hoặc Chuyển khoản VietQR & Gửi ảnh Bill UNC.
        </p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        ${
          invoices.length === 0
            ? `<div class="col-span-2 bg-white p-10 rounded-2xl border border-slate-200 text-center text-sm text-slate-400">Hiện chưa có hóa đơn nào cho phòng của bạn.</div>`
            : invoices
                .map((inv) => {
                  const pdfUrl = `${API_BASE}/invoices/${inv.id}/pdf?token=${encodeURIComponent(state.token)}`;
                  const isPaid = inv.status === "PAID";
                  const isOverdue = inv.status === "OVERDUE";
                  return `
                    <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between ${
                      isOverdue ? "room-card-overdue" : ""
                    }">
                      <div>
                        <div class="flex items-center justify-between mb-3">
                          <div>
                            <span class="text-base font-bold text-slate-900">Hóa đơn Kỳ ${escapeHtml(inv.month_year)}</span>
                            <div class="text-xs font-mono-code text-slate-500">${escapeHtml(inv.invoice_code)} • Hạn đóng: ${fmtDate(inv.due_date)}</div>
                          </div>
                          ${renderInvoiceStatusBadge(inv.status, inv.payment_method)}
                        </div>

                        <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5 mb-4">
                          <div class="flex justify-between">
                            <span class="text-slate-600">1. Tiền phòng cơ bản:</span>
                            <span class="font-mono-code font-semibold">${fmtVND(inv.room_charge)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">2. Tiền điện (${inv.new_electricity} - ${inv.old_electricity} = ${inv.electricity_usage} kWh):</span>
                            <span class="font-mono-code font-semibold">${fmtVND(inv.electricity_charge)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">3. Tiền nước (${inv.new_water} - ${inv.old_water} = ${inv.water_usage} m³):</span>
                            <span class="font-mono-code font-semibold">${fmtVND(inv.water_charge)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">4. Phụ phí gửi xe:</span>
                            <span class="font-mono-code">${fmtVND(inv.parking_fee)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">5. Phụ phí bảo trì điện nước:</span>
                            <span class="font-mono-code">${fmtVND(inv.maintenance_fee)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">6. Phụ phí Internet / Wifi:</span>
                            <span class="font-mono-code">${fmtVND(inv.wifi_fee)}</span>
                          </div>
                          <div class="flex justify-between">
                            <span class="text-slate-600">7. Phụ phí vệ sinh / rác:</span>
                            <span class="font-mono-code">${fmtVND(inv.trash_fee)}</span>
                          </div>
                          <div class="flex justify-between pt-2 border-t border-slate-200 text-sm font-bold text-teal-800">
                            <span>TỔNG CỘNG:</span>
                            <span class="font-mono-code">${fmtVND(inv.total_amount)}</span>
                          </div>
                        </div>
                      </div>

                      <div class="flex flex-wrap items-center justify-between gap-2 pt-2">
                        <a href="${pdfUrl}" target="_blank"
                          class="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold">
                          ⬇️ Tải Hóa đơn PDF
                        </a>

                        ${
                          !isPaid
                            ? `
                              <div class="flex items-center gap-2">
                                <button type="button" onclick="openOnlinePaymentGatewayModal(${inv.id})"
                                  class="px-3.5 py-2 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs cursor-pointer">
                                  💳 Thanh toán Online (MoMo/Visa/Bank)
                                </button>
                                <button type="button" onclick="openVietQRUploadBillModal(${inv.id})"
                                  class="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold shadow-xs cursor-pointer">
                                  📤 VietQR & Gửi Bill
                                </button>
                              </div>
                            `
                            : `<span class="text-xs font-semibold text-emerald-700">✓ Đã thanh toán ngày ${fmtDate(inv.paid_date)}</span>`
                        }
                      </div>
                    </div>
                  `;
                })
                .join("")
        }
      </div>
    </div>
  `;
}

// ==========================================================================
// TENANT TAB 2: MỤC "THANH TOÁN NỢ" (CHỌN ĐÓNG TIỀN NỢ CHO ĐÚNG THÁNG ĐÓ)
// ==========================================================================

async function loadAndRenderTenantDebt() {
  const invoices = await apiFetch("/invoices/my-invoices");
  state.invoices = invoices;
  const debtList = invoices.filter((i) => i.status === "OVERDUE" || i.status === "UNPAID");
  const totalDebt = debtList.reduce((acc, i) => acc + Number(i.total_amount || 0), 0);

  const main = document.getElementById("main-content");
  main.innerHTML = `
    <div class="space-y-5">
      <div class="bg-red-50 border-2 border-red-300 p-5 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-red-900">Mục Thanh toán Nợ theo Tháng - Phòng ${escapeHtml(state.user.username)}</h2>
          <p class="text-xs text-red-800 mt-0.5">
            Liệt kê rõ các tháng đang nợ quá hạn hoặc chưa đóng • Cho phép chọn đóng tiền nợ dứt điểm cho đúng tháng bạn chọn.
          </p>
        </div>
        <div class="bg-white px-4 py-3 rounded-xl border border-red-200 text-right shrink-0">
          <div class="text-[11px] text-slate-500 uppercase font-semibold">Tổng dư nợ cần thanh toán</div>
          <div class="text-xl font-bold text-red-600 font-mono-code">${fmtVND(totalDebt)}</div>
        </div>
      </div>

      ${
        debtList.length === 0
          ? `
            <div class="bg-white p-10 rounded-2xl border border-emerald-200 text-center">
              <div class="text-base font-bold text-emerald-700 mb-1">🎉 Tuyệt vời! Phòng ${escapeHtml(state.user.username)} không có khoản nợ nào tồn đọng.</div>
              <p class="text-xs text-slate-500">Tất cả hóa đơn các tháng đều đã được thanh toán đầy đủ.</p>
            </div>
          `
          : `
            <div class="space-y-3">
              ${debtList
                .map(
                  (inv) => `
                    <div class="bg-white p-5 rounded-2xl border-2 ${
                      inv.status === "OVERDUE" ? "border-red-400" : "border-amber-300"
                    } shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div class="flex items-center gap-2 mb-1">
                          <span class="px-2.5 py-0.5 rounded bg-red-600 text-white font-mono-code font-bold text-xs">
                            KỲ NỢ: THÁNG ${escapeHtml(inv.month_year)}
                          </span>
                          <span class="font-mono-code text-xs text-slate-500">${escapeHtml(inv.invoice_code)}</span>
                          ${renderInvoiceStatusBadge(inv.status, inv.payment_method)}
                        </div>
                        <div class="text-xs text-slate-600">
                          Tiền phòng: ${fmtVND(inv.room_charge)} + Điện: ${fmtVND(inv.electricity_charge)} + Nước: ${fmtVND(inv.water_charge)} + Phụ phí: ${fmtVND(inv.service_charge)}
                        </div>
                        <div class="text-xs text-red-700 font-semibold mt-1">
                          Hạn đóng cố định: ${fmtDate(inv.due_date)} (Quá hạn từ ngày 15)
                        </div>
                      </div>

                      <div class="flex flex-col sm:items-end gap-2 shrink-0">
                        <div class="text-lg font-bold text-red-600 font-mono-code">${fmtVND(inv.total_amount)}</div>
                        <div class="flex items-center gap-2">
                          <button type="button" onclick="openOnlinePaymentGatewayModal(${inv.id})"
                            class="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-bold shadow-xs cursor-pointer">
                            💳 Đóng nợ Tháng ${escapeHtml(inv.month_year)} (Online)
                          </button>
                          <button type="button" onclick="openVietQRUploadBillModal(${inv.id})"
                            class="px-3 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold cursor-pointer">
                            📤 Chuyển khoản & Gửi Bill
                          </button>
                        </div>
                      </div>
                    </div>
                  `
                )
                .join("")}
            </div>
          `
      }
    </div>
  `;
}

// ==========================================================================
// CỔNG THANH TOÁN DEMO (PHƯƠNG THỨC 1: MOMO / VISA / NGÂN HÀNG LIÊN KẾT
// & PHƯƠNG THỨC 2: VIETQR & UPLOAD ẢNH BILL UNC)
// ==========================================================================

function openOnlinePaymentGatewayModal(invoiceId) {
  const inv = state.invoices.find((x) => x.id === invoiceId);
  if (!inv) return;

  openModal(
    `Cổng Thanh Toán Trực Tuyến (Demo Tích Hợp) - Kỳ ${inv.month_year}`,
    `
      <form onsubmit="submitOnlinePayment(event, ${inv.id})" class="space-y-4">
        <div class="p-4 rounded-2xl bg-gradient-to-r from-teal-800 to-teal-600 text-white flex items-center justify-between">
          <div>
            <div class="text-xs opacity-80">Thanh toán Hóa đơn Phòng ${escapeHtml(state.user.username)}</div>
            <div class="text-base font-bold font-mono-code">${escapeHtml(inv.invoice_code)} (Kỳ ${escapeHtml(inv.month_year)})</div>
          </div>
          <div class="text-right">
            <div class="text-xs opacity-80">Tổng thanh toán (100%)</div>
            <div class="text-xl font-bold font-mono-code">${fmtVND(inv.total_amount)}</div>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-700 uppercase mb-2">Chọn Phương thức Thanh toán Online:</label>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label class="p-3.5 rounded-xl border-2 border-pink-500 bg-pink-50/40 cursor-pointer flex items-center gap-2.5">
              <input type="radio" name="pay_method" value="MOMO" checked class="text-pink-600" />
              <div>
                <div class="font-bold text-xs text-pink-800">Ví Điện Tử MoMo</div>
                <div class="text-[11px] text-slate-500">Quét mã / Liên kết siêu tốc</div>
              </div>
            </label>

            <label class="p-3.5 rounded-xl border-2 border-sky-500 bg-sky-50/40 cursor-pointer flex items-center gap-2.5">
              <input type="radio" name="pay_method" value="VISA" class="text-sky-600" />
              <div>
                <div class="font-bold text-xs text-sky-900">Thẻ Quốc Tế Visa</div>
                <div class="text-[11px] text-slate-500">Visa / Mastercard / JCB</div>
              </div>
            </label>

            <label class="p-3.5 rounded-xl border-2 border-teal-500 bg-teal-50/40 cursor-pointer flex items-center gap-2.5">
              <input type="radio" name="pay_method" value="LINKED_BANK" class="text-teal-600" />
              <div>
                <div class="font-bold text-xs text-teal-900">Ngân Hàng Liên Kết</div>
                <div class="text-[11px] text-slate-500">Vietcombank / MB / Techcombank</div>
              </div>
            </label>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 text-xs">
          <div class="font-bold text-slate-800">🔒 Thông tin xác thực giao dịch Demo:</div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-slate-600 mb-1">Số thẻ / Tài khoản / Ví Demo</label>
              <input type="text" value="4111 •••• •••• 8899 (Đã xác thực OTP)" readonly
                class="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white font-mono-code text-xs" />
            </div>
            <div>
              <label class="block text-slate-600 mb-1">Gmail nhận Hóa đơn PDF ngay sau khi đóng</label>
              <input type="text" value="${escapeHtml(state.user.email || "phong" + state.user.username + "@gmail.com")}" readonly
                class="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-xs" />
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
          <button type="submit" class="px-5 py-2.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-md cursor-pointer">
            ✨ Xác nhận Thanh toán ${fmtVND(inv.total_amount)}
          </button>
        </div>
      </form>
    `
  );
}

async function submitOnlinePayment(e, invoiceId) {
  e.preventDefault();
  const checked = document.querySelector('input[name="pay_method"]:checked');
  const method = checked ? checked.value : "MOMO";

  try {
    const paid = await apiFetch(`/invoices/${invoiceId}/pay`, {
      method: "POST",
      body: JSON.stringify({
        payment_method: method,
        notes: `Khách thuê thanh toán trực tuyến qua cổng ${method}`,
      }),
    });
    closeModal();
    showToast10s(
      `Thanh toán thành công (${method})!`,
      `Đã gạch nợ hóa đơn ${paid.invoice_code} (${fmtVND(paid.total_amount)}). Hóa đơn PDF đã được gửi vào Gmail của bạn!`,
      "PAYMENT_SUCCESS"
    );
    await fetchNotifications(true);
    await switchTab(state.activeTab);
  } catch (err) {
    alert(err.message);
  }
}

// Phương thức 2: Chuyển khoản Ngân hàng (VietQR) & Gửi ảnh Bill (UNC)
function openVietQRUploadBillModal(invoiceId) {
  const inv = state.invoices.find((x) => x.id === invoiceId);
  if (!inv) return;

  const roomNum = state.user.username;
  const transferContent = `PHONG ${roomNum} TT ${inv.month_year}`;
  const vietQrUrl = `https://img.vietqr.io/image/VCB-1029384756-compact2.png?amount=${inv.total_amount}&addInfo=${encodeURIComponent(
    transferContent
  )}&accountName=${encodeURIComponent("NGUYEN MINH HOANG")}`;

  openModal(
    `Chuyển khoản VietQR & Tải lên ảnh Bill (UNC) - Kỳ ${inv.month_year}`,
    `
      <form onsubmit="submitUploadBillUNC(event, ${inv.id})" class="grid grid-cols-1 md:grid-cols-12 gap-5">
        <div class="md:col-span-5 bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center text-center">
          <span class="px-2.5 py-0.5 rounded bg-teal-700 text-white text-[10px] font-bold mb-2">MÃ VIETQR TỰ ĐỘNG</span>
          <img src="${vietQrUrl}" alt="VietQR" class="w-48 h-48 object-contain rounded-xl border border-slate-200 bg-white p-2 mb-2"
            onerror="this.style.display='none'" />
          <div class="text-xs space-y-1 text-slate-700">
            <div>Ngân hàng: <b>Vietcombank (VCB)</b></div>
            <div>Số TK: <b class="font-mono-code text-teal-800">1029384756</b></div>
            <div>Chủ TK: <b>NGUYEN MINH HOANG</b></div>
            <div>Số tiền: <b class="font-mono-code text-red-600">${fmtVND(inv.total_amount)}</b></div>
            <div>Nội dung: <code class="font-mono-code font-bold bg-amber-100 px-1.5 py-0.5 rounded">${escapeHtml(transferContent)}</code></div>
          </div>
        </div>

        <div class="md:col-span-7 flex flex-col justify-between space-y-4">
          <div class="space-y-3">
            <h4 class="text-sm font-bold text-slate-900">Tải ảnh chụp màn hình Bill chuyển khoản (UNC) lên hệ thống</h4>
            <p class="text-xs text-slate-600">
              Sau khi chuyển khoản, bạn chọn file ảnh chụp màn hình giao dịch hoặc bấm nút <b>"Tạo ảnh Bill UNC mẫu Demo"</b> bên dưới để gửi cho Chủ trọ đối soát.
            </p>

            <div>
              <label class="block text-xs font-bold text-slate-700 mb-1">Chọn file ảnh Bill từ thiết bị (PNG/JPG):</label>
              <input type="file" accept="image/*" onchange="handleBillFileSelect(event)"
                class="w-full text-xs file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-teal-50 file:text-teal-800 file:font-bold" />
            </div>

            <div class="flex items-center gap-2">
              <button type="button" onclick="generateDemoBillPreview('${escapeHtml(roomNum)}', '${escapeHtml(state.user.full_name)}', '${fmtVND(inv.total_amount)}', '${escapeHtml(inv.month_year)}')"
                class="px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 text-xs font-bold cursor-pointer">
                ✨ Tạo nhanh ảnh Bill UNC mẫu Demo
              </button>
            </div>

            <input type="hidden" id="bill-data-url-input" />
            <div id="bill-preview-box" class="p-3 rounded-xl bg-slate-50 border border-dashed border-slate-300 text-center text-xs text-slate-400">
              Chưa chọn ảnh Bill UNC
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
            <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Hủy</button>
            <button type="submit" class="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold shadow-md cursor-pointer">
              📤 Gửi ảnh Bill cho Chủ trọ duyệt
            </button>
          </div>
        </div>
      </form>
    `
  );

  // Tự động tạo sẵn ảnh Bill mẫu để tiện test ngay 1 click
  generateDemoBillPreview(roomNum, state.user.full_name, fmtVND(inv.total_amount), inv.month_year);
}

function handleBillFileSelect(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result;
    document.getElementById("bill-data-url-input").value = dataUrl;
    document.getElementById("bill-preview-box").innerHTML = `
      <img src="${dataUrl}" class="max-h-48 mx-auto rounded-lg shadow-xs object-contain" />
    `;
  };
  reader.readAsDataURL(file);
}

function generateDemoBillPreview(roomNum, senderName, amountStr, monthYear) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="380" height="240" viewBox="0 0 380 240">
    <rect width="380" height="240" rx="14" fill="#f0fdfa" stroke="#14b8a6" stroke-width="2"/>
    <text x="190" y="34" font-family="Arial" font-size="14" font-weight="bold" fill="#0f766e" text-anchor="middle">✓ ỦY NHIỆM CHI / BILL CHUYỂN KHOẢN</text>
    <text x="190" y="68" font-family="Arial" font-size="22" font-weight="bold" fill="#0f172a" text-anchor="middle">${amountStr}</text>
    <text x="24" y="106" font-family="Arial" font-size="12" fill="#334155">Người chuyển: ${senderName} (Phòng ${roomNum})</text>
    <text x="24" y="132" font-family="Arial" font-size="12" fill="#334155">TK nhận: 1029384756 - NGUYEN MINH HOANG (VCB)</text>
    <text x="24" y="158" font-family="Arial" font-size="12" font-weight="bold" fill="#0f766e">Nội dung: PHONG ${roomNum} TT ${monthYear}</text>
    <text x="24" y="184" font-family="Arial" font-size="11" fill="#64748b">Mã GD: VCB-${Date.now().toString().slice(-8)}</text>
  </svg>`;
  const dataUrl = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svg)));
  const input = document.getElementById("bill-data-url-input");
  const box = document.getElementById("bill-preview-box");
  if (input) input.value = dataUrl;
  if (box) {
    box.innerHTML = `<img src="${dataUrl}" class="max-h-44 mx-auto rounded-lg shadow-xs" />`;
  }
}

async function submitUploadBillUNC(e, invoiceId) {
  e.preventDefault();
  const billUrl = document.getElementById("bill-data-url-input")?.value;
  if (!billUrl) {
    alert("Vui lòng chọn hoặc tạo ảnh Bill UNC trước khi gửi.");
    return;
  }
  try {
    const updated = await apiFetch(`/invoices/${invoiceId}/upload-bill`, {
      method: "POST",
      body: JSON.stringify({
        bill_image_url: billUrl,
        notes: "Khách thuê gửi ảnh chụp màn hình Bill chuyển khoản VietQR",
      }),
    });
    closeModal();
    showToast10s(
      `Đã gửi ảnh Bill ${updated.invoice_code}`,
      "Hệ thống đã thông báo cho Chủ trọ kiểm tra đối soát và xác nhận thu tiền.",
      "BILL_UPLOADED"
    );
    await switchTab(state.activeTab);
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// TENANT TAB 3: XEM & TẢI HỢP ĐỒNG THUÊ NHÀ PHÁP LÝ VIỆT NAM
// ==========================================================================

async function loadAndRenderTenantContract() {
  const main = document.getElementById("main-content");
  try {
    const contract = await apiFetch("/contracts/my-contract");
    state.myContract = contract;
    main.innerHTML = `
      <div class="max-w-4xl mx-auto">
        ${buildVietnameseContractHtml(contract)}
      </div>
    `;
  } catch (err) {
    main.innerHTML = `
      <div class="bg-white p-8 rounded-2xl border border-slate-200 text-center">
        <h3 class="text-base font-bold text-slate-800 mb-1">Chưa có Hợp đồng điện tử cho Phòng ${escapeHtml(state.user.username)}</h3>
        <p class="text-xs text-slate-500">Vui lòng hoàn tất khai báo hồ sơ cá nhân để Chủ trọ ban hành Hợp đồng thuê phòng.</p>
      </div>
    `;
  }
}

// ==========================================================================
// TENANT TAB 4: GỬI FEEDBACK / BÁO HỎNG & XEM PHẢN HỒI TỪ CHỦ TRỌ
// ==========================================================================

async function loadAndRenderTenantFeedbacks() {
  const list = await apiFetch("/feedbacks/my-feedbacks");
  state.feedbacks = list;

  const main = document.getElementById("main-content");
  main.innerHTML = `
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5 bg-white p-5 rounded-2xl border border-slate-200 shadow-xs h-fit">
        <h3 class="text-base font-bold text-slate-900 mb-1">Gửi Góp ý / Báo hỏng kỹ thuật</h3>
        <p class="text-xs text-slate-500 mb-4">
          Khi bạn gửi Feedback, Phòng <b>${escapeHtml(state.user.username)}</b> sẽ được đẩy lên đầu danh sách của Chủ trọ với nhãn <b>"Cần đọc"</b>.
        </p>

        <form onsubmit="submitTenantFeedback(event)" class="space-y-3.5">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Phân loại phản ánh</label>
            <select id="fb-cat" class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm bg-white">
              <option value="ELECTRIC_WATER">⚡ Điện nước (Hỏng hóc, rò rỉ...)</option>
              <option value="SECURITY">🛡️ An ninh & Trật tự</option>
              <option value="HYGIENE">🧹 Vệ sinh & Môi trường</option>
              <option value="GENERAL">💬 Góp ý chung</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Tiêu đề ngắn gọn</label>
            <input type="text" id="fb-title" required placeholder="VD: Bóng đèn ban công bị cháy..."
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Nội dung chi tiết</label>
            <textarea id="fb-content" rows="4" required placeholder="Mô tả chi tiết tình trạng để chủ trọ hỗ trợ nhanh nhất..."
              class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm"></textarea>
          </div>
          <button type="submit"
            class="w-full py-2.5 px-4 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs cursor-pointer">
            📨 Gửi Feedback tới Chủ trọ
          </button>
        </form>
      </div>

      <div class="lg:col-span-7 space-y-3">
        <h3 class="text-base font-bold text-slate-900">Lịch sử Phản ánh & Phản hồi từ Chủ trọ (${list.length})</h3>
        ${
          list.length === 0
            ? `<div class="bg-white p-8 rounded-2xl border border-slate-200 text-center text-xs text-slate-400">Bạn chưa gửi phản ánh nào.</div>`
            : list
                .map(
                  (fb) => `
                    <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                      <div class="flex items-center justify-between">
                        <span class="px-2.5 py-0.5 rounded bg-slate-100 text-slate-700 font-bold text-xs">${escapeHtml(fb.category)}</span>
                        <span class="text-xs text-slate-400">${fmtDateTime(fb.created_at)}</span>
                      </div>
                      <div class="font-bold text-sm text-slate-900">${escapeHtml(fb.title)}</div>
                      <p class="text-xs text-slate-600">${escapeHtml(fb.content)}</p>
                      ${
                        fb.admin_reply
                          ? `<div class="p-3 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900">
                              <b>✓ Chủ trọ đã phản hồi (${fmtDateTime(fb.replied_at)}):</b> ${escapeHtml(fb.admin_reply)}
                            </div>`
                          : `<div class="text-[11px] text-amber-700 font-semibold">⏳ Đang chờ Chủ trọ xem và phản hồi...</div>`
                      }
                    </div>
                  `
                )
                .join("")
        }
      </div>
    </div>
  `;
}

async function submitTenantFeedback(e) {
  e.preventDefault();
  try {
    const category = document.getElementById("fb-cat").value;
    const title = document.getElementById("fb-title").value.trim();
    const content = document.getElementById("fb-content").value.trim();

    await apiFetch("/feedbacks", {
      method: "POST",
      body: JSON.stringify({ category, title, content }),
    });
    showToast10s(
      `Đã gửi Feedback từ Phòng ${state.user.username}`,
      "Phản ánh của bạn đã được đẩy lên đầu danh sách của Chủ trọ với nhãn 'Cần đọc'.",
      "FEEDBACK_NEW"
    );
    await loadAndRenderTenantFeedbacks();
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// TENANT TAB 5 & MODAL: KHAI BÁO / CẬP NHẬT HỒ SƠ CÁ NHÂN LẦN ĐẦU
// ==========================================================================

function buildProfileFormHtml(isModal = false) {
  const u = state.user || {};
  const bDate = u.birth_date || "2000-01-15";
  return `
    <form onsubmit="submitTenantProfileUpdate(event, ${isModal})" class="space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Họ và tên đầy đủ *</label>
          <input type="text" id="prof-name" required value="${escapeHtml(
            u.is_profile_completed ? u.full_name : ""
          )}" placeholder="VD: Nguyễn Văn Minh"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Giới tính *</label>
          <select id="prof-gender" class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm bg-white">
            <option value="Nam" ${u.gender === "Nam" ? "selected" : ""}>Nam</option>
            <option value="Nữ" ${u.gender === "Nữ" ? "selected" : ""}>Nữ</option>
            <option value="Khác" ${u.gender === "Khác" ? "selected" : ""}>Khác</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Ngày sinh *</label>
          <input type="date" id="prof-dob" required value="${bDate}"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Số CCCD (12 số) *</label>
          <input type="text" id="prof-cccd" required value="${escapeHtml(u.cccd || "")}" placeholder="VD: 079200001234"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Số điện thoại *</label>
          <input type="text" id="prof-phone" required value="${escapeHtml(u.phone || "")}" placeholder="VD: 0909123456"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm font-mono-code" />
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Địa chỉ Gmail (nhận Hóa đơn PDF) *</label>
          <input type="email" id="prof-email" required value="${escapeHtml(u.email || "")}" placeholder="VD: khachthue@gmail.com"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Quê quán / Thường trú *</label>
          <input type="text" id="prof-hometown" required value="${escapeHtml(u.hometown || "")}" placeholder="VD: Quận Ninh Kiều, TP. Cần Thơ"
            class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
        </div>
      </div>

      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Đổi mật khẩu mới (Để trống nếu giữ nguyên)</label>
        <input type="password" id="prof-pw" placeholder="Nhập mật khẩu mới nếu muốn thay đổi..."
          class="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-sm" />
      </div>

      <div class="flex justify-end gap-2 pt-3 border-t border-slate-200">
        ${
          isModal
            ? `<button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold cursor-pointer">Để sau</button>`
            : ""
        }
        <button type="submit" class="px-5 py-2.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold shadow-xs cursor-pointer">
          💾 Lưu Hồ sơ Khách thuê Phòng ${escapeHtml(u.username)}
        </button>
      </div>
    </form>
  `;
}

function openFirstTimeProfileModal() {
  openModal(
    `Khai báo Thông tin Khách thuê Lần đầu - Phòng ${state.user.username}`,
    `
      <div class="space-y-4">
        <div class="p-3.5 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900">
          Chào mừng bạn nhận <b>Phòng ${escapeHtml(state.user.username)}</b>! Vui lòng khai báo đầy đủ thông tin cá nhân dưới đây để hệ thống cập nhật lên trang Quản trị của Chủ trọ và điền tự động vào Hợp đồng thuê nhà.
        </div>
        ${buildProfileFormHtml(true)}
      </div>
    `
  );
}

async function renderTenantProfileTab() {
  const main = document.getElementById("main-content");
  main.innerHTML = `
    <div class="max-w-3xl mx-auto bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
      <div>
        <h2 class="text-lg font-bold text-slate-900">Hồ sơ Cá nhân & Tài khoản Phòng ${escapeHtml(state.user.username)}</h2>
        <p class="text-xs text-slate-500">Thông tin này được hiển thị trên trang Admin của Chủ trọ và dùng để nhận Hóa đơn PDF qua Gmail.</p>
      </div>
      ${buildProfileFormHtml(false)}
    </div>
  `;
}

async function submitTenantProfileUpdate(e, isModal) {
  e.preventDefault();
  try {
    const payload = {
      full_name: document.getElementById("prof-name").value.trim(),
      gender: document.getElementById("prof-gender").value,
      birth_date: document.getElementById("prof-dob").value,
      cccd: document.getElementById("prof-cccd").value.trim(),
      phone: document.getElementById("prof-phone").value.trim(),
      email: document.getElementById("prof-email").value.trim(),
      hometown: document.getElementById("prof-hometown").value.trim(),
    };
    const pw = document.getElementById("prof-pw").value.trim();
    if (pw) payload.new_password = pw;

    const updated = await apiFetch("/auth/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.user = updated;
    localStorage.setItem("qlpt_user", JSON.stringify(updated));
    document.getElementById("header-user-name").textContent = updated.full_name;

    if (isModal) closeModal();
    showToast10s(
      `Đã cập nhật hồ sơ Phòng ${updated.username}`,
      `Cảm ơn ${updated.full_name}! Hồ sơ của bạn đã được đồng bộ lên trang Quản trị của Chủ trọ.`,
      "PAYMENT_SUCCESS"
    );
    await switchTab(state.activeTab);
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// MODAL HỘP THƯ GMAIL ĐÃ GỬI (EMAIL LOGS PREVIEW)
// ==========================================================================

async function openEmailLogsModal() {
  try {
    const logs = await apiFetch("/invoices/email-logs");
    openModal(
      `Hộp thư Gmail Đã Gửi Tự Động (${logs.length} Email gần nhất)`,
      `
        <div class="space-y-4">
          <p class="text-xs text-slate-500">
            Mọi Hóa đơn phát hành, Biên lai thanh toán PDF và Cảnh báo nợ đều được gửi tới đúng Gmail của phòng tương ứng (cô lập dữ liệu 100%).
          </p>
          ${
            logs.length === 0
              ? `<div class="p-8 text-center text-xs text-slate-400">Chưa có email nào trong lịch sử. Hãy bấm nút 'Gmail' hoặc thanh toán thử 1 hóa đơn!</div>`
              : logs
                  .map(
                    (lg) => `
                      <div class="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                        <div class="flex items-center justify-between text-xs">
                          <span class="font-bold text-teal-800">Tới: ${escapeHtml(lg.recipient_email)} (${escapeHtml(lg.recipient_name || "")})</span>
                          <span class="text-slate-400">${fmtDateTime(lg.created_at)}</span>
                        </div>
                        <div class="font-bold text-sm text-slate-900">${escapeHtml(lg.subject)}</div>
                        <div class="text-xs text-slate-600">📎 Đính kèm: <code class="font-mono-code font-bold text-teal-700">${escapeHtml(lg.attachment_name || "")}</code></div>
                        <details class="text-xs">
                          <summary class="cursor-pointer font-semibold text-teal-700 hover:underline">Xem nội dung HTML của Email</summary>
                          <div class="mt-2 p-3 bg-white rounded-lg border border-slate-200">${lg.body_html}</div>
                        </details>
                      </div>
                    `
                  )
                  .join("")
          }
        </div>
      `
    );
  } catch (err) {
    alert(err.message);
  }
}

// ==========================================================================
// GLOBAL MODAL CONTROLS & BOOTSTRAP
// ==========================================================================

function openModal(title, bodyHtml) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = bodyHtml;
  document.getElementById("modal-backdrop").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("modal-backdrop").classList.add("hidden");
  document.getElementById("modal-body").innerHTML = "";
}

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const u = document.getElementById("login-username").value;
      const p = document.getElementById("login-password").value;
      handleLogin(u, p);
    });
  }

  if (state.token) {
    initAppPortal();
  }
});
