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
let chartTimelineInstance = null;
let chartHourlyInstance = null;
let chartCallTypeInstance = null;
let chartDurationInstance = null;

// Suspect workspace state
let currentSuspectPhone = "";
let activeMapMode = "towers";
let sectorConesLayer = null;
let meetingBuffersLayer = null;

// Pagination state for Raw CDR
let cdrCurrentPage = 1;
const cdrPageLimit = 25;
let cdrTotalRecords = 0;
let cdrSearchDebounceTimer = null;

// Cached analytics data & dynamic ingestion state
let cachedAnalytics = null;
let currentCaseHasData = false;
let cachedMappings = {};
let slotInspections = { 1: null, 2: null };

// ----------------- DOM READY INITIALIZATION -----------------
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  startLiveClock();
  setupKeyboardShortcuts();
  renderWorkbenchSubnav("command", "dashboard");
  await initSession();
  await loadCasesList();
  await loadAvailableMappings();
  await loadExecutiveMetrics();
  await getCaseAnalytics();
});

// ----------------- DARK / LIGHT THEME TOGGLE -----------------
function initTheme() {
  const saved = localStorage.getItem("forensic-theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("forensic-theme", next);
}

function toggleRolePopover(e) {
  if (e) e.stopPropagation();
  const pop = document.getElementById("role-popover");
  if (pop) pop.classList.toggle("open");
}

function closeRolePopover() {
  const pop = document.getElementById("role-popover");
  if (pop) pop.classList.remove("open");
}

document.addEventListener("click", () => closeRolePopover());

// ----------------- DUAL SIDEBAR CONTEXT & COLLAPSE -----------------
let sidebarContext = "home"; // "home" (Image 1) | "investigation" (Images 3/4/modules)

function switchSidebarContext(ctx) {
  sidebarContext = ctx;
  const homeMenu = document.getElementById("sidebar-home-menu");
  const invMenu = document.getElementById("sidebar-investigation-menu");
  if (ctx === "investigation") {
    if (homeMenu) homeMenu.style.display = "none";
    if (invMenu) invMenu.style.display = "flex";
  } else {
    if (homeMenu) homeMenu.style.display = "block";
    if (invMenu) invMenu.style.display = "none";
  }
}

function toggleSidebarContext() {
  switchSidebarContext(sidebarContext === "home" ? "investigation" : "home");
}

function toggleSidebarCollapsed() {
  const sb = document.getElementById("app-sidebar");
  if (sb) sb.classList.toggle("collapsed");
}

function enterInvestigationWorkspace(targetView = "advanced-cdr") {
  switchSidebarContext("investigation");
  switchView(targetView);
}

// ----------------- REAL-TIME LIVE TICKING CLOCK -----------------
function startLiveClock() {
  function updateClock() {
    const now = new Date();
    const istOffset = 5.5 * 60 * 60 * 1000;
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const istDate = new Date(utc + istOffset);

    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const dayName = days[istDate.getDay()];
    const mmm = months[istDate.getMonth()];
    const dd = istDate.getDate();

    let h = istDate.getHours();
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    const hh = String(h).padStart(2, "0");
    const mm = String(istDate.getMinutes()).padStart(2, "0");
    const ss = String(istDate.getSeconds()).padStart(2, "0");

    const clockEl = document.getElementById("live-clock-display");
    if (clockEl) {
      clockEl.innerText = `${dayName}, ${mmm} ${dd}  ${hh}:${mm}:${ss} ${ampm}`;
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
  const auditBtn = document.getElementById("audit-nav-btn");

  if (nameEl) nameEl.innerText = currentUser.full_name;
  if (roleEl) {
    if (currentUser.role === "admin") {
      roleEl.innerText = "ACP Meena (Admin)";
      roleEl.className = "role-tag role-admin";
      if (auditBtn) auditBtn.style.display = "flex";
    } else if (currentUser.role === "senior_officer") {
      roleEl.innerText = "SP Verma (Senior)";
      roleEl.className = "role-tag role-senior";
      if (auditBtn) auditBtn.style.display = "flex";
    } else {
      roleEl.innerText = "IO Sharma (Analyst)";
      roleEl.className = "role-tag role-io";
      if (auditBtn) auditBtn.style.display = "none";
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
    if (selector) selector.innerHTML = "";

    if (cases.length === 0) {
      currentCaseId = "";
      currentCaseHasData = false;
      if (selector) selector.innerHTML = `<option value="">-- No Cases Registered --</option>`;
      const sHdrCdr = document.getElementById("stat-hdr-cdr");
      if (sHdrCdr) sHdrCdr.innerText = "0";
      const sHdrIpdr = document.getElementById("stat-hdr-ipdr");
      if (sHdrIpdr) sHdrIpdr.innerText = "0";
      const sHdrSus = document.getElementById("stat-hdr-suspects");
      if (sHdrSus) sHdrSus.innerText = "0";
      return;
    }

    cases.forEach(c => {
      if (selector) {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `${c.id} — ${c.title}`;
        selector.appendChild(opt);
      }
    });

    if (!currentCaseId || !cases.some(c => c.id === currentCaseId)) {
      // Pick first case with CDRs uploaded, else latest case
      const withData = cases.find(c => (c.cdr_count || 0) + (c.ipdr_count || 0) > 0);
      currentCaseId = withData ? withData.id : cases[0].id;
    }
    if (selector) selector.value = currentCaseId;
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
  ["common-numbers-input", "meet-num1", "meet-num2", "link-num1", "link-num2", "ipdr-sub-input", "ipdr-query-ip", "ipdr-query-port", "ipdr-query-time"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  await loadExecutiveMetrics(caseId);
  await loadCaseDetails(caseId);

  if (currentCaseHasData) {
    await getCaseAnalytics();
  } else {
    const gateMsg = document.getElementById("ingestion-gate-msg");
    if (gateMsg) {
      gateMsg.innerText = `Case '${caseId}' has 0 records. Upload CDR / IPDR CSV or Excel files below to populate analytics.`;
    }
  }

  // Refresh active view cleanly
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

    const cdrCnt = data.stats.cdr_count || 0;
    const ipdrCnt = data.stats.ipdr_count || 0;
    currentCaseHasData = (cdrCnt + ipdrCnt) > 0;

    // Update Header Stats
    const sHdrCdr = document.getElementById("stat-hdr-cdr");
    if (sHdrCdr) sHdrCdr.innerText = cdrCnt;
    const sHdrIpdr = document.getElementById("stat-hdr-ipdr");
    if (sHdrIpdr) sHdrIpdr.innerText = ipdrCnt;
    const suspects = (data.brief_data && data.brief_data.suspects) ? data.brief_data.suspects : [];
    const sHdrSus = document.getElementById("stat-hdr-suspects");
    if (sHdrSus) sHdrSus.innerText = suspects.length;
    const bCdrCnt = document.getElementById("badge-cdr-count");
    if (bCdrCnt) bCdrCnt.innerText = cdrCnt;

    // Update Dashboard Brief
    const dashTitle = document.getElementById("dash-case-title");
    if (dashTitle) dashTitle.innerText = `${data.id}: ${data.title}`;
    const dashDesc = document.getElementById("dash-case-desc");
    if (dashDesc) dashDesc.innerText = data.description || "No narrative brief provided.";
    const dashStatus = document.getElementById("dash-case-status");
    if (dashStatus) dashStatus.innerText = data.status || "ACTIVE";

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
      chipsBox.innerHTML = `<span style="color:var(--text-muted);font-size:12px;">Targets will appear dynamically after CDR ingestion.</span>`;
    }
  } catch (err) {
    console.error("Error loading case details:", err);
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

// ----------------- 7-WORKBENCH ARCHITECTURE & NAVIGATION -----------------
const WORKBENCHES = {
  "command": {
    title: "Command Center",
    defaultView: "dashboard",
    views: [
      { id: "dashboard", label: "Executive Dashboard", icon: "🎛️" },
      { id: "assistant", label: "AI Assistant Chat", icon: "🤖" },
      { id: "reports", label: "Reports & Statutory Export", icon: "📥" }
    ]
  },
  "import": {
    title: "Data & Ingestion",
    defaultView: "import",
    views: [
      { id: "import", label: "Data Ingestion & Mapping", icon: "📂" },
      { id: "raw-cdr", label: "Raw CDR Records", icon: "🗄️" },
      { id: "batch-ipdr", label: "Batch IPDR NAT Resolver", icon: "⚡" }
    ]
  },
  "behavior": {
    title: "Behavioral Forensics",
    defaultView: "day-night",
    views: [
      { id: "day-night", label: "Day / Night Analysis", icon: "🌓" },
      { id: "mfc", label: "MFC Frequent Contacts", icon: "👥" },
      { id: "missing-dates", label: "Missing Dates & Silence", icon: "📅" },
      { id: "first-last", label: "First / Last Calls", icon: "📞" },
      { id: "day-calls", label: "Day Calls", icon: "🌤️" },
      { id: "night-calls", label: "Night Calls", icon: "🌑" },
      { id: "interactive-timeline", label: "Timeline", icon: "🕒" }
    ]
  },
  "geo": {
    title: "Geospatial Mobility",
    defaultView: "geo-map",
    views: [
      { id: "geo-map", label: "Geo Intelligence Map", icon: "🌐" },
      { id: "meetings", label: "Meeting Rendezvous", icon: "🚨" },
      { id: "movement", label: "Movement Chart", icon: "🔀" },
      { id: "cell-id-changes", label: "Cell ID Changes", icon: "⇄" },
      { id: "location-changes", label: "Location Changes", icon: "🗺️" },
      { id: "location-summary", label: "Location Summary", icon: "📍" },
      { id: "location-intelligence", label: "Location Intelligence", icon: "🧭" },
      { id: "day-locations", label: "Day Locations", icon: "☀️" },
      { id: "night-locations", label: "Night Locations", icon: "🌙" }
    ]
  },
  "network": {
    title: "Syndicate Network",
    defaultView: "graph",
    views: [
      { id: "graph", label: "Interactive Network Graph", icon: "📊" },
      { id: "link-analysis", label: "Link Analysis & Bridges", icon: "🔗" },
      { id: "common-numbers", label: "Common Numbers", icon: "🤝" },
      { id: "advanced-cdr", label: "Advanced CDR", icon: "📚" },
      { id: "network-analysis", label: "Network Matrix", icon: "📶" }
    ]
  },
  "device-cyber": {
    title: "Handset & Cyber",
    defaultView: "imei-summary",
    views: [
      { id: "imei-summary", label: "IMEI & 275k TAC Handset", icon: "📱" },
      { id: "imsi-summary", label: "IMSI Circle Attribution", icon: "💳" },
      { id: "device-changes", label: "SIM Swapping & Hopping", icon: "🔄" },
      { id: "ipdr", label: "Carrier NAT IPDR", icon: "🛰️" },
      { id: "imei-patterns", label: "IMEI Patterns", icon: "🧬" },
      { id: "imsi-patterns", label: "IMSI Patterns", icon: "🪪" }
    ]
  },
  "legal-audit": {
    title: "Legal & Sec 65B Audit",
    defaultView: "audit",
    views: [
      { id: "audit", label: "Section 65B Audit Log & SHA-256", icon: "🛡️" },
      { id: "ownership", label: "Ownership Intelligence", icon: "👤" },
      { id: "international", label: "International Intel", icon: "🌍" },
      { id: "service-numbers", label: "Service Helplines", icon: "🏢" }
    ]
  }
};

let activeWorkbench = "command";

function switchWorkbench(wbId, preferredView = null) {
  const wb = WORKBENCHES[wbId] || WORKBENCHES["command"];
  activeWorkbench = wbId;

  document.querySelectorAll(".sidebar-workbench-btn").forEach(btn => {
    btn.classList.toggle("active", btn.id === `wb-btn-${wbId}`);
  });

  const targetView = preferredView || wb.defaultView;
  renderWorkbenchSubnav(wbId, targetView);
  switchView(targetView, false);
}

function renderWorkbenchSubnav(wbId, activeViewId) {
  const subnav = document.getElementById("workbench-subnav");
  if (!subnav) return;

  const wb = WORKBENCHES[wbId] || WORKBENCHES["command"];
  let html = "";
  wb.views.forEach(v => {
    const isActive = v.id === activeViewId ? "active" : "";
    html += `
      <div class="wb-subnav-pill ${isActive}" data-view="${v.id}" onclick="switchView('${v.id}')">
        <span>${v.icon}</span>
        <span>${v.label}</span>
      </div>
    `;
  });
  subnav.innerHTML = html;
}

// ----------------- SIDEBAR & VIEW SWITCHER -----------------
const INVESTIGATION_ONLY_VIEWS = new Set([
  "advanced-cdr", "graph", "raw-cdr", "mfc", "network-analysis", "international",
  "service-numbers", "imei-summary", "imsi-summary", "imei-patterns", "imsi-patterns",
  "first-last", "location-summary", "location-intelligence", "day-locations", "day-calls",
  "night-locations", "night-calls", "movement", "cell-id-changes", "location-changes",
  "missing-dates", "interactive-timeline", "link-analysis", "geo-map", "ipdr", "batch-ipdr",
  "device-changes", "meetings"
]);

function switchView(viewName, updateWorkbench = true) {
  if (INVESTIGATION_ONLY_VIEWS.has(viewName) && sidebarContext !== "investigation") {
    switchSidebarContext("investigation");
  }

  if (updateWorkbench) {
    let foundWb = "command";
    for (const [wbKey, wbObj] of Object.entries(WORKBENCHES)) {
      if (wbObj.views.some(v => v.id === viewName)) {
        foundWb = wbKey;
        break;
      }
    }
    activeWorkbench = foundWb;
    document.querySelectorAll(".sidebar-workbench-btn").forEach(btn => {
      btn.classList.toggle("active", btn.id === `wb-btn-${foundWb}`);
    });
    renderWorkbenchSubnav(foundWb, viewName);
  } else {
    document.querySelectorAll(".wb-subnav-pill").forEach(pill => {
      pill.classList.toggle("active", pill.dataset.view === viewName);
    });
  }

  // Switch view containers
  document.querySelectorAll(".module-view").forEach(v => v.classList.remove("active"));
  const viewEl = document.getElementById(`view-${viewName}`);
  if (viewEl) {
    viewEl.classList.add("active");
  }

  // Highlight active item across both home & investigation sidebars cleanly
  const homeIdMap = {
    "dashboard": "home-btn-dashboard",
    "cases": "home-btn-view-cases",
    "number-lookup": "home-btn-number-lookup",
    "ownership": "home-btn-ownership",
    "reports": "home-btn-reports",
    "watchlist": "home-btn-watchlist",
    "common-numbers": "home-btn-common",
    "import": "home-btn-import",
    "assistant": "home-btn-assistant",
    "audit": "home-btn-audit"
  };

  document.querySelectorAll(".sidebar-module-link").forEach(btn => {
    const isModMatch = btn.id === `mod-btn-${viewName}`;
    const isHomeMatch = btn.id === (homeIdMap[viewName] || "");
    btn.classList.toggle("active", isModMatch || isHomeMatch);
  });

  dispatchViewLoad(viewName);
}

function dispatchViewLoad(viewName) {
  if (viewName === "cases") {
    loadCasesDirectoryView();
    return;
  }
  if (!currentCaseId) return;

  switch (viewName) {
    case "dashboard":
      loadDashboardDistribution();
      loadSuspectThreatRadar();
      load24x7Heatmap();
      break;
    case "advanced-cdr":
      loadSuspectWorkspace();
      break;
    case "graph":
      loadGraphAnalyticsView();
      break;
    case "network-analysis":
      loadNetworkGraph();
      loadNetworkAnalysisView();
      break;
    case "raw-cdr":
      loadRawCdrPage(1);
      break;
    case "mfc":
      loadMfcView();
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
    case "imei-patterns":
      loadImeiPatternsView();
      break;
    case "imsi-patterns":
      loadImsiPatternsView();
      break;
    case "location-summary":
      loadLocationSummaryView();
      break;
    case "location-intelligence":
      loadLocationIntelView();
      break;
    case "day-calls":
      loadDayCallsView();
      break;
    case "night-calls":
      loadNightCallsView();
      break;
    case "cell-id-changes":
      loadCellChangesView();
      break;
    case "location-changes":
      loadLocationChangesView();
      break;
    case "interactive-timeline":
      loadInteractiveTimelineView();
      break;
    case "link-analysis":
      runLinkAnalysis();
      break;
    case "watchlist":
      loadWatchlistView();
      break;
    case "assistant":
      loadObservations();
      break;
    case "import":
      loadCaseBatches();
      break;
    case "batch-ipdr":
      loadBatchIpdrSample();
      break;
    case "audit":
      loadAuditLogs();
      break;
  }
}

// ----------------- FETCH CACHED ANALYTICS -----------------
async function getCaseAnalytics() {
  if (cachedAnalytics) return cachedAnalytics;
  if (!currentCaseId) return null;
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/analytics`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      cachedAnalytics = await res.json();
      populateDynamicCaseUI(cachedAnalytics);
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

  // Render Suspect Threat Radar Cards & 24x7 Heatmap
  if (data.threat_scores) {
    renderThreatCards(data.threat_scores);
  } else {
    loadSuspectThreatRadar();
  }

  if (data.heatmap_24x7) {
    render24x7Heatmap(data.heatmap_24x7);
  } else {
    load24x7Heatmap();
  }
}

async function loadSuspectThreatRadar() {
  if (!currentCaseId) return;
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/threat-scoring`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      const threats = await res.json();
      renderThreatCards(threats);
    }
  } catch (e) {
    console.error("Threat scoring error:", e);
  }
}

async function load24x7Heatmap() {
  if (!currentCaseId) return;
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/heatmap`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      const heat = await res.json();
      render24x7Heatmap(heat);
    }
  } catch (e) {
    console.error("Heatmap fetch error:", e);
  }
}

function renderThreatCards(threats) {
  const grid = document.getElementById("threat-cards-grid");
  if (!grid) return;
  if (!threats || threats.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="padding:20px;color:#94a3b8;">No suspect threat profiles detected. Upload CDR/IPDR files to initiate analysis.</div>`;
    return;
  }

  let html = "";
  threats.forEach(s => {
    const score = s.threat_score || 0;
    const risk = (s.risk_level || "LOW").toUpperCase();
    const archetype = s.archetype || "Standard Subscriber";
    let badgeClass = "threat-badge-low";
    let meterColor = "#10b981";

    if (score >= 75) {
      badgeClass = "threat-badge-critical";
      meterColor = "#ef4444";
    } else if (score >= 50) {
      badgeClass = "threat-badge-high";
      meterColor = "#f59e0b";
    } else if (score >= 25) {
      badgeClass = "threat-badge-medium";
      meterColor = "#eab308";
    }

    const factors = s.factors || [];
    const factorPills = factors.map(f => `<span class="threat-factor-pill">${f}</span>`).join("");

    html += `
      <div class="threat-card">
        <div class="threat-card-header">
          <div>
            <div class="threat-card-name">${s.name || 'Target Suspect'}</div>
            <div class="threat-card-phone">${s.phone}</div>
          </div>
          <span class="threat-badge ${badgeClass}">${risk}</span>
        </div>

        <div class="threat-archetype-chip">🏷️ ${archetype}</div>

        <div class="threat-meter-container">
          <div class="threat-meter-labels">
            <span style="color:#94a3b8;">Threat Index</span>
            <span style="color:${meterColor};font-weight:700;">${score}/100</span>
          </div>
          <div class="threat-meter-track">
            <div class="threat-meter-fill" style="width:${Math.max(5, score)}%;background:${meterColor};"></div>
          </div>
        </div>

        <div style="font-size:11px;color:#94a3b8;display:flex;justify-content:space-between;">
          <span>🌙 Night: <b>${s.night_ratio_pct}%</b></span>
          <span>📱 IMEIs: <b>${s.imei_count}</b></span>
          <span>⚡ Hops: <b>${s.rapid_movements_count}</b></span>
        </div>

        <div class="threat-factors-list">
          ${factorPills}
        </div>

        <div class="threat-card-actions">
          <button class="btn btn-outline btn-sm" style="flex:1;padding:3px 6px;font-size:11px;" onclick="focusSuspectNetwork('${s.phone}')">
            🕸️ Network
          </button>
          <button class="btn btn-outline btn-sm" style="flex:1;padding:3px 6px;font-size:11px;" onclick="focusSuspectTrajectory('${s.phone}')">
            📍 Trajectory
          </button>
        </div>
      </div>
    `;
  });
  grid.innerHTML = html;
}

function focusSuspectNetwork(phone) {
  switchView("graph");
  setTimeout(() => {
    if (cytoscapeInstance) {
      const node = cytoscapeInstance.getElementById(phone);
      if (node && node.length) {
        cytoscapeInstance.center(node);
        cytoscapeInstance.zoom(1.8);
        node.select();
        openNodeInspectorDrawer(phone, node.data());
      }
    }
  }, 400);
}

function focusSuspectTrajectory(phone) {
  switchView("geo-map");
  const sel = document.getElementById("map-suspect-select");
  if (sel) {
    sel.value = phone;
    renderTowerMap(phone);
  }
}

function render24x7Heatmap(heatmapData) {
  const container = document.getElementById("heatmap-grid-24x7");
  const busiestPill = document.getElementById("heatmap-busiest-pill");
  if (!container) return;

  if (!heatmapData || !heatmapData.matrix) {
    container.innerHTML = `<div style="grid-column:1/-1;padding:20px;text-align:center;color:#94a3b8;">No temporal heatmap activity recorded.</div>`;
    return;
  }

  if (busiestPill) {
    busiestPill.innerText = `Busiest: ${heatmapData.busiest_day} @ ${heatmapData.busiest_hour}:00 (${heatmapData.busiest_calls} calls)`;
  }

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const maxVal = heatmapData.max_hourly_calls || 1;
  let html = "";

  html += `<div class="heat-hdr-cell">Day</div>`;
  for (let h = 0; h < 24; h++) {
    html += `<div class="heat-hdr-cell">${h}h</div>`;
  }

  for (let d = 0; d < 7; d++) {
    html += `<div class="heat-day-lbl">${days[d]}</div>`;
    const rowCounts = heatmapData.matrix[d] || [];
    for (let h = 0; h < 24; h++) {
      const count = rowCounts[h] || 0;
      let lvl = 0;
      if (count > 0) {
        const ratio = count / maxVal;
        if (ratio >= 0.75) lvl = 4;
        else if (ratio >= 0.50) lvl = 3;
        else if (ratio >= 0.25) lvl = 2;
        else lvl = 1;
      }
      const title = `${days[d]} ${h}:00 - ${count} calls ${lvl >= 3 ? '(Peak Syndicate Activity)' : ''}`;
      html += `<div class="heat-cell heat-lvl-${lvl}" title="${title}">${count > 0 ? count : ''}</div>`;
    }
  }

  container.innerHTML = html;
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
        animate: false,
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
        numIter: 400
      }
    });

    cytoscapeInstance.on("tap", "node", (evt) => {
      const node = evt.target;
      openNodeInspectorDrawer(node.data("id"), node.data());
    });

  } catch (err) {
    console.error("Network graph error:", err);
    label.innerText = "Error drawing network topology";
  }
}

