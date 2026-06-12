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

async function refresh() {
  state.status = await api("/api/refresh", { method: "POST", body: "{}" });
  render();
}

function render() {
  if (!state.status) return;
  document.getElementById("readiness").textContent =
    `Readiness: ${state.status.readiness.state.replaceAll("_", " ")}`;
  renderSetup();
  renderRuntime();
  renderClients();
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
    const node = card(title, confirmed ? "user confirmed" : "manual action", text);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = confirmed ? "Confirmed" : "I did this";
    button.disabled = Boolean(confirmed);
    button.addEventListener("click", () => confirmStep(key));
    node.appendChild(button);
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
  for (const [name, proc] of Object.entries(state.status.processes)) {
    container.appendChild(card(name, proc.running ? "running" : (proc.state || "stopped"), (proc.logs || []).slice(-6).join("\n") || "No recent logs."));
  }
  for (const [name, port] of Object.entries(state.status.ports)) {
    const fallback = port.fallback_port ? `Fallback: ${port.fallback_port}` : "No fallback needed.";
    container.appendChild(card(`${name} port`, `${port.host}:${port.selected_port}`, `Default: ${port.preferred_port}. ${fallback}`));
  }
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
  node.className = "snippet";
  const h = document.createElement("h3");
  h.textContent = title;
  const pre = document.createElement("pre");
  pre.textContent = text;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Copy";
  button.addEventListener("click", () => navigator.clipboard.writeText(text));
  node.append(h, pre, button);
  container.appendChild(node);
}

function card(title, status, text) {
  const node = document.createElement("article");
  node.className = "card";
  const h = document.createElement("h3");
  h.textContent = title;
  const chip = document.createElement("span");
  chip.className = `chip ${String(status).toLowerCase().replaceAll(" ", "-")}`;
  chip.textContent = status;
  const p = document.createElement("p");
  p.textContent = text;
  node.append(h, chip, p);
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

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab, .panel").forEach((el) => el.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
    if (tab.dataset.tab === "support") loadReport();
  });
});

document.getElementById("refresh").addEventListener("click", refresh);
document.getElementById("start-daemon").addEventListener("click", () => processAction("/api/process/daemon/start"));
document.getElementById("stop-daemon").addEventListener("click", () => processAction("/api/process/daemon/stop"));
document.getElementById("start-sse").addEventListener("click", () => processAction("/api/process/sse/start"));
document.getElementById("stop-sse").addEventListener("click", () => processAction("/api/process/sse/stop"));
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
  document.getElementById("readiness").textContent = `Could not load status: ${error.message}`;
});
