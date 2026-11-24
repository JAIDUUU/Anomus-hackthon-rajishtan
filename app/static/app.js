// ==============================================================================
// RAJASTHAN POLICE CYBER CRIME CELL - COMMAND CENTER CORE JS
// ==============================================================================

let currentToken = localStorage.getItem("token") || "";
let currentUser = null;
let currentCaseId = "";
let cytoscapeInstance = null;
let leafletMap = null;
let leafletLayerGroup = null;

// Chart Instances
let dashDistChart = null;
let mfcChartInstance = null;
let dayNightChartInstance = null;

// Pagination state for Raw CDR
let cdrCurrentPage = 1;
const cdrPageLimit = 25;
let cdrTotalRecords = 0;
let cdrSearchDebounceTimer = null;

// Cached analytics data
let cachedAnalytics = null;

// ----------------- DOM READY INITIALIZATION -----------------
document.addEventListener("DOMContentLoaded", async () => {
  startLiveClock();
  setupKeyboardShortcuts();
  await initSession();
  await loadCasesList();
  await loadAvailableMappings();
  await loadExecutiveMetrics();
});

// ----------------- REAL-TIME LIVE TICKING CLOCK (IST) -----------------
function startLiveClock() {
  function updateClock() {
    const now = new Date();
    // Offset for Indian Standard Time (UTC +5:30)
    const istOffset = 5.5 * 60 * 60 * 1000;
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const istDate = new Date(utc + istOffset);

    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const dd = String(istDate.getDate()).padStart(2, "0");
    const mmm = months[istDate.getMonth()];
    const yyyy = istDate.getFullYear();
    const hh = String(istDate.getHours()).padStart(2, "0");
    const mm = String(istDate.getMinutes()).padStart(2, "0");
    const ss = String(istDate.getSeconds()).padStart(2, "0");

    const clockEl = document.getElementById("live-clock-display");
    if (clockEl) {
      clockEl.innerText = `${dd}-${mmm}-${yyyy} ${hh}:${mm}:${ss} IST`;
    }
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// ----------------- KEYBOARD SHORTCUTS -----------------
function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Focus search on Ctrl+K or /
    if ((e.ctrlKey && e.key === "k") || (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA")) {
      e.preventDefault();
      const s = document.getElementById("global-search-input");
      if (s) {
        s.focus();
        s.select();
      }
    }
    // Close modals on Escape
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay.active").forEach(m => m.classList.remove("active"));
    }
  });
}

// ----------------- AUTHENTICATION & SESSION -----------------
async function initSession() {
  if (!currentToken) {
    await autoLogin("io_sharma", "IO@RajPolice2026");
    return;
  }
  try {
    const res = await fetch("/api/auth/me", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      currentUser = await res.json();
      updateUserUI();
    } else {
      await autoLogin("io_sharma", "IO@RajPolice2026");
    }
  } catch (err) {
    console.error("Session init error:", err);
    await autoLogin("io_sharma", "IO@RajPolice2026");
  }
}

async function autoLogin(username, password) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (res.ok) {
      const data = await res.json();
      currentToken = data.access_token;
      localStorage.setItem("token", currentToken);
      currentUser = data.user;
      updateUserUI();
    }
  } catch (e) {
    console.error("Auto login error:", e);
  }
}

function updateUserUI() {
  if (!currentUser) return;
  const nameEl = document.getElementById("header-user-name");
  const roleEl = document.getElementById("header-user-role");
  const badgeWrap = document.getElementById("user-profile-badge");

  if (nameEl) nameEl.innerText = currentUser.full_name;
  if (roleEl) {
    if (currentUser.role === "admin") {
      roleEl.innerText = "ACP Meena (Admin)";
      roleEl.className = "role-tag role-admin";
      document.getElementById("audit-nav-btn").style.display = "flex";
    } else if (currentUser.role === "senior_officer") {
      roleEl.innerText = "SP Verma (Senior)";
      roleEl.className = "role-tag role-senior";
      document.getElementById("audit-nav-btn").style.display = "flex";
    } else {
      roleEl.innerText = "IO Sharma (Analyst)";
      roleEl.className = "role-tag role-io";
      document.getElementById("audit-nav-btn").style.display = "none";
    }
  }

  const selectBox = document.getElementById("quick-role-switch");
  if (selectBox) selectBox.value = currentUser.username;
}

async function switchRole(username) {
  const passwords = {
    "io_sharma": "IO@RajPolice2026",
    "sp_verma": "SP@RajPolice2026",
    "admin": "Admin@RajPolice2026"
  };
  await autoLogin(username, passwords[username]);
  alert(`Switched active officer to: ${currentUser.full_name} (${currentUser.role})`);
  if (currentCaseId) {
    loadCaseBatches();
    loadObservations();
  }
}

function showLoginModal() {
  document.getElementById("login-modal").classList.add("active");
}

function closeLoginModal() {
  document.getElementById("login-modal").classList.remove("active");
}

async function handleManualLogin(e) {
  e.preventDefault();
  const u = document.getElementById("login-username").value;
  const p = document.getElementById("login-password").value;
  await autoLogin(u, p);
  closeLoginModal();
}