let drawerActiveNode = null;

function openNodeInspectorDrawer(nodeId, nodeData) {
  drawerActiveNode = nodeId;
  const drawer = document.getElementById("node-inspector-drawer");
  if (!drawer) return;

  const titleEl = document.getElementById("drawer-node-title");
  const subEl = document.getElementById("drawer-node-subtitle");
  const centralityEl = document.getElementById("drawer-stat-centrality");
  const degreeEl = document.getElementById("drawer-stat-degree");
  const statusEl = document.getElementById("drawer-stat-status");

  if (titleEl) titleEl.innerText = nodeData.label || nodeId;
  if (subEl) subEl.innerText = nodeData.is_suspect ? "Target Syndicate Suspect" : "Associated Peer Contact";
  if (centralityEl) centralityEl.innerText = nodeData.degree ? `#${nodeData.degree >= 8 ? 1 : (nodeData.degree >= 4 ? 2 : 3)}` : "Rank #1";
  if (degreeEl) degreeEl.innerText = `${nodeData.degree || 1} links`;
  if (statusEl) statusEl.innerText = nodeData.is_suspect ? "SUSPECT" : "ASSOCIATE";

  // Connections list from graph edges
  const connList = document.getElementById("drawer-connections-list");
  if (connList && cytoscapeInstance) {
    connList.innerHTML = "";
    const connectedEdges = cytoscapeInstance.edges(`[source = "${nodeId}"], [target = "${nodeId}"]`);
    if (connectedEdges.length === 0) {
      connList.innerHTML = `<span style="font-size:11px;color:#94a3b8;">No direct connections</span>`;
    } else {
      connectedEdges.forEach(edge => {
        const otherId = edge.data("source") === nodeId ? edge.data("target") : edge.data("source");
        const calls = edge.data("call_count") || edge.data("weight") || 1;
        const item = document.createElement("div");
        item.className = "drawer-conn-item";
        item.innerHTML = `
          <span style="font-family:monospace;color:#38bdf8;">${otherId}</span>
          <span style="color:#94a3b8;">${calls} calls</span>
        `;
        connList.appendChild(item);
      });
    }
  }

  // Section 65B evidence records
  const evList = document.getElementById("drawer-evidence-list");
  if (evList) {
    evList.innerHTML = `
      <div class="drawer-ev-pill">
        <b>Section 65B Lineage:</b> Target identifier <code>${nodeId}</code> verified in carrier CDR stream.
      </div>
    `;
  }

  drawer.classList.add("open");
}

