// ─── State ───────────────────────────────────────────────────────────────────
const state = {
  status: null,
  report: "",
  setupFeedback: {},
  actionFeedback: {},
  evidenceKeys: new Set()
};

// ─── Terminology Constants ────────────────────────────────────────────────────
const TERMINOLOGY = {
  stateLabels: {
    blocked: "SETUP REQUIRED",
    needs_manual_action: "ACTION NEEDED",
    disconnected: "NOT CONNECTED",
    partial: "PARTIAL",
    connected: "CONNECTED",
    live: "LIVE",
    ready_for_review: "READY",
    ready_for_write_tools: "READY",
    stopped: "NOT RUNNING",
    running: "RUNNING",
    external: "RUNNING",
    unavailable: "NOT CONNECTED",
    checking: "CHECKING",
  }
};

// ─── Setup Doctor Layers ──────────────────────────────────────────────────────
const setupLayers = [
  { group: "environment",  title: "Environment",                priority: "required" },
  { group: "daemon",       title: "FL Studio Bridge Service",   priority: "required" },
  { group: "midi",         title: "MIDI Loopback Ports",        priority: "required" },
  { group: "controller",  title: "FL Studio Controller",        priority: "required" },
  { group: "mcp_sse",     title: "AI Client Server",            priority: "optional" },
  { group: "mcp_apply",   title: "Piano Roll Apply",            priority: "optional" }
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Safe value for normal UI – never shows [object Object] */
function safeString(value) {
  if (value == null || value === "") return "N/A";
  if (typeof value === "object") return "Unavailable";
  return String(value);
}

/** Safe value for Advanced/Debug/Logs contexts – pretty-prints objects */
function safeDebugString(value) {
  if (value == null || value === "") return "N/A";
  if (typeof value === "object") {
    try { return JSON.stringify(value, null, 2); } catch { return "Unavailable"; }
  }
  return String(value);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  const type = response.headers.get("content-type") || "";
  return type.includes("application/json") ? response.json() : response.text();
}

let loadingInterval = null;

async function refresh() {
  const loadingOverlay = document.getElementById("loading-overlay");
  const loadingText = document.getElementById("loading-text");

  if (loadingOverlay) {
    loadingOverlay.style.display = "flex";
    let isPerforming = true;
    if (loadingText) loadingText.textContent = "performing tests ...";
    if (loadingInterval) clearInterval(loadingInterval);
    loadingInterval = setInterval(() => {
      isPerforming = !isPerforming;
      if (loadingText) loadingText.textContent = isPerforming ? "performing tests ..." : "retrieving results ...";
    }, 1500);
  }

  try {
    state.status = await api("/api/refresh", { method: "POST", body: "{}" });
    render();
  } catch (error) {
    const refreshTime = document.getElementById("refresh-time");
    if (refreshTime) refreshTime.textContent = "Error";
    const bridgePill = document.getElementById("bridge-pill");
    if (bridgePill) {
      bridgePill.textContent = "Error";
      bridgePill.className = "pill pill-offline";
    }
  } finally {
    if (loadingOverlay) loadingOverlay.style.display = "none";
    if (loadingInterval) { clearInterval(loadingInterval); loadingInterval = null; }
  }
}

// ─── Status data accessor (supports both status_report and dashboard keys) ───
function getStatusReport() {
  if (!state.status) return null;
  return state.status.status_report || state.status.dashboard || null;
}

// ─── Render coordinator ───────────────────────────────────────────────────────
function render() {
  if (!state.status) return;

  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const live = bridge.state === "live";

  // Topbar readiness pill
  const rawState = state.status.readiness?.state || "unavailable";
  let stateLabel = live ? "LIVE" : (TERMINOLOGY.stateLabels[rawState] || rawState.replaceAll("_", " ").toUpperCase());

  const bridgePill = document.getElementById("bridge-pill");
  if (bridgePill) {
    bridgePill.textContent = stateLabel;
    bridgePill.className = (live || stateLabel === "READY" || stateLabel === "CONNECTED")
      ? "pill pill-live" : "pill pill-offline";
  }

  const versionPill = document.getElementById("version-pill");
  if (versionPill && state.status.version) {
    const v = state.status.version.startsWith("v") ? state.status.version : "v" + state.status.version;
    versionPill.textContent = v.toUpperCase();
  }

  const refreshTime = document.getElementById("refresh-time");
  if (refreshTime) refreshTime.textContent = new Date().toLocaleTimeString();

  renderOverview();
  renderConnectionCheck();
  renderSetup();
  renderRuntime();
  renderClients();
  renderProjectData();
  renderLogsHistory();
  renderPorts();
  renderConnection();

  if (hasLiveFlData() && !window.successOverlayShown) {
    const overlay = document.getElementById("success-overlay");
    if (overlay) {
      overlay.style.display = "flex";
      window.successOverlayShown = true;
    }
  }
}

// ─── Setup Overview ───────────────────────────────────────────────────────────
function renderOverview() {
  const data = getStatusReport();
  renderOverviewCards(data);
}

function renderOverviewCards(data) {
  const cardsEl = document.getElementById("overview-status-cards");
  if (!cardsEl) return;

  const bridge = data?.bridge || {};
  const safety = data?.safety || {};
  const daemonProc = state.status?.processes?.daemon || {};
  const sseProc = state.status?.processes?.sse || {};
  const snippets = state.status?.snippets || {};

  const daemonRunning = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const sseRunning = isManagedProcessRunning(sseProc);
  const live = bridge.state === "live";
  const readOnly = safety.read_only !== false;

  cardsEl.innerHTML = "";

  // Card 1: FL Studio Connection
  const bridgeStatus = live ? "connected" : (bridge.state === "unavailable" || !bridge.state ? "not_connected" : bridge.state);
  const bridgeLabel = live ? "Connected" : "Not Connected";
  const bridgeDesc = live
    ? `FL Studio is responding. ${safeString(bridge.fl_version || data?.project?.fl_version) !== "N/A" ? "Version: " + safeString(bridge.fl_version || data?.project?.fl_version) : "Bridge heartbeat is live."}`
    : "FL Studio is not sending controller data yet. Run a connection check to diagnose.";
  cardsEl.appendChild(makeStatusCard({
    id: "card-fl-connection",
    icon: "◈",
    title: "FL Studio Connection",
    status: bridgeStatus,
    statusLabel: bridgeLabel,
    description: bridgeDesc,
    actionLabel: "Run Connection Check",
    actionTarget: "connection_check",
    live
  }));

  // Card 2: Background Service
  const svcStatus = daemonRunning ? "running" : "stopped";
  const svcLabel = daemonRunning ? "Running" : "Not Running";
  const svcDesc = daemonRunning
    ? (daemonProc.state === "external" ? "FL Studio Bridge Service is reachable (managed externally)." : "FL Studio Bridge Service is running under this Control Center.")
    : "The background service is not running. Start it to enable FL Studio communication.";
  cardsEl.appendChild(makeStatusCard({
    id: "card-background-service",
    icon: "▶",
    title: "Background Service",
    status: svcStatus,
    statusLabel: svcLabel,
    description: svcDesc,
    actionLabel: daemonRunning ? "View Services" : "Start Service",
    actionTarget: "runtime",
    actionDirect: !daemonRunning ? () => processAction("/api/process/daemon/start") : null,
    live: daemonRunning
  }));

  // Card 3: AI Client Setup
  const aiStatus = sseRunning ? "running" : "not_required";
  const aiLabel = sseRunning ? "Running" : "Optional";
  const aiDesc = sseRunning
    ? `AI Client Server is running. Copy the SSE URL to connect your AI client.`
    : "The AI Client Server is optional. Start it only if your AI client uses SSE/HTTP (e.g. ChatGPT).";
  cardsEl.appendChild(makeStatusCard({
    id: "card-ai-client",
    icon: "◇",
    title: "AI Client Setup",
    status: aiStatus,
    statusLabel: aiLabel,
    description: aiDesc,
    actionLabel: "Open AI Clients",
    actionTarget: "clients",
    live: sseRunning
  }));

  // Card 4: Safety Mode
  const safetyStatus = readOnly ? "readonly" : "write_enabled";
  const safetyLabel = readOnly ? "Read-only" : "Write Enabled";
  const safetyDesc = readOnly
    ? "Read-only mode is active. No FL Studio project changes will be made."
    : "Write-capable mode is active. Safe Apply uses a proposal-first workflow.";
  cardsEl.appendChild(makeStatusCard({
    id: "card-safety-mode",
    icon: "◆",
    title: "Safety Mode",
    status: safetyStatus,
    statusLabel: safetyLabel,
    description: safetyDesc,
    actionLabel: "View Safety Details",
    actionTarget: "overview",
    actionHash: "safety",
    live: true
  }));
}

function makeStatusCard({ id, icon, title, status, statusLabel, description, actionLabel, actionTarget, actionDirect, actionHash, live }) {
  const card = document.createElement("article");
  card.className = "status-card";
  card.id = id || "";

  // Status indicator dot
  const indicator = document.createElement("div");
  indicator.className = `status-card-indicator ${live ? "live" : (status === "not_required" || status === "readonly" ? "neutral" : "offline")}`;

  const body = document.createElement("div");
  body.className = "status-card-body";

  const header = document.createElement("div");
  header.className = "status-card-header";

  const titleEl = document.createElement("span");
  titleEl.className = "status-card-icon";
  titleEl.ariaHidden = "true";
  titleEl.textContent = icon;

  const h3 = document.createElement("h3");
  h3.className = "status-card-title";
  h3.textContent = title;

  const badge = document.createElement("span");
  badge.className = `status-card-badge ${live ? "badge-ok" : (status === "not_required" || status === "readonly" ? "badge-neutral" : "badge-warn")}`;
  badge.textContent = statusLabel;

  header.append(titleEl, h3, badge);

  const desc = document.createElement("p");
  desc.className = "status-card-desc";
  desc.textContent = description;

  const footer = document.createElement("div");
  footer.className = "status-card-footer";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "ghost-button";
  btn.textContent = actionLabel;
  btn.addEventListener("click", () => {
    if (actionDirect) { actionDirect(); }
    else { selectPanel(actionTarget); }
  });
  footer.appendChild(btn);

  body.append(header, desc, footer);
  card.append(indicator, body);
  return card;
}

// ─── Connection Check ─────────────────────────────────────────────────────────
function renderConnectionCheck() {
  const container = document.getElementById("connection-check-grid");
  if (!container) return;
  container.innerHTML = "";

  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const safety = data?.safety || {};
  const daemonProc = state.status?.processes?.daemon || {};
  const sseProc = state.status?.processes?.sse || {};
  const sseProbe = state.status?.mcp?.sse_probe || state.status?.processes?.sse?.probe || {};

  const live = bridge.state === "live";
  const daemonRunning = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const sseRunning = isManagedProcessRunning(sseProc);
  const readOnly = safety.read_only !== false;

  const rows = [
    {
      label: "FL Studio Bridge",
      status: live ? "Connected" : "Not Connected",
      ok: live,
      detail: live ? "Bridge heartbeat is live." : (bridge.error || "No fresh controller heartbeat received."),
    },
    {
      label: "Background Service",
      status: daemonRunning ? "Running" : "Not Running",
      ok: daemonRunning,
      detail: daemonRunning
        ? (daemonProc.state === "external" ? "Running (external)." : "Running under this Control Center.")
        : "Start the FL Studio Bridge Service to enable communication.",
    },
    {
      label: "AI Client Server",
      status: sseRunning ? "Running" : "Not Started",
      ok: sseRunning,
      neutral: !sseRunning,
      detail: sseRunning
        ? (sseProbe.message || "SSE server is running.")
        : "Optional — start only if your AI client uses SSE/HTTP.",
    },
    {
      label: "Basic Read Test",
      status: live ? "Passed" : "Not Available",
      ok: live,
      detail: live
        ? "FL Studio project data is readable."
        : "Connect FL Studio to run a read test.",
    },
    {
      label: "Safety Mode",
      status: readOnly ? "Read-only Active" : "Write Enabled",
      ok: true,
      neutral: true,
      detail: readOnly ? "No project changes will be made." : "Write mode — changes require Safe Apply.",
    },
    {
      label: "Last Check",
      status: new Date().toLocaleTimeString(),
      ok: true,
      neutral: true,
      detail: "Click Refresh to run all checks again.",
    },
  ];

  // Summary card
  const summaryCard = document.createElement("article");
  summaryCard.className = "panel connection-check-summary";

  const summaryHeading = document.createElement("div");
  summaryHeading.className = "panel-heading";
  const summaryH2 = document.createElement("h2");
  summaryH2.textContent = "Connection Status";
  summaryHeading.appendChild(summaryH2);

  const summaryList = document.createElement("ul");
  summaryList.className = "connection-check-list";
  for (const row of rows) {
    const li = document.createElement("li");
    li.className = "connection-check-row";

    const dot = document.createElement("span");
    dot.className = `check-dot ${row.ok && !row.neutral ? "ok" : (row.neutral ? "neutral" : "warn")}`;

    const labelEl = document.createElement("strong");
    labelEl.className = "check-label";
    labelEl.textContent = row.label;

    const statusEl = document.createElement("span");
    statusEl.className = "check-status";
    statusEl.textContent = row.status;

    const detailEl = document.createElement("span");
    detailEl.className = "check-detail";
    detailEl.textContent = row.detail;

    li.append(dot, labelEl, statusEl, detailEl);
    summaryList.appendChild(li);
  }

  // Next step
  const nextStep = _recommendedNextStep();
  const nextStepEl = document.createElement("div");
  nextStepEl.className = "check-next-step";
  const nextStepLabel = document.createElement("span");
  nextStepLabel.className = "check-next-step-label";
  nextStepLabel.textContent = "Recommended next step:";
  const nextStepText = document.createElement("p");
  nextStepText.textContent = nextStep;
  nextStepEl.append(nextStepLabel, nextStepText);

  summaryCard.append(summaryHeading, summaryList, nextStepEl);
  container.appendChild(summaryCard);

  // Action buttons
  const actionsCard = document.createElement("article");
  actionsCard.className = "panel";
  const actionsHeading = document.createElement("div");
  actionsHeading.className = "panel-heading";
  const actionsH2 = document.createElement("h2");
  actionsH2.textContent = "Actions";
  actionsHeading.appendChild(actionsH2);

  const btnRow = document.createElement("div");
  btnRow.className = "check-action-row";

  const actions = [
    { text: "Refresh / Run Check Again", onclick: () => refresh() },
    { text: "Open Setup Doctor", onclick: () => selectPanel("setup") },
    { text: "Open Services", onclick: () => selectPanel("runtime") },
    { text: "Open AI Clients", onclick: () => selectPanel("clients") },
    { text: "Copy Support Report", onclick: async () => {
        await loadReport();
        await navigator.clipboard.writeText(state.report);
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy Support Report"; }, 1400);
      }
    },
  ];

  for (const action of actions) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost-button";
    btn.textContent = action.text;
    btn.addEventListener("click", action.onclick);
    btnRow.appendChild(btn);
  }

  actionsCard.append(actionsHeading, btnRow);
  container.appendChild(actionsCard);
}