// ----------------- CASE MANAGEMENT -----------------
async function loadCasesList() {
  try {
    const res = await fetch("/api/cases", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const cases = await res.json();
    const selector = document.getElementById("case-selector");
    selector.innerHTML = "";

    if (cases.length === 0) {
      selector.innerHTML = `<option value="">-- No Cases In System --</option>`;
      return;
    }

    cases.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.id} - ${c.title}`;
      selector.appendChild(opt);
    });

    if (!currentCaseId && cases.length > 0) {
      currentCaseId = cases[0].id;
    }
    selector.value = currentCaseId;
    await onCaseSelected(currentCaseId);
  } catch (err) {
    console.error("Error loading cases:", err);
  }
}

async function changeActiveCase(caseId) {
  if (!caseId) return;
  currentCaseId = caseId;
  await onCaseSelected(caseId);
}

async function onCaseSelected(caseId) {
  cachedAnalytics = null;
  await loadExecutiveMetrics(caseId);
  await loadCaseDetails(caseId);

  // Refresh whatever active view is open
  const activeView = document.querySelector(".module-view.active");
  if (activeView) {
    const viewId = activeView.id.replace("view-", "");
    dispatchViewLoad(viewId);
  }
}

async function loadCaseDetails(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    // Update Header Stats
    document.getElementById("stat-hdr-cdr").innerText = data.stats.cdr_count || 0;
    document.getElementById("stat-hdr-ipdr").innerText = data.stats.ipdr_count || 0;
    const suspects = (data.brief_data && data.brief_data.suspects) ? data.brief_data.suspects : [];
    document.getElementById("stat-hdr-suspects").innerText = suspects.length;
    document.getElementById("badge-cdr-count").innerText = data.stats.cdr_count || 0;

    // Update Dashboard Brief
    document.getElementById("dash-case-title").innerText = `${data.id}: ${data.title}`;
    document.getElementById("dash-case-desc").innerText = data.description || "No narrative brief provided.";
    document.getElementById("dash-case-status").innerText = data.status || "ACTIVE";

    // Suspect Chips
    const chipsBox = document.getElementById("dash-suspects-chips");
    chipsBox.innerHTML = "";
    if (suspects.length > 0) {
      suspects.forEach(s => {
        const btn = document.createElement("button");
        btn.className = "chip-btn";
        btn.innerHTML = `👤 <b>${s.name || s.role}</b>: ${s.phone || ""}`;
        btn.onclick = () => {
          switchView("mfc");
        };
        chipsBox.appendChild(btn);
      });
    } else {
      chipsBox.innerHTML = `<span style="color:var(--text-muted);font-size:12px;">No suspects indexed yet.</span>`;
    }
  } catch (err) {
    console.error("Error loading case details:", err);
  }
}

async function loadDemoCase() {
  const btn = document.getElementById("btn-load-demo");
  const origText = btn.innerText;
  btn.innerText = "⏳ Loading Demo Case...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/cases/demo", {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const data = await res.json();
    if (res.ok) {
      alert("✅ Demo Case 'CASE-RAJ-2026-0042' loaded successfully with CDRs & IPDRs!");
      await loadCasesList();
      currentCaseId = "CASE-RAJ-2026-0042";
      document.getElementById("case-selector").value = currentCaseId;
      await onCaseSelected(currentCaseId);
    } else {
      alert("Error: " + (data.detail || "Failed to load demo case"));
    }
  } catch (e) {
    console.error("Demo loader error:", e);
    alert("Connection error loading demo case");
  } finally {
    btn.innerText = origText;
    btn.disabled = false;
  }
}

// ----------------- EXECUTIVE 8-CARD METRICS -----------------
async function loadExecutiveMetrics(caseId = null) {
  try {
    const url = caseId ? `/api/dashboard/metrics?case_id=${encodeURIComponent(caseId)}` : `/api/dashboard/metrics`;
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const m = await res.json();

    document.getElementById("metric-total-cases").innerText = m.total_cases;
    document.getElementById("metric-pending-cases").innerText = m.pending_cases;
    document.getElementById("metric-completed-cases").innerText = m.completed_cases;
    document.getElementById("metric-active-cases").innerText = m.active_investigations;
    document.getElementById("metric-total-cdrs").innerText = (m.total_uploaded_cdrs ?? m.total_cdrs ?? 0).toLocaleString();
    document.getElementById("metric-analyzed-numbers").innerText = m.analyzed_numbers || 0;
    document.getElementById("metric-common-numbers").innerText = m.common_numbers || 0;
    document.getElementById("metric-locations-tracked").innerText = m.locations_tracked || 0;
  } catch (err) {
    console.error("Error loading metrics:", err);
  }
}

// ----------------- SIDEBAR & VIEW SWITCHER -----------------
function switchView(viewName) {
  // Update sidebar buttons
  document.querySelectorAll(".sidebar-nav-btn").forEach(btn => {
    btn.classList.remove("active");
  });
  const targetBtn = Array.from(document.querySelectorAll(".sidebar-nav-btn")).find(btn => 
    btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(`'${viewName}'`)
  );
  if (targetBtn) targetBtn.classList.add("active");

  // Switch view containers
  document.querySelectorAll(".module-view").forEach(v => v.classList.remove("active"));
  const viewEl = document.getElementById(`view-${viewName}`);
  if (viewEl) {
    viewEl.classList.add("active");
  }

  dispatchViewLoad(viewName);
}

function dispatchViewLoad(viewName) {
  if (!currentCaseId) return;

  switch (viewName) {
    case "dashboard":
      loadDashboardDistribution();
      break;
    case "raw-cdr":
      loadRawCdrPage(1);
      break;
    case "mfc":
      loadMfcView();
      break;
    case "graph":
      loadNetworkGraph();
      break;
    case "first-last":
      loadFirstLastView();
      break;
    case "day-night":
      loadDayNightView();
      break;
    case "missing-dates":
      loadMissingDatesView();
      break;
    case "movement":
      loadMovementView();
      break;
    case "service-numbers":
      loadServiceNumbersView();
      break;
    case "international":
      loadInternationalView();
      break;
    case "common-numbers":
      runCommonAnalysis();
      break;
    case "meetings":
      runMeetingDetection();
      break;
    case "imei-summary":
      loadImeiSummaryView();
      break;
    case "imsi-summary":
      loadImsiSummaryView();
      break;
    case "device-changes":
      runDeviceChangeDetection();
      break;
    case "ownership":
      loadOwnershipView();
      break;
    case "geo-map":
      renderTowerMap();
      break;
    case "day-locations":
      loadDayLocationsView();
      break;
    case "night-locations":
      loadNightLocationsView();
      break;
    case "assistant":
      loadObservations();
      break;
    case "import":
      loadCaseBatches();
      break;
    case "audit":
      loadAuditLogs();
      break;
  }
}

// ----------------- FETCH CACHED ANALYTICS -----------------
async function getCaseAnalytics() {
  if (cachedAnalytics) return cachedAnalytics;
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/analytics`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      cachedAnalytics = await res.json();
      return cachedAnalytics;
    }
  } catch (e) {
    console.error("Analytics fetch error:", e);
  }
  return null;
}

// ----------------- DASHBOARD DISTRIBUTION CHART -----------------
async function loadDashboardDistribution() {
  const data = await getCaseAnalytics();
  if (!data) return;

  const ctx = document.getElementById("chart-dash-distribution");
  if (!ctx) return;

  const dayCalls = data.day_night.day_calls || 0;
  const nightCalls = data.day_night.night_calls || 0;
  let inCalls = 0, outCalls = 0, smsCalls = 0;

  if (data.mfc) {
    data.mfc.forEach(c => {
      inCalls += c.in_count || 0;
      outCalls += c.out_count || 0;
      smsCalls += c.sms_count || 0;
    });
  }

  if (dashDistChart) dashDistChart.destroy();
  dashDistChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Day (06-22h)", "Night (22-06h)", "Incoming", "Outgoing", "SMS"],
      datasets: [{
        data: [dayCalls, nightCalls, inCalls, outCalls, smsCalls],
        backgroundColor: ["#0ea5e9", "#f59e0b", "#10b981", "#3b82f6", "#a855f7"],
        borderWidth: 1,
        borderColor: "#131f37"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#94a3b8", font: { size: 11 } }
        }
      }
    }
  });
}

// ----------------- MODULE: RAW CDR DATA (PAGINATED) -----------------
async function loadRawCdrPage(page = 1) {
  cdrCurrentPage = page;
  const tbody = document.getElementById("raw-cdr-tbody");
  tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;"><div class="spinner"></div> Loading CDRs...</td></tr>`;

  const search = document.getElementById("cdr-filter-search").value;
  const callType = document.getElementById("cdr-filter-type").value;

  try {
    const url = `/api/cases/${currentCaseId}/raw-cdr?page=${page}&limit=${cdrPageLimit}&search=${encodeURIComponent(search)}&call_type=${encodeURIComponent(callType)}`;
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:#fca5a5;">Failed to load CDRs.</td></tr>`;
      return;
    }
    const data = await res.json();
    cdrTotalRecords = data.total;

    if (data.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--text-muted);">No records match criteria.</td></tr>`;
      document.getElementById("cdr-pagination-info").innerText = "Showing 0 of 0";
      return;
    }

    const startIdx = (data.page - 1) * data.limit + 1;
    const endIdx = Math.min(startIdx + data.records.length - 1, data.total);
    document.getElementById("cdr-pagination-info").innerText = `Showing ${startIdx}-${endIdx} of ${data.total} records`;

    tbody.innerHTML = "";
    data.records.forEach((r, i) => {
      const tr = document.createElement("tr");
      const badgeClass = r.call_type === "OUT" ? "badge-blue" : (r.call_type === "IN" ? "badge-green" : "badge-purple");
      tr.innerHTML = `
        <td>${startIdx + i}</td>
        <td style="font-family:monospace;font-size:11.5px;color:#cbd5e1;">${r.start_time}</td>
        <td><b style="color:#f8fafc;">${r.a_number}</b></td>
        <td><b style="color:#f8fafc;">${r.b_number}</b></td>
        <td><span class="metric-card-badge ${badgeClass}">${r.call_type}</span></td>
        <td>${r.duration_sec}s</td>
        <td><span style="color:#fbbf24;">${r.cell_id}</span> <small style="color:var(--text-muted);">${r.area_name || r.location_name || ""}</small></td>
        <td style="font-family:monospace;font-size:11px;">${r.imei || "-"}</td>
        <td style="font-family:monospace;font-size:11px;">${r.imsi || "-"}</td>
        <td>
          <button class="ev-pill" onclick="viewEvidence('CDR', '${r.source_file}', ${r.source_row})">
            ⚖️ Sec 65B
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("btn-cdr-prev").disabled = (data.page <= 1);
    document.getElementById("btn-cdr-next").disabled = (endIdx >= data.total);
  } catch (e) {
    console.error("CDR load error:", e);
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:#fca5a5;">Error loading CDR records.</td></tr>`;
  }
}