function closeNodeInspectorDrawer() {
  const drawer = document.getElementById("node-inspector-drawer");
  if (drawer) drawer.classList.remove("open");
}

function runDrawerLinkAnalysis() {
  if (!drawerActiveNode) return;
  const targetSuspect = cachedAnalytics?.suspects?.[0]?.phone || "";
  if (targetSuspect && targetSuspect !== drawerActiveNode) {
    switchView("link-analysis");
    const n1 = document.getElementById("link-num1");
    const n2 = document.getElementById("link-num2");
    if (n1) n1.value = targetSuspect;
    if (n2) n2.value = drawerActiveNode;
    runLinkAnalysis();
  } else {
    switchView("link-analysis");
  }
}

function runDrawerFilterCdr() {
  if (!drawerActiveNode) return;
  switchView("raw-cdr");
  const filterInput = document.getElementById("cdr-filter-search");
  if (filterInput) {
    filterInput.value = drawerActiveNode;
    loadRawCdrPage(1);
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
  const sel = document.getElementById("map-suspect-select");
  const num = targetNum || (sel ? sel.value : "") || (cachedAnalytics?.suspects?.[0]?.phone || "");
  if (!num) return;
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

    initTrajectoryScrubber(data.timeline);
  } catch (err) {
    console.error("Map render error:", err);
    countLabel.innerText = "Error loading trajectory points";
  }
}

let currentMapTimeline = [];
let trajectoryPlayInterval = null;
let trajectorySpeedMultiplier = 1;

function initTrajectoryScrubber(timeline) {
  currentMapTimeline = timeline || [];
  const slider = document.getElementById("trajectory-time-slider");
  const playBtn = document.getElementById("btn-trajectory-play");
  if (trajectoryPlayInterval) {
    clearInterval(trajectoryPlayInterval);
    trajectoryPlayInterval = null;
  }
  if (playBtn) playBtn.innerHTML = "▶️ Play Route";

  if (!slider || currentMapTimeline.length === 0) return;
  slider.min = 0;
  slider.max = currentMapTimeline.length - 1;
  slider.value = 0;

  const startLbl = document.getElementById("trajectory-start-lbl");
  const endLbl = document.getElementById("trajectory-end-lbl");
  const curLbl = document.getElementById("trajectory-current-lbl");

  if (startLbl && currentMapTimeline[0]) startLbl.innerText = `#1 ${currentMapTimeline[0].area_name?.slice(0, 14) || ''}`;
  if (endLbl && currentMapTimeline.length > 1) {
    const last = currentMapTimeline[currentMapTimeline.length - 1];
    endLbl.innerText = `#${last.seq} ${last.area_name?.slice(0, 14) || ''}`;
  }
  if (curLbl) curLbl.innerText = `Step 1 of ${currentMapTimeline.length}`;
}

function handleTrajectorySlider(val) {
  const idx = parseInt(val, 10);
  if (!currentMapTimeline || !currentMapTimeline[idx] || !leafletMap) return;
  const pt = currentMapTimeline[idx];
  const curLbl = document.getElementById("trajectory-current-lbl");
  if (curLbl) {
    curLbl.innerText = `Seq #${pt.seq} (${pt.timestamp?.slice(11, 19) || ''}) @ ${pt.area_name || ''}`;
  }
  leafletMap.panTo([pt.lat, pt.lon], { animate: true });
}

function toggleTrajectoryPlayback() {
  const playBtn = document.getElementById("btn-trajectory-play");
  const slider = document.getElementById("trajectory-time-slider");
  if (!slider || !currentMapTimeline.length) return;

  if (trajectoryPlayInterval) {
    clearInterval(trajectoryPlayInterval);
    trajectoryPlayInterval = null;
    if (playBtn) playBtn.innerHTML = "▶️ Play Route";
    return;
  }

  if (playBtn) playBtn.innerHTML = "⏸️ Pause";
  let curIdx = parseInt(slider.value, 10);
  if (curIdx >= currentMapTimeline.length - 1) {
    curIdx = 0;
    slider.value = 0;
  }

  const stepMs = Math.max(250, Math.floor(1000 / trajectorySpeedMultiplier));
  trajectoryPlayInterval = setInterval(() => {
    curIdx++;
    if (curIdx >= currentMapTimeline.length) {
      clearInterval(trajectoryPlayInterval);
      trajectoryPlayInterval = null;
      if (playBtn) playBtn.innerHTML = "🔄 Replay";
      return;
    }
    slider.value = curIdx;
    handleTrajectorySlider(curIdx);
  }, stepMs);
}

function setTrajectorySpeed(spd) {
  trajectorySpeedMultiplier = parseFloat(spd) || 1;
  if (trajectoryPlayInterval) {
    toggleTrajectoryPlayback();
    toggleTrajectoryPlayback();
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

async function prefillIpdrTest() {
  if (!currentCaseId) {
    alert("Please create/select a case and upload IPDR data first.");
    return;
  }
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/ipdr/sample`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const d = await res.json();
    if (!d.available) {
      alert("No IPDR records uploaded in this case yet. Upload an IPDR CSV/Excel file first.");
      return;
    }
    document.getElementById("ipdr-query-ip").value = d.source_ip;
    document.getElementById("ipdr-query-port").value = d.source_port;
    document.getElementById("ipdr-query-time").value = d.timestamp;
  } catch (e) {
    alert("Unable to fetch uploaded IPDR sample.");
  }
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

// ----------------- MODULE: INGESTION & BATCHES (DUAL-FORMAT DYNAMIC MAPPER) -----------------
async function loadAvailableMappings() {
  try {
    const res = await fetch("/api/mappings");
    if (!res.ok) return;
    cachedMappings = await res.json();
    updateSlotMappingOptions(1);
    updateSlotMappingOptions(2);
  } catch (err) {
    console.error("Error loading mappings:", err);
  }
}

function updateSlotMappingOptions(slot) {
  const typeEl = document.getElementById(`upload-type-${slot}`);
  const sel = document.getElementById(`upload-mapping-${slot}`);
  if (!typeEl || !sel) return;
  const ftype = typeEl.value;
  sel.innerHTML = `<option value="auto">✨ Auto-Detect Dynamic Columns</option>`;
  Object.keys(cachedMappings).forEach(k => {
    const cfg = cachedMappings[k];
    const isIpdr = (cfg.file_type || (k.includes("ipdr") ? "IPDR" : "CDR")).toUpperCase() === "IPDR";
    if ((ftype === "IPDR" && isIpdr) || (ftype === "CDR" && !isIpdr)) {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = `${cfg.operator_name || k} (${cfg.description || ""})`;
      sel.appendChild(opt);
    }
  });
  if (slotInspections[slot]) {
    renderSlotMapperUI(slot);
  }
}

async function inspectSlotFile(slot) {
  const input = document.getElementById(`upload-file-${slot}`);
  const box = document.getElementById(`slot${slot}-inspect-box`);
  if (!input || !input.files || input.files.length === 0) {
    slotInspections[slot] = null;
    if (box) box.style.display = "none";
    return;
  }

  const file = input.files[0];
  box.style.display = "block";
  box.innerHTML = `<div class="spinner"></div> Inspecting columns in <b>${file.name}</b>...`;

  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/ingest/inspect", {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` },
      body: fd
    });
    const info = await res.json();
    if (!res.ok) {
      box.innerHTML = `<span style="color:#fca5a5;">❌ ${info.detail || "Unable to inspect file"}</span>`;
      slotInspections[slot] = null;
      return;
    }

    slotInspections[slot] = info;
    const typeEl = document.getElementById(`upload-type-${slot}`);
    if (typeEl) {
      typeEl.value = info.suggested_type || "CDR";
      updateSlotMappingOptions(slot);
    }
    renderSlotMapperUI(slot);
  } catch (err) {
    box.innerHTML = `<span style="color:#fca5a5;">❌ File inspection failed: ${err.message}</span>`;
  }
}

function renderSlotMapperFromPreset(slot) {
  if (!slotInspections[slot]) return;
  const presetKey = document.getElementById(`upload-mapping-${slot}`).value;
  if (presetKey !== "auto" && cachedMappings[presetKey]) {
    slotInspections[slot].active_mapping = { ...(cachedMappings[presetKey].mappings || {}) };
  } else {
    slotInspections[slot].active_mapping = { ...(slotInspections[slot].suggested_mapping || {}) };
  }
  renderSlotMapperUI(slot);
}

function renderSlotMapperUI(slot) {
  const info = slotInspections[slot];
  const box = document.getElementById(`slot${slot}-inspect-box`);
  if (!info || !box) return;

  const ftype = document.getElementById(`upload-type-${slot}`).value;
  const fields = ftype === "IPDR"
    ? ["subscriber_number", "source_ip", "source_port", "destination_ip", "destination_port", "session_start", "session_end", "bytes_transferred", "app_hint"]
    : ["a_number", "b_number", "call_type", "start_time", "duration_sec", "imei", "imsi", "cell_id"];

  const currentMap = info.active_mapping || info.suggested_mapping || {};
  const colOptions = (selected) => {
    let opts = `<option value="">-- Skip / None --</option>`;
    info.columns.forEach(col => {
      const sel = (Array.isArray(selected) ? selected[0] === col : selected === col) ? "selected" : "";
      opts += `<option value="${col}" ${sel}>${col}</option>`;
    });
    return opts;
  };

  box.innerHTML = `
    <div style="background:var(--bg-card-subtle);border:1px solid var(--border-color);border-radius:6px;padding:10px;font-size:11.5px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span>Detected: <b style="color:#38bdf8;">${info.format}</b> (${info.row_count} rows, ${info.columns.length} cols)</span>
        <span class="metric-card-badge badge-green">Dynamic Map Ready</span>
      </div>
      <div class="grid-2" style="gap:6px;">
        ${fields.map(f => `
          <div>
            <label style="color:var(--text-muted);font-size:10.5px;display:block;">${f}:</label>
            <select class="form-control slot-${slot}-col-map" data-field="${f}" style="padding:4px 6px;font-size:11px;">
              ${colOptions(currentMap[f] || "")}
            </select>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function collectSlotMapping(slot) {
  const selects = document.querySelectorAll(`.slot-${slot}-col-map`);
  if (!selects.length) return null;
  const map = {};
  selects.forEach(sel => {
    const field = sel.getAttribute("data-field");
    if (sel.value) map[field] = sel.value;
  });
  return { name: `Dynamic Slot ${slot}`, mappings: map };
}

async function uploadSingleSlot(slot) {
  const fileInput = document.getElementById(`upload-file-${slot}`);
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) return null;

  const file = fileInput.files[0];
  const ftype = document.getElementById(`upload-type-${slot}`).value;
  const mappingKey = document.getElementById(`upload-mapping-${slot}`).value;
  const dynMapping = collectSlotMapping(slot);

  const formData = new FormData();
  formData.append("file", file);
  formData.append("file_type", ftype);
  formData.append("mapping_name", mappingKey);
  if (dynMapping) {
    formData.append("custom_mapping_json", JSON.stringify(dynMapping));
  }

  const res = await fetch(`/api/cases/${currentCaseId}/upload`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${currentToken}` },
    body: formData
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(`${file.name}: ${data.detail || "Upload failed"}`);
  }
  return data;
}

async function handleDualFileUpload(e) {
  e.preventDefault();
  if (!currentCaseId) {
    alert("Please register or select an FIR Case first (+ Register FIR Case).");
    openNewCaseModal();
    return;
  }

  const alertBox = document.getElementById("upload-progress-alert");
  alertBox.style.display = "block";
  alertBox.className = "alert-banner";
  alertBox.innerText = "⏳ Inspecting & ingesting uploaded formats...";

  try {
    const reports = [];
    for (const slot of [1, 2]) {
      const rep = await uploadSingleSlot(slot);
      if (rep) reports.push(rep);
    }
    if (!reports.length) {
      alertBox.innerText = "⚠️ Please select at least one CSV or Excel file.";
      return;
    }

    const totalValid = reports.reduce((acc, r) => acc + (r.valid_rows || 0), 0);
    const totalRej = reports.reduce((acc, r) => acc + (r.rejected_rows || 0), 0);
    alertBox.style.background = "rgba(16, 185, 129, 0.2)";
    alertBox.style.color = "#34d399";
    alertBox.innerText = `✅ Ingested ${reports.length} format(s): ${totalValid} valid rows (${totalRej} rejected). Unlocking Command Center...`;

    displayValidationReports(reports);
    cachedAnalytics = null;
    await loadExecutiveMetrics(currentCaseId);
    await loadCaseDetails(currentCaseId);
    await getCaseAnalytics();
    await loadCaseBatches();

    if (currentCaseHasData) {
      setTimeout(() => switchView("dashboard"), 400);
    }
  } catch (err) {
    alertBox.style.background = "rgba(239, 68, 68, 0.2)";
    alertBox.style.color = "#fca5a5";
    alertBox.innerText = `❌ ${err.message}`;
  }
}

function displayValidationReports(reports) {
  const container = document.getElementById("validation-report-container");
  container.innerHTML = reports.map(s => `
    <div style="font-size:13px; line-height:1.7; padding:8px 0; border-bottom:1px solid var(--border-color);">
      <div><b>File:</b> ${s.filename} &bull; <b>Batch ID:</b> #${s.batch_id ?? "-"} &bull; <b>Mapping:</b> ${s.mapping_used}</div>
      <div><b>Total:</b> ${s.total_rows} | <b>Valid:</b> <span style="color:#10b981;">${s.valid_rows}</span> | <b>Rejected:</b> <span style="color:#ef4444;">${s.rejected_rows}</span></div>
      ${(s.rejected_details && s.rejected_details.length) ? `<div style="color:#fca5a5;margin-top:4px;font-size:11.5px;">Sample rejections: ${JSON.stringify(s.rejected_details.slice(0, 2))}</div>` : ""}
    </div>
  `).join("");
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
  if (!tbody) return;
  if (currentUser && currentUser.role === "investigating_officer") {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:18px;color:#94a3b8;">Audit logs require Senior Officer (SP) or Admin clearance. <button class="btn-save-case" style="padding:3px 10px;font-size:11px;margin-left:8px;" onclick="switchRole('sp_verma')">Switch to SP Verma</button></td></tr>`;
    return;
  }
  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;"><div class="spinner"></div> Fetching immutable Section 65B audit trail...</td></tr>`;

  try {
    const res = await fetch("/api/audit?limit=100", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#fca5a5;">Access denied. Requires Senior Officer or Admin role.</td></tr>`;
      return;
    }
    const logs = await res.json();
    tbody.innerHTML = "";

    logs.forEach(l => {
      const tr = document.createElement("tr");
      const hashDisplay = l.entry_hash
        ? `<code style="font-size:10px;color:#38bdf8;" title="${l.entry_hash}">${l.entry_hash.slice(0, 14)}...</code>`
        : `<span style="color:#64748b;">-</span>`;
      tr.innerHTML = `
        <td>#${l.id}</td>
        <td style="font-family:monospace;font-size:11px;">${l.timestamp}</td>
        <td><b>${l.username}</b></td>
        <td><span class="role-tag role-io">${l.role}</span></td>
        <td><span class="metric-card-badge badge-blue">${l.action}</span></td>
        <td style="font-size:11.5px;max-width:300px;overflow:hidden;text-overflow:ellipsis;">${JSON.stringify(l.details)}</td>
        <td style="font-family:monospace;font-size:11px;">${l.ip_address}</td>
        <td>${hashDisplay}</td>
      `;
      tbody.appendChild(tr);
    });

    runAuditChainVerification();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#fca5a5;">Error loading audit logs.</td></tr>`;
  }
}