function _recommendedNextStep() {
  if (!state.status) return "Run a check to see the current status.";
  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const daemonProc = state.status?.processes?.daemon || {};
  const live = bridge.state === "live";
  const daemonRunning = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";

  if (!daemonRunning) return "Start the FL Studio Bridge Service from the Services screen.";
  if (!live) return "FL Studio Bridge Service is running, but FL Studio is not sending controller data yet. Open FL Studio, load fls-pilot in the controller settings, and check the MIDI loopback ports.";
  return "FL Studio is connected. You can now open AI Clients to configure your MCP client.";
}

// ─── Setup Doctor ─────────────────────────────────────────────────────────────
function renderSetup() {
  const container = document.getElementById("setup-steps");
  if (!container) return;
  container.innerHTML = "";

  // Root-cause summary banner
  const banner = _buildSetupDoctorBanner();
  if (banner) container.appendChild(banner);

  renderGuidedTroubleshooting(container);

  // Required group header
  const requiredHeader = document.createElement("div");
  requiredHeader.className = "setup-group-header";
  requiredHeader.textContent = "Required";
  container.appendChild(requiredHeader);

  for (const item of setupLayers.filter(l => l.priority === "required")) {
    container.appendChild(card(item.title, groupStatus(item.group), groupText(item.group)));
  }

  // Optional group header
  const optionalHeader = document.createElement("div");
  optionalHeader.className = "setup-group-header setup-group-optional";
  optionalHeader.textContent = "Optional";
  container.appendChild(optionalHeader);

  for (const item of setupLayers.filter(l => l.priority === "optional")) {
    container.appendChild(card(item.title, groupStatus(item.group), groupText(item.group)));
  }
}

