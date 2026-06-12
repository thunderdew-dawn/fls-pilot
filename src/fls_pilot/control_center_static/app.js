const state = { status: null, report: "" };

const setupSteps = [
  ["created_midi_ports", "MIDI ports", "Create FLStudioPilot RX and FLStudioPilot TX."],
  ["opened_fl_studio", "Open FL Studio", "Start FL Studio and load or create a project."],
  ["configured_fl_midi", "FL MIDI settings", "Enable FLStudioPilot RX/TX and set port 42."],
  ["granted_macos_accessibility", "macOS Accessibility", "Grant permission for note-writing hotkeys if needed."],
  ["ran_mcp_apply", "MCP_Apply", "Run MCP_Apply once in Piano Roll for note-writing only."]
];

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
    if (loadingOverlay) {
      loadingOverlay.style.display = "none";
    }
    if (loadingInterval) {
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
  }
}

function render() {
  if (!state.status) return;
  
  const bridge = state.status.dashboard?.bridge || {};
  const live = bridge.state === "live";

  // Topbar readiness
  let stateLabel = state.status.readiness.state.replaceAll("_", " ").toUpperCase();
  if (live) {
    stateLabel = "LIVE";
  }

  const bridgePill = document.getElementById("bridge-pill");
  if (bridgePill) {
    bridgePill.textContent = stateLabel;
    if (live || stateLabel.includes("OK") || stateLabel.includes("READY")) {
      bridgePill.className = "pill pill-live";
    } else {
      bridgePill.className = "pill pill-offline";
    }
  }

  const versionPill = document.getElementById("version-pill");
  if (versionPill && state.status.version) {
    const v = state.status.version.startsWith("v") ? state.status.version : "v" + state.status.version;
    versionPill.textContent = v.toUpperCase();
  }

  const refreshTime = document.getElementById("refresh-time");
  if (refreshTime) {
    refreshTime.textContent = new Date().toLocaleTimeString();
  }

  renderSetup();
  renderRuntime();
  renderClients();
  renderProjectData();
  renderConnection();
}

function renderSetup() {
  const container = document.getElementById("setup-steps");
  container.innerHTML = "";
  const technical = [
    ["environment", "Environment"],
    ["midi", "MIDI ports"],
    ["controller", "FL controller"],
    ["daemon", "Daemon"],
    ["mcp_sse", "MCP SSE"],
    ["mcp_apply", "MCP_Apply file"]
  ];
  for (const [group, title] of technical) {
    container.appendChild(card(title, groupStatus(group), groupText(group)));
  }
  for (const [key, title, text] of setupSteps) {
    const confirmed = state.status.checkpoints[key];
    const node = card(title, confirmed ? "user confirmed" : "manual action", text, {
      text: confirmed ? "Confirmed" : "I did this",
      disabled: Boolean(confirmed),
      onclick: () => confirmStep(key)
    });
    container.appendChild(node);
  }
}

function groupStatus(group) {
  const findings = state.status.groups[group] || [];
  const failed = findings.find((item) => item.status === "failed");
  if (failed) return failed.severity === "blocker" ? "blocked" : "action needed";
  const manual = findings.find((item) => item.status === "manual_check" || item.status === "probe_needed");
  if (manual) return "manual check";
  return findings.length ? "OK" : "not required";
}

function groupText(group) {
  const findings = state.status.groups[group] || [];
  if (!findings.length) return "No finding for this setup layer.";
  return findings.map((item) => `${item.component}: ${item.evidence}${item.remediation ? ` Fix: ${item.remediation}` : ""}`).join("\n");
}