async function runAuditChainVerification() {
  const badge = document.getElementById("audit-integrity-badge");
  const hashLabel = document.getElementById("audit-latest-hash");
  const countLabel = document.getElementById("audit-verified-count");
  if (!badge) return;

  badge.innerText = "VERIFYING CRYPTOGRAPHIC CHAIN...";
  badge.className = "badge-amber";

  try {
    const res = await fetch("/api/audit/verify", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      badge.innerText = "ACCESS DENIED (Requires Authorized Officer)";
      badge.className = "badge-amber";
      return;
    }
    const data = await res.json();
    if (data.is_valid) {
      badge.innerText = "✅ CRYPTOGRAPHICALLY AUTHENTIC";
      badge.className = "badge-green";
      if (hashLabel) hashLabel.innerText = data.latest_hash || "Genesis Hash Established";
      if (countLabel) countLabel.innerText = `All ${data.total_records} events verified under Section 65B`;
    } else {
      badge.innerText = "❌ INTEGRITY BREACH DETECTED";
      badge.className = "badge-amber";
      badge.style.background = "#ef4444";
      if (hashLabel) hashLabel.innerText = "Tampering detected in chain!";
      if (countLabel) countLabel.innerText = `Alert: ${data.tampered_records?.length || 1} records altered!`;
    }
  } catch (e) {
    console.error("Audit verification error:", e);
    badge.innerText = "VERIFICATION ERROR";
  }
}

// ----------------- MODULE: BATCH IPDR NAT RESOLVER -----------------
function loadBatchIpdrSample() {
  const ta = document.getElementById("batch-ipdr-input");
  if (ta) {
    ta.value = "103.211.54.12:44321, 2026-11-20 18:25:10\n103.211.54.88:51234, 2026-11-18 23:14:00\n103.211.68.38:28083, 2026-11-17 01:12:40\n198.51.100.99:9999, 2026-11-20 12:00:00";
  }
}

async function runBatchIpdrLookup() {
  if (!currentCaseId) return;
  const input = document.getElementById("batch-ipdr-input").value.trim();
  const tolerance = parseInt(document.getElementById("batch-ipdr-tolerance").value, 10) || 15;
  if (!input) {
    alert("Please enter at least one IP:Port, Timestamp query.");
    return;
  }

  const lines = input.split("\n");
  const queries = [];
  lines.forEach((line, idx) => {
    line = line.trim();
    if (!line) return;
    const parts = line.split(",");
    let ip = "", port = 0, ts = "";
    if (parts.length >= 2) {
      const ipPort = parts[0].trim();
      ts = parts.slice(1).join(",").trim();
      if (ipPort.includes(":")) {
        const ipp = ipPort.split(":");
        ip = ipp[0].trim();
        port = parseInt(ipp[1], 10) || 0;
      } else {
        ip = ipPort;
      }
    }
    if (ip && port && ts) {
      queries.push({
        query_id: `Q-${idx + 1}`,
        ip: ip,
        port: port,
        timestamp: ts
      });
    }
  });

  if (queries.length === 0) {
    alert("Could not parse queries. Format: IP:Port, YYYY-MM-DD HH:MM:SS");
    return;
  }

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/ipdr/batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ queries, tolerance_minutes: tolerance })
    });
    if (!res.ok) {
      alert("Error resolving batch IPDR queries.");
      return;
    }
    const data = await res.json();
    renderBatchIpdrResults(data);
  } catch (err) {
    console.error("Batch IPDR error:", err);
    alert("Network error executing batch IPDR resolution.");
  }
}

