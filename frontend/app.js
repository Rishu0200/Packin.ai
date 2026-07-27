// PackIn.ai frontend — vanilla JS, no build step needed.
// Change this to your deployed backend URL in production.
const API_BASE = window.PACKIN_API_BASE || "http://localhost:8000";

// ---------------- Auth ----------------
function getToken() {
  return localStorage.getItem("packin_token");
}

function setToken(token) {
  localStorage.setItem("packin_token", token);
}

function clearToken() {
  localStorage.removeItem("packin_token");
}

// Every authenticated call should go through this instead of raw fetch() —
// it attaches the token and bounces back to login on a 401 automatically.
async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    showScreen("login");
    throw new Error("Session expired — please log in again.");
  }
  return res;
}

async function login() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const errorBox = document.getElementById("login-error");
  errorBox.innerHTML = "";

  if (!username || !password) {
    errorBox.innerHTML = `<p class="tagline" style="color:var(--red-600)">Enter both fields.</p>`;
    return;
  }

  try {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      errorBox.innerHTML = `<p class="tagline" style="color:var(--red-600)">${data.detail || "Login failed"}</p>`;
      return;
    }
    const data = await res.json();
    setToken(data.access_token);
    document.getElementById("bottom-nav").classList.remove("hidden");
    showScreen("dashboard");
  } catch (err) {
    errorBox.innerHTML = `<p class="tagline" style="color:var(--red-600)">Could not reach the server.</p>`;
  }
}

function logout() {
  clearToken();
  document.getElementById("bottom-nav").classList.add("hidden");
  showScreen("login");
}

// ---------------- Navigation ----------------
function showScreen(name) {
  document.querySelectorAll("main > section").forEach((s) => s.classList.add("hidden"));
  document.getElementById(`screen-${name}`).classList.remove("hidden");

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.screen === name);
  });

  if (name === "dashboard") loadDashboard();
  if (name === "review") loadReviewQueue();
  if (name === "brands") loadBrands();
}

// ---------------- Dashboard ----------------
async function loadDashboard() {
  try {
    const [stockRes, lowStockRes, activityRes] = await Promise.all([
      authFetch(`${API_BASE}/inventory`).then((r) => r.json()),
      authFetch(`${API_BASE}/inventory/low-stock`).then((r) => r.json()),
      authFetch(`${API_BASE}/activity?limit=10`).then((r) => r.json()),
    ]);

    const grid = document.getElementById("stock-grid");
    grid.innerHTML = "";
    stockRes.stock.forEach((box) => {
      const card = document.createElement("div");
      card.className = `stock-card ${box.low_stock ? "low" : ""}`;
      card.innerHTML = `
        <p class="size">${box.size}</p>
        <p class="brand">${box.brand}</p>
        <p class="qty">${box.stock} pcs</p>
      `;
      grid.appendChild(card);
    });

    const bannerSlot = document.getElementById("alert-banner-slot");
    const low = lowStockRes.low_stock || [];
    bannerSlot.innerHTML = low.length
      ? `<div class="alert-banner">⚠️ ${low.length} box size${low.length > 1 ? "s are" : " is"} low on stock. Consider raising a PO.</div>`
      : "";

    const feedEl = document.getElementById("activity-feed");
    const activity = activityRes.activity || [];
    feedEl.innerHTML = activity.length
      ? activity.map((a) => `
          <div style="padding:8px 0; border-bottom:1px solid var(--line);">
            <p style="margin:0; font-size:13px;">${a.summary}</p>
            <p class="mono" style="margin:2px 0 0; font-size:11px; color:var(--ink-600);">${new Date(a.timestamp).toLocaleString()}</p>
          </div>
        `).join("")
      : `<p class="tagline" style="color:var(--ink-600)">No activity yet.</p>`;
  } catch (err) {
    console.error("Failed to load dashboard", err);
  }
}