function renderRuntime() {
  const container = document.getElementById("runtime-status");
  container.innerHTML = "";
  
  if (!state.status || !state.status.processes || !state.status.ports) return;

  const daemonProc = state.status.processes.daemon || {};
  const daemonPort = state.status.ports.daemon || {};
  
  const daemonStatus = daemonProc.running ? "running" : (daemonProc.state || "stopped");
  let daemonText = `Port: ${daemonPort.host}:${daemonPort.selected_port} (Default: ${daemonPort.preferred_port})\n\n`;
  daemonText += "Logs:\n" + ((daemonProc.logs || []).slice(-6).join("\n") || "No recent logs.");
  
  container.appendChild(card("daemon", daemonStatus, daemonText, [
    { text: "Start daemon", disabled: daemonStatus === "running", onclick: () => processAction("/api/process/daemon/start") },
    { text: "Stop daemon", disabled: daemonStatus !== "running", onclick: () => processAction("/api/process/daemon/stop") }
  ]));

  const sseProc = state.status.processes.sse || {};
  const ssePort = state.status.ports.sse || {};
  
  const sseStatus = sseProc.running ? "running" : (sseProc.state || "stopped");
  let sseText = `Port: ${ssePort.host}:${ssePort.selected_port} (Default: ${ssePort.preferred_port})\n\n`;
  sseText += "Logs:\n" + ((sseProc.logs || []).slice(-6).join("\n") || "No recent logs.");
  
  container.appendChild(card("sse", sseStatus, sseText, [
    { text: "Start SSE server", disabled: sseStatus === "running", onclick: () => processAction("/api/process/sse/start") },
    { text: "Stop SSE server", disabled: sseStatus !== "running", onclick: () => processAction("/api/process/sse/stop") }
  ]));
  
  const ccPort = state.status.ports.control_center || {};
  const footerPortSpan = document.getElementById("footer-cc-port");
  if (footerPortSpan) {
    footerPortSpan.textContent = `Control Center Port: ${ccPort.host}:${ccPort.selected_port} (Default: ${ccPort.preferred_port})`;
  }
}

function renderConnection() {
  if (!state.status || !state.status.dashboard) return;
  const bridge = state.status.dashboard.bridge || {};
  const project = state.status.dashboard.project || {};
  const live = bridge.state === "live";
  
  const card = document.querySelector(".connection-card");
  if (card) {
    card.classList.toggle("offline", !live);
  }
  
  const eyebrow = document.querySelector(".connection-card .eyebrow");
  if (eyebrow) {
    eyebrow.textContent = live ? "Connected To" : "Status";
  }

  const dot = byId("connection-dot");
  if (dot) {
    dot.classList.toggle("live", live);
  }
  
  text("connected-version", live ? (project.fl_version || bridge.fl_version || "Local daemon API") : "API unreachable");
  text("connected-target", live ? "FL Studio (Local)" : "Disconnected");
}

function renderClients() {
  const container = document.getElementById("client-snippets");
  container.innerHTML = "";
  const snippets = state.status.snippets;
  addSnippet(container, "ChatGPT SSE URL", snippets.chatgpt.url);
  addSnippet(container, "Claude Desktop JSON", JSON.stringify(snippets.claude, null, 2));
  addSnippet(container, "Cursor JSON", JSON.stringify(snippets.cursor, null, 2));
  addSnippet(container, "Terminal fallback", `${snippets.terminal.daemon}\n${snippets.terminal.sse}`);
}

function addSnippet(container, title, text) {
  const node = document.createElement("article");
  node.className = "panel";
  
  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  heading.appendChild(h2);
  
  const preContainer = document.createElement("div");
  preContainer.style.padding = "0 18px 18px";
  
  const pre = document.createElement("pre");
  pre.textContent = text;
  pre.style.background = "rgba(0,0,0,0.5)";
  pre.style.padding = "16px";
  pre.style.borderRadius = "8px";
  pre.style.border = "1px solid rgba(130, 180, 245, 0.22)";
  pre.style.color = "#a5b4fc";
  pre.style.overflow = "auto";
  pre.style.whiteSpace = "pre-wrap";
  pre.style.wordBreak = "break-word";
  pre.style.fontFamily = "monospace";
  
  preContainer.appendChild(pre);
  
  const btnRow = document.createElement("div");
  btnRow.style.padding = "0 18px 18px";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost-button";
  button.textContent = "Copy";
  button.addEventListener("click", () => navigator.clipboard.writeText(text));
  btnRow.appendChild(button);
  
  node.append(heading, preContainer, btnRow);
  container.appendChild(node);
}