function renderBatchIpdrResults(data) {
  const container = document.getElementById("batch-ipdr-results");
  const statsSpan = document.getElementById("batch-ipdr-stats");
  const subsPill = document.getElementById("batch-ipdr-subs-pill");
  const tbody = document.getElementById("batch-ipdr-tbody");
  if (!container || !tbody) return;

  container.style.display = "block";
  statsSpan.innerText = `Matched ${data.matched_count} of ${data.total_queries} queries (${data.unmatched_count} unassigned)`;
  subsPill.innerText = `${data.identified_subscribers_count} Distinct Subscribers Identified`;

  let html = "";
  data.results.forEach(r => {
    const isMatched = r.matched;
    const statusHtml = isMatched
      ? `<span class="badge-green">MATCHED</span>`
      : `<span class="badge-amber">NO MATCH</span>`;
    const subHtml = r.primary_subscriber
      ? `<b style="color:#38bdf8;font-family:monospace;">${r.primary_subscriber}</b>`
      : `<span style="color:#64748b;">Unallocated NAT port</span>`;
    const appHint = r.session?.app_hint || "Unclassified Traffic";
    const lineage = r.session ? `<code>${r.session.source_file || 'operator_cgnat'} (R${r.session.source_row || '1'})</code>` : "-";

    html += `
      <tr>
        <td style="font-weight:700;">${r.query_id}</td>
        <td style="font-family:monospace;">${r.ip}:${r.port}</td>
        <td style="font-family:monospace;font-size:11px;">${r.timestamp}</td>
        <td>${statusHtml}</td>
        <td>${subHtml}</td>
        <td><span style="font-size:11px;">${appHint}</span></td>
        <td style="font-size:11px;">${lineage}</td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

// ----------------- MODAL: TAC DEVICE LOOKUP -----------------
function openTacLookupModal() {
  document.getElementById("modal-tac").classList.add("active");
  const samplesEl = document.getElementById("tac-dynamic-samples");
  if (samplesEl) {
    const imeis = (cachedAnalytics && cachedAnalytics.imei_summary) ? cachedAnalytics.imei_summary.slice(0, 4) : [];
    if (imeis.length) {
      samplesEl.innerHTML = `Case IMEIs: ` + imeis.map(im =>
        `<button class="chip-btn" onclick="lookupTacSample('${im.imei}')">${im.brand} (${im.imei.slice(-4)})</button>`
      ).join(" ");
    } else {
      samplesEl.innerText = "Upload CDR records to populate case IMEI shortcuts.";
    }
  }
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
  const case_type = document.getElementById("newcase-type")?.value || "Murder";
  const police_station = document.getElementById("newcase-station")?.value.trim() || "";
  const investigator_name = document.getElementById("newcase-io")?.value.trim() || "";
  const desc = document.getElementById("newcase-desc").value.trim();
  const status = document.getElementById("newcase-status")?.value || "ACTIVE";

  try {
    const res = await fetch("/api/cases", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({
        id,
        title,
        description: desc,
        case_type,
        police_station,
        investigator_name,
        status
      })
    });
    const data = await res.json();
    if (res.ok) {
      closeNewCaseModal();
      e.target.reset();
      currentCaseId = id;
      await loadCasesList();
      const sel = document.getElementById("case-selector");
      if (sel) sel.value = currentCaseId;
      await onCaseSelected(currentCaseId);
      // Offer immediate upload view for new empty case
      switchView("import");
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

// ----------------- DYNAMIC CASE UI POPULATION (ZERO HARDCODING) -----------------
function populateDynamicCaseUI(analytics) {
  if (!analytics) return;
  const suspects = analytics.suspects || [];
  const p1 = suspects[0]?.phone || "";
  const p2 = suspects[1]?.phone || "";
  const p3 = suspects[2]?.phone || "";
  const p4 = suspects[3]?.phone || "";

  // Update suspect count in header pill
  const sHdrSus = document.getElementById("stat-hdr-suspects");
  if (sHdrSus) sHdrSus.innerText = suspects.length;

  // Populate Dashboard Target Suspects Chips dynamically (Click -> Opens Image 3 Suspect Workspace!)
  const dashChips = document.getElementById("dash-suspects-chips");
  if (dashChips) {
    if (suspects.length > 0) {
      dashChips.innerHTML = "";
      suspects.forEach(s => {
        const btn = document.createElement("button");
        btn.className = "chip-btn";
        btn.innerHTML = `<b>${s.name || s.role || "Target"}</b>: ${s.phone || ""}`;
        btn.onclick = () => {
          currentSuspectPhone = s.phone;
          enterInvestigationWorkspace("advanced-cdr");
        };
        dashChips.appendChild(btn);
      });
    } else {
      dashChips.innerHTML = `<span style="color:var(--text-muted);font-size:12px;">Upload CDR files to auto-extract top syndicate targets.</span>`;
    }
  }

  // Populate map suspect selector dynamically
  const mapSel = document.getElementById("map-suspect-select");
  if (mapSel) {
    mapSel.innerHTML = suspects.length
      ? suspects.map(s => `<option value="${s.phone}">${s.name || s.id} (${s.phone})</option>`).join("")
      : `<option value="">No targets available</option>`;
  }

  // Dynamically seed inputs if empty
  const setIfEmpty = (id, val) => {
    const el = document.getElementById(id);
    if (el && !el.value && val) el.value = val;
  };
  if (p1 && p2) {
    setIfEmpty("common-numbers-input", `${p1}, ${p2}`);
    setIfEmpty("meet-num1", p1);
    setIfEmpty("meet-num2", p2);
    setIfEmpty("link-num1", p1);
    setIfEmpty("link-num2", p2);
  }
  setIfEmpty("ipdr-sub-input", p1);

  // Dynamic AI quick chips based on active targets
  const chipsEl = document.getElementById("assistant-quick-chips");
  if (chipsEl) {
    let html = `<span style="font-size: 11px; color: var(--text-muted); align-self: center;">Quick Questions:</span>`;
    if (p1) html += `<button class="chip-btn" onclick="sendQuickPrompt('Who are the top frequent contacts of ${p1}?')">Top contacts (${p1})</button>`;
    if (p1 && p2) html += `<button class="chip-btn" onclick="sendQuickPrompt('Find common numbers between ${p1} and ${p2}')">Common numbers</button>`;
    if (p3) html += `<button class="chip-btn" onclick="sendQuickPrompt('${p3} ne kab SIM badla ya IMEI reuse kiya?')">SIM swap check (Hindi)</button>`;
    if (p4 || p1) html += `<button class="chip-btn" onclick="sendQuickPrompt('Check night activity for ${p4 || p1}')">Night calls</button>`;
    if (p1 && p2) html += `<button class="chip-btn" onclick="sendQuickPrompt('Did ${p1} and ${p2} have a physical meeting at any tower?')">Physical meeting</button>`;
    html += `<button class="chip-btn" onclick="sendQuickPrompt('Call me kya baat hui aur recording sunao')">Guardrail test (Hindi)</button>`;
    chipsEl.innerHTML = html;
  }

  // Dynamic Notifications
  const notifs = analytics.notifications || [];
  const badge = document.getElementById("notif-badge");
  const container = document.getElementById("notifs-container");
  if (badge) badge.innerText = notifs.length;
  if (container) {
    if (!notifs.length) {
      container.innerHTML = `<p style="color: var(--text-muted); font-size: 12px;">No anomaly alerts detected for this case.</p>`;
    } else {
      const colors = { critical: "#ef4444", warning: "#f59e0b", info: "#10b981" };
      const icons = { critical: "🚨", warning: "📍", info: "✅" };
      container.innerHTML = notifs.map(n => `
        <div style="padding: 10px; background: var(--bg-card-subtle); border-left: 3px solid ${colors[n.severity] || '#38bdf8'}; border-radius: 4px; margin-bottom: 8px;">
          <b style="color: ${colors[n.severity] || '#38bdf8'};">${icons[n.severity] || '🔔'} ${n.title}</b>
          <p style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px;">${n.message}</p>
          <small style="color: var(--text-muted);">${n.meta || ""}</small>
        </div>
      `).join("");
    }
  }
}

// ----------------- SHARED TABLE HELPERS -----------------
function renderCallTableRows(tbodyId, rows) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  if (!rows || !rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No matching calls found.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td style="font-family:monospace;font-size:11px;">${r.timestamp}</td>
      <td><b>${r.a_number}</b></td>
      <td>${r.b_number}</td>
      <td><span class="metric-card-badge badge-blue">${r.call_type}</span></td>
      <td>${r.duration_sec}s</td>
      <td><small>${r.cell_id} (${r.area_name})</small></td>
      <td><span class="evidence-chip" onclick="openEvidenceModal('${r.source_file}', ${r.source_row})">${r.source_file}:R${r.source_row}</span></td>
    </tr>
  `).join("");
}

function renderHopTableRows(tbodyId, rows, areaOnly) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  if (!rows || !rows.length) {
    tbody.innerHTML = `<tr><td colspan="${areaOnly ? 6 : 7}" style="text-align:center;color:var(--text-muted);">No transitions detected.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(h => areaOnly ? `
    <tr>
      <td>${h.seq}</td>
      <td style="font-family:monospace;font-size:11px;">${h.timestamp}</td>
      <td><b>${h.number}</b></td>
      <td>${h.from_area}</td>
      <td style="color:#38bdf8;font-weight:600;">${h.area_name}</td>
      <td>${h.time_delta_sec}s</td>
    </tr>
  ` : `
    <tr>
      <td>${h.seq}</td>
      <td style="font-family:monospace;font-size:11px;">${h.timestamp}</td>
      <td><b>${h.number}</b></td>
      <td style="font-family:monospace;">${h.from_cell}</td>
      <td style="font-family:monospace;color:#38bdf8;font-weight:600;">${h.cell_id}</td>
      <td>${h.area_name}</td>
      <td>${h.time_delta_sec}s</td>
    </tr>
  `).join("");
}

// ----------------- NEW SIDEBAR MODULE RENDERERS -----------------
async function loadNetworkAnalysisView() {
  const d = await getCaseAnalytics();
  if (!d || !d.network_stats) return;
  const hubsBody = document.getElementById("network-hubs-tbody");
  const pairsBody = document.getElementById("network-pairs-tbody");
  if (hubsBody) {
    hubsBody.innerHTML = (d.network_stats.top_hubs || []).map(h => `
      <tr><td><b>${h.number}</b></td><td>${h.calls}</td><td>${h.unique_towers}</td><td>${h.duration}s</td><td>${h.in_out}</td></tr>
    `).join("") || `<tr><td colspan="5">No data</td></tr>`;
  }
  if (pairsBody) {
    pairsBody.innerHTML = (d.network_stats.top_pairs || []).map(p => `
      <tr><td><b>${p.source}</b></td><td><b>${p.target}</b></td><td><span class="metric-card-badge badge-amber">${p.calls}</span></td><td>${p.duration}s</td></tr>
    `).join("") || `<tr><td colspan="4">No data</td></tr>`;
  }
}

async function loadImeiPatternsView() {
  const d = await getCaseAnalytics();
  const tbody = document.getElementById("imei-patterns-tbody");
  if (!d || !tbody) return;
  tbody.innerHTML = (d.imei_patterns || []).map(p => `
    <tr>
      <td style="font-family:monospace;color:#38bdf8;">${p.imei}</td>
      <td>${p.device}</td>
      <td><b>${p.distinct_sims}</b></td>
      <td>${p.distinct_imsis}</td>
      <td>${p.calls}</td>
      <td><span class="metric-card-badge ${p.pattern_flag === 'MULTI_SIM_SWAP' ? 'badge-amber' : 'badge-blue'}">${p.pattern_flag}</span></td>
      <td><small>${p.numbers.join(", ")}</small></td>
    </tr>
  `).join("") || `<tr><td colspan="7">No IMEI patterns</td></tr>`;
}

async function loadImsiPatternsView() {
  const d = await getCaseAnalytics();
  const tbody = document.getElementById("imsi-patterns-tbody");
  if (!d || !tbody) return;
  tbody.innerHTML = (d.imsi_patterns || []).map(p => `
    <tr>
      <td style="font-family:monospace;color:#38bdf8;">${p.imsi}</td>
      <td><b>${p.distinct_imeis}</b></td>
      <td>${p.distinct_numbers}</td>
      <td>${p.calls}</td>
      <td><span class="metric-card-badge ${p.pattern_flag === 'MULTI_HANDSET_HOP' ? 'badge-amber' : 'badge-green'}">${p.pattern_flag}</span></td>
      <td><small style="font-family:monospace;">${p.imeis.join(", ")}</small></td>
    </tr>
  `).join("") || `<tr><td colspan="6">No IMSI patterns</td></tr>`;
}

async function loadLocationSummaryView() {
  const d = await getCaseAnalytics();
  const tbody = document.getElementById("location-summary-tbody");
  if (!d || !tbody) return;
  tbody.innerHTML = (d.location_summary || []).map(l => `
    <tr>
      <td style="font-family:monospace;color:#fbbf24;">${l.cell_id}</td>
      <td><b>${l.area_name}</b></td>
      <td>${l.hits}</td>
      <td>${l.unique_numbers}</td>
      <td><span class="metric-card-badge badge-blue">${l.pct}%</span></td>
      <td style="font-size:11px;font-family:monospace;">${l.first_seen}</td>
      <td style="font-size:11px;font-family:monospace;">${l.last_seen}</td>
    </tr>
  `).join("") || `<tr><td colspan="7">No tower data</td></tr>`;
}

async function loadLocationIntelView() {
  const d = await getCaseAnalytics();
  const box = document.getElementById("location-intel-cards");
  if (!d || !d.location_intelligence || !box) return;
  const li = d.location_intelligence;
  box.innerHTML = `
    <div class="metric-card metric-card-blue"><div class="metric-card-title">Unique Cell Towers</div><div class="metric-card-val">${li.total_unique_towers || 0}</div><div class="metric-card-footer"><span>Active Sites</span></div></div>
    <div class="metric-card metric-card-amber"><div class="metric-card-title">Daytime Base Tower</div><div class="metric-card-val" style="font-size:16px;">${li.primary_day_tower ? li.primary_day_tower.area_name : '-'}</div><div class="metric-card-footer"><span>${li.primary_day_tower ? li.primary_day_tower.visits + ' hits' : ''}</span></div></div>
    <div class="metric-card metric-card-purple"><div class="metric-card-title">Nighttime Residence Tower</div><div class="metric-card-val" style="font-size:16px;">${li.primary_night_tower ? li.primary_night_tower.area_name : '-'}</div><div class="metric-card-footer"><span>${li.primary_night_tower ? li.primary_night_tower.visits + ' hits' : ''}</span></div></div>
    <div class="metric-card metric-card-green"><div class="metric-card-title">Most Visited Tower</div><div class="metric-card-val" style="font-size:16px;">${li.most_visited_tower ? li.most_visited_tower.cell_id : '-'}</div><div class="metric-card-footer"><span>${li.most_visited_tower ? li.most_visited_tower.area_name : ''}</span></div></div>
    <div class="metric-card metric-card-blue"><div class="metric-card-title">Total Cell Hops</div><div class="metric-card-val">${li.total_tower_hops || 0}</div><div class="metric-card-footer"><span>Tower Transitions</span></div></div>
    <div class="metric-card metric-card-amber"><div class="metric-card-title">Area Changes</div><div class="metric-card-val">${li.total_area_transitions || 0}</div><div class="metric-card-footer"><span>City/Sector Shifts</span></div></div>
  `;
}

async function loadDayCallsView() {
  const d = await getCaseAnalytics();
  if (d) renderCallTableRows("day-calls-tbody", d.day_calls);
}

async function loadNightCallsView() {
  const d = await getCaseAnalytics();
  if (d) renderCallTableRows("night-calls-tbody", d.night_calls);
}

async function loadCellChangesView() {
  const d = await getCaseAnalytics();
  if (d) renderHopTableRows("cell-changes-tbody", d.cell_id_changes, false);
}

async function loadLocationChangesView() {
  const d = await getCaseAnalytics();
  if (d) renderHopTableRows("location-changes-tbody", d.location_changes, true);
}

async function loadInteractiveTimelineView() {
  const d = await getCaseAnalytics();
  const tbody = document.getElementById("interactive-timeline-tbody");
  if (!d || !tbody) return;
  tbody.innerHTML = (d.interactive_timeline || []).map(ev => `
    <tr>
      <td style="font-family:monospace;font-size:11px;">${ev.timestamp}</td>
      <td><span class="metric-card-badge ${ev.event_type.startsWith('IPDR') ? 'badge-purple' : 'badge-blue'}">${ev.event_type}</span></td>
      <td><b>${ev.entity}</b></td>
      <td>${ev.target}</td>
      <td>${ev.location}</td>
      <td><small>${ev.details}</small></td>
      <td><small style="color:#38bdf8;">${ev.evidence}</small></td>
    </tr>
  `).join("") || `<tr><td colspan="7">No timeline events</td></tr>`;
}

async function runLinkAnalysis() {
  const d = await getCaseAnalytics();
  const n1El = document.getElementById("link-num1");
  const n2El = document.getElementById("link-num2");
  if (d && d.suspects && d.suspects.length >= 2) {
    if (n1El && !n1El.value) n1El.value = d.suspects[0].phone;
    if (n2El && !n2El.value) n2El.value = d.suspects[1].phone;
  }
  const num1 = n1El ? n1El.value.trim() : "";
  const num2 = n2El ? n2El.value.trim() : "";
  const box = document.getElementById("link-analysis-results");
  if (!num1 || !num2 || !box || !currentCaseId) return;

  try {
    const res = await fetch(`/api/cases/${currentCaseId}/link-analysis?num1=${encodeURIComponent(num1)}&num2=${encodeURIComponent(num2)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    box.innerHTML = `
      <div class="metric-grid-8" style="grid-template-columns: repeat(4, 1fr); margin-bottom:12px;">
        <div class="metric-card metric-card-blue"><div class="metric-card-title">Link Status</div><div class="metric-card-val" style="font-size:16px;">${data.link_strength}</div></div>
        <div class="metric-card metric-card-amber"><div class="metric-card-title">Direct Calls</div><div class="metric-card-val">${data.direct_calls_count}</div></div>
        <div class="metric-card metric-card-purple"><div class="metric-card-title">Shared Bridge Contacts</div><div class="metric-card-val">${data.shared_contacts.length}</div></div>
        <div class="metric-card metric-card-green"><div class="metric-card-title">Shared Cell Towers</div><div class="metric-card-val">${data.shared_towers.length}</div></div>
      </div>
      <div class="table-container">
        <table>
          <thead><tr><th>Bridge Contact</th><th>Calls w/ ${num1}</th><th>Calls w/ ${num2}</th><th>Total Bridge Calls</th></tr></thead>
          <tbody>
            ${data.shared_contacts.map(c => `<tr><td><b>${c.number}</b></td><td>${c.calls_with_num1}</td><td>${c.calls_with_num2}</td><td><span class="metric-card-badge badge-amber">${c.total_bridge_calls}</span></td></tr>`).join("") || '<tr><td colspan="4">No shared contacts found.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    box.innerHTML = `<p style="color:#fca5a5;">Error running link analysis.</p>`;
  }
}


// ==============================================================================
// HOME SIDEBAR DEDICATED VIEWS: CASES DIRECTORY, ENTITY LOOKUP & WATCHLIST
// ==============================================================================
let cachedCasesList = [];

async function loadCasesDirectoryView() {
  const tbody = document.getElementById("cases-page-tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#64748b;">Loading cases directory...</td></tr>`;
  try {
    const res = await fetch("/api/cases", { headers: { "Authorization": `Bearer ${currentToken}` } });
    if (!res.ok) return;
    cachedCasesList = await res.json();
    renderCasesDirectoryRows(cachedCasesList);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#f87171;">Error fetching cases.</td></tr>`;
  }
}

function renderCasesDirectoryRows(list) {
  const tbody = document.getElementById("cases-page-tbody");
  if (!tbody) return;
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#64748b;">No matching cases found. Click "+ Add New Case" to register one.</td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(c => `
    <tr>
      <td><b style="color:#38bdf8;font-family:monospace;">${c.id}</b></td>
      <td><b>${c.title}</b></td>
      <td><span class="metric-card-badge badge-purple">${c.case_type || "Cyber / Telecom"}</span></td>
      <td>${c.police_station || "State Cyber Cell"}</td>
      <td>${c.investigator_name || c.created_by}</td>
      <td><b>${(c.cdr_count || 0).toLocaleString()}</b></td>
      <td><b>${(c.ipdr_count || 0).toLocaleString()}</b></td>
      <td>
        <select class="form-control" style="padding:3px 6px;font-size:11px;width:125px;" onchange="updateCaseStatusFromDir('${c.id}', this.value)">
          <option value="ACTIVE" ${c.status === "ACTIVE" ? "selected" : ""}>ACTIVE</option>
          <option value="PENDING" ${c.status === "PENDING" ? "selected" : ""}>PENDING</option>
          <option value="UNDER_SCRUTINY" ${c.status === "UNDER_SCRUTINY" ? "selected" : ""}>UNDER REVIEW</option>
          <option value="COMPLETED" ${c.status === "COMPLETED" ? "selected" : ""}>COMPLETED</option>
        </select>
      </td>
      <td>
        <div style="display:flex;gap:6px;">
          <button class="btn-save-case" style="padding:4px 10px;font-size:11.5px;" onclick="openCaseInWorkspace('${c.id}')">Open Workspace</button>
          <button class="btn-action-suspect" style="padding:4px 8px;font-size:11px;" onclick="changeActiveCase('${c.id}').then(() => switchView('import'))">Upload Data</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function filterCasesPage() {
  const q = (document.getElementById("cases-dir-search")?.value || "").toLowerCase();
  const filtered = cachedCasesList.filter(c =>
    c.id.toLowerCase().includes(q) ||
    c.title.toLowerCase().includes(q) ||
    (c.police_station || "").toLowerCase().includes(q) ||
    (c.case_type || "").toLowerCase().includes(q)
  );
  renderCasesDirectoryRows(filtered);
}

async function updateCaseStatusFromDir(caseId, status) {
  try {
    await fetch(`/api/cases/${encodeURIComponent(caseId)}/status`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ status })
    });
    await loadExecutiveMetrics(currentCaseId);
  } catch (e) {}
}