function _buildSetupDoctorBanner() {
  if (!state.status) return null;
  const daemonProc = state.status?.processes?.daemon || {};
  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const daemonRunning = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const live = bridge.state === "live";

  let message = null;
  if (daemonRunning && !live) {
    message = "FL Studio Bridge Service is running, but FL Studio is not sending controller data yet. Check the FL Studio controller settings and MIDI loopback ports.";
  } else if (!daemonRunning) {
    message = "The Background Service is not running. Start the FL Studio Bridge Service to begin setup.";
  }

  if (!message) return null;

  const banner = document.createElement("div");
  banner.className = "setup-summary-banner";
  const icon = document.createElement("span");
  icon.className = "banner-icon";
  icon.ariaHidden = "true";
  icon.textContent = "ℹ";
  const text = document.createElement("p");
  text.textContent = message;
  banner.append(icon, text);
  return banner;
}

function renderGuidedTroubleshooting(container) {
  const guidance = state.status?.setup_guidance || [];
  for (const item of guidance) {
    const buttons = [];
    if (item.checkpoint) {
      const feedback = state.setupFeedback[item.checkpoint];
      const isChecking = feedback?.state === "checking";
      buttons.push({
        text: isChecking ? "Checking..." : (item.action_label || "I did this"),
        disabled: isChecking,
        onclick: () => confirmStep({ key: item.checkpoint, groups: item.groups || [] })
      });
    } else if (item.action_path) {
      buttons.push({
        text: item.action_label || "Run",
        disabled: false,
        onclick: () => runGuidanceAction(item.action_path)
      });
    }
    const node = card(item.title, item.status, item.text, buttons.length ? buttons : null);
    if (item.checkpoint) {
      const confirmed = state.status.checkpoints?.[item.checkpoint];
      const feedback = state.setupFeedback[item.checkpoint] || (
        confirmed ? { state: "attention", text: "Confirmation saved. The related automated check still needs attention." } : null
      );
      appendSetupFeedback(node, feedback);
    }
    container.appendChild(node);
  }
}

function groupStatus(group) {
  const findings = state.status?.groups?.[group] || [];
  if (group === "daemon") {
    const dynamicStatus = daemonRuntimeStatus(findings);
    if (dynamicStatus) return dynamicStatus;
  }
  if (group === "mcp_sse") {
    const dynamicStatus = mcpSseStatus(findings);
    if (dynamicStatus) return dynamicStatus;
  }
  const failed = findings.find(item => item.status === "failed");
  if (failed) return failed.severity === "blocker" ? "Setup Required" : "Action Needed";
  const manual = findings.find(item => item.status === "manual_check" || item.status === "probe_needed");
  if (manual) return "Manual Check";
  return findings.length ? "OK" : "Not Required";
}

function groupNeedsAction(group) {
  const status = groupStatus(group).toLowerCase();
  return status !== "ok" && status !== "not required";
}

function isGroupOk(group) {
  return groupStatus(group).toLowerCase() === "ok";
}

