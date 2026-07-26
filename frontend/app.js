// PackIn.ai frontend — vanilla JS, no build step needed.
// Change this to your deployed backend URL in production.
const API_BASE = window.PACKIN_API_BASE || "http://localhost:8000";

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
      fetch(`${API_BASE}/inventory`).then((r) => r.json()),
      fetch(`${API_BASE}/inventory/low-stock`).then((r) => r.json()),
      fetch(`${API_BASE}/activity?limit=10`).then((r) => r.json()),
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

function downloadExport(format) {
  window.open(`${API_BASE}/inventory/export?format=${format}`, "_blank");
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
    const res = await fetch(`${API_BASE}/invoices/upload`, { method: "POST", body: formData });
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
    const res = await fetch(`${API_BASE}${endpoint}`, { method: "POST", body: formData });
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
    const data = await fetch(`${API_BASE}/review`).then((r) => r.json());
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
    const data = await fetch(`${API_BASE}/brands`).then((r) => r.json());
    listEl.innerHTML = data.brands.map((b) => `<p style="margin:6px 0;">🏷️ ${b.name}</p>`).join("");
    selectEl.innerHTML = data.brands.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="tagline" style="color:var(--red-600)">Failed to load brands.</p>`;
  }
}

async function addBrand() {
  const name = document.getElementById("new-brand-name").value.trim();
  if (!name) return;
  await fetch(`${API_BASE}/brands`, {
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
  await fetch(`${API_BASE}/brands/map-customer`, {
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

showScreen("dashboard");