async function openCaseInWorkspace(caseId) {
  currentCaseId = caseId;
  const sel = document.getElementById("case-selector");
  if (sel) sel.value = caseId;
  await onCaseSelected(caseId);
  enterInvestigationWorkspace(currentCaseHasData ? "advanced-cdr" : "import");
}

async function runNumberLookup() {
  const q = document.getElementById("number-lookup-input")?.value.trim();
  const box = document.getElementById("number-lookup-results");
  if (!q || !box) return;
  box.innerHTML = `<div class="spinner"></div> Querying CDR/IPDR/TAC databases for <b>${q}</b>...`;

  try {
    const url = `/api/lookup?q=${encodeURIComponent(q)}${currentCaseId ? `&case_id=${encodeURIComponent(currentCaseId)}` : ""}`;
    const res = await fetch(url, { headers: { "Authorization": `Bearer ${currentToken}` } });
    if (!res.ok) return;
    const d = await res.json();

    if (!d.found) {
      box.innerHTML = `<div class="module-empty-banner"><b style="color:#f8fafc;">No records matched "${q}"</b><p style="color:#64748b;margin-top:4px;font-size:12px;">Upload CDR/IPDR files containing this entity or try searching across all cases.</p></div>`;
      return;
    }

    const tacHtml = d.tac_device && d.tac_device.brand
      ? `<div class="summary-tile"><div class="tile-val" style="font-size:15px;color:#38bdf8;">${d.tac_device.brand} ${d.tac_device.model || ""}</div><div class="tile-lbl">TAC Device (${d.tac_device.generation || "4G/5G"})</div></div>`
      : `<div class="summary-tile"><div class="tile-val">${d.imeis.length}</div><div class="tile-lbl">Linked IMEIs</div></div>`;

    box.innerHTML = `
      <div class="quick-summary-grid" style="margin-bottom:14px;">
        <div class="summary-tile"><div class="tile-val" style="color:#38bdf8;font-size:15px;">${d.classification}</div><div class="tile-lbl">Classification</div></div>
        <div class="summary-tile"><div class="tile-val">${d.total_cdr_hits}</div><div class="tile-lbl">CDR Records</div></div>
        <div class="summary-tile"><div class="tile-val">${d.total_ipdr_hits}</div><div class="tile-lbl">IPDR Sessions</div></div>
        <div class="summary-tile"><div class="tile-val">${d.towers.length}</div><div class="tile-lbl">Cell Towers</div></div>
        ${tacHtml}
      </div>
      <div class="grid-2" style="gap:14px;">
        <div class="card" style="margin-bottom:0;">
          <div class="card-header"><div class="card-title">Top Linked Peers</div></div>
          <div class="table-container" style="max-height:240px;overflow-y:auto;">
            <table>
              <thead><tr><th>Peer Number</th><th>Interactions</th></tr></thead>
              <tbody>${d.top_peers.map(p => `<tr><td><b>${p.number}</b></td><td><span class="metric-card-badge badge-blue">${p.count}</span></td></tr>`).join("") || '<tr><td colspan="2">No peers</td></tr>'}</tbody>
            </table>
          </div>
        </div>
        <div class="card" style="margin-bottom:0;">
          <div class="card-header"><div class="card-title">Tower Presence</div></div>
          <div class="table-container" style="max-height:240px;overflow-y:auto;">
            <table>
              <thead><tr><th>Cell ID</th><th>Location</th></tr></thead>
              <tbody>${d.towers.map(t => `<tr><td style="font-family:monospace;color:#fbbf24;">${t.cell_id}</td><td>${t.area_name}</td></tr>`).join("") || '<tr><td colspan="2">No tower hits</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    box.innerHTML = `<p style="color:#f87171;">Error querying entity profile.</p>`;
  }
}

async function loadWatchlistView() {
  if (!currentCaseId) return;
  const velBox = document.getElementById("watchlist-velocity-box");
  const thrBox = document.getElementById("watchlist-threats-box");

  if (velBox) {
    velBox.innerHTML = `<div class="spinner"></div> Scanning cell tower transitions for impossible travel velocity (>120 km/h)...`;
    try {
      const r = await fetch(`/api/cases/${currentCaseId}/velocity-anomalies`, { headers: { "Authorization": `Bearer ${currentToken}` } });
      const items = r.ok ? await r.json() : [];
      if (!items.length) {
        velBox.innerHTML = `<p style="color:#64748b;font-size:12.5px;">No impossible travel velocity anomalies detected in active case.</p>`;
      } else {
        velBox.innerHTML = `<div class="table-container"><table><thead><tr><th>Target</th><th>From Tower</th><th>To Tower</th><th>Distance</th><th>Elapsed</th><th>Speed</th><th>Alert</th></tr></thead><tbody>${items.map(a => `
          <tr>
            <td><b>${a.suspect_number}</b></td>
            <td>${a.from_tower} <small>(${a.from_time})</small></td>
            <td>${a.to_tower} <small>(${a.to_time})</small></td>
            <td>${a.distance_km} km</td>
            <td>${a.time_elapsed_min} min</td>
            <td><b style="color:#f87171;">${a.calculated_speed_kmh} km/h</b></td>
            <td><span class="metric-card-badge badge-red">${a.risk_level}</span></td>
          </tr>
        `).join("")}</tbody></table></div>`;
      }
    } catch (e) {
      velBox.innerHTML = `<p style="color:#f87171;">Error checking velocity anomalies.</p>`;
    }
  }

  if (thrBox) {
    try {
      const res = await fetch(`/api/cases/${currentCaseId}/threat-scoring`, { headers: { "Authorization": `Bearer ${currentToken}` } });
      const scores = res.ok ? await res.json() : [];
      if (!scores.length) {
        thrBox.innerHTML = `<p style="color:#64748b;">Upload CDR records to evaluate suspect threat profiles.</p>`;
      } else {
        thrBox.innerHTML = scores.map(s => `
          <div class="threat-card">
            <div class="threat-card-header">
              <div>
                <div class="threat-card-name">${s.name}</div>
                <div class="threat-card-phone">${s.phone}</div>
              </div>
              <span class="threat-badge threat-badge-${(s.risk_level || 'low').toLowerCase()}">${s.risk_level} (${s.threat_score}/100)</span>
            </div>
            <div class="threat-archetype-chip">${s.archetype}</div>
            <div class="threat-factors-list">${(s.factors || []).map(f => `<span class="threat-factor-pill">${f}</span>`).join("")}</div>
            <div class="threat-card-actions">
              <button class="btn-save-case" style="padding:4px 10px;font-size:11px;" onclick="currentSuspectPhone='${s.phone}'; enterInvestigationWorkspace('advanced-cdr');">Investigate &rarr;</button>
            </div>
          </div>
        `).join("");
      }
    } catch (e) {}
  }
}

// ==============================================================================
// ADVANCED SUSPECT WORKSPACE (IMAGE 3), GRAPH ANALYTICS (IMAGE 4) & 7 POLICE MAPS
// ==============================================================================

async function loadSuspectWorkspace(targetPhone = null) {
  if (!currentCaseId) return;
  const sel = document.getElementById("suspect-workspace-select");

  let phone = targetPhone || (sel ? sel.value : "") || currentSuspectPhone;
  if (!phone && cachedAnalytics?.suspects?.length > 0) {
    phone = cachedAnalytics.suspects[0].phone;
  }
  currentSuspectPhone = phone;

  if (sel && cachedAnalytics?.suspects?.length > 0) {
    sel.innerHTML = `<option value="">-- Switch Suspect --</option>`;
    cachedAnalytics.suspects.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.phone;
      opt.textContent = `${s.name || 'Target'}: ${s.phone}`;
      if (s.phone === currentSuspectPhone) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  try {
    const url = phone 
      ? `/api/cases/${currentCaseId}/suspect/${encodeURIComponent(phone)}/summary`
      : `/api/cases/${currentCaseId}/suspect/_/summary`;
    const res = await fetch(url, { headers: { "Authorization": `Bearer ${currentToken}` } });
    if (!res.ok) return;
    const data = await res.json();

    const phoneDisp = document.getElementById("suspect-phone-display");
    const subPhone = document.getElementById("suspect-subtitle-phone");
    const subRows = document.getElementById("suspect-subtitle-rows");
    if (phoneDisp) phoneDisp.innerText = data.suspect_phone || "No Suspect Selected";
    if (subPhone) subPhone.innerText = data.suspect_phone || "All Case Rows";
    if (subRows) subRows.innerText = (data.total_rows || 0).toLocaleString();

    // 10 Centered KPI Summary Cards (Image 3)
    const mapFields = {
      "sum-target-op": data.target_operator || "N/A",
      "sum-total-calls": (data.total_calls || 0).toLocaleString(),
      "sum-total-sms": (data.total_sms || 0).toLocaleString(),
      "sum-total-contacts": (data.total_contacts || 0).toLocaleString(),
      "sum-total-imeis": data.total_imeis || 0,
      "sum-total-imsis": data.total_imsis || 0,
      "sum-total-locations": data.total_locations || 0,
      "sum-total-active-days": data.total_active_days || 0,
      "sum-intl-contacts": data.international_contacts || 0,
      "sum-ownership-found": data.ownership_found || 0
    };
    for (const [id, val] of Object.entries(mapFields)) {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    }

    // Network Distribution Summary (Image 3)
    const statBoxes = document.getElementById("network-dist-stat-boxes");
    const barsContainer = document.getElementById("network-dist-bars-container");
    const totalUniq = data.network_distribution?.total_unique_numbers || 0;
    const ops = data.network_distribution?.operators || [];

    if (statBoxes) {
      statBoxes.innerHTML = `
        <div class="net-stat-box">
          <div class="net-stat-val">${totalUniq.toLocaleString()}</div>
          <div class="net-stat-lbl">Total Unique Mobile Numbers</div>
        </div>
      `;
      ops.forEach(op => {
        statBoxes.innerHTML += `
          <div class="net-stat-box">
            <div class="net-stat-val" style="color: ${op.color};">${op.count}</div>
            <div class="net-stat-lbl">${op.operator} (${op.percentage}%)</div>
          </div>
        `;
      });
    }

    if (barsContainer) {
      barsContainer.innerHTML = ops.map(op => `
        <div class="net-bar-row">
          <div class="net-bar-name">${op.operator}</div>
          <div class="net-bar-track">
            <div class="net-bar-fill" style="width: ${op.percentage}%; background: ${op.color};"></div>
          </div>
          <div class="net-bar-count">${op.count}</div>
          <div class="net-bar-pct">${op.percentage}%</div>
        </div>
      `).join("") || `<div style="color:#64748b;font-size:12px;">Upload CDR files to analyze network operator breakdown.</div>`;
    }

    // Render Suspect Recent Records Table
    const advBody = document.getElementById("adv-cdr-tbody");
    if (advBody) {
      const recs = data.recent_records || [];
      advBody.innerHTML = recs.map(r => `
        <tr>
          <td style="font-family:monospace;font-size:11px;">${r.start_time}</td>
          <td><b>${r.a_number}</b></td>
          <td><b>${r.b_number}</b></td>
          <td><span class="metric-card-badge ${r.call_type === 'IN' ? 'badge-green' : 'badge-blue'}">${r.call_type}</span></td>
          <td>${r.duration_sec}s</td>
          <td style="font-family:monospace;font-size:11px;color:#38bdf8;">${r.imei || "-"}</td>
          <td style="font-family:monospace;font-size:11px;color:#fbbf24;">${r.cell_id || "-"}</td>
        </tr>
      `).join("") || `<tr><td colspan="7" style="text-align:center;color:#64748b;">No records available for selected target.</td></tr>`;
    }
  } catch (err) {
    console.error("Error loading suspect workspace:", err);
  }
}

async function runAdvancedCdrFilter() {
  if (!currentCaseId) return;
  const search = document.getElementById("adv-cdr-num")?.value.trim() || currentSuspectPhone || "";
  const durMin = parseInt(document.getElementById("adv-cdr-dur")?.value || "0", 10);
  const ctype = document.getElementById("adv-cdr-type")?.value || "";
  const advBody = document.getElementById("adv-cdr-tbody");
  if (!advBody) return;

  advBody.innerHTML = `<tr><td colspan="7" style="text-align:center;">Querying filtered records...</td></tr>`;
  try {
    const res = await fetch(`/api/cases/${currentCaseId}/raw-cdr?page=1&limit=200&search=${encodeURIComponent(search)}&call_type=${encodeURIComponent(ctype)}`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const data = res.ok ? await res.json() : { records: [] };
    const filtered = (data.records || []).filter(r => (r.duration_sec || 0) >= durMin);
    advBody.innerHTML = filtered.map(r => `
      <tr>
        <td style="font-family:monospace;font-size:11px;">${r.start_time}</td>
        <td><b>${r.a_number}</b></td>
        <td><b>${r.b_number}</b></td>
        <td><span class="metric-card-badge ${r.call_type === 'IN' ? 'badge-green' : 'badge-blue'}">${r.call_type}</span></td>
        <td>${r.duration_sec}s</td>
        <td style="font-family:monospace;font-size:11px;color:#38bdf8;">${r.imei || "-"}</td>
        <td style="font-family:monospace;font-size:11px;color:#fbbf24;">${r.cell_id || "-"}</td>
      </tr>
    `).join("") || `<tr><td colspan="7" style="text-align:center;color:#64748b;">No records match custom filter.</td></tr>`;
  } catch (e) {}
}

function downloadSuspectExport(fmt) {
  if (!currentCaseId) return;
  const phone = currentSuspectPhone || "";
  window.open(`/api/cases/${currentCaseId}/report?format=${fmt}&suspect=${encodeURIComponent(phone)}`, "_blank");
}

function pinCurrentSuspect() {
  if (!currentSuspectPhone) return;
  localStorage.setItem(`pinned_suspect_${currentCaseId}`, currentSuspectPhone);
  const tagEl = document.querySelector(".suspect-tag");
  if (tagEl) tagEl.innerText = `INVESTIGATION WORKSPACE · PINNED (${currentSuspectPhone})`;
}

function toggleAutoHide() {
  toggleSidebarCollapsed();
}

function openSuspectEvidence() {
  viewEvidence("CDR", "Uploaded Case Records", 1);
}

// ----------------- IMAGE 4: GRAPH ANALYTICS 4-QUADRANT VIEW -----------------
async function loadGraphAnalyticsView() {
  if (!currentCaseId) return;

  try {
    const rawRes = await fetch(`/api/cases/${currentCaseId}/raw-cdr?page=1&limit=500`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const rawData = rawRes.ok ? await rawRes.json() : { records: [] };
    const records = rawData.records || [];

    // --- QUADRANT 1: Communication Timeline ---
    const dateCounts = {};
    records.forEach(r => {
      if (!r.start_time) return;
      const d = r.start_time.split("T")[0] || r.start_time.split(" ")[0];
      dateCounts[d] = (dateCounts[d] || 0) + 1;
    });
    const sortedDates = Object.keys(dateCounts).sort();
    const timelineCounts = sortedDates.map(d => dateCounts[d]);
    const totalEvents = timelineCounts.reduce((a, b) => a + b, 0) || records.length;
    let peakDate = sortedDates[0] || "None";
    let peakCount = 0;
    sortedDates.forEach(d => {
      if (dateCounts[d] > peakCount) {
        peakCount = dateCounts[d];
        peakDate = d;
      }
    });

    const metaTl = document.getElementById("quad-meta-timeline");
    if (metaTl) {
      metaTl.innerText = `Total: ${totalEvents.toLocaleString()}   Days: ${sortedDates.length}   Peak: ${peakDate} (${peakCount})`;
    }

    const tBodyTl = document.getElementById("quad-tbody-timeline");
    if (tBodyTl) {
      tBodyTl.innerHTML = sortedDates.slice(0, 30).map(d => {
        const cnt = dateCounts[d];
        const pct = totalEvents ? ((cnt / totalEvents) * 100).toFixed(1) : "0.0";
        return `<tr><td>${d}</td><td style="text-align:right;"><b>${cnt}</b></td><td style="text-align:right;color:#38bdf8;">${pct}%</td></tr>`;
      }).join("") || `<tr><td colspan="3" style="text-align:center;color:#64748b;">No records available</td></tr>`;
    }

    const ctxTl = document.getElementById("timeline-chart")?.getContext("2d");
    if (ctxTl) {
      if (chartTimelineInstance) chartTimelineInstance.destroy();
      chartTimelineInstance = new Chart(ctxTl, {
        type: "line",
        data: {
          labels: sortedDates,
          datasets: [{
            label: "Events",
            data: timelineCounts,
            borderColor: "#22d3ee",
            backgroundColor: "rgba(34, 211, 238, 0.08)",
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 4,
            tension: 0.38,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { display: false } },
            y: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { color: "rgba(255,255,255,0.04)" } }
          }
        }
      });
    }

    // --- QUADRANT 2: Hourly Call Pattern (Image 4 Red Peak + Teal Bars + 3 KPIs) ---
    const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0") + ":00");
    const hourlyCounts = Array(24).fill(0);
    records.forEach(r => {
      if (!r.start_time) return;
      try {
        const timePart = r.start_time.split("T")[1] || r.start_time.split(" ")[1];
        if (timePart) {
          const h = parseInt(timePart.split(":")[0], 10);
          if (!isNaN(h) && h >= 0 && h < 24) hourlyCounts[h]++;
        }
      } catch (e) {}
    });

    let peakHourIdx = 0;
    let peakHourVal = 0;
    let activeHoursCount = 0;
    hourlyCounts.forEach((cnt, idx) => {
      if (cnt > 0) activeHoursCount++;
      if (cnt > peakHourVal) {
        peakHourVal = cnt;
        peakHourIdx = idx;
      }
    });

    const hKpiTot = document.getElementById("hourly-kpi-total");
    const hKpiHrs = document.getElementById("hourly-kpi-hours");
    const hKpiPk = document.getElementById("hourly-kpi-peak");
    if (hKpiTot) hKpiTot.innerText = totalEvents.toLocaleString();
    if (hKpiHrs) hKpiHrs.innerText = activeHoursCount;
    if (hKpiPk) hKpiPk.innerText = `${String(peakHourIdx).padStart(2, "0")}:00 (${peakHourVal})`;

    const tBodyH = document.getElementById("quad-tbody-hourly");
    if (tBodyH) {
      let sumPct = 0;
      tBodyH.innerHTML = hours.map((h, i) => {
        const cnt = hourlyCounts[i];
        const pctVal = totalEvents ? (cnt / totalEvents) * 100 : 0;
        sumPct += pctVal;
        const isPeak = (i === peakHourIdx && peakHourVal > 0);
        return `<tr style="${isPeak ? 'background:rgba(244,63,94,0.12);font-weight:700;' : ''}">
          <td>${h}</td><td style="text-align:right;">${cnt.toLocaleString()}</td><td style="text-align:right;color:${isPeak ? '#fb7185' : '#38bdf8'};">${pctVal.toFixed(1)}%</td>
        </tr>`;
      }).join("") + `<tr style="border-top:1px solid rgba(255,255,255,0.1);color:#64748b;"><td colspan="2">Total</td><td style="text-align:right;">${sumPct.toFixed(1)}%</td></tr>`;
    }

    const ctxH = document.getElementById("hourly-chart")?.getContext("2d");
    if (ctxH) {
      if (chartHourlyInstance) chartHourlyInstance.destroy();
      const bgColors = hourlyCounts.map((_, i) => (i === peakHourIdx && peakHourVal > 0) ? "#f43f5e" : "#14b8a6");
      chartHourlyInstance = new Chart(ctxH, {
        type: "bar",
        data: {
          labels: hours,
          datasets: [{
            data: hourlyCounts,
            backgroundColor: bgColors,
            borderRadius: { topLeft: 4, topRight: 4 },
            borderSkipped: false
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#64748b", font: { size: 9 }, maxRotation: 0 }, grid: { display: false } },
            y: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { color: "rgba(255,255,255,0.04)" } }
          }
        }
      });
    }

    // --- QUADRANT 3: Call Type Distribution ---
    const typeCounts = { "Incoming": 0, "Outgoing": 0, "SMS-In": 0, "SMS-Out": 0, "Roaming": 0 };
    records.forEach(r => {
      const ct = (r.call_type || "").toUpperCase();
      if (ct.includes("ROAM")) typeCounts["Roaming"]++;
      else if (ct.includes("SMS") && ct.includes("IN")) typeCounts["SMS-In"]++;
      else if (ct.includes("SMS")) typeCounts["SMS-Out"]++;
      else if (ct.includes("IN")) typeCounts["Incoming"]++;
      else typeCounts["Outgoing"]++;
    });

    const tBodyCt = document.getElementById("quad-tbody-calltype");
    if (tBodyCt) {
      tBodyCt.innerHTML = Object.entries(typeCounts).map(([type, cnt]) => {
        const pct = totalEvents ? ((cnt / totalEvents) * 100).toFixed(1) : "0.0";
        return `<tr><td>${type}</td><td style="text-align:right;"><b>${cnt.toLocaleString()}</b></td><td style="text-align:right;color:#38bdf8;">${pct}%</td></tr>`;
      }).join("");
    }

    const ctxCt = document.getElementById("calltype-chart")?.getContext("2d");
    if (ctxCt) {
      if (chartCallTypeInstance) chartCallTypeInstance.destroy();
      chartCallTypeInstance = new Chart(ctxCt, {
        type: "doughnut",
        data: {
          labels: Object.keys(typeCounts),
          datasets: [{
            data: Object.values(typeCounts),
            backgroundColor: ["#3b82f6", "#14b8a6", "#f59e0b", "#a855f7", "#f43f5e"],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "62%",
          plugins: { legend: { position: "right", labels: { color: "#94a3b8", font: { size: 11 }, boxWidth: 12 } } }
        }
      });
    }

    // --- QUADRANT 4: Call Duration Distribution ---
    const durBins = { "0s (Missed/SMS)": 0, "1-30s": 0, "31-60s": 0, "1-5m": 0, ">5m": 0 };
    records.forEach(r => {
      const d = r.duration_sec || 0;
      if (d === 0) durBins["0s (Missed/SMS)"]++;
      else if (d <= 30) durBins["1-30s"]++;
      else if (d <= 60) durBins["31-60s"]++;
      else if (d <= 300) durBins["1-5m"]++;
      else durBins[">5m"]++;
    });

    const tBodyDur = document.getElementById("quad-tbody-duration");
    if (tBodyDur) {
      tBodyDur.innerHTML = Object.entries(durBins).map(([range, cnt]) => {
        const pct = totalEvents ? ((cnt / totalEvents) * 100).toFixed(1) : "0.0";
        return `<tr><td>${range}</td><td style="text-align:right;"><b>${cnt.toLocaleString()}</b></td><td style="text-align:right;color:#38bdf8;">${pct}%</td></tr>`;
      }).join("");
    }

    const ctxDur = document.getElementById("duration-chart")?.getContext("2d");
    if (ctxDur) {
      if (chartDurationInstance) chartDurationInstance.destroy();
      chartDurationInstance = new Chart(ctxDur, {
        type: "bar",
        data: {
          labels: Object.keys(durBins),
          datasets: [{
            data: Object.values(durBins),
            backgroundColor: ["#f43f5e", "#f59e0b", "#3b82f6", "#14b8a6", "#a855f7"],
            borderRadius: { topLeft: 4, topRight: 4 }
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#64748b", font: { size: 10 } }, grid: { display: false } },
            y: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { color: "rgba(255,255,255,0.04)" } }
          }
        }
      });
    }

  } catch (err) {
    console.error("Error loading graph analytics:", err);
  }
}

function exportQuadCSV(type) {
  const table = document.getElementById(`quad-tbody-${type}`)?.closest("table");
  if (!table) return;
  let csv = [];
  for (let row of table.rows) {
    let cols = [];
    for (let cell of row.cells) cols.push(`"${cell.innerText.replace(/"/g, '""')}"`);
    csv.push(cols.join(","));
  }
  const blob = new Blob([csv.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Graph_Analytics_${type}_${currentCaseId}.csv`;
  a.click();
}

function exportQuadImage(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const url = canvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.href = url;
  a.download = `Graph_Widget_${canvasId}_${currentCaseId}.png`;
  a.click();
}

function printQuad() {
  window.print();
}

function toggleFullscreenQuad(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;
  if (!document.fullscreenElement) {
    card.requestFullscreen?.().catch(() => {});
  } else {
    document.exitFullscreen?.().catch(() => {});
  }
}

function downloadAllGraphData() {
  exportQuadCSV("timeline");
  exportQuadCSV("hourly");
}

// ----------------- 7 POLICE GIS MAP MODES -----------------
async function switchMapLayerMode(mode) {
  activeMapMode = mode;
  document.querySelectorAll(".map-pill-btn").forEach(btn => {
    btn.classList.toggle("active", btn.id === `btn-map-mode-${mode}`);
  });

  if (!leafletMap || !currentCaseId) return;
  leafletLayerGroup.clearLayers();

  const num = document.getElementById("map-suspect-select")?.value || currentSuspectPhone || (cachedAnalytics?.suspects?.[0]?.phone || "");
  const descEl = document.getElementById("map-mode-desc");
  const cntEl = document.getElementById("map-event-count");

  if (mode === "towers") {
    if (descEl) descEl.innerText = "Showing exact cell tower markers and call locations.";
    await renderTowerMap(num);
  } else if (mode === "heatmap") {
    try {
      const res = await fetch(`/api/cases/${currentCaseId}/towers/timeline?number=${encodeURIComponent(num)}`, {
        headers: { "Authorization": `Bearer ${currentToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        const agg = {};
        (data.timeline || []).forEach(pt => {
          const key = `${pt.lat},${pt.lon}`;
          if (!agg[key]) agg[key] = { lat: pt.lat, lon: pt.lon, area: pt.area_name, count: 0 };
          agg[key].count++;
        });
        const points = Object.values(agg);
        const maxCnt = Math.max(...points.map(p => p.count), 1);
        const bounds = [];
        points.forEach(p => {
          const ratio = p.count / maxCnt;
          const color = ratio > 0.7 ? "#ef4444" : (ratio > 0.4 ? "#f97316" : "#eab308");
          const c = L.circle([p.lat, p.lon], {
            radius: 350 + ratio * 1200,
            color: color,
            fillColor: color,
            fillOpacity: 0.42,
            weight: 1
          }).addTo(leafletLayerGroup);
          c.bindPopup(`<b>Density Hotspot: ${p.area}</b><br/>Tower Hits: ${p.count}`);
          bounds.push([p.lat, p.lon]);
        });
        if (bounds.length) leafletMap.fitBounds(bounds, { padding: [30, 30] });
        if (descEl) descEl.innerText = "Density Heatmap: Concentric thermal zones scaled by communication frequency.";
        if (cntEl) cntEl.innerText = `Hotspots: ${points.length}`;
      }
    } catch (e) {}
  } else if (mode === "trajectory") {
    if (descEl) descEl.innerText = "Chronological route trajectory with animated timeline playback.";
    await renderTowerMap(num);
    const scrubber = document.getElementById("trajectory-scrubber-bar");
    if (scrubber) scrubber.scrollIntoView({ behavior: "smooth" });
  } else if (mode === "daynight") {
    try {
      const res = await fetch(`/api/cases/${currentCaseId}/towers/timeline?number=${encodeURIComponent(num)}`, {
        headers: { "Authorization": `Bearer ${currentToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        const bounds = [];
        let dayC = 0, nightC = 0;
        (data.timeline || []).forEach(pt => {
          const hour = pt.time ? parseInt((pt.time.split("T")[1] || pt.time.split(" ")[1] || "12").split(":")[0], 10) : 12;
          const isNight = (hour >= 20 || hour < 8);
          if (isNight) nightC++; else dayC++;
          const color = isNight ? "#818cf8" : "#f59e0b";
          const marker = L.circleMarker([pt.lat, pt.lon], {
            radius: isNight ? 9 : 7,
            color: color,
            fillColor: color,
            fillOpacity: 0.85,
            weight: 2
          }).addTo(leafletLayerGroup);
          marker.bindPopup(`<b>${isNight ? 'Night Stay / Hideout (20-08h)' : 'Daytime Base (08-20h)'}</b><br/>Area: ${pt.area_name}<br/>Time: ${pt.time}<br/>Type: ${pt.call_type}`);
          bounds.push([pt.lat, pt.lon]);
        });
        if (bounds.length) leafletMap.fitBounds(bounds, { padding: [30, 30] });
        if (descEl) descEl.innerText = `Day/Night Clusters: Amber = Daytime (${dayC}) · Indigo = Night Hideout (${nightC}).`;
        if (cntEl) cntEl.innerText = `Day: ${dayC} | Night: ${nightC}`;
      }
    } catch (e) {}
  } else if (mode === "sectors") {
    try {
      const res = await fetch(`/api/cases/${currentCaseId}/towers/sectors?suspect=${encodeURIComponent(num)}`, {
        headers: { "Authorization": `Bearer ${currentToken}` }
      });
      if (res.ok) {
        const sectors = await res.json();
        const bounds = [];
        sectors.forEach(sec => {
          const poly = L.polygon(sec.polygon, {
            color: "#38bdf8",
            fillColor: "#0284c7",
            fillOpacity: 0.28,
            weight: 1.5
          }).addTo(leafletLayerGroup);
          poly.bindPopup(`<b>Sector Antenna Cone</b><br/>Tower: ${sec.tower_name}<br/>Cell ID: ${sec.cell_id}<br/>Azimuth: ${sec.azimuth}&deg;<br/>Beamwidth: ${sec.beamwidth}&deg;`);
          if (sec.polygon && sec.polygon[0]) bounds.push(sec.polygon[0]);
        });
        if (bounds.length) leafletMap.fitBounds(bounds, { padding: [35, 35] });
        if (descEl) descEl.innerText = `Sector Azimuth Cones: Showing directional 120-degree BTS radio coverage beams (${sectors.length} sectors).`;
        if (cntEl) cntEl.innerText = `Rendered ${sectors.length} Sector Cones`;
      }
    } catch (e) {}
  } else if (mode === "meetings") {
    try {
      const suspects = cachedAnalytics?.suspects || [];
      if (suspects.length >= 2) {
        const res = await fetch(`/api/cases/${currentCaseId}/meetings?num1=${encodeURIComponent(suspects[0].phone)}&num2=${encodeURIComponent(suspects[1].phone)}&window_mins=30`, {
          headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (res.ok) {
          const meetings = await res.json();
          const bounds = [];
          meetings.forEach(m => {
            const circle = L.circle([m.lat, m.lon], {
              radius: 550,
              color: "#ef4444",
              fillColor: "#ef4444",
              fillOpacity: 0.38,
              weight: 2
            }).addTo(leafletLayerGroup);
            circle.bindPopup(`<b>Co-Location Rendezvous</b><br/>Tower: ${m.area_name}<br/>Time: ${m.approx_time}<br/>${suspects[0].phone}: ${m.suspect1_call_type}<br/>${suspects[1].phone}: ${m.suspect2_call_type}`);
            bounds.push([m.lat, m.lon]);
          });
          if (bounds.length) leafletMap.fitBounds(bounds, { padding: [35, 35] });
          if (descEl) descEl.innerText = `Co-Location Meetings: Found ${meetings.length} spatial-temporal overlaps (±30 min window).`;
          if (cntEl) cntEl.innerText = `Meetings: ${meetings.length}`;
        }
      } else {
        if (descEl) descEl.innerText = "Co-Location requires at least 2 active suspect targets in case CDRs.";
      }
    } catch (e) {}
  } else if (mode === "velocity") {
    try {
      const res = await fetch(`/api/cases/${currentCaseId}/velocity-anomalies?suspect=${encodeURIComponent(num)}`, {
        headers: { "Authorization": `Bearer ${currentToken}` }
      });
      if (res.ok) {
        const anomalies = await res.json();
        const tRes = await fetch(`/api/cases/${currentCaseId}/towers/timeline?number=${encodeURIComponent(num)}`, {
          headers: { "Authorization": `Bearer ${currentToken}` }
        });
        const tData = tRes.ok ? await tRes.json() : { timeline: [] };
        const coordMap = {};
        (tData.timeline || []).forEach(pt => { coordMap[pt.cell_id] = [pt.lat, pt.lon]; });

        const bounds = [];
        anomalies.forEach(a => {
          const p1 = coordMap[a.from_cell_id];
          const p2 = coordMap[a.to_cell_id];
          if (p1 && p2) {
            const line = L.polyline([p1, p2], { color: "#f43f5e", weight: 3, dashArray: "6 6" }).addTo(leafletLayerGroup);
            line.bindPopup(`<b>Impossible Travel Alert (${a.risk_level})</b><br/>${a.from_tower} &rarr; ${a.to_tower}<br/>Distance: ${a.distance_km} km in ${a.time_elapsed_min} min<br/>Calculated Speed: <b>${a.calculated_speed_kmh} km/h</b>`);
            L.circleMarker(p1, { radius: 6, color: "#f43f5e", fillOpacity: 0.9 }).addTo(leafletLayerGroup);
            L.circleMarker(p2, { radius: 6, color: "#f43f5e", fillOpacity: 0.9 }).addTo(leafletLayerGroup);
            bounds.push(p1, p2);
          }
        });
        if (bounds.length) leafletMap.fitBounds(bounds, { padding: [35, 35] });
        if (descEl) descEl.innerText = anomalies.length
          ? `Impossible Travel Alerts: Detected ${anomalies.length} anomalous tower hops (>120 km/h — possible SIM cloning).`
          : "No impossible travel speed anomalies (>120 km/h) detected for this target.";
        if (cntEl) cntEl.innerText = `Velocity Alerts: ${anomalies.length}`;
      }
    } catch (e) {}
  }
}

function downloadMapKML() {
  if (!currentCaseId) return;
  const phone = currentSuspectPhone || "";
  window.open(`/api/cases/${currentCaseId}/report?format=kml&suspect=${encodeURIComponent(phone)}`, "_blank");
}

function downloadMapKMZ() {
  if (!currentCaseId) return;
  const phone = currentSuspectPhone || "";
  window.open(`/api/cases/${currentCaseId}/report?format=kmz&suspect=${encodeURIComponent(phone)}`, "_blank");
}

function toggleSidebarSuiteMode() {
  toggleSidebarContext();
}