function groupText(group) {
  const findings = state.status?.groups?.[group] || [];
  if (group === "daemon") {
    const dynamicText = daemonRuntimeText(findings);
    if (dynamicText) return dynamicText;
  }
  if (group === "mcp_sse") {
    const dynamicText = mcpSseText(findings);
    if (dynamicText) return dynamicText;
  }
  if (!findings.length) return "No finding for this setup layer.";
  return findings.map(item =>
    `${safeString(item.component)}: ${safeString(item.evidence)}${item.remediation ? ` Fix: ${safeString(item.remediation)}` : ""}`
  ).join("\n");
}

function hasLiveFlData() {
  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const project = data?.project || {};
  return bridge.state === "live" && project.state === "live";
}

function daemonRuntimeStatus(findings = []) {
  const daemonProc = state.status?.processes?.daemon || {};
  const health = daemonProc.health || {};
  const running = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const problemFinding = findings.some(item => item.status === "failed" || item.status === "manual_check" || item.status === "probe_needed");
  if (problemFinding) return null;
  if (!running) return "Not Running";
  if (health.reachable === false) return "Action Needed";
  return null;
}

function daemonRuntimeText(findings = []) {
  const daemonProc = state.status?.processes?.daemon || {};
  const health = daemonProc.health || {};
  const running = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const problemFinding = findings.some(item => item.status === "failed" || item.status === "manual_check" || item.status === "probe_needed");
  if (problemFinding) return null;
  if (!running) return "FL Studio Bridge Service is not running. Start the service, then re-check setup.";
  if (health.reachable === false) return "The service process is running, but the TCP health check is not reachable.";
  return null;
}

function mcpSseProbe() {
  return state.status?.mcp?.sse_probe || state.status?.processes?.sse?.probe || null;
}

function mcpSseStatus(findings = []) {
  const probe = mcpSseProbe();
  if (!probe) return null;
  const sseProc = state.status?.processes?.sse || {};
  const running = isManagedProcessRunning(sseProc);
  if (!running && (probe.state === "not_required" || probe.state === "stopped")) {
    return findings.length ? null : "Not Required";
  }
  if (probe.state === "ok") return "OK";
  if (probe.state === "failed") return "Action Needed";
  if (probe.state === "checking") return "Checking";
  if (running) return "Running";
  return null;
}

function mcpSseText(findings = []) {
  const probe = mcpSseProbe();
  if (!probe) return null;
  if (findings.length && !state.status?.processes?.sse?.running && (probe.state === "not_required" || probe.state === "stopped")) {
    return null;
  }
  const parts = [safeString(probe.message) !== "N/A" ? probe.message : "AI Client Server status is unavailable."];
  if (probe.url) parts.push(`URL: ${safeString(probe.url)}`);
  if (probe.checked_at) parts.push(`Last test: ${new Date(probe.checked_at).toLocaleTimeString()}`);
  return parts.join("\n");
}

function setupGroupSnapshot(groups) {
  const out = {};
  for (const group of groups) out[group] = groupStatus(group);
  return out;
}

function groupStatusRank(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "ok") return 4;
  if (normalized === "not required") return 3;
  if (normalized === "manual check") return 2;
  if (normalized === "action needed") return 1;
  if (normalized === "setup required") return 0;
  return 0;
}

function evaluateSetupFeedback(step, before) {
  const after = setupGroupSnapshot(step.groups);
  const groupsOk = step.groups.every(group => isGroupOk(group) || groupStatus(group).toLowerCase() === "not required");
  const improved = step.groups.some(group => groupStatusRank(after[group]) > groupStatusRank(before[group]));
  const stillNeedsAction = step.groups.some(group => groupNeedsAction(group));

  if (groupsOk) return { state: "verified", text: "Verified: the related automated check now passes." };
  if (improved) return { state: "progress", text: "Progress detected. One related check improved; continue with the next setup layer." };
  if (stillNeedsAction) return { state: "attention", text: "Checked again: the expected automated signal is still missing." };
  return { state: "saved", text: "Confirmation saved. No additional automated signal is available for this step." };
}

function appendSetupFeedback(node, feedback) {
  if (!feedback) return;
  const message = document.createElement("div");
  message.className = `setup-feedback ${feedback.state}`;
  message.textContent = feedback.text;
  node.appendChild(message);
}

// ─── Services / Runtime ───────────────────────────────────────────────────────
function processStatus(process) {
  return process?.running ? "running" : (safeString(process?.state) || "stopped");
}

function isManagedProcessRunning(process) {
  return Boolean(process?.running) || process?.state === "running";
}

function isProcessReachable(process) {
  return isManagedProcessRunning(process) || process?.state === "external";
}

function processActionKey(path) {
  if (path.includes("/daemon/")) return "daemon";
  if (path.includes("/sse/")) return "sse";
  return "runtime";
}

function processActionLabel(path) {
  if (path.endsWith("/start")) return "Start";
  if (path.endsWith("/stop")) return "Stop";
  if (path.endsWith("/test")) return "Test";
  return "Action";
}

function processActionFeedback(path, result) {
  const label = processActionLabel(path);
  const parts = [];
  if (result?.message) parts.push(safeString(result.message));
  if (result?.fallback_port) parts.push(`Fallback port: ${safeString(result.fallback_port)}.`);
  if (result?.url) parts.push(`URL: ${safeString(result.url)}`);
  if (result?.probe?.message) parts.push(`Probe: ${safeString(result.probe.message)}`);
  if (!parts.length) parts.push(result?.ok ? `${label} completed.` : `${label} did not complete.`);
  return { state: result?.ok ? "verified" : "attention", text: parts.join("\n") };
}