function card(title, status, text, buttonConfig) {
  const node = document.createElement("article");
  node.className = "panel";
  
  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  
  const tag = document.createElement("span");
  tag.className = "evidence-state";
  tag.textContent = status;
  tag.style.marginLeft = "auto";
  tag.style.fontSize = "11px";
  
  const statLower = String(status).toLowerCase();
  if (statLower.includes("ok") || statLower.includes("running") || statLower.includes("confirmed")) {
    tag.style.color = "#70fba0";
    tag.style.background = "rgba(27, 228, 126, 0.14)";
    tag.style.borderColor = "rgba(54, 244, 152, 0.44)";
  } else if (statLower.includes("block") || statLower.includes("fail") || statLower.includes("stop")) {
    tag.style.color = "#ffb0ba";
    tag.style.background = "rgba(255, 77, 104, 0.12)";
    tag.style.borderColor = "rgba(255, 96, 116, 0.38)";
  } else if (statLower.includes("not required")) {
    tag.style.color = "#9eacc7";
    tag.style.background = "rgba(158, 172, 199, 0.12)";
    tag.style.borderColor = "rgba(158, 172, 199, 0.44)";
  } else {
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
  p.textContent = text;
  
  node.append(heading, p);
  
  if (buttonConfig) {
    const btnRow = document.createElement("div");
    btnRow.style.padding = "0 26px 20px";
    btnRow.style.display = "flex";
    btnRow.style.gap = "8px";
    
    const configs = Array.isArray(buttonConfig) ? buttonConfig : [buttonConfig];
    
    for (const config of configs) {
      const btn = document.createElement("button");
      btn.className = "ghost-button";
      btn.textContent = config.text;
      btn.disabled = config.disabled;
      btn.onclick = config.onclick;
      
      if (config.disabled) {
        btn.style.opacity = "0.5";
        btn.style.cursor = "not-allowed";
      }
      
      btnRow.appendChild(btn);
    }
    
    node.appendChild(btnRow);
  }
  
  return node;
}

async function confirmStep(step) {
  state.status = await api("/api/setup/confirm-step", {
    method: "POST",
    body: JSON.stringify({ step })
  });
  render();
}

async function processAction(path) {
  await api(path, { method: "POST", body: "{}" });
  await refresh();
}

async function loadReport() {
  state.report = await api("/api/setup/report");
  document.getElementById("setup-report").textContent = state.report;
}

// Data format helpers
function byId(id) {
  return document.getElementById(id);
}

function text(id, value) {
  const node = byId(id);
  if (node) {
    node.textContent = value == null || value === "" ? "N/A" : String(value);
  }
}

function numberValue(value, digits) {
  if (value == null || value === "") return "N/A";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return digits == null ? String(Math.round(numeric)) : numeric.toFixed(digits);
}

function bpm(value) {
  if (value == null) return "N/A";
  return numberValue(value, 3);
}

function yesNo(value) {
  return value ? "YES" : "NO";
}

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
  }
  return String(value);
}