function changeCdrPage(delta) {
  const newPage = cdrCurrentPage + delta;
  if (newPage >= 1) {
    loadRawCdrPage(newPage);
  }
}

function debounceCdrSearch() {
  clearTimeout(cdrSearchDebounceTimer);
  cdrSearchDebounceTimer = setTimeout(() => {
    loadRawCdrPage(1);
  }, 350);
}

function exportCdrCsv() {
  window.open(`/api/cases/${currentCaseId}/report?format=xlsx`, "_blank");
}

// ----------------- MODULE: MFC ANALYSIS -----------------
async function loadMfcView() {
  const data = await getCaseAnalytics();
  if (!data || !data.mfc) return;

  const tbody = document.getElementById("mfc-table-body");
  tbody.innerHTML = "";

  if (data.mfc.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No communication data.</td></tr>`;
    return;
  }

  const top10 = data.mfc.slice(0, 10);
  data.mfc.forEach((c, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td><b style="color:#38bdf8;">${c.number}</b></td>
      <td><b>${c.calls}</b></td>
      <td>${c.duration}s</td>
      <td><small>${c.in_count} IN / ${c.out_count} OUT / ${c.sms_count} SMS</small></td>
      <td><span class="metric-card-badge badge-blue">${c.percentage}%</span></td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="filterByNumber('${c.number}')">Filter</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Chart
  const ctx = document.getElementById("chart-mfc");
  if (ctx) {
    if (mfcChartInstance) mfcChartInstance.destroy();
    mfcChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: top10.map(c => c.number),
        datasets: [{
          label: "Call Volume",
          data: top10.map(c => c.calls),
          backgroundColor: "#0ea5e9",
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
          y: { ticks: { color: "#f8fafc", font: { weight: "bold" } }, grid: { display: false } }
        }
      }
    });
  }
}

function filterByNumber(number) {
  switchView("raw-cdr");
  document.getElementById("cdr-filter-search").value = number;
  loadRawCdrPage(1);
}

// ----------------- MODULE: FIRST / LAST CALL -----------------
async function loadFirstLastView() {
  const data = await getCaseAnalytics();
  if (!data || !data.first_last) return;

  const tbody = document.getElementById("first-last-table-body");
  tbody.innerHTML = "";

  data.first_last.forEach(c => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#38bdf8;">${c.number}</b></td>
      <td style="font-family:monospace;font-size:11.5px;">${c.first_call || "-"}</td>
      <td style="font-family:monospace;font-size:11.5px;">${c.last_call || "-"}</td>
      <td><span class="metric-card-badge badge-purple">${c.days_span} days</span></td>
      <td><b>${c.total_calls}</b></td>
      <td>${c.avg_duration}s</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: DAY / NIGHT ANALYSIS -----------------
async function loadDayNightView() {
  const data = await getCaseAnalytics();
  if (!data || !data.day_night) return;

  const dn = data.day_night;
  document.getElementById("stat-day-calls").innerText = dn.day_calls;
  document.getElementById("stat-day-pct").innerText = `${dn.day_pct}%`;
  document.getElementById("stat-night-calls").innerText = dn.night_calls;
  document.getElementById("stat-night-pct").innerText = `${dn.night_pct}%`;

  // Chart
  const ctx = document.getElementById("chart-day-night");
  if (ctx) {
    if (dayNightChartInstance) dayNightChartInstance.destroy();
    dayNightChartInstance = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Daytime (06:00 - 22:00)", "Nighttime (22:00 - 06:00)"],
        datasets: [{
          data: [dn.day_calls, dn.night_calls],
          backgroundColor: ["#0ea5e9", "#f59e0b"],
          borderColor: "#131f37",
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#f8fafc" } }
        }
      }
    });
  }

  // Night Table
  const tbody = document.getElementById("night-numbers-tbody");
  tbody.innerHTML = "";
  if (dn.night_numbers && dn.night_numbers.length > 0) {
    dn.night_numbers.forEach(n => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b style="color:#fbbf24;">${n.number}</b></td>
        <td><b>${n.night_calls}</b></td>
        <td>${n.total_calls}</td>
        <td><span class="metric-card-badge badge-amber">${n.night_ratio}%</span></td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No night communications detected.</td></tr>`;
  }
}