function renderRuntime() {
  const container = document.getElementById("runtime-status");
  if (!container) return;
  container.innerHTML = "";

  if (!state.status || !state.status.processes || !state.status.ports) return;

  const daemonProc = state.status.processes.daemon || {};
  const daemonPort = state.status.ports.daemon || {};

  const daemonStatus = processStatus(daemonProc);
  const daemonHost = safeString(daemonPort.host);
  const daemonSelectedPort = safeString(daemonPort.selected_port);
  const daemonPreferredPort = safeString(daemonPort.preferred_port);

  let daemonText = `Local connection: ${daemonHost === "N/A" || daemonHost === "Unavailable" ? "127.0.0.1" : daemonHost}:${daemonSelectedPort}`;
  if (daemonPreferredPort !== daemonSelectedPort && daemonSelectedPort !== "N/A") {
    daemonText += ` (preferred: ${daemonPreferredPort})`;
  }
  if (daemonStatus === "external") {
    daemonText += "\n\nExternal daemon is reachable. This Control Center can use it but cannot stop it.";
  }
  const logs = (daemonProc.logs || []).slice(-6);
  daemonText += "\n\nService log:\n" + (logs.length ? logs.join("\n") : "No recent log entries.");

  const daemonCard = card("FL Studio Bridge Service", daemonStatus, daemonText, [
    { text: "Start Service", disabled: isProcessReachable(daemonProc), onclick: () => processAction("/api/process/daemon/start") },
    { text: "Stop Service", disabled: !isManagedProcessRunning(daemonProc), onclick: () => processAction("/api/process/daemon/stop") }
  ]);
  appendSetupFeedback(daemonCard, state.actionFeedback.daemon);

  // Add link buttons to Advanced screens
  const daemonLinks = document.createElement("div");
  daemonLinks.style.cssText = "padding: 0 26px 16px; display: flex; gap: 8px;";
  const logsBtn = document.createElement("button");
  logsBtn.type = "button"; logsBtn.className = "ghost-button"; logsBtn.textContent = "View Logs & History";
  logsBtn.addEventListener("click", () => selectPanel("logs_history"));
  const portsBtn = document.createElement("button");
  portsBtn.type = "button"; portsBtn.className = "ghost-button"; portsBtn.textContent = "View Ports";
  portsBtn.addEventListener("click", () => selectPanel("ports"));
  daemonLinks.append(logsBtn, portsBtn);
  daemonCard.appendChild(daemonLinks);
  container.appendChild(daemonCard);

  const sseProc = state.status.processes.sse || {};
  const ssePort = state.status.ports.sse || {};

  const sseStatus = processStatus(sseProc);
  const sseHost = safeString(ssePort.host);
  const sseSelectedPort = safeString(ssePort.selected_port);
  const ssePreferredPort = safeString(ssePort.preferred_port);

  let sseText = `Local connection: ${sseHost === "N/A" || sseHost === "Unavailable" ? "127.0.0.1" : sseHost}:${sseSelectedPort}`;
  if (ssePreferredPort !== sseSelectedPort && sseSelectedPort !== "N/A") {
    sseText += ` (preferred: ${ssePreferredPort})`;
  }
  const sseLogs = (sseProc.logs || []).slice(-6);
  sseText += "\n\nService log:\n" + (sseLogs.length ? sseLogs.join("\n") : "No recent log entries.");

  const sseCard = card("AI Client Server", sseStatus, sseText, [
    { text: "Start AI Client Server", disabled: isProcessReachable(sseProc), onclick: () => processAction("/api/process/sse/start") },
    { text: "Stop AI Client Server", disabled: !isManagedProcessRunning(sseProc), onclick: () => processAction("/api/process/sse/stop") }
  ]);
  appendSetupFeedback(sseCard, state.actionFeedback.sse);
  container.appendChild(sseCard);

  const ccPort = state.status.ports.control_center || {};
  const footerPortSpan = document.getElementById("footer-cc-port");
  if (footerPortSpan) {
    const ccHost = safeString(ccPort.host);
    const ccSelected = safeString(ccPort.selected_port);
    const ccPreferred = safeString(ccPort.preferred_port);
    footerPortSpan.textContent = `Control Center: ${ccHost}:${ccSelected} (default: ${ccPreferred})`;
  }
}

// ─── Connection card (sidebar) ─────────────────────────────────────────────────
function renderConnection() {
  const data = getStatusReport();
  if (!data) return;
  const bridge = data.bridge || {};
  const project = data.project || {};
  const live = bridge.state === "live";

  const connCard = document.querySelector(".connection-card");
  if (connCard) connCard.classList.toggle("offline", !live);

  const eyebrow = document.querySelector(".connection-card .eyebrow");
  if (eyebrow) eyebrow.textContent = live ? "Connected To" : "Status";

  const dot = byId("connection-dot");
  if (dot) dot.classList.toggle("live", live);

  text("connected-version", live
    ? (safeString(project.fl_version || bridge.fl_version) !== "N/A" ? safeString(project.fl_version || bridge.fl_version) : "Local connection")
    : "Not reachable");
  text("connected-target", live ? "FL Studio (Local)" : "Disconnected");
}

// ─── AI Clients ───────────────────────────────────────────────────────────────
function renderClients() {
  const container = document.getElementById("client-snippets");
  if (!container) return;
  container.innerHTML = "";
  const snippets = state.status?.snippets;
  if (!snippets) return;

  // ChatGPT
  const chatgptUrl = safeString(snippets.chatgpt?.url);
  container.appendChild(makeAiClientCard({
    id: "ai-chatgpt",
    title: "ChatGPT",
    badge: "SSE / HTTP",
    steps: [
      "Start the AI Client Server from the Services screen.",
      "Open ChatGPT → Settings → Connected Apps → MCP.",
      "Paste the SSE URL below.",
      "Run a connection check."
    ],
    copyLabel: "Copy URL",
    copyValue: chatgptUrl !== "N/A" ? chatgptUrl : snippets.chatgpt?.url,
    fieldLabel: "SSE URL",
    fieldValue: chatgptUrl !== "N/A" ? chatgptUrl : "Start the AI Client Server to get the URL.",
    advancedLabel: "Show advanced config",
    advancedContent: safeDebugString(snippets.chatgpt)
  }));

  // Claude Desktop
  const claudeJson = JSON.stringify(snippets.claude, null, 2);
  container.appendChild(makeAiClientCard({
    id: "ai-claude",
    title: "Claude Desktop",
    badge: "stdio / TCP",
    steps: [
      "Open claude_desktop_config.json (usually in ~/Library/Application Support/Claude/).",
      "Add the JSON snippet below to the file.",
      "Restart Claude Desktop."
    ],
    copyLabel: "Copy config",
    copyValue: claudeJson,
    fieldLabel: "Config JSON",
    fieldValue: claudeJson,
    advancedLabel: null
  }));

  // Cursor
  const cursorJson = JSON.stringify(snippets.cursor, null, 2);
  container.appendChild(makeAiClientCard({
    id: "ai-cursor",
    title: "Cursor",
    badge: "stdio / TCP",
    steps: [
      "Open Cursor Settings → MCP (Cmd+Shift+P → 'MCP').",
      "Add the JSON snippet below.",
      "Restart Cursor."
    ],
    copyLabel: "Copy config",
    copyValue: cursorJson,
    fieldLabel: "Config JSON",
    fieldValue: cursorJson,
    advancedLabel: null
  }));

  // Terminal fallback
  const termDaemon = safeString(snippets.terminal?.daemon);
  const termSse = safeString(snippets.terminal?.sse);
  const termText = `${termDaemon}\n${termSse}`;
  container.appendChild(makeAiClientCard({
    id: "ai-terminal",
    title: "Terminal Fallback",
    badge: "Manual",
    steps: [
      "Run these commands manually in your terminal to start the services."
    ],
    copyLabel: "Copy commands",
    copyValue: termText,
    fieldLabel: "Commands",
    fieldValue: termText,
    advancedLabel: null
  }));
}