async function downloadExport(format) {
  try {
    const res = await authFetch(`${API_BASE}/inventory/export?format=${format}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `packin_inventory_report.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Export download failed", err);
  }
}

// ---------------- Invoice upload ----------------
async function uploadInvoice() {
  const fileInput = document.getElementById("invoice-file");
  const resultBox = document.getElementById("invoice-result");
  if (!fileInput.files.length) {
    resultBox.innerHTML = `<p class="tagline">Choose a file first.</p>`;
    return;
  }
  resultBox.innerHTML = `<p class="tagline">Processing…</p>`;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  try {
    const res = await authFetch(`${API_BASE}/invoices/upload`, { method: "POST", body: formData });
    const data = await res.json();
    resultBox.innerHTML = `<div class="card"><pre class="mono" style="white-space:pre-wrap;font-size:12px;">${JSON.stringify(data, null, 2)}</pre></div>`;
  } catch (err) {
    resultBox.innerHTML = `<p class="tagline" style="color:var(--red-600)">Upload failed: ${err}</p>`;
  }
}

// ---------------- PO upload ----------------
async function uploadPO() {
  const fileInput = document.getElementById("po-file");
  const resultBox = document.getElementById("po-result");
  if (!fileInput.files.length) {
    resultBox.innerHTML = `<p class="tagline">Choose a file first.</p>`;
    return;
  }
  resultBox.innerHTML = `<p class="tagline">Processing…</p>`;

  const file = fileInput.files[0];
  const isExcel = file.name.endsWith(".xlsx");
  const endpoint = isExcel ? "/po/upload-excel" : "/po/upload-slip";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}${endpoint}`, { method: "POST", body: formData });
    const data = await res.json();
    resultBox.innerHTML = `<div class="card"><pre class="mono" style="white-space:pre-wrap;font-size:12px;">${JSON.stringify(data, null, 2)}</pre></div>`;
    if (!isExcel) {
      resultBox.innerHTML += `<p class="tagline">Scanned slip extracted — review the values above, then confirm via <span class="mono">/po/confirm</span> before they're applied to stock.</p>`;
    }
  } catch (err) {
    resultBox.innerHTML = `<p class="tagline" style="color:var(--red-600)">Upload failed: ${err}</p>`;
  }
}

// ---------------- Review queue ----------------
async function loadReviewQueue() {
  const list = document.getElementById("review-list");
  try {
    const data = await authFetch(`${API_BASE}/review`).then((r) => r.json());
    if (!data.queue.length) {
      list.innerHTML = `<p class="tagline" style="color:var(--ink-600)">Nothing flagged right now.</p>`;
      return;
    }
    list.innerHTML = data.queue.map((item) => `
      <div class="queue-item ${item.status === "needs_substitution_confirm" ? "substitution" : ""}">
        <span class="tag">${item.status.replace(/_/g, " ")}</span>
        <p style="margin:6px 0 2px; font-weight:600;">${item.raw_description || "—"}</p>
        <p class="reason">${item.reason || ""}</p>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = `<p class="tagline" style="color:var(--red-600)">Failed to load review queue.</p>`;
  }
}

// ---------------- Brands ----------------
async function loadBrands() {
  const listEl = document.getElementById("brands-list");
  const selectEl = document.getElementById("map-brand-select");
  try {
    const data = await authFetch(`${API_BASE}/brands`).then((r) => r.json());
    listEl.innerHTML = data.brands.map((b) => `<p style="margin:6px 0;">🏷️ ${b.name}</p>`).join("");
    selectEl.innerHTML = data.brands.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="tagline" style="color:var(--red-600)">Failed to load brands.</p>`;
  }
}

async function addBrand() {
  const name = document.getElementById("new-brand-name").value.trim();
  if (!name) return;
  await authFetch(`${API_BASE}/brands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  document.getElementById("new-brand-name").value = "";
  loadBrands();
}

async function mapCustomer() {
  const customer_name = document.getElementById("map-customer-name").value.trim();
  const brand_id = parseInt(document.getElementById("map-brand-select").value, 10);
  if (!customer_name || !brand_id) return;
  await authFetch(`${API_BASE}/brands/map-customer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_name, brand_id }),
  });
  document.getElementById("map-customer-name").value = "";
}

// ---------------- Init ----------------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  });
}

(async function init() {
  if (getToken()) {
    try {
      const res = await authFetch(`${API_BASE}/auth/me`);
      if (res.ok) {
        document.getElementById("bottom-nav").classList.remove("hidden");
        showScreen("dashboard");
        return;
      }
    } catch (err) {
      // authFetch already redirects to login on a 401
      return;
    }
  }
  showScreen("login");
})();