// Project Data rendering
function renderProjectData() {
  const disconnectedOverlay = document.getElementById("disconnected-overlay");
  if (!state.status || !state.status.dashboard) {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "flex";
    return;
  }
  const data = state.status.dashboard;
  const bridge = data.bridge || {};
  const live = bridge.state === "live";

  if (!live) {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "flex";
    document.querySelectorAll(".tab, .nav-item, .dashboard").forEach((el) => el.classList.remove("active"));
    document.querySelectorAll(".dashboard").forEach((el) => el.style.display = "none");
    const setupTabBtn = document.querySelector('[data-target="setup"]');
    if (setupTabBtn) setupTabBtn.classList.add("active");
    const setupPanel = document.getElementById("setup");
    if (setupPanel) {
      setupPanel.classList.add("active");
      setupPanel.style.display = "block";
    }
  } else {
    if (disconnectedOverlay) disconnectedOverlay.style.display = "none";
  }
  
  // Project Snapshot
  const project = data.project || {};
  const resources = data.resources || {};
  text("tempo-value", bpm(project.tempo_bpm));
  text("channel-count", project.channel_count == null ? count(resources.channels) : project.channel_count);
  text("mixer-count", project.mixer_track_count == null ? count(resources.mixer) : project.mixer_track_count);
  text("pattern-count", project.pattern_count == null ? count(resources.patterns) : project.pattern_count);
  text("playlist-count", project.playlist_track_count == null ? count(resources.playlist) : project.playlist_track_count);
  
  // Transport
  const transport = data.transport || {};
  let playing = transport.playing;
  if (playing == null) playing = project.playing;
  let recording = transport.recording;
  if (recording == null) recording = project.recording;
  
  text("playing-state", playing == null ? "N/A" : yesNo(Boolean(playing)));
  text("record-state", recording == null ? "N/A" : recording ? "ON" : "OFF");
  text("song-position", formatPosition(transport.song_position));

  const statusOrb = document.getElementById("status-orb");
  if (statusOrb) {
    statusOrb.className = "status-orb";
    if (recording) {
      statusOrb.classList.add("is-recording");
    } else if (playing) {
      statusOrb.classList.add("is-playing");
    } else if (playing === false) {
      statusOrb.classList.add("is-stopped");
    }
  }
  
  // Safety
  const safety = data.safety || {};
  text("read-only-state", yesNo(safety.read_only !== false));
  text("rollback-state", safety.rollback_available ? "YES" : "NO");
  text("dry-run-state", safety.dry_run_available ? "YES" : "NO");
  
  // Evidence
  const table = byId("evidence-table");
  let evidence = data.evidence || [];
  if (table) {
    table.innerHTML = "";
    if (!evidence.length) {
      evidence = [
        {
          label: "Dashboard data",
          state: "unavailable",
          value: "N/A",
          source: "Generated data",
          detail: "Dashboard data was not populated."
        }
      ];
    }
    evidence.forEach(entry => {
      const row = document.createElement("div");
      row.className = "evidence-row";
      row.dataset.state = entry.state || "unavailable";

      const stateSpan = document.createElement("span");
      stateSpan.className = "evidence-state";
      stateSpan.textContent = stateLabel(entry.state || "unavailable");

      const label = document.createElement("strong");
      label.textContent = entry.label || "Evidence";

      const value = document.createElement("span");
      value.textContent = entry.value == null ? "N/A" : String(entry.value);

      const source = document.createElement("span");
      source.textContent = entry.source || entry.detail || "Source unavailable";
      source.title = entry.detail || "";

      row.append(stateSpan, label, value, source);
      table.appendChild(row);
    });
  }
}


document.querySelectorAll(".nav-item").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
    document.querySelectorAll(".dashboard").forEach((el) => el.style.display = "none");
    
    tab.classList.add("active");
    const targetId = tab.dataset.target;
    document.getElementById(targetId).style.display = "block";
    
    if (targetId === "support") loadReport();
  });
});

document.getElementById("refresh-button").addEventListener("click", refresh);

document.getElementById("copy-report").addEventListener("click", async () => {
  await loadReport();
  await navigator.clipboard.writeText(state.report);
});
document.getElementById("download-report").addEventListener("click", async () => {
  await loadReport();
  const url = URL.createObjectURL(new Blob([state.report], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "fls-pilot-setup-report.md";
  link.click();
  URL.revokeObjectURL(url);
});

refresh().catch((error) => {
  const refreshTime = document.getElementById("refresh-time");
  if (refreshTime) refreshTime.textContent = "Error";
});