function makeAiClientCard({ id, title, badge, steps, copyLabel, copyValue, fieldLabel, fieldValue, advancedLabel, advancedContent }) {
  const node = document.createElement("article");
  node.className = "panel ai-client-card";
  if (id) node.id = id;

  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  const badgeEl = document.createElement("span");
  badgeEl.className = "badge badge-neutral";
  badgeEl.textContent = badge;
  badgeEl.style.marginLeft = "auto";
  heading.append(h2, badgeEl);

  const stepsEl = document.createElement("ol");
  stepsEl.className = "ai-client-steps";
  for (const step of steps) {
    const li = document.createElement("li");
    li.textContent = step;
    stepsEl.appendChild(li);
  }

  const fieldWrap = document.createElement("div");
  fieldWrap.className = "ai-client-field-wrap";
  const fieldLabelEl = document.createElement("label");
  fieldLabelEl.className = "ai-client-field-label";
  fieldLabelEl.textContent = fieldLabel;
  const fieldEl = document.createElement("pre");
  fieldEl.className = "copy-field";
  fieldEl.textContent = safeString(fieldValue) !== "N/A" ? fieldValue : "N/A";

  const btnRow = document.createElement("div");
  btnRow.className = "ai-client-btn-row";
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "ghost-button";
  copyBtn.textContent = copyLabel;
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(String(copyValue || ""));
      copyBtn.textContent = "Copied!";
      copyBtn.classList.add("copied");
      setTimeout(() => { copyBtn.textContent = copyLabel; copyBtn.classList.remove("copied"); }, 1400);
    } catch { copyBtn.textContent = "Copy failed"; }
  });
  btnRow.appendChild(copyBtn);

  fieldWrap.append(fieldLabelEl, fieldEl);

  node.append(heading, stepsEl, fieldWrap, btnRow);

  if (advancedLabel && advancedContent) {
    const details = document.createElement("details");
    details.className = "ai-client-advanced";
    const summary = document.createElement("summary");
    summary.textContent = advancedLabel;
    const advPre = document.createElement("pre");
    advPre.className = "copy-field";
    advPre.textContent = advancedContent;
    details.append(summary, advPre);
    node.appendChild(details);
  }

  return node;
}

// ─── Project Data (Connection Evidence, within Overview) ──────────────────────
function renderProjectData() {
  const disconnectedOverlay = document.getElementById("disconnected-overlay");
  const data = getStatusReport();

  if (!state.status || !data) {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "flex";
    return;
  }

  const bridge = data.bridge || {};
  const live = bridge.state === "live";

  if (!live) {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "flex";
  } else {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "none";
  }

  // Project Snapshot
  const project = data.project || {};
  const resources = data.resources || {};
  text("tempo-value", bpm(project.tempo_bpm));
  text("channel-count", project.channel_count == null ? count(resources.channels) : project.channel_count);

  let mixCount = project.mixer_track_count == null ? count(resources.mixer) : project.mixer_track_count;
  if (typeof mixCount === "number") mixCount = Math.max(0, mixCount - 2);
  text("mixer-count", mixCount);

  let patCount = project.pattern_count == null ? count(resources.patterns) : project.pattern_count;
  if (typeof patCount === "number") patCount = Math.max(1, patCount);
  text("pattern-count", patCount);
  text("playlist-count", project.playlist_track_count == null ? count(resources.playlist) : project.playlist_track_count);

  // Transport
  const transport = data.transport || {};
  let playing = transport.playing;
  if (playing == null) playing = project.playing;
  let recording = transport.recording;
  if (recording == null) recording = project.recording;

  text("record-state", recording == null ? "N/A" : recording ? "ON" : "OFF");
  text("song-position", formatPosition(transport.song_position));

  const statusOrb = document.getElementById("status-orb");
  if (statusOrb) {
    statusOrb.className = "status-orb";
    if (recording) statusOrb.classList.add("is-recording");
    else if (playing) statusOrb.classList.add("is-playing");
    else if (playing === false) statusOrb.classList.add("is-stopped");
  }

  // Safety (read-only-context)
  const safety = data.safety || {};
  const readOnly = safety.read_only !== false;
  const dryRunAvailable = safety.dry_run_available !== false;

  text("read-only-state", readOnly ? "Active" : "Inactive");
  text("dry-run-state", dryRunAvailable ? "Available" : "Not available");

  // Rollback row: only show if not read-only / write context is relevant
  const rollbackRow = document.getElementById("rollback-row");
  if (rollbackRow) {
    rollbackRow.style.display = readOnly ? "none" : "";
  }
  if (!readOnly) {
    text("rollback-state", safety.rollback_available ? "Available" : "Not available");
  }

  // Evidence
  const table = byId("evidence-table");
  let evidence = data.evidence || [];
  if (table) {
    table.innerHTML = "";
    if (!evidence.length) {
      evidence = [{
        label: "Status data",
        state: "unavailable",
        value: "N/A",
        source: "Generated data",
        detail: "Status data was not populated."
      }];
    }
    evidence.forEach(entry => {
      const row = document.createElement("div");
      row.className = "evidence-row";

      const entryLabel = safeString(entry.label);
      const entryValue = safeString(entry.value);
      const entryDetail = safeString(entry.detail);
      const entryState = safeString(entry.state);
      const key = entryLabel + entryValue + entryDetail + entryState;
      if (!state.evidenceKeys.has(key)) {
        row.classList.add("new");
        state.evidenceKeys.add(key);
      }

      row.dataset.state = entry.state || "unavailable";

      const stateSpan = document.createElement("span");
      stateSpan.className = "evidence-state";
      stateSpan.textContent = stateLabel(entry.state || "unavailable");

      const label = document.createElement("strong");
      label.textContent = entryLabel !== "N/A" ? entryLabel : "Evidence";

      const value = document.createElement("span");
      value.textContent = entryValue;

      const source = document.createElement("span");
      source.textContent = safeString(entry.source || entry.detail);
      source.title = entryDetail;

      row.append(stateSpan, label, value, source);
      table.appendChild(row);
    });
  }
}

