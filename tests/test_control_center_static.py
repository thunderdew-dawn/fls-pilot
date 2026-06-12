from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "fls_pilot" / "control_center_static" / "app.js"


def _run_node_dom_check(script: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for control center static DOM checks")
    result = subprocess.run(
        [node, "-e", script, str(APP_JS)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_control_center_static_runtime_and_disconnect_behaviour() -> None:
    _run_node_dom_check(
        r"""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

class ClassList {
  constructor(element) {
    this.element = element;
    this.values = new Set();
  }

  setFromString(value) {
    this.values = new Set(String(value || "").split(/\s+/).filter(Boolean));
  }

  sync() {
    this.element._className = Array.from(this.values).join(" ");
  }

  add(name) {
    this.values.add(name);
    this.sync();
  }

  remove(name) {
    this.values.delete(name);
    this.sync();
  }

  contains(name) {
    return this.values.has(name);
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) {
      this.values.add(name);
    } else {
      this.values.delete(name);
    }
    this.sync();
    return enabled;
  }
}

class Element {
  constructor(tagName = "div", id = "") {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.children = [];
    this.dataset = {};
    this.disabled = false;
    this.listeners = {};
    this.onclick = null;
    this.parentElement = null;
    this.style = {};
    this.textContent = "";
    this.title = "";
    this._className = "";
    this.classList = new ClassList(this);
  }

  set className(value) {
    this._className = String(value || "");
    this.classList.setFromString(this._className);
  }

  get className() {
    return this._className;
  }

  append(...nodes) {
    for (const node of nodes) {
      this.appendChild(node);
    }
  }

  appendChild(node) {
    node.parentElement = this;
    this.children.push(node);
    return node;
  }

  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }
}

function collect(root, predicate) {
  const out = [];
  function walk(node) {
    if (predicate(node)) out.push(node);
    for (const child of node.children || []) walk(child);
  }
  walk(root);
  return out;
}

function textTree(root) {
  let out = root.textContent || "";
  for (const child of root.children || []) out += "\n" + textTree(child);
  return out;
}

function response(payload) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: { get: () => "application/json" },
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}

function baseStatus(daemonProcess, bridgeState = "unavailable") {
  return {
    version: "3.0.0a1",
    readiness: { state: "blocked" },
    groups: {
      environment: [],
      daemon: [],
      midi: [],
      controller: [],
      mcp_sse: [],
      mcp_apply: []
    },
    setup_guidance: [],
    checkpoints: {},
    processes: {
      daemon: daemonProcess,
      sse: { state: "stopped", logs: [] }
    },
    ports: {
      control_center: { host: "127.0.0.1", selected_port: 8766, preferred_port: 8766 },
      daemon: { host: "127.0.0.1", selected_port: 9787, preferred_port: 9787 },
      sse: { host: "127.0.0.1", selected_port: 8080, preferred_port: 8080 }
    },
    snippets: {
      chatgpt: { url: "http://localhost:8080/sse" },
      claude: {},
      cursor: {},
      terminal: { daemon: "fls-pilot-daemon", sse: "fls-pilot --sse" }
    },
    mcp: {
      sse_probe: {
        state: "not_required",
        message: "SSE server is stopped.",
        url: "http://localhost:8080/sse"
      }
    },
    dashboard: {
      bridge: { state: bridgeState },
      project: {},
      resources: {},
      transport: {},
      safety: { read_only: true, dry_run_available: true, rollback_available: false },
      evidence: []
    }
  };
}

function createHarness() {
  const elements = new Map();
  const navItems = [];
  const dashboards = [];

  function register(id, tagName = "div", className = "") {
    const element = new Element(tagName, id);
    element.className = className;
    elements.set(id, element);
    return element;
  }

  for (const id of [
    "bridge-pill",
    "version-pill",
    "refresh-time",
    "setup-steps",
    "runtime-status",
    "client-snippets",
    "connected-version",
    "connected-target",
    "connection-dot",
    "disconnected-overlay",
    "tempo-value",
    "channel-count",
    "mixer-count",
    "pattern-count",
    "playlist-count",
    "record-state",
    "song-position",
    "status-orb",
    "read-only-state",
    "rollback-state",
    "dry-run-state",
    "evidence-table",
    "footer-cc-port",
    "success-overlay",
    "loading-overlay",
    "loading-text"
  ]) {
    register(id);
  }

  for (const id of ["project_data", "setup", "runtime", "clients", "support"]) {
    const dashboard = register(id, "main", "dashboard");
    dashboard.style.display = id === "project_data" ? "block" : "none";
    dashboards.push(dashboard);
  }

  for (const target of ["project_data", "runtime", "clients", "setup", "support"]) {
    const item = new Element("button");
    item.className = target === "project_data" ? "nav-item active" : "nav-item";
    item.dataset.target = target;
    navItems.push(item);
  }

  const connectionCard = new Element("div");
  connectionCard.className = "connection-card";
  const eyebrow = new Element("span");
  eyebrow.className = "eyebrow";
  connectionCard.appendChild(eyebrow);

  const document = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements.get(id) || null,
    querySelectorAll: (selector) => {
      if (selector === ".nav-item") return navItems;
      if (selector === ".dashboard") return dashboards;
      return [];
    },
    querySelector: (selector) => {
      if (selector === ".connection-card") return connectionCard;
      if (selector === ".connection-card .eyebrow") return eyebrow;
      return null;
    }
  };

  const context = {
    Blob,
    URL,
    clearInterval,
    console,
    document,
    fetch: async () => response({}),
    navigator: { clipboard: { writeText: async () => undefined } },
    setInterval,
    window: { __FLS_PILOT_TEST__: true }
  };
  context.window.document = document;

  vm.createContext(context);
  vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);

  return {
    controls: context.window.flsPilotControlCenter,
    context,
    dashboards,
    elements
  };
}

(async () => {
  const harness = createHarness();
  const controls = harness.controls;

  controls.state.status = baseStatus({ state: "stopped", logs: [] });
  controls.renderProjectData();
  assert.strictEqual(harness.elements.get("disconnected-overlay").style.display, "flex");
  assert.strictEqual(harness.elements.get("project_data").style.display, "block");
  assert.strictEqual(harness.elements.get("setup").style.display, "none");

  controls.state.status = baseStatus(
    { state: "external", health: { reachable: true }, logs: [] },
    "live"
  );
  controls.renderRuntime();
  const runtime = harness.elements.get("runtime-status");
  const daemonCard = runtime.children[0];
  const daemonButtons = collect(daemonCard, (node) => node.tagName === "BUTTON");
  assert.strictEqual(daemonButtons[0].disabled, true);
  assert.strictEqual(daemonButtons[1].disabled, true);
  assert.match(textTree(daemonCard), /External daemon is reachable/);

  const calls = [];
  harness.context.fetch = async (path) => {
    calls.push(path);
    if (path === "/api/process/daemon/start") {
      return response({
        ok: false,
        state: "port_conflict",
        message: "Port 127.0.0.1:9787 is occupied by a non-daemon process.",
        fallback_port: 9788
      });
    }
    if (path === "/api/refresh") {
      return response(baseStatus({ state: "stopped", logs: [] }));
    }
    throw new Error(`unexpected fetch path: ${path}`);
  };

  await controls.processAction("/api/process/daemon/start");
  assert.deepStrictEqual(calls, ["/api/process/daemon/start", "/api/refresh"]);
  assert.strictEqual(controls.state.actionFeedback.daemon.state, "attention");
  assert.match(controls.state.actionFeedback.daemon.text, /non-daemon process/);
  assert.match(controls.state.actionFeedback.daemon.text, /9788/);
  assert.match(textTree(harness.elements.get("runtime-status")), /non-daemon process/);
})().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
"""
    )