// ----------------- MODULE: MISSING DATES / GAPS -----------------
async function loadMissingDatesView() {
  const data = await getCaseAnalytics();
  if (!data || !data.missing_dates) return;

  const tbody = document.getElementById("missing-dates-tbody");
  tbody.innerHTML = "";

  if (data.missing_dates.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#10b981;">No silence gaps detected. Consistent communication throughout timeframe.</td></tr>`;
    return;
  }

  data.missing_dates.forEach(d => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#ef4444;font-family:monospace;">${d.date}</b></td>
      <td>${d.day_name}</td>
      <td><span class="metric-card-badge badge-amber">SILENCE GAP</span></td>
      <td style="color:var(--text-secondary);">${d.description}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: MOVEMENT & CELL CHANGES -----------------
async function loadMovementView() {
  const data = await getCaseAnalytics();
  if (!data || !data.movement) return;

  const tbody = document.getElementById("movement-tbody");
  tbody.innerHTML = "";

  if (data.movement.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No movement data.</td></tr>`;
    return;
  }

  data.movement.forEach(m => {
    const tr = document.createElement("tr");
    const isRapid = m.time_delta_sec > 0 && m.time_delta_sec < 600;
    tr.innerHTML = `
      <td>#${m.seq}</td>
      <td style="font-family:monospace;font-size:11.5px;">${m.timestamp}</td>
      <td><span style="color:#fbbf24;font-family:monospace;">${m.cell_id}</span></td>
      <td><b>${m.area_name}</b></td>
      <td><b style="color:#38bdf8;">${m.number}</b></td>
      <td>${m.time_delta_sec ? m.time_delta_sec + 's' : '-'}</td>
      <td>
        ${isRapid ? '<span class="metric-card-badge badge-amber">⚡ Rapid Hop (&lt;10m)</span>' : '<span style="color:var(--text-muted);">Standard Transit</span>'}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: SERVICE NUMBERS -----------------
async function loadServiceNumbersView() {
  const data = await getCaseAnalytics();
  if (!data || !data.service_numbers) return;

  const tbody = document.getElementById("service-numbers-tbody");
  tbody.innerHTML = "";

  if (data.service_numbers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No service or toll-free numbers contacted.</td></tr>`;
    return;
  }

  data.service_numbers.forEach(s => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#38bdf8;">${s.number}</b></td>
      <td><span class="metric-card-badge badge-purple">${s.label}</span></td>
      <td><b>${s.calls}</b></td>
      <td style="font-family:monospace;font-size:11px;">${s.first_seen}</td>
      <td style="font-family:monospace;font-size:11px;">${s.last_seen}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: INTERNATIONAL INTEL -----------------
async function loadInternationalView() {
  const data = await getCaseAnalytics();
  if (!data || !data.international_numbers) return;

  const tbody = document.getElementById("international-tbody");
  tbody.innerHTML = "";

  if (data.international_numbers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No international communication detected. All calls domestic (+91).</td></tr>`;
    return;
  }

  data.international_numbers.forEach(item => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#ef4444;">${item.number}</b></td>
      <td><span class="metric-card-badge badge-amber">${item.country_code}</span></td>
      <td><b>${item.calls}</b></td>
      <td style="font-family:monospace;font-size:11px;">${item.first_seen}</td>
      <td style="font-family:monospace;font-size:11px;">${item.last_seen}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: IMEI SUMMARY & TAC -----------------
async function loadImeiSummaryView() {
  const data = await getCaseAnalytics();
  if (!data || !data.imei_summary) return;

  const tbody = document.getElementById("imei-summary-tbody");
  tbody.innerHTML = "";

  if (data.imei_summary.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-muted);">No IMEI records logged.</td></tr>`;
    return;
  }

  data.imei_summary.forEach(im => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#fbbf24;font-family:monospace;">${im.imei}</b></td>
      <td><b style="color:#f8fafc;">${im.brand} ${im.model}</b></td>
      <td><span class="metric-card-badge badge-blue">${im.generation}</span></td>
      <td><small style="color:#38bdf8;">${im.associated_numbers.join(", ") || "-"}</small></td>
      <td><small style="font-family:monospace;">${im.associated_imsis.join(", ") || "-"}</small></td>
      <td><b>${im.calls}</b></td>
      <td style="font-family:monospace;font-size:11px;">${im.first_seen}</td>
      <td style="font-family:monospace;font-size:11px;">${im.last_seen}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: IMSI SUMMARY -----------------
async function loadImsiSummaryView() {
  const data = await getCaseAnalytics();
  if (!data || !data.imsi_summary) return;

  const tbody = document.getElementById("imsi-summary-tbody");
  tbody.innerHTML = "";

  if (data.imsi_summary.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);">No IMSI records logged.</td></tr>`;
    return;
  }

  data.imsi_summary.forEach(im => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b style="color:#38bdf8;font-family:monospace;">${im.imsi}</b></td>
      <td><small>${im.associated_numbers.join(", ") || "-"}</small></td>
      <td><small style="font-family:monospace;">${im.associated_imeis.join(", ") || "-"}</small></td>
      <td><b>${im.calls}</b></td>
      <td style="font-family:monospace;font-size:11px;">${im.first_seen}</td>
      <td style="font-family:monospace;font-size:11px;">${im.last_seen}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: OWNERSHIP INTELLIGENCE / DOSSIERS -----------------
async function loadOwnershipView() {
  const data = await getCaseAnalytics();
  if (!data || !data.ownership) return;

  const container = document.getElementById("ownership-dossiers-container");
  container.innerHTML = "";

  if (data.ownership.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted);">No suspect dossiers recorded in case brief.</p>`;
    return;
  }

  data.ownership.forEach(s => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.background = "#0d172c";
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <h4 style="color:#38bdf8; font-size:15px;">👤 ${s.name} (${s.role || "Target"})</h4>
        <span class="role-tag role-io">${s.id || "SUSPECT"}</span>
      </div>
      <div style="font-size:12.5px; line-height:1.7;">
        <div><b>Primary SIM:</b> <span style="color:#f8fafc; font-weight:bold;">${s.phone || "-"}</span></div>
        ${s.new_phone ? `<div><b>Swapped SIM:</b> <span style="color:#ef4444; font-weight:bold;">${s.new_phone}</span></div>` : ""}
        <div><b>Handset Model:</b> <span style="color:#fbbf24;">${s.handset || "Smartphone"}</span></div>
        <div><b>Assigned IMEI:</b> <span style="font-family:monospace;">${s.imei || "-"}</span></div>
        <div style="margin-top:6px; color:var(--text-secondary);">${s.notes || ""}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

// ----------------- MODULE: DAY & NIGHT LOCATIONS -----------------
async function loadDayLocationsView() {
  const data = await getCaseAnalytics();
  if (!data || !data.day_locations) return;

  const tbody = document.getElementById("day-locs-tbody");
  tbody.innerHTML = "";

  data.day_locations.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span style="color:#fbbf24;font-family:monospace;">${l.cell_id}</span></td>
      <td><b>${l.area_name}</b></td>
      <td><span class="metric-card-badge badge-blue">${l.visits} visits</span></td>
      <td>${l.lat || "-"}</td>
      <td>${l.lon || "-"}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadNightLocationsView() {
  const data = await getCaseAnalytics();
  if (!data || !data.night_locations) return;

  const tbody = document.getElementById("night-locs-tbody");
  tbody.innerHTML = "";

  data.night_locations.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span style="color:#fbbf24;font-family:monospace;">${l.cell_id}</span></td>
      <td><b>${l.area_name}</b></td>
      <td><span class="metric-card-badge badge-amber">${l.visits} night visits</span></td>
      <td>${l.lat || "-"}</td>
      <td>${l.lon || "-"}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ----------------- MODULE: NETWORK GRAPH (CYTOSCAPE) -----------------
function updateNetworkSlider(val) {
  document.getElementById("min-calls-display").innerText = val;
}

async function loadNetworkGraph() {
  const minCalls = document.getElementById("min-calls-slider").value || 1;
  const container = document.getElementById("network-container");
  const label = document.getElementById("network-stats-label");
  label.innerText = "Querying network topology...";

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/network?min_calls=${minCalls}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    label.innerText = `Nodes: ${data.stats.total_nodes} | Edges: ${data.stats.total_edges}`;

    const elements = [];
    data.nodes.forEach(n => {
      elements.push({
        data: {
          id: n.data.id,
          label: n.data.label,
          degree: n.data.degree,
          is_suspect: n.data.is_suspect
        }
      });
    });

    data.edges.forEach(e => {
      elements.push({
        data: {
          id: e.data.id,
          source: e.data.source,
          target: e.data.target,
          weight: Math.min(10, Math.max(1, e.data.call_count / 2)),
          call_count: e.data.call_count
        }
      });
    });

    if (cytoscapeInstance) cytoscapeInstance.destroy();
    cytoscapeInstance = cytoscape({
      container: container,
      elements: elements,
      style: [
        {
          selector: "node",
          style: {
            "label": "data(label)",
            "color": "#f8fafc",
            "font-size": "11px",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "mapData(degree, 1, 20, #0ea5e9, #2563eb)",
            "width": "mapData(degree, 1, 20, 32, 64)",
            "height": "mapData(degree, 1, 20, 32, 64)",
            "border-width": 2,
            "border-color": "#ffffff"
          }
        },
        {
          selector: "node[?is_suspect]",
          style: {
            "background-color": "#ef4444",
            "border-color": "#fbbf24",
            "border-width": 3,
            "font-weight": "bold"
          }
        },
        {
          selector: "edge",
          style: {
            "width": "data(weight)",
            "line-color": "#334155",
            "curve-style": "bezier",
            "opacity": 0.8
          }
        },
        {
          selector: ":selected",
          style: {
            "border-color": "#fbbf24",
            "border-width": 4,
            "line-color": "#0ea5e9"
          }
        }
      ],
      layout: {
        name: "cose",
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000
      }
    });

    cytoscapeInstance.on("tap", "node", (evt) => {
      const node = evt.target;
      alert(`Node Selected: ${node.data("label")}\nConnection Degree: ${node.data("degree")}\nSuspect Flag: ${node.data("is_suspect") ? "YES" : "NO"}`);
    });

  } catch (err) {
    console.error("Network graph error:", err);
    label.innerText = "Error drawing network topology";
  }
}

function explainNetworkWithAI() {
  switchView("assistant");
  sendQuickPrompt("Explain the network topology and identify the central node or syndicate leader.");
}

// ----------------- MODULE: COMMON NUMBERS -----------------
async function runCommonAnalysis() {
  const nums = document.getElementById("common-numbers-input").value;
  const box = document.getElementById("common-numbers-results");
  box.innerHTML = `<div class="spinner"></div> Correlating shared contacts...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/common?numbers=${encodeURIComponent(nums)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    if (data.common_contacts.length === 0 && data.direct_mutual_links.length === 0) {
      box.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">No shared contacts or direct calls found between these numbers.</p>`;
      return;
    }

    let html = "";
    if (data.direct_mutual_links.length > 0) {
      html += `<h4 style="color:#ef4444;margin-bottom:8px;">🚨 Direct Mutual Calls Between Suspects:</h4>`;
      data.direct_mutual_links.forEach(l => {
        html += `
          <div style="background:#0d172c;padding:8px 12px;border-radius:6px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <span><b>${l.party_a}</b> ⟷ <b>${l.party_b}</b></span>
            <span class="metric-card-badge badge-amber">${l.call_count} Direct Calls</span>
          </div>
        `;
      });
    }

    if (data.common_contacts.length > 0) {
      html += `<h4 style="color:#38bdf8;margin-top:12px;margin-bottom:8px;">🔗 Shared Common Contacts (${data.common_contacts.length}):</h4>`;
      html += `
        <div class="table-container">
          <table>
            <thead>
              <tr><th>Common Number</th><th>Connected Targets</th><th>Evidence</th></tr>
            </thead>
            <tbody>
      `;
      data.common_contacts.forEach(c => {
        html += `
          <tr>
            <td><b style="color:#f8fafc;">${c.common_number}</b></td>
            <td><span class="metric-card-badge badge-blue">${c.connected_to_targets.join(", ")}</span></td>
            <td>
              <button class="ev-pill" onclick="viewEvidence('CDR', '${c.evidence[0].source_file}', ${c.evidence[0].source_row})">
                ⚖️ Section 65B
              </button>
            </td>
          </tr>
        `;
      });
      html += `</tbody></table></div>`;
    }

    box.innerHTML = html;
  } catch (err) {
    box.innerHTML = `<p style="color:#fca5a5;">Error running common number correlation.</p>`;
  }
}

// ----------------- MODULE: MEETING DETECTION -----------------
async function runMeetingDetection() {
  const n1 = document.getElementById("meet-num1").value;
  const n2 = document.getElementById("meet-num2").value;
  const win = document.getElementById("meet-window").value || 30;
  const box = document.getElementById("meeting-detection-results");

  box.innerHTML = `<div class="spinner"></div> Scanning concurrent cell site events...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/meetings?num1=${encodeURIComponent(n1)}&num2=${encodeURIComponent(n2)}&window=${win}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    if (!data.meetings || data.meetings.length === 0) {
      box.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">No concurrent cell tower meetings detected within ${win} minutes.</p>`;
      return;
    }

    let html = `
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Cell Tower ID</th>
              <th>Area / Location</th>
              <th>Time Difference</th>
              <th>${n1} Timestamp</th>
              <th>${n2} Timestamp</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
    `;

    data.meetings.forEach(m => {
      const diffMins = Math.round(m.time_diff_sec / 60);
      html += `
        <tr>
          <td><b style="color:#fbbf24;">${m.cell_id}</b></td>
          <td><b>${m.area_name}</b></td>
          <td><span class="metric-card-badge badge-amber">${diffMins} min diff</span></td>
          <td style="font-family:monospace;font-size:11px;">${m.event_target_1.timestamp}</td>
          <td style="font-family:monospace;font-size:11px;">${m.event_target_2.timestamp}</td>
          <td>
            <button class="ev-pill" onclick="viewEvidence('CDR', '${m.event_target_1.source_file}', ${m.event_target_1.source_row})">
              ⚖️ Sec 65B
            </button>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table></div>`;
    box.innerHTML = html;
  } catch (err) {
    box.innerHTML = `<p style="color:#fca5a5;">Error running meeting scan.</p>`;
  }
}

// ----------------- MODULE: SIM SWAPS & HOPPING -----------------
async function runDeviceChangeDetection() {
  const box = document.getElementById("device-changes-results");
  box.innerHTML = `<div class="spinner"></div> Analyzing IMEI and SIM hops...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/device-changes`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    let html = "";
    if (data.multi_number_imeis && data.multi_number_imeis.length > 0) {
      html += `<h4 style="color:#ef4444;margin-bottom:8px;">🚨 Handsets (IMEI) Shared Across Multiple Phone Numbers:</h4>`;
      data.multi_number_imeis.forEach(item => {
        html += `
          <div style="background:#0d172c;padding:10px 14px;border-radius:6px;margin-bottom:8px;border-left:3px solid #ef4444;">
            <div><b>IMEI:</b> <span style="font-family:monospace;color:#fbbf24;">${item.imei}</span> &bull; <b>Distinct Numbers:</b> ${item.distinct_numbers_count}</div>
            <div style="margin-top:4px;color:#38bdf8;font-size:12px;">Numbers: ${item.numbers.join(", ")}</div>
          </div>
        `;
      });
    }

    if (data.multi_imei_numbers && data.multi_imei_numbers.length > 0) {
      html += `<h4 style="color:#f59e0b;margin-top:14px;margin-bottom:8px;">⚠️ Phone Numbers Hopping Multiple Handsets (IMEIs):</h4>`;
      data.multi_imei_numbers.forEach(item => {
        html += `
          <div style="background:#0d172c;padding:10px 14px;border-radius:6px;margin-bottom:8px;border-left:3px solid #f59e0b;">
            <div><b>Phone:</b> <span style="color:#38bdf8;font-weight:bold;">${item.number}</span> &bull; <b>Handsets:</b> ${item.distinct_imeis_count}</div>
            <div style="margin-top:4px;font-family:monospace;font-size:11px;color:var(--text-secondary);">IMEIs: ${item.imeis.join(", ")}</div>
          </div>
        `;
      });
    }

    if (!html) {
      html = `<p style="color:#10b981;">No SIM swap anomalies detected in this case dataset.</p>`;
    }

    box.innerHTML = html;
  } catch (err) {
    box.innerHTML = `<p style="color:#fca5a5;">Error running device changes detection.</p>`;
  }
}

// ----------------- MODULE: GEO MAP (LEAFLET) -----------------
async function renderTowerMap(targetNum = null) {
  const num = targetNum || document.getElementById("map-suspect-select").value || "9829022222";
  const countLabel = document.getElementById("map-event-count");
  countLabel.innerText = "Querying location timeline...";

  if (!leafletMap) {
    leafletMap = L.map("map-container").setView([26.9124, 75.7873], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap | Rajasthan Police Cyber Cell",
      maxZoom: 18
    }).addTo(leafletMap);
    leafletLayerGroup = L.layerGroup().addTo(leafletMap);
  } else {
    leafletLayerGroup.clearLayers();
  }
  setTimeout(() => {
    if (leafletMap) leafletMap.invalidateSize();
  }, 100);

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/towers/timeline?number=${encodeURIComponent(num)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    countLabel.innerText = `Tracked Tower Events: ${data.total_tower_events}`;

    const latlngs = [];
    data.timeline.forEach(pt => {
      if (pt.lat && pt.lon) {
        latlngs.push([pt.lat, pt.lon]);

        const markerHtml = `
          <div style="background:#0ea5e9;color:#0b1120;border:2px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;">
            ${pt.seq}
          </div>
        `;
        const customIcon = L.divIcon({
          html: markerHtml,
          className: "",
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });

        const m = L.marker([pt.lat, pt.lon], { icon: customIcon });
        m.bindPopup(`
          <div style="font-family:sans-serif;font-size:12px;color:#0b1120;">
            <b style="color:#1e3a8a;">Seq #${pt.seq}: ${pt.area_name}</b><br>
            Cell ID: <code>${pt.cell_id}</code><br>
            Time: ${pt.timestamp}<br>
            Peer: <b>${pt.peer}</b> (${pt.call_type})
          </div>
        `);
        leafletLayerGroup.addLayer(m);
      }
    });

    if (latlngs.length > 0) {
      const poly = L.polyline(latlngs, {
        color: "#f59e0b",
        weight: 3,
        dashArray: "6, 8",
        opacity: 0.8
      });
      leafletLayerGroup.addLayer(poly);
      setTimeout(() => {
        if (leafletMap) {
          leafletMap.invalidateSize();
          leafletMap.fitBounds(poly.getBounds(), { padding: [40, 40] });
        }
      }, 150);
    }
  } catch (err) {
    console.error("Map render error:", err);
    countLabel.innerText = "Error loading trajectory points";
  }
}

// ----------------- MODULE: IPDR ANALYSIS -----------------
async function handleIpdrMatch(e) {
  e.preventDefault();
  const ip = document.getElementById("ipdr-query-ip").value;
  const port = document.getElementById("ipdr-query-port").value;
  const time = document.getElementById("ipdr-query-time").value;
  const resBox = document.getElementById("ipdr-match-result");

  resBox.innerHTML = `<div class="spinner"></div> Resolving carrier CGNAT subscriber match...`;

  try {
    const url = `/api/cases/${currentCaseId}/ipdr/match?ip=${encodeURIComponent(ip)}&port=${encodeURIComponent(port)}&timestamp=${encodeURIComponent(time)}`;
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const data = await res.json();

    if (!data.matched && !data.match_found) {
      resBox.innerHTML = `
        <div style="color:#ef4444;font-size:13px;padding:12px;background:#0d172c;border-radius:6px;">
          ❌ No CGNAT session matched for IP <b>${ip}:${port}</b> at <b>${time}</b>.
        </div>
      `;
      return;
    }

    const s = data.session || (data.sessions && data.sessions[0]);
    resBox.innerHTML = `
      <div style="background:#0d172c;border:1px solid #1e3a8a;border-radius:6px;padding:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <h4 style="color:#10b981;font-size:15px;">✅ Carrier NAT Session Resolved</h4>
          <span class="metric-card-badge badge-green">99.8% Confidence</span>
        </div>
        <div style="font-size:13px;line-height:1.8;">
          <div><b>Subscriber Mobile Number:</b> <span style="color:#38bdf8;font-size:14px;font-weight:bold;">${s.subscriber_number}</span></div>
          <div><b>Source Public IP:</b> <span style="font-family:monospace;">${s.source_ip}:${s.source_port}</span></div>
          <div><b>Destination IP:</b> <span style="font-family:monospace;">${s.destination_ip}:${s.destination_port}</span></div>
          <div><b>Session Window:</b> ${s.session_start} to ${s.session_end}</div>
          <div><b>App Protocol Hint:</b> <span style="color:#fbbf24;font-weight:bold;">${s.app_hint}</span></div>
          <div><b>Data Transferred:</b> ${s.bytes_transferred} bytes</div>
          <div style="margin-top:12px;">
            <button class="ev-pill" onclick="viewEvidence('IPDR', '${s.source_file}', ${s.source_row})">
              ⚖️ Section 65B Source Log Evidence
            </button>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    resBox.innerHTML = `<p style="color:#fca5a5;">Error querying IPDR session.</p>`;
  }
}

function prefillIpdrTest() {
  document.getElementById("ipdr-query-ip").value = "103.211.54.12";
  document.getElementById("ipdr-query-port").value = "44321";
  document.getElementById("ipdr-query-time").value = "2026-11-20 18:25:10";
}

async function runSubscriberIpdr() {
  const sub = document.getElementById("ipdr-sub-input").value;
  const resBox = document.getElementById("ipdr-match-result");
  resBox.innerHTML = `<div class="spinner"></div> Searching subscriber sessions...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/ipdr/subscriber?subscriber=${encodeURIComponent(sub)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const data = await res.json();

    if (!data.sessions || data.sessions.length === 0) {
      resBox.innerHTML = `<p style="color:var(--text-muted);">No IPDR sessions found for subscriber ${sub}.</p>`;
      return;
    }

    let html = `
      <div style="margin-bottom:8px;font-size:13px;">
        Total Sessions for <b>${sub}</b>: <b>${data.total_sessions}</b> (Total Volume: ${data.total_bytes} bytes)
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr><th>Public IP:Port</th><th>Dest IP:Port</th><th>Session Start</th><th>App Hint</th><th>Evidence</th></tr>
          </thead>
          <tbody>
    `;

    data.sessions.forEach(s => {
      html += `
        <tr>
          <td><span style="font-family:monospace;">${s.source_ip}:${s.source_port}</span></td>
          <td><span style="font-family:monospace;">${s.destination_ip}:${s.destination_port}</span></td>
          <td style="font-family:monospace;font-size:11px;">${s.session_start}</td>
          <td><span class="metric-card-badge badge-blue">${s.app_hint}</span></td>
          <td>
            <button class="ev-pill" onclick="viewEvidence('IPDR', '${s.source_file}', ${s.source_row})">
              ⚖️ Sec 65B
            </button>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table></div>`;
    resBox.innerHTML = html;
  } catch (err) {
    resBox.innerHTML = `<p style="color:#fca5a5;">Error loading subscriber sessions.</p>`;
  }
}

// ----------------- MODULE: AI ASSISTANT CHAT -----------------
async function loadObservations() {
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/observations`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const obsList = await res.json();
    const chatContainer = document.getElementById("chat-messages-container");

    obsList.forEach(obs => {
      // Check if message already rendered
      if (!document.getElementById(`obs-card-${obs.id}`)) {
        renderAIResponseCard(obs);
      }
    });
  } catch (err) {
    console.error("Error loading observations:", err);
  }
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const query = input.value.trim();
  if (!query) return;

  renderUserMessage(query);
  input.value = "";

  const sendBtn = document.getElementById("btn-chat-send");
  sendBtn.disabled = true;
  sendBtn.innerText = "⏳...";

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/assistant`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ query: query })
    });
    const data = await res.json();
    renderAIResponseCard(data);
  } catch (err) {
    renderUserMessage("⚠️ Error: Assistant could not answer at this moment.");
  } finally {
    sendBtn.disabled = false;
    sendBtn.innerText = "Send";
  }
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById("chat-input");
  input.value = promptText;
  document.querySelector(".chat-input-row button[type='submit']").click();
}

function renderUserMessage(text) {
  const container = document.getElementById("chat-messages-container");
  const msg = document.createElement("div");
  msg.className = "msg-card msg-user";
  msg.innerText = text;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function renderAIResponseCard(obs) {
  const container = document.getElementById("chat-messages-container");
  const card = document.createElement("div");
  card.className = "msg-card msg-ai";
  card.id = `obs-card-${obs.id || obs.observation_id}`;

  const isVerified = (obs.status === "verified");
  const isRejected = (obs.status === "rejected");
  const badgeClass = isVerified ? "badge-verified" : (isRejected ? "badge-rejected" : "badge-pending");
  const badgeText = isVerified ? "Senior Officer Verified & Endorsed" : (isRejected ? "Rejected by Senior Officer" : "AI Observation - Officer Verification Pending");

  let evidencePills = "";
  if (obs.evidence && obs.evidence.length > 0) {
    evidencePills = `<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">`;
    obs.evidence.forEach(ev => {
      evidencePills += `
        <button class="ev-pill" onclick="viewEvidence('${ev.record_type || 'CDR'}', '${ev.source_file}', ${ev.source_row})">
          ⚖️ File: ${ev.source_file} (Row ${ev.source_row})
        </button>
      `;
    });
    evidencePills += `</div>`;
  }

  const isSenior = (currentUser && currentUser.role === "senior_officer");
  let actionBtns = "";
  if (isSenior && !isVerified && !isRejected) {
    actionBtns = `
      <div style="margin-top:10px; display:flex; gap:8px;">
        <button class="btn btn-success btn-sm" onclick="openVerifyModal(${obs.id || obs.observation_id}, 'verify')">Verify &amp; Endorse</button>
        <button class="btn btn-danger btn-sm" onclick="openVerifyModal(${obs.id || obs.observation_id}, 'reject')">Reject</button>
      </div>
    `;
  }

  card.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
      <span class="${badgeClass}">${badgeText}</span>
      <span style="font-size:10px; color:var(--text-muted);">${obs.created_at || "Just now"}</span>
    </div>
    <div style="white-space:pre-wrap; line-height:1.6;">${obs.answer || obs.answer_text}</div>
    ${evidencePills}
    ${obs.officer_notes ? `<div style="margin-top:8px;font-size:11.5px;color:#fbbf24;"><b>Officer Notes:</b> ${obs.officer_notes}</div>` : ""}
    ${actionBtns}
  `;

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

// ----------------- MODULE: REPORTS -----------------
function downloadCaseReport(format) {
  window.open(`/api/cases/${currentCaseId}/report?format=${format}`, "_blank");
}

// ----------------- MODULE: INGESTION & BATCHES -----------------
async function loadAvailableMappings() {
  try {
    const res = await fetch("/api/mappings");
    if (!res.ok) return;
    const mappings = await res.json();
    const select = document.getElementById("upload-mapping-select");
    select.innerHTML = "";
    Object.keys(mappings).forEach(k => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = `${mappings[k].operator_name || k} (${mappings[k].description || ""})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading mappings:", err);
  }
}

function updateMappingOptions() {
  const type = document.getElementById("upload-file-type").value;
  const select = document.getElementById("upload-mapping-select");
  if (type === "IPDR") {
    select.value = "ipdr_operator_a";
  } else {
    select.value = "operator_a";
  }
}

async function handleFileUpload(e) {
  e.preventDefault();
  const fileInput = document.getElementById("upload-file-input");
  if (!fileInput.files || fileInput.files.length === 0) return;

  const file = fileInput.files[0];
  const type = document.getElementById("upload-file-type").value;
  const mapping = document.getElementById("upload-mapping-select").value;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("file_type", type);
  formData.append("mapping_name", mapping);

  const alertBox = document.getElementById("upload-progress-alert");
  alertBox.style.display = "block";
  alertBox.className = "alert-banner";
  alertBox.innerText = `⏳ Ingesting and validating ${file.name}...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/upload`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` },
      body: formData
    });
    const summary = await res.json();

    if (res.ok) {
      alertBox.className = "alert-banner";
      alertBox.style.background = "rgba(16, 185, 129, 0.2)";
      alertBox.style.color = "#34d399";
      alertBox.innerText = `✅ Ingested ${summary.valid_rows} rows successfully. (${summary.rejected_rows} rejected).`;

      displayValidationReport(summary);
      await loadExecutiveMetrics(currentCaseId);
      await loadCaseBatches();
    } else {
      alertBox.style.background = "rgba(239, 68, 68, 0.2)";
      alertBox.style.color = "#fca5a5";
      alertBox.innerText = `❌ Error: ${summary.detail || "Upload failed"}`;
    }
  } catch (err) {
    alertBox.innerText = `❌ Ingestion failed: ${err.message}`;
  }
}

function displayValidationReport(s) {
  const container = document.getElementById("validation-report-container");
  container.innerHTML = `
    <div style="font-size:13px; line-height:1.7;">
      <div><b>File:</b> ${s.filename} &bull; <b>Batch ID:</b> #${s.batch_id}</div>
      <div><b>Total Processed:</b> ${s.total_rows} | <b>Valid:</b> <span style="color:#10b981;">${s.valid_rows}</span> | <b>Rejected:</b> <span style="color:#ef4444;">${s.rejected_rows}</span></div>
      ${s.rejected_rows > 0 ? `<div style="color:#ef4444;margin-top:6px;">Sample rejections: ${JSON.stringify(s.rejections.slice(0, 3))}</div>` : ""}
    </div>
  `;
}

async function loadCaseBatches() {
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/batches`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const batches = await res.json();
    const tbody = document.getElementById("batches-table-body");
    tbody.innerHTML = "";

    if (batches.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-muted);">No batches uploaded yet.</td></tr>`;
      return;
    }

    batches.forEach(b => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>#${b.id}</td>
        <td><b>${b.filename}</b></td>
        <td><span class="metric-card-badge badge-blue">${b.file_type}</span></td>
        <td>${b.mapping_name}</td>
        <td>${b.total_rows}</td>
        <td style="color:#10b981;"><b>${b.valid_rows}</b></td>
        <td style="color:#ef4444;">${b.rejected_rows}</td>
        <td style="font-size:11px;color:var(--text-muted);">${b.created_at}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Batches error:", e);
  }
}

// ----------------- MODULE: AUDIT LOG (SECTION 65B) -----------------
async function loadAuditLogs() {
  const tbody = document.getElementById("audit-table-body");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;"><div class="spinner"></div> Fetching immutable Section 65B audit trail...</td></tr>`;

  try {
    const res = await fetch("/api/audit?limit=100", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#fca5a5;">Access denied. Requires Senior Officer or Admin role.</td></tr>`;
      return;
    }
    const logs = await res.json();
    tbody.innerHTML = "";

    logs.forEach(l => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>#${l.id}</td>
        <td style="font-family:monospace;font-size:11px;">${l.timestamp}</td>
        <td><b>${l.username}</b></td>
        <td><span class="role-tag role-io">${l.role}</span></td>
        <td><span class="metric-card-badge badge-blue">${l.action}</span></td>
        <td style="font-size:11.5px;max-width:320px;overflow:hidden;text-overflow:ellipsis;">${JSON.stringify(l.details)}</td>
        <td style="font-family:monospace;font-size:11px;">${l.ip_address}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#fca5a5;">Error loading audit logs.</td></tr>`;
  }
}

// ----------------- MODAL: TAC DEVICE LOOKUP -----------------
function openTacLookupModal() {
  document.getElementById("modal-tac").classList.add("active");
  document.getElementById("tac-imei-input").focus();
}

function closeTacModal() {
  document.getElementById("modal-tac").classList.remove("active");
}

async function handleTacLookup(e) {
  e.preventDefault();
  const imei = document.getElementById("tac-imei-input").value.trim();
  if (!imei) return;

  try {
    const res = await fetch(`/api/tac/${encodeURIComponent(imei)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    const card = document.getElementById("tac-result-card");
    card.style.display = "block";

    document.getElementById("tac-res-model").innerText = `${data.brand} ${data.model}`;
    document.getElementById("tac-res-brand").innerText = data.brand;
    document.getElementById("tac-res-gen").innerText = data.generation;
    document.getElementById("tac-res-code").innerText = data.tac;
    document.getElementById("tac-res-mfr").innerText = data.mfr;
    document.getElementById("tac-res-origin").innerText = data.origin;
    document.getElementById("tac-res-imei").innerText = data.imei;

    const luhnEl = document.getElementById("tac-res-luhn");
    if (data.luhn_valid) {
      luhnEl.className = "badge-verified";
      luhnEl.innerText = "Luhn Checksum VALID (GSMA Compliant)";
    } else {
      luhnEl.className = "badge-rejected";
      luhnEl.innerText = "Luhn Checksum INVALID (Spoofed IMEI)";
    }
  } catch (err) {
    alert("Error decoding TAC info.");
  }
}

function lookupTacSample(imei) {
  document.getElementById("tac-imei-input").value = imei;
  document.querySelector("#modal-tac form button[type='submit']").click();
}

// ----------------- MODAL: REGISTER NEW FIR -----------------
function openNewCaseModal() {
  document.getElementById("modal-new-case").classList.add("active");
}

function closeNewCaseModal() {
  document.getElementById("modal-new-case").classList.remove("active");
}

async function handleCreateCase(e) {
  e.preventDefault();
  const id = document.getElementById("newcase-id").value.trim();
  const title = document.getElementById("newcase-title").value.trim();
  const desc = document.getElementById("newcase-desc").value.trim();

  try {
    const res = await fetch("/api/cases", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ id, title, description: desc })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Case ${id} registered successfully!`);
      closeNewCaseModal();
      await loadCasesList();
      currentCaseId = id;
      document.getElementById("case-selector").value = currentCaseId;
      await onCaseSelected(currentCaseId);
    } else {
      alert(`Error: ${data.detail || "Failed to create case"}`);
    }
  } catch (err) {
    alert("Network error registering FIR.");
  }
}

// ----------------- MODAL: ALL CASES DIRECTORY -----------------
async function openAllCasesModal() {
  const modal = document.getElementById("modal-all-cases");
  modal.classList.add("active");
  const tbody = document.getElementById("all-cases-tbody");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;"><div class="spinner"></div> Loading cases...</td></tr>`;

  try {
    const res = await fetch("/api/cases", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const cases = await res.json();
    tbody.innerHTML = "";

    cases.forEach(c => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b style="color:#38bdf8;">${c.id}</b></td>
        <td><b>${c.title}</b></td>
        <td><span class="badge-verified">${c.status}</span></td>
        <td>${c.cdr_count}</td>
        <td>${c.ipdr_count}</td>
        <td>${c.created_by}</td>
        <td>
          <button class="btn btn-police btn-sm" onclick="selectCaseFromModal('${c.id}')">Select</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#fca5a5;">Error loading cases directory.</td></tr>`;
  }
}

function closeAllCasesModal() {
  document.getElementById("modal-all-cases").classList.remove("active");
}

function selectCaseFromModal(caseId) {
  closeAllCasesModal();
  document.getElementById("case-selector").value = caseId;
  changeActiveCase(caseId);
}

// ----------------- MODAL: GLOBAL SEARCH -----------------
function handleSearchKey(e) {
  if (e.key === "Enter") {
    const q = e.target.value.trim();
    if (q) {
      executeGlobalSearch(q);
    }
  }
}

async function executeGlobalSearch(q) {
  const modal = document.getElementById("modal-search");
  modal.classList.add("active");
  document.getElementById("search-modal-title").innerText = `🔍 Global Search: "${q}"`;
  const body = document.getElementById("search-modal-body");
  body.innerHTML = `<div class="spinner"></div> Searching across active case records...`;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/search?q=${encodeURIComponent(q)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    let html = `<div style="font-size:13px;margin-bottom:12px;">Matched <b>${data.cdr_count}</b> CDR records, <b>${data.ipdr_count}</b> IPDR sessions, <b>${data.tower_count}</b> towers.</div>`;

    if (data.cdrs.length > 0) {
      html += `<h4 style="color:#38bdf8;margin-bottom:6px;">Matching Call Detail Records:</h4>`;
      html += `
        <div class="table-container" style="margin-bottom:14px;">
          <table>
            <thead><tr><th>Time</th><th>A-Number</th><th>B-Number</th><th>Type</th><th>Duration</th><th>Evidence</th></tr></thead>
            <tbody>
      `;
      data.cdrs.slice(0, 10).forEach(r => {
        html += `
          <tr>
            <td style="font-family:monospace;font-size:11px;">${r.start_time}</td>
            <td><b>${r.a_number}</b></td>
            <td><b>${r.b_number}</b></td>
            <td>${r.call_type}</td>
            <td>${r.duration_sec}s</td>
            <td>
              <button class="ev-pill" onclick="viewEvidence('CDR', '${r.source_file}', ${r.source_row})">Sec 65B</button>
            </td>
          </tr>
        `;
      });
      html += `</tbody></table></div>`;
    }

    if (data.ipdrs.length > 0) {
      html += `<h4 style="color:#10b981;margin-bottom:6px;">Matching IPDR Sessions:</h4>`;
      html += `
        <div class="table-container" style="margin-bottom:14px;">
          <table>
            <thead><tr><th>Subscriber</th><th>Source IP:Port</th><th>Time</th><th>App Hint</th></tr></thead>
            <tbody>
      `;
      data.ipdrs.slice(0, 5).forEach(i => {
        html += `
          <tr>
            <td><b>${i.subscriber_number}</b></td>
            <td style="font-family:monospace;">${i.source_ip}:${i.source_port}</td>
            <td style="font-family:monospace;font-size:11px;">${i.session_start}</td>
            <td><span class="metric-card-badge badge-blue">${i.app_hint}</span></td>
          </tr>
        `;
      });
      html += `</tbody></table></div>`;
    }

    if (data.towers.length > 0) {
      html += `<h4 style="color:#fbbf24;margin-bottom:6px;">Matching Cell Towers:</h4>`;
      html += `<div style="display:flex;gap:8px;flex-wrap:wrap;">`;
      data.towers.forEach(t => {
        html += `<span class="metric-card-badge badge-amber" style="font-size:12px;">📡 ${t.cell_id} - ${t.area_name}</span>`;
      });
      html += `</div>`;
    }

    if (data.cdr_count === 0 && data.ipdr_count === 0 && data.tower_count === 0) {
      html = `<p style="color:var(--text-muted);">No records found matching "${q}".</p>`;
    }

    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<p style="color:#fca5a5;">Search failed.</p>`;
  }
}

function closeSearchModal() {
  document.getElementById("modal-search").classList.remove("active");
}

// ----------------- MODAL: NOTIFICATIONS -----------------
function toggleNotifsModal() {
  const m = document.getElementById("modal-notifs");
  m.classList.toggle("active");
}

// ----------------- MODAL: EVIDENCE RECORD (SECTION 65B) -----------------
async function viewEvidence(recordType, sourceFile, sourceRow) {
  const modal = document.getElementById("evidence-modal");
  modal.classList.add("active");

  const titleEl = document.getElementById("evidence-modal-title");
  const bodyEl = document.getElementById("evidence-modal-body");

  titleEl.innerText = `Section 65B Raw Evidence [${recordType} - ${sourceFile} Row #${sourceRow}]`;
  bodyEl.innerHTML = `<div class="spinner"></div> Fetching raw telco record...`;

  try {
    const url = `/api/cases/${currentCaseId}/record/${recordType}/${sourceRow}?source_file=${encodeURIComponent(sourceFile)}`;
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      bodyEl.innerHTML = `<p style="color:#fca5a5;">Evidence record not found in case database.</p>`;
      return;
    }
    const data = await res.json();

    let jsonHtml = `<pre style="background:#070d18;padding:14px;border-radius:6px;font-family:monospace;font-size:12px;color:#38bdf8;overflow-x:auto;">${JSON.stringify(data.raw_payload, null, 2)}</pre>`;
    bodyEl.innerHTML = `
      <div style="font-size:12.5px;margin-bottom:10px;color:var(--text-secondary);">
        <b>Source Data File:</b> <code>${data.source_file}</code> &bull; <b>Row Index:</b> #${data.source_row} &bull; <b>DB Record ID:</b> #${data.record_id}
      </div>
      <div style="font-size:12px;color:#fbbf24;margin-bottom:8px;">
        🔒 Unaltered raw payload preserved under Indian Evidence Act Section 65B requirements:
      </div>
      ${jsonHtml}
    `;
  } catch (err) {
    bodyEl.innerHTML = `<p style="color:#fca5a5;">Error retrieving raw evidence.</p>`;
  }
}

function closeEvidenceModal() {
  document.getElementById("evidence-modal").classList.remove("active");
}

// ----------------- MODAL: SUPERVISOR VERIFICATION -----------------
function openVerifyModal(obsId, action) {
  document.getElementById("verify-obs-id").value = obsId;
  document.getElementById("verify-modal").classList.add("active");
}

function closeVerifyModal() {
  document.getElementById("verify-modal").classList.remove("active");
}

async function submitObservationVerification(action) {
  const obsId = document.getElementById("verify-obs-id").value;
  const notes = document.getElementById("verify-notes-input").value;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/observations/${obsId}/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ action: action, notes: notes })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Observation #${obsId} ${action === 'verify' ? 'verified' : 'rejected'} successfully!`);
      closeVerifyModal();
      // Reload observations
      document.getElementById("chat-messages-container").innerHTML = "";
      loadObservations();
    } else {
      alert(`Verification failed: ${data.detail}`);
    }
  } catch (err) {
    alert("Network error during verification.");
  }
}

// ----------------- MODAL: MAPPING EDITOR -----------------
function openMappingEditorModal() {
  document.getElementById("mapping-editor-modal").classList.add("active");
}

function closeMappingEditorModal() {
  document.getElementById("mapping-editor-modal").classList.remove("active");
}

async function saveCustomMapping() {
  const id = document.getElementById("mapping-id-input").value;
  const jsonStr = document.getElementById("mapping-json-input").value;

  const form = new FormData();
  form.append("mapping_id", id);
  form.append("config_json", jsonStr);

  try {
    const res = await fetch("/api/mappings", {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` },
      body: form
    });
    if (res.ok) {
      alert("Mapping saved successfully!");
      closeMappingEditorModal();
      loadAvailableMappings();
    } else {
      alert("Invalid JSON configuration.");
    }
  } catch (e) {
    alert("Failed to save mapping.");
  }
}