// ─── Logs & History ───────────────────────────────────────────────────────────
function renderLogsHistory() {
  const container = document.getElementById("logs-history-content");
  if (!container) return;
  container.innerHTML = "";

  // Section 1: Runtime Logs
  const runtimeSection = document.createElement("div");
  runtimeSection.className = "log-section";
  const runtimeH3 = document.createElement("h3");
  runtimeH3.className = "log-section-title";
  runtimeH3.textContent = "Runtime Logs";
  runtimeSection.appendChild(runtimeH3);

  const daemonProc = state.status?.processes?.daemon || {};
  const sseProc = state.status?.processes?.sse || {};
  const daemonLogs = (daemonProc.logs || []);
  const sseLogs = (sseProc.logs || []);

  // Daemon logs
  const daemonLogCard = document.createElement("div");
  daemonLogCard.className = "log-subsection";
  const daemonLogTitle = document.createElement("h4");
  daemonLogTitle.className = "log-subsection-title";
  daemonLogTitle.textContent = "FL Studio Bridge Service";
  const daemonLogPre = document.createElement("pre");
  daemonLogPre.className = "log-output";
  daemonLogPre.textContent = daemonLogs.length ? daemonLogs.join("\n") : "No log entries yet.";
  daemonLogCard.append(daemonLogTitle, daemonLogPre);

  // SSE logs
  const sseLogCard = document.createElement("div");
  sseLogCard.className = "log-subsection";
  const sseLogTitle = document.createElement("h4");
  sseLogTitle.className = "log-subsection-title";
  sseLogTitle.textContent = "AI Client Server";
  const sseLogPre = document.createElement("pre");
  sseLogPre.className = "log-output";
  sseLogPre.textContent = sseLogs.length ? sseLogs.join("\n") : "No log entries yet.";
  sseLogCard.append(sseLogTitle, sseLogPre);

  runtimeSection.append(daemonLogCard, sseLogCard);

  // Section 2: Setup Check History
  const historySection = document.createElement("div");
  historySection.className = "log-section";
  const historyH3 = document.createElement("h3");
  historyH3.className = "log-section-title";
  historyH3.textContent = "Setup Check History";
  const historyPlaceholder = document.createElement("div");
  historyPlaceholder.className = "placeholder-card";
  historyPlaceholder.textContent = "Setup check history is not persisted yet. The latest setup state is shown in Setup Doctor.";
  historySection.append(historyH3, historyPlaceholder);

  // Section 3: Safety & Rollback Logs
  const rollbackSection = document.createElement("div");
  rollbackSection.className = "log-section";
  const rollbackH3 = document.createElement("h3");
  rollbackH3.className = "log-section-title";
  rollbackH3.textContent = "Safety & Rollback Logs";
  const rollbackPlaceholder = document.createElement("div");
  rollbackPlaceholder.className = "placeholder-card";
  rollbackPlaceholder.textContent = "No rollback events yet. Rollback logs will appear here when proposal/apply workflows are available.";
  rollbackSection.append(rollbackH3, rollbackPlaceholder);

  container.append(runtimeSection, historySection, rollbackSection);
}

// ─── Ports ────────────────────────────────────────────────────────────────────
function renderPorts() {
  const container = document.getElementById("ports-table-wrap");
  if (!container) return;
  container.innerHTML = "";

  const ports = state.status?.ports;
  if (!ports || typeof ports !== "object" || Object.keys(ports).length === 0) {
    const empty = document.createElement("div");
    empty.className = "placeholder-card";
    empty.textContent = "Ports are not available in the current status payload.";
    container.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  table.className = "port-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const col of ["Service", "Host", "Preferred Port", "Selected Port", "Fallback", "Local Connection"]) {
    const th = document.createElement("th");
    th.textContent = col;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const serviceNames = {
    control_center: "Control Center",
    daemon: "FL Studio Bridge Service",
    sse: "AI Client Server",
  };

  for (const [key, data] of Object.entries(ports)) {
    if (typeof data !== "object" || !data) continue;
    const tr = document.createElement("tr");

    const name = serviceNames[key] || safeString(key);
    const host = safeString(data.host);
    const preferred = safeString(data.preferred_port);
    const selected = safeString(data.selected_port);
    const fallback = data.fallback_port ? safeString(data.fallback_port) : "None";
    const localAddr = (host !== "N/A" && host !== "Unavailable" && selected !== "N/A")
      ? `http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${selected}/`
      : "N/A";

    for (const val of [name, host, preferred, selected, fallback, localAddr]) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

// ─── Support Report ───────────────────────────────────────────────────────────
function renderSupportSummary() {
  const summaryEl = document.getElementById("support-summary-content");
  if (!summaryEl) return;

  const data = getStatusReport();
  const bridge = data?.bridge || {};
  const safety = data?.safety || {};
  const daemonProc = state.status?.processes?.daemon || {};
  const sseProc = state.status?.processes?.sse || {};

  const live = bridge.state === "live";
  const daemonRunning = isManagedProcessRunning(daemonProc) || daemonProc.state === "external";
  const sseRunning = isManagedProcessRunning(sseProc);
  const readOnly = safety.read_only !== false;

  const rows = [
    { label: "Overall Status", value: live ? "FL Studio connected" : "FL Studio not connected" },
    { label: "FL Studio Bridge", value: live ? "Connected" : "Not connected" },
    { label: "Background Service", value: daemonRunning ? "Running" : "Not running" },
    { label: "AI Client Server", value: sseRunning ? "Running" : "Not started" },
    { label: "Safety Mode", value: readOnly ? "Read-only (no project changes)" : "Write-enabled" },
    { label: "Recommended Next Step", value: _recommendedNextStep() },
  ];

  summaryEl.innerHTML = "";
  const dl = document.createElement("dl");
  dl.className = "support-summary-list";
  for (const row of rows) {
    const dt = document.createElement("dt");
    dt.textContent = row.label;
    const dd = document.createElement("dd");
    dd.textContent = row.value;
    dl.append(dt, dd);
  }
  summaryEl.appendChild(dl);
}

// ─── Panel card factory ───────────────────────────────────────────────────────
function card(title, status, bodyText, buttonConfig) {
  const node = document.createElement("article");
  node.className = "panel";

  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const h2 = document.createElement("h2");
  h2.textContent = safeString(title);

  const tag = document.createElement("span");
  tag.className = "evidence-state";
  tag.textContent = safeString(status);
  tag.style.marginLeft = "auto";
  tag.style.fontSize = "11px";

  const statLower = String(status || "").toLowerCase();
  // Only use red/blocker for genuine safety blockades — not normal first-run states
  if (statLower === "ok" || statLower.includes("running") || statLower === "external" || statLower.includes("confirmed")) {
    tag.style.color = "#70fba0";
    tag.style.background = "rgba(27, 228, 126, 0.14)";
    tag.style.borderColor = "rgba(54, 244, 152, 0.44)";
  } else if (statLower === "blocked" || statLower.includes("fail") || statLower === "port_conflict") {
    // "BLOCKED" only for genuine security/safety blockades
    tag.style.color = "#ffb0ba";
    tag.style.background = "rgba(255, 77, 104, 0.12)";
    tag.style.borderColor = "rgba(255, 96, 116, 0.38)";
  } else if (statLower === "not required" || statLower === "not running" || statLower === "stopped") {
    tag.style.color = "#9eacc7";
    tag.style.background = "rgba(158, 172, 199, 0.12)";
    tag.style.borderColor = "rgba(158, 172, 199, 0.44)";
  } else {
    // setup required, action needed, manual check, checking — all amber
    tag.style.color = "#ffb23e";
    tag.style.background = "rgba(255, 178, 62, 0.12)";
    tag.style.borderColor = "rgba(255, 178, 62, 0.5)";
  }

  heading.append(h2, tag);

  const p = document.createElement("p");
  p.className = "panel-note";
  p.style.marginTop = "16px";
  p.style.whiteSpace = "pre-wrap";
  p.style.lineHeight = "1.5";
  p.textContent = safeString(bodyText);

  node.append(heading, p);

  if (buttonConfig) {
    const btnRow = document.createElement("div");
    btnRow.style.cssText = "padding: 0 26px 20px; display: flex; gap: 8px; flex-wrap: wrap;";
    const configs = Array.isArray(buttonConfig) ? buttonConfig : [buttonConfig];
    for (const config of configs) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost-button";
      btn.textContent = safeString(config.text);
      btn.disabled = Boolean(config.disabled);
      btn.onclick = config.onclick;
      if (config.disabled) { btn.style.opacity = "0.5"; btn.style.cursor = "not-allowed"; }
      btnRow.appendChild(btn);
    }
    node.appendChild(btnRow);
  }

  return node;
}

// ─── Setup step confirmation ──────────────────────────────────────────────────
async function confirmStep(step) {
  const before = setupGroupSnapshot(step.groups);
  state.setupFeedback[step.key] = { state: "checking", text: "Checking for the expected setup improvement..." };
  render();
  try {
    state.status = await api("/api/setup/confirm-step", {
      method: "POST",
      body: JSON.stringify({ step: step.key })
    });
    state.setupFeedback[step.key] = evaluateSetupFeedback(step, before);
  } catch (error) {
    state.setupFeedback[step.key] = { state: "attention", text: `Could not re-check this step: ${error.message}` };
  }
  render();
}

async function processAction(path) {
  const key = processActionKey(path);
  state.actionFeedback[key] = { state: "checking", text: `${processActionLabel(path)} in progress...` };
  render();
  try {
    const result = await api(path, { method: "POST", body: "{}" });
    state.actionFeedback[key] = processActionFeedback(path, result);
    render();
    await refresh();
  } catch (error) {
    state.actionFeedback[key] = { state: "attention", text: `${processActionLabel(path)} failed: ${error.message}` };
    render();
  }
}

async function runGuidanceAction(path) {
  if (path === "/api/refresh") { await refresh(); return; }
  await processAction(path);
}

async function loadReport() {
  state.report = await api("/api/setup/report");
  const reportEl = document.getElementById("setup-report");
  if (reportEl) reportEl.textContent = state.report;
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function selectPanel(targetId) {
  // Backward compat alias
  if (targetId === "project_data") targetId = "overview";

  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.target === targetId);
  });

  // Support both .status-report (live HTML) and .dashboard (test harness)
  const panels = [
    ...Array.from(document.querySelectorAll(".status-report")),
    ...Array.from(document.querySelectorAll(".dashboard"))
  ];
  const seen = new Set();
  for (const el of panels) {
    if (seen.has(el)) continue;
    seen.add(el);
    const isTarget = el.id === targetId;
    el.classList.toggle("active", isTarget);
    el.style.display = isTarget ? "block" : "none";
  }

  if (targetId === "support") {
    loadReport();
    renderSupportSummary();
  }
  if (targetId === "logs_history") renderLogsHistory();
  if (targetId === "ports") renderPorts();
}

// ─── Data format helpers ──────────────────────────────────────────────────────
function byId(id) { return document.getElementById(id); }

function text(id, value) {
  const node = byId(id);
  if (node) node.textContent = safeString(value);
}

function numberValue(value, digits) {
  if (value == null || value === "") return "N/A";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return safeString(value);
  return digits == null ? String(Math.round(numeric)) : numeric.toFixed(digits);
}

function bpm(value) {
  if (value == null) return "N/A";
  return numberValue(value, 1);
}

function yesNo(value) { return value ? "YES" : "NO"; }

function stateLabel(s) {
  if (!s) return "Unavailable";
  if (s === "server-state") return "Server";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function count(resource) {
  if (!resource || resource.state !== "live") return "N/A";
  return resource.total == null ? resource.shown || 0 : resource.total;
}

function formatPosition(value) {
  if (value == null) return "N/A";
  if (typeof value === "object") {
    if (value.song_position != null) return formatPosition(value.song_position);
    if (value.position != null) return formatPosition(value.position);
    return "Unavailable";
  }
  const str = String(value);
  // Guard against raw JSON-like strings that might appear if value is serialized
  if (str.startsWith("{") || str.startsWith("[")) return "Unavailable";
  return str;
}

// ─── Event wiring ─────────────────────────────────────────────────────────────
function wireEvents() {
  document.querySelectorAll(".nav-item").forEach(tab => {
    tab.addEventListener("click", () => selectPanel(tab.dataset.target));
  });

  const refreshButton = document.getElementById("refresh-button");
  if (refreshButton) refreshButton.addEventListener("click", refresh);

  const setupButton = document.getElementById("disconnected-setup-button");
  if (setupButton) setupButton.addEventListener("click", () => selectPanel("setup"));

  const copyReport = document.getElementById("copy-report");
  if (copyReport) {
    copyReport.addEventListener("click", async () => {
      await loadReport();
      await navigator.clipboard.writeText(state.report);
      copyReport.textContent = "Copied!";
      copyReport.classList.add("copied");
      setTimeout(() => { copyReport.textContent = "Copy support report"; copyReport.classList.remove("copied"); }, 1400);
    });
  }

  const downloadReport = document.getElementById("download-report");
  if (downloadReport) {
    downloadReport.addEventListener("click", async () => {
      await loadReport();
      const url = URL.createObjectURL(new Blob([state.report], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "fls-pilot-setup-report.md";
      link.click();
      URL.revokeObjectURL(url);
    });
  }
}

// ─── Public API (for testing) ─────────────────────────────────────────────────
window.flsPilotControlCenter = {
  state,
  processAction,
  renderProjectData,
  renderRuntime,
  renderOverview,
  renderConnectionCheck,
  renderLogsHistory,
  renderPorts,
  selectPanel,
  safeString,
  safeDebugString,
};

if (!window.__FLS_PILOT_TEST__) {
  wireEvents();
  refresh().catch(() => {
    const refreshTime = document.getElementById("refresh-time");
    if (refreshTime) refreshTime.textContent = "Error";
  });
}
