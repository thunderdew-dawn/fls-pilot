"""Local first-run and runtime Control Center for FL Studio Pilot."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

from . import doctor
from .connection import DEFAULT_TCP_HOST, DEFAULT_TCP_PORT, TCPBridge
from .dashboard import collect_dashboard_snapshot
from .runtime_config import (
    DEFAULT_CONTROL_CENTER_HOST,
    DEFAULT_CONTROL_CENTER_PORT,
    DEFAULT_SSE_HOST,
    DEFAULT_SSE_PORT,
    can_bind_tcp,
    find_available_tcp_port,
    tcp_port_status,
)

STATIC_PACKAGE = "fls_pilot.control_center_static"
MAX_LOG_LINES = 80
MANUAL_CHECKPOINTS = {
    "created_midi_ports",
    "opened_fl_studio",
    "configured_fl_midi",
    "ran_mcp_apply",
    "granted_macos_accessibility",
}


def _read_project_version() -> str:
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        pyproject_path = project_root / "pyproject.toml"
        if pyproject_path.exists():
            for line in pyproject_path.read_text("utf-8").splitlines():
                if line.startswith("version = "):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    from . import __version__
    return __version__


PROJECT_VERSION = _read_project_version()



@dataclass
class ManagedProcess:
    name: str
    args: list[str]
    env: dict[str, str]
    process: subprocess.Popen
    started_at: str
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    reader_threads: list[threading.Thread] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.process.pid,
            "state": "running" if self.running else "exited",
            "running": self.running,
            "returncode": self.process.poll(),
            "started_at": self.started_at,
            "args": _redact_args(self.args),
            "logs": list(self.logs),
        }


class ControlCenterState:
    def __init__(self, *, host: str, port: int, sse_host: str, sse_port: int) -> None:
        daemon_host, daemon_port = _resolve_daemon_endpoint()
        self.host = host
        self.port = port
        self.sse_host = sse_host
        self.sse_port = sse_port
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.daemon_fallback_port: int | None = None
        self.checkpoints: dict[str, dict[str, Any]] = {}
        self.processes: dict[str, ManagedProcess] = {}
        self.last_findings: list[doctor.Finding] = []
        self.daemon_autostart_attempted = False
        self.daemon_autostart: dict[str, Any] = {
            "state": "pending",
            "message": "Daemon auto-start has not run yet.",
        }
        self.sse_probe: dict[str, Any] = _sse_probe_state(
            "not_required",
            "SSE server is stopped. Start it only if your MCP client uses SSE/HTTP.",
            sse_host,
            sse_port,
        )
        self.started_at = _now_iso()
        self.lock = threading.RLock()

    def shutdown(self) -> None:
        with self.lock:
            for name in list(self.processes):
                _stop_managed_process(self.processes[name])
            self.processes.clear()


def collect_status(state: ControlCenterState, *, refresh: bool = True) -> dict[str, Any]:
    """Collect Control Center status without mutating FL Studio project state."""
    with state.lock:
        daemon_host, daemon_port = _selected_daemon_endpoint(state)
        if refresh or not state.last_findings:
            state.last_findings = _run_doctor_checks(state, daemon_host, daemon_port)
            autostart = _auto_start_daemon_if_ready(state, state.last_findings)
            if autostart.get("rerun_checks"):
                daemon_host, daemon_port = _selected_daemon_endpoint(state)
                state.last_findings = _run_doctor_checks(state, daemon_host, daemon_port)
        findings = [finding.to_dict() for finding in state.last_findings]
        groups = _group_findings(state.last_findings)
        readiness = _readiness(state.last_findings, state.checkpoints)
        _sync_sse_probe_state(state, refresh=refresh)
        process_state = _process_status(state)
        ports = _port_state(state)
        dashboard_data = collect_dashboard_snapshot(
            offline=False,
            bridge_factory=lambda: TCPBridge(daemon_host, daemon_port),
        )
        return {
            "version": PROJECT_VERSION,
            "generated_at": _now_iso(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python": sys.version.split()[0],
                "executable": sys.executable,
            },
            "control_center": {
                "host": state.host,
                "port": state.port,
                "url": f"http://{state.host}:{state.port}/",
                "started_at": state.started_at,
            },
            "ports": ports,
            "readiness": readiness,
            "groups": groups,
            "findings": findings,
            "checkpoints": dict(state.checkpoints),
            "processes": process_state,
            "automation": {"daemon_autostart": dict(state.daemon_autostart)},
            "mcp": {"sse_probe": dict(state.sse_probe)},
            "setup_guidance": _setup_guidance(
                groups=groups,
                readiness=readiness,
                processes=process_state,
                ports=ports,
                daemon_autostart=state.daemon_autostart,
                sse_probe=state.sse_probe,
            ),
            "snippets": client_snippets(state),
            "dashboard": dashboard_data,
        }


def _run_doctor_checks(
    state: ControlCenterState,
    daemon_host: str,
    daemon_port: int,
) -> list[doctor.Finding]:
    return doctor.run_all_checks(
        server_transport="stdio",
        sse_host=state.sse_host,
        sse_port=state.sse_port,
        bridge_transport="tcp",
        tcp_host=daemon_host,
        tcp_port=daemon_port,
        smoke_timeout_seconds=1.5,
    )


def _auto_start_daemon_if_ready(
    state: ControlCenterState,
    findings: list[doctor.Finding],
) -> dict[str, Any]:
    if state.daemon_autostart_attempted:
        return {}

    if not _environment_ready(findings):
        state.daemon_autostart = {
            "state": "skipped",
            "message": "Daemon auto-start waits until Python and core dependencies are OK.",
        }
        return {}

    state.daemon_autostart_attempted = True
    existing = state.processes.get("daemon")
    if existing and existing.running:
        state.daemon_autostart = {
            "state": "running",
            "message": "Daemon is already running under this Control Center.",
            "port": _selected_daemon_endpoint(state)[1],
        }
        return {}

    health = _daemon_health(state.daemon_host, state.daemon_port)
    if health.get("reachable"):
        state.daemon_fallback_port = None
        state.daemon_autostart = {
            "state": "external",
            "message": "A daemon is already reachable. Control Center will use it.",
            "port": state.daemon_port,
        }
        return {}

    port_status = tcp_port_status(state.daemon_host, state.daemon_port)
    target_port = state.daemon_port
    fallback_used = False
    if not port_status["available"]:
        target_port = int(port_status["fallback_port"])
        state.daemon_fallback_port = target_port
        fallback_used = True
    else:
        state.daemon_fallback_port = None

    try:
        proc = _spawn_daemon(state, target_port)
    except Exception as exc:
        state.daemon_autostart = {
            "state": "failed",
            "message": f"Daemon auto-start failed: {type(exc).__name__}: {exc}",
            "port": target_port,
        }
        return {}

    state.processes["daemon"] = proc
    health = _wait_for_daemon_health(state.daemon_host, target_port)
    state.daemon_autostart = {
        "state": "started" if health.get("reachable") else "starting",
        "message": (
            f"Started daemon on fallback port {target_port}."
            if fallback_used
            else f"Started daemon on port {target_port}."
        ),
        "port": target_port,
        "fallback_used": fallback_used,
        "reachable": bool(health.get("reachable")),
    }
    return {"rerun_checks": True}


def _environment_ready(findings: list[doctor.Finding]) -> bool:
    required = {"Python Environment", "Core Dependencies"}
    seen: set[str] = set()
    for finding in findings:
        if finding.component not in required:
            continue
        seen.add(finding.component)
        if finding.status != "ok":
            return False
    return required.issubset(seen)


def _spawn_daemon(state: ControlCenterState, port: int) -> ManagedProcess:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["FLS_PILOT_TCP_HOST"] = state.daemon_host
    env["FLS_PILOT_TCP_PORT"] = str(port)
    return _spawn("daemon", [sys.executable, "-m", "fls_pilot.daemon"], env)


def _wait_for_daemon_health(host: str, port: int, *, timeout: float = 2.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = {"reachable": False}
    while time.monotonic() < deadline:
        last = _daemon_health(host, port)
        if last.get("reachable"):
            return last
        time.sleep(0.1)
    return last


def _sync_sse_probe_state(state: ControlCenterState, *, refresh: bool) -> None:
    proc = state.processes.get("sse")
    if proc is None:
        state.sse_probe = _sse_probe_state(
            "not_required",
            "SSE server is stopped. Start it only if your MCP client uses SSE/HTTP.",
            state.sse_host,
            state.sse_port,
        )
        return
    if not proc.running:
        if state.sse_probe.get("state") not in {"not_required", "stopped"}:
            state.sse_probe = _sse_probe_state(
                "failed",
                f"SSE server is not running. Last exit code: {proc.process.poll()}.",
                state.sse_host,
                state.sse_port,
                checked_at=_now_iso(),
            )
        return

    expected_url = _sse_url(state.sse_host, state.sse_port)
    probe_state = str(state.sse_probe.get("state") or "")
    should_probe = (
        state.sse_probe.get("url") != expected_url
        or probe_state in {
            "",
            "not_required",
            "stopped",
            "pending",
            "checking",
        }
        or (refresh and probe_state == "failed")
    )
    if should_probe:
        _probe_sse_connection(state)


def _probe_sse_connection(
    state: ControlCenterState,
    *,
    timeout: float = 2.0,
) -> dict[str, Any]:
    url = _sse_url(state.sse_host, state.sse_port)
    state.sse_probe = _sse_probe_state(
        "checking",
        "Testing the MCP connection over SSE...",
        state.sse_host,
        state.sse_port,
    )
    proc = state.processes.get("sse")
    try:
        _wait_for_tcp_listener(
            state.sse_host,
            state.sse_port,
            process=proc.process if proc is not None else None,
            timeout=timeout,
        )
        import anyio

        result = anyio.run(doctor._sse_mcp_client_smoke_async, url, timeout)
    except Exception as exc:
        state.sse_probe = _sse_probe_state(
            "failed",
            f"SSE MCP connection test failed at {url}: {type(exc).__name__}: {exc}",
            state.sse_host,
            state.sse_port,
            checked_at=_now_iso(),
            error=f"{type(exc).__name__}: {exc}",
        )
    else:
        state.sse_probe = _sse_probe_state(
            "ok",
            _sse_probe_success_message(url, result),
            state.sse_host,
            state.sse_port,
            checked_at=_now_iso(),
            result=result,
        )
    return dict(state.sse_probe)


def _wait_for_tcp_listener(
    host: str,
    port: int,
    *,
    process: subprocess.Popen | None = None,
    timeout: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout
    connect_host = _connect_host_for_bind_host(host)
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"SSE server exited early with code {process.returncode}.")
        try:
            with socket.create_connection((connect_host, int(port)), timeout=0.3):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for SSE server at {host}:{port}: {last_error}")


def _sse_probe_state(
    state: str,
    message: str,
    host: str,
    port: int,
    *,
    checked_at: str | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "state": state,
        "message": message,
        "host": host,
        "port": int(port),
        "url": _sse_url(host, port),
    }
    if checked_at is not None:
        data["checked_at"] = checked_at
    if error:
        data["error"] = error
    if result is not None:
        data["result"] = result
    return data


def _sse_probe_success_message(url: str, result: dict[str, Any]) -> str:
    pieces = [
        f"SSE MCP connection test passed at {url}.",
        f"Tools: {result.get('tool_count', 'unknown')}.",
        f"Resources: {result.get('resource_count', 'unknown')}.",
    ]
    if result.get("has_fl_transport"):
        pieces.append("fl_transport is available.")
    if result.get("has_status_resource"):
        pieces.append("fl://status is readable.")
    return " ".join(pieces)


def _sse_url(host: str, port: int) -> str:
    connect_host = _connect_host_for_bind_host(host)
    if connect_host == "127.0.0.1":
        connect_host = "localhost"
    connect_host = _url_host(connect_host)
    return f"http://{connect_host}:{int(port)}/sse"


def _connect_host_for_bind_host(host: str) -> str:
    if host in {"0.0.0.0", ""}:
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def client_snippets(state: ControlCenterState) -> dict[str, Any]:
    chatgpt_url = f"http://localhost:{state.sse_port}/sse"
    command = _console_script_path("fls-pilot")
    daemon_host, daemon_port = _selected_daemon_endpoint(state)
    mcp_tcp_env = {
        "FLS_PILOT_TRANSPORT": "tcp",
        "FLS_PILOT_TCP_HOST": daemon_host,
        "FLS_PILOT_TCP_PORT": str(daemon_port),
    }
    return {
        "chatgpt": {
            "name": "fls-pilot",
            "type": "sse",
            "url": chatgpt_url,
        },
        "claude": {
            "mcpServers": {
                "fls-pilot": {
                    "command": command,
                    "env": dict(mcp_tcp_env),
                }
            }
        },
        "cursor": {
            "mcpServers": {
                "fls-pilot": {
                    "command": command,
                    "env": dict(mcp_tcp_env),
                }
            }
        },
        "terminal": {
            "daemon": _daemon_terminal_command(daemon_host, daemon_port),
            "sse": _sse_terminal_command(state, command),
        },
    }


def setup_report(state: ControlCenterState) -> str:
    status = collect_status(state, refresh=False)
    lines = [
        "# fls-pilot setup report",
        "",
        f"Generated: {status['generated_at']}",
        f"Version: {status['version']}",
        f"OS: {status['platform']['system']} {status['platform']['release']}",
        f"Python: {status['platform']['python']}",
        f"Executable: {_redact_path(status['platform']['executable'])}",
        "",
        "## Ports",
    ]
    for name, data in status["ports"].items():
        lines.append(
            f"- {name}: default {data['host']}:{data['preferred_port']}; "
            f"selected {data['host']}:{data['selected_port']}; "
            f"fallback {data.get('fallback_port') or 'none'}"
        )
    lines.extend(["", "## Readiness", f"- State: {status['readiness']['state']}"])
    lines.extend(["", "## Manual checkpoints"])
    if status["checkpoints"]:
        for key, value in status["checkpoints"].items():
            lines.append(f"- {key}: {value.get('status')} at {value.get('updated_at')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Processes"])
    for name, proc in status["processes"].items():
        lines.append(f"- {name}: {_process_state_text(proc)}")
        for log in proc.get("logs", [])[-10:]:
            lines.append(f"  - {log}")
    autostart = status.get("automation", {}).get("daemon_autostart", {})
    sse_probe = status.get("mcp", {}).get("sse_probe", {})
    lines.extend(
        [
            "",
            "## Automation",
            f"- Daemon auto-start: {autostart.get('state', 'unknown')} - "
            f"{autostart.get('message', 'no detail')}",
            f"- MCP SSE probe: {sse_probe.get('state', 'unknown')} - "
            f"{sse_probe.get('message', 'no detail')}",
        ]
    )
    lines.extend(["", "## Guided troubleshooting"])
    for item in status.get("setup_guidance", []):
        lines.append(f"- [{item.get('status')}] {item.get('title')}: {item.get('text')}")
    lines.extend(["", "## Doctor findings"])
    for finding in status["findings"]:
        lines.append(
            f"- [{finding['severity']}/{finding['status']}] {finding['component']}: "
            f"{_redact_path(finding['evidence'])}"
        )
        if finding.get("remediation"):
            lines.append(f"  Fix: {finding['remediation']}")
    return "\n".join(lines) + "\n"


def create_server(state: ControlCenterState) -> ThreadingHTTPServer:
    handler = _handler_factory(state)
    return ThreadingHTTPServer((state.host, state.port), handler)


def serve_control_center(
    *,
    host: str = DEFAULT_CONTROL_CENTER_HOST,
    port: int = DEFAULT_CONTROL_CENTER_PORT,
    open_browser: bool = False,
) -> None:
    if not _is_loopback_host(host):
        raise ValueError("Control Center host must be localhost or a loopback address.")
    selected_port = find_available_tcp_port(host, port)
    sse_port = find_available_tcp_port(DEFAULT_SSE_HOST, DEFAULT_SSE_PORT)
    state = ControlCenterState(
        host=host,
        port=selected_port,
        sse_host=DEFAULT_SSE_HOST,
        sse_port=sse_port,
    )
    server = create_server(state)
    url = f"http://{host}:{selected_port}/"
    if selected_port != port:
        print(f"Control Center port {port} is busy; using {selected_port}.")
    print(f"Serving fls-pilot Control Center at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped Control Center.")
    finally:
        state.shutdown()
        server.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the local FL Studio Pilot Control Center.")
    parser.add_argument("--host", default=DEFAULT_CONTROL_CENTER_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_CONTROL_CENTER_PORT)
    parser.add_argument("--open", action="store_true", help="Open the Control Center in a browser.")
    args = parser.parse_args(argv)
    if not _is_loopback_host(args.host):
        parser.error("--host must be localhost or a loopback address")
    serve_control_center(host=args.host, port=args.port, open_browser=args.open)


def _handler_factory(state: ControlCenterState):
    class ControlCenterHandler(BaseHTTPRequestHandler):
        server_version = "FLSPilotControlCenter/1.0"

        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/index.html"}:
                self._serve_static("index.html", "text/html; charset=utf-8")
            elif self.path == "/app.js":
                self._serve_static("app.js", "application/javascript; charset=utf-8")
            elif self.path == "/styles.css":
                self._serve_static("styles.css", "text/css; charset=utf-8")
            elif self.path.startswith("/assets/") and self.path.endswith(".png"):
                self._serve_static(self.path.lstrip("/"), "image/png")
            elif self.path == "/api/status":
                self._json(collect_status(state))
            elif self.path == "/api/client-snippets":
                self._json(client_snippets(state))
            elif self.path == "/api/setup/report":
                self._text(setup_report(state), content_type="text/markdown; charset=utf-8")
            else:
                self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            body = self._read_json()
            if self.path == "/api/refresh":
                self._json(collect_status(state, refresh=True))
            elif self.path == "/api/process/daemon/start":
                self._json(_start_daemon(state))
            elif self.path == "/api/process/daemon/stop":
                self._json(_stop_process(state, "daemon"))
            elif self.path == "/api/process/sse/start":
                self._json(_start_sse(state))
            elif self.path == "/api/process/sse/test":
                self._json(_test_sse(state))
            elif self.path == "/api/process/sse/stop":
                self._json(_stop_process(state, "sse"))
            elif self.path == "/api/setup/confirm-step":
                step = str(body.get("step", ""))
                self._json(_confirm_step(state, step))
            else:
                self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {}
            return data if isinstance(data, dict) else {}

        def _serve_static(self, name: str, content_type: str) -> None:
            try:
                data = resources.files(STATIC_PACKAGE).joinpath(name).read_bytes()
            except FileNotFoundError:
                self._json({"ok": False, "error": "static asset not found"}, status=500)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, data: Any, *, status: int | HTTPStatus = HTTPStatus.OK) -> None:
            payload = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _text(self, data: str, *, content_type: str) -> None:
            payload = data.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ControlCenterHandler


def _start_daemon(state: ControlCenterState) -> dict[str, Any]:
    with state.lock:
        existing = state.processes.get("daemon")
        if existing and existing.running:
            return {"ok": True, "process": existing.to_dict(), "message": "daemon already running"}

        health = _daemon_health(state.daemon_host, state.daemon_port)
        if health.get("reachable"):
            state.daemon_fallback_port = None
            return {
                "ok": True,
                "external": True,
                "state": "external",
                "message": (
                    "A fls-pilot daemon is already reachable at "
                    f"{state.daemon_host}:{state.daemon_port}."
                ),
            }
        port_status = tcp_port_status(state.daemon_host, state.daemon_port)
        if not port_status["available"]:
            fallback = int(port_status["fallback_port"])
            state.daemon_fallback_port = fallback
            return {
                "ok": False,
                "state": "port_conflict",
                "message": (
                    f"Port {state.daemon_host}:{state.daemon_port} is occupied by "
                    "a non-daemon process. "
                    f"Start the daemon with FLS_PILOT_TCP_PORT={fallback}."
                ),
                "fallback_port": fallback,
            }

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FLS_PILOT_TCP_HOST"] = state.daemon_host
        env["FLS_PILOT_TCP_PORT"] = str(state.daemon_port)
        proc = _spawn("daemon", [sys.executable, "-m", "fls_pilot.daemon"], env)
        state.processes["daemon"] = proc
        state.daemon_fallback_port = None
        return {"ok": True, "process": proc.to_dict()}


def _start_sse(state: ControlCenterState) -> dict[str, Any]:
    with state.lock:
        existing = state.processes.get("sse")
        if existing and existing.running:
            probe = _probe_sse_connection(state)
            return {
                "ok": True,
                "process": existing.to_dict(),
                "message": "SSE server already running",
                "probe": probe,
            }

        selected = find_available_tcp_port(state.sse_host, DEFAULT_SSE_PORT)
        state.sse_port = selected
        state.sse_probe = _sse_probe_state(
            "checking",
            "SSE server started. Testing the MCP connection...",
            state.sse_host,
            selected,
        )
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FLS_PILOT_TRANSPORT"] = "tcp"
        daemon_host, daemon_port = _selected_daemon_endpoint(state)
        env["FLS_PILOT_TCP_HOST"] = daemon_host
        env["FLS_PILOT_TCP_PORT"] = str(daemon_port)
        env["FLS_PILOT_SERVER_TRANSPORT"] = "sse"
        env["FLS_PILOT_SSE_HOST"] = state.sse_host
        env["FLS_PILOT_SSE_PORT"] = str(selected)
        proc = _spawn(
            "sse",
            [sys.executable, "-m", "fls_pilot.server", "--sse", "--port", str(selected)],
            env,
        )
        state.processes["sse"] = proc
        probe = _probe_sse_connection(state)
        return {
            "ok": True,
            "process": proc.to_dict(),
            "url": _sse_url(state.sse_host, selected),
            "probe": probe,
        }


def _test_sse(state: ControlCenterState) -> dict[str, Any]:
    with state.lock:
        proc = state.processes.get("sse")
        if proc is None or not proc.running:
            state.sse_probe = _sse_probe_state(
                "not_required",
                "SSE server is stopped. Start it only if your MCP client uses SSE/HTTP.",
                state.sse_host,
                state.sse_port,
            )
            return {
                "ok": False,
                "state": "stopped",
                "message": "SSE server is not running.",
                "probe": dict(state.sse_probe),
            }
        probe = _probe_sse_connection(state)
        return {"ok": probe.get("state") == "ok", "probe": probe}


def _stop_process(state: ControlCenterState, name: str) -> dict[str, Any]:
    with state.lock:
        proc = state.processes.get(name)
        if proc is None:
            if name == "sse":
                state.sse_probe = _sse_probe_state(
                    "not_required",
                    "SSE server is stopped. Start it only if your MCP client uses SSE/HTTP.",
                    state.sse_host,
                    state.sse_port,
                )
            return {"ok": True, "state": "stopped", "message": f"{name} is not managed here"}
        _stop_managed_process(proc)
        if name == "sse":
            state.sse_probe = _sse_probe_state(
                "not_required",
                "SSE server stopped. SSE is only needed for MCP clients that use SSE/HTTP.",
                state.sse_host,
                state.sse_port,
            )
        return {"ok": True, "process": proc.to_dict()}


def _confirm_step(state: ControlCenterState, step: str) -> dict[str, Any]:
    if step not in MANUAL_CHECKPOINTS:
        return {"ok": False, "error": f"unknown setup checkpoint: {step}"}
    with state.lock:
        state.checkpoints[step] = {"status": "user_confirmed", "updated_at": _now_iso()}
    return collect_status(state, refresh=True)


def _spawn(name: str, args: list[str], env: dict[str, str]) -> ManagedProcess:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        env=env,
        cwd=os.getcwd(),
    )
    managed = ManagedProcess(name=name, args=args, env=env, process=proc, started_at=_now_iso())
    for stream_name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        if stream is None:
            continue
        thread = threading.Thread(
            target=_read_stream,
            args=(managed, stream_name, stream),
            daemon=True,
        )
        thread.start()
        managed.reader_threads.append(thread)
    return managed


def _read_stream(managed: ManagedProcess, stream_name: str, stream: Any) -> None:
    for line in iter(stream.readline, ""):
        managed.logs.append(f"{stream_name}: {line.rstrip()}")


def _stop_managed_process(proc: ManagedProcess) -> None:
    if proc.running:
        proc.process.terminate()
        try:
            proc.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.process.kill()
            proc.process.wait(timeout=5)


def _process_status(state: ControlCenterState) -> dict[str, Any]:
    managed = {name: proc.to_dict() for name, proc in state.processes.items()}
    for name in ("daemon", "sse"):
        if name not in managed:
            managed[name] = {"state": "stopped", "logs": []}
    managed["sse"]["probe"] = dict(state.sse_probe)
    daemon_host, daemon_port = _selected_daemon_endpoint(state)
    daemon_health = _daemon_health(daemon_host, daemon_port)
    daemon_proc = state.processes.get("daemon")
    if daemon_health.get("reachable") and not (daemon_proc and daemon_proc.running):
        managed["daemon"] = {"state": "external", "health": daemon_health, "logs": []}
    else:
        managed["daemon"]["health"] = daemon_health
    return managed


def _port_state(state: ControlCenterState) -> dict[str, dict[str, Any]]:
    _, daemon_selected = _selected_daemon_endpoint(state)
    return {
        "control_center": {
            "host": state.host,
            "preferred_port": DEFAULT_CONTROL_CENTER_PORT,
            "selected_port": state.port,
            "fallback_port": None if state.port == DEFAULT_CONTROL_CENTER_PORT else state.port,
        },
        "sse": {
            "host": state.sse_host,
            "preferred_port": DEFAULT_SSE_PORT,
            "available": can_bind_tcp(state.sse_host, DEFAULT_SSE_PORT),
            "selected_port": state.sse_port,
            "fallback_port": None if state.sse_port == DEFAULT_SSE_PORT else state.sse_port,
        },
        "daemon": {
            "host": state.daemon_host,
            "preferred_port": state.daemon_port,
            "available": can_bind_tcp(state.daemon_host, state.daemon_port),
            "selected_port": daemon_selected,
            "fallback_port": state.daemon_fallback_port,
        },
        "dashboard": tcp_port_status(DEFAULT_CONTROL_CENTER_HOST, 8765),
    }


def _group_findings(findings: list[doctor.Finding]) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "environment": [],
        "midi": [],
        "controller": [],
        "daemon": [],
        "mcp_stdio": [],
        "mcp_sse": [],
        "mcp_apply": [],
        "optional_dependencies": [],
        "other": [],
    }
    for finding in findings:
        key = _finding_group(finding.component)
        groups[key].append(finding.to_dict())
    return groups


def _finding_group(component: str) -> str:
    lowered = component.lower()
    if "python" in lowered or "core dependencies" in lowered:
        return "environment"
    if "optional" in lowered:
        return "optional_dependencies"
    if "midi" in lowered or "loopmidi" in lowered or "iac" in lowered:
        return "midi"
    if "daemon" in lowered or "bridge" in lowered:
        return "daemon"
    if "controller" in lowered or "heartbeat" in lowered or "ping" in lowered:
        return "controller"
    if "stdio" in lowered:
        return "mcp_stdio"
    if "sse" in lowered or "http" in lowered:
        return "mcp_sse"
    if "mcp_apply" in lowered or "piano roll" in lowered:
        return "mcp_apply"
    return "other"


def _readiness(
    findings: list[doctor.Finding],
    checkpoints: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blockers = [f for f in findings if f.severity == "blocker" and f.status != "ok"]
    manual = [f for f in findings if f.status in {"manual_check", "probe_needed"}]
    if blockers:
        state = "blocked"
    elif manual and not checkpoints:
        state = "needs_manual_action"
    else:
        state = "ready_for_review"
    write_ready = state == "ready_for_review" and "ran_mcp_apply" in checkpoints
    if write_ready:
        state = "ready_for_write_tools"
    return {
        "state": state,
        "blocker_count": len(blockers),
        "manual_count": len(manual),
        "read_only_review_ready": not blockers,
        "write_tools_ready": write_ready,
    }


def _setup_guidance(
    *,
    groups: dict[str, list[dict[str, Any]]],
    readiness: dict[str, Any],
    processes: dict[str, Any],
    ports: dict[str, dict[str, Any]],
    daemon_autostart: dict[str, Any],
    sse_probe: dict[str, Any],
) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []

    if _group_needs_action(groups, "environment"):
        guidance.append(
            _guidance_item(
                title="Fix the Python environment",
                status="blocked",
                text=_group_guidance_text(
                    groups,
                    "environment",
                    "Run the installer again or install the missing package, then re-check setup.",
                ),
                groups=["environment"],
                action_label="Re-check",
                action_path="/api/refresh",
            )
        )
        return guidance

    daemon_process = processes.get("daemon", {})
    daemon_running = _process_running(daemon_process)
    daemon_start_action_shown = False
    autostart_state = str(daemon_autostart.get("state") or "")
    if autostart_state in {"started", "starting", "external", "failed"}:
        daemon_status = _daemon_startup_status(
            autostart_state,
            daemon_process=daemon_process,
            groups=groups,
        )
        daemon_action_path = "/api/refresh"
        daemon_action_label = "Re-check"
        if daemon_status == "action needed" and not daemon_running:
            daemon_action_path = "/api/process/daemon/start"
            daemon_action_label = "Start daemon"
            daemon_start_action_shown = True
        guidance.append(
            _guidance_item(
                title="Daemon startup",
                status=daemon_status,
                text=_daemon_startup_text(
                    daemon_autostart=daemon_autostart,
                    daemon_process=daemon_process,
                    groups=groups,
                ),
                groups=["daemon"],
                action_label=daemon_action_label,
                action_path=daemon_action_path,
            )
        )

    if (
        _group_needs_action(groups, "daemon")
        and not daemon_running
        and not daemon_start_action_shown
    ):
        guidance.append(
            _guidance_item(
                title="Start the local daemon",
                status="action needed",
                text=(
                    "The daemon owns the MIDI bridge. Start it before checking FL Studio. "
                    f"Target port: {ports.get('daemon', {}).get('host', '127.0.0.1')}:"
                    f"{ports.get('daemon', {}).get('selected_port', 'unknown')}."
                ),
                groups=["daemon"],
                action_label="Start daemon",
                action_path="/api/process/daemon/start",
            )
        )

    if _group_needs_action(groups, "midi"):
        guidance.append(
            _guidance_item(
                title="Create MIDI loopback ports",
                status=_group_status(groups, "midi"),
                text=_group_guidance_text(
                    groups,
                    "midi",
                    "Create FLStudioPilot RX and FLStudioPilot TX, then re-check setup.",
                ),
                groups=["midi"],
                checkpoint="created_midi_ports",
                action_label="I did this",
            )
        )

    if _group_needs_action(groups, "controller"):
        guidance.append(
            _guidance_item(
                title="Connect FL Studio to the controller",
                status=_group_status(groups, "controller"),
                text=_group_guidance_text(
                    groups,
                    "controller",
                    (
                        "Open FL Studio, enable FLStudioPilot RX as the controller input, "
                        "set FLStudioPilot TX to the same port number, then re-check."
                    ),
                ),
                groups=["controller"],
                checkpoint="configured_fl_midi",
                action_label="I did this",
            )
        )

    if _group_needs_action(groups, "mcp_sse"):
        guidance.append(
            _guidance_item(
                title="Check MCP SSE",
                status=_group_status(groups, "mcp_sse"),
                text=_group_guidance_text(
                    groups,
                    "mcp_sse",
                    "Start the SSE server only if your MCP client uses SSE, then re-check.",
                ),
                groups=["mcp_sse"],
                action_label="Start SSE server",
                action_path="/api/process/sse/start",
            )
        )

    sse_probe_state = str(sse_probe.get("state") or "")
    if sse_probe_state in {"ok", "failed", "checking"}:
        guidance.append(
            _guidance_item(
                title="MCP SSE connection",
                status=(
                    "OK"
                    if sse_probe_state == "ok"
                    else ("checking" if sse_probe_state == "checking" else "action needed")
                ),
                text=str(sse_probe.get("message") or "SSE connection test has no detail."),
                groups=["mcp_sse"],
                action_label="Re-test SSE",
                action_path="/api/process/sse/test",
            )
        )

    if _group_needs_action(groups, "mcp_apply"):
        guidance.append(
            _guidance_item(
                title="Arm Piano Roll note writing",
                status=_group_status(groups, "mcp_apply"),
                text=_group_guidance_text(
                    groups,
                    "mcp_apply",
                    "Run MCP_Apply once from the Piano Roll script menu if you need note writing.",
                ),
                groups=["mcp_apply"],
                checkpoint="ran_mcp_apply",
                action_label="I did this",
            )
        )

    if not guidance:
        guidance.append(
            _guidance_item(
                title="Setup is ready",
                status="OK",
                text=(
                    "Read-only workflows are ready."
                    if readiness.get("read_only_review_ready")
                    else "No next setup action is available from the current checks."
                ),
                groups=[],
                action_label="Re-check",
                action_path="/api/refresh",
            )
        )

    return guidance


def _daemon_startup_status(
    autostart_state: str,
    *,
    daemon_process: dict[str, Any],
    groups: dict[str, list[dict[str, Any]]],
) -> str:
    if autostart_state == "starting":
        return "starting"
    if autostart_state == "failed":
        return "action needed"
    if not _process_running(daemon_process):
        return "action needed"
    if _group_needs_action(groups, "daemon"):
        return _group_status(groups, "daemon")
    return "OK"


def _daemon_startup_text(
    *,
    daemon_autostart: dict[str, Any],
    daemon_process: dict[str, Any],
    groups: dict[str, list[dict[str, Any]]],
) -> str:
    if not _process_running(daemon_process):
        return "Daemon is not running. Start the daemon, then re-check setup."
    if _group_needs_action(groups, "daemon"):
        return _group_guidance_text(
            groups,
            "daemon",
            "Daemon is running, but the bridge health check still needs attention.",
        )
    return str(daemon_autostart.get("message") or "Daemon is running.")


def _process_running(process: dict[str, Any]) -> bool:
    return bool(process.get("running")) or process.get("state") in {"running", "external"}


def _guidance_item(
    *,
    title: str,
    status: str,
    text: str,
    groups: list[str],
    action_label: str | None = None,
    action_path: str | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "status": status,
        "text": text,
        "groups": groups,
        "action_label": action_label,
        "action_path": action_path,
        "checkpoint": checkpoint,
    }


def _group_status(groups: dict[str, list[dict[str, Any]]], group: str) -> str:
    findings = groups.get(group, [])
    failed = next((item for item in findings if item.get("status") == "failed"), None)
    if failed:
        return "blocked" if failed.get("severity") == "blocker" else "action needed"
    manual = next(
        (
            item
            for item in findings
            if item.get("status") in {"manual_check", "probe_needed"}
        ),
        None,
    )
    if manual:
        return "manual check"
    return "OK" if findings else "not required"


def _group_needs_action(groups: dict[str, list[dict[str, Any]]], group: str) -> bool:
    return _group_status(groups, group).lower() not in {"ok", "not required"}


def _group_guidance_text(
    groups: dict[str, list[dict[str, Any]]],
    group: str,
    fallback: str,
) -> str:
    findings = [
        item
        for item in groups.get(group, [])
        if item.get("status") in {"failed", "manual_check", "probe_needed"}
    ]
    if not findings:
        return fallback
    first = findings[0]
    evidence = str(first.get("evidence") or fallback)
    remediation = str(first.get("remediation") or "")
    return f"{evidence} {remediation}".strip()


def _daemon_health(host: str, port: int) -> dict[str, Any]:
    try:
        with socket.create_connection((host, int(port)), timeout=0.3) as sock:
            sock.sendall(b'{"op":"health"}\n')
            sock.settimeout(0.5)
            raw = sock.recv(4096)
    except OSError:
        return {"reachable": False}
    try:
        data = json.loads(raw.decode("utf-8").strip())
    except json.JSONDecodeError:
        return {"reachable": False, "invalid_response": True}
    data["reachable"] = True
    return data


def _resolve_daemon_endpoint() -> tuple[str, int]:
    host = os.environ.get("FLS_PILOT_TCP_HOST", DEFAULT_TCP_HOST)
    raw_port = os.environ.get("FLS_PILOT_TCP_PORT", str(DEFAULT_TCP_PORT))
    try:
        port = int(raw_port)
        if port <= 0 or port > 65535:
            raise ValueError
    except ValueError:
        port = DEFAULT_TCP_PORT
    return host, port


def _selected_daemon_endpoint(state: ControlCenterState) -> tuple[str, int]:
    return state.daemon_host, state.daemon_fallback_port or state.daemon_port


def _console_script_path(script: str) -> str:
    scripts_dir = Path(sys.executable).parent
    suffix = ".exe" if os.name == "nt" else ""
    candidate = scripts_dir / f"{script}{suffix}"
    return str(candidate) if candidate.exists() else script


def _daemon_terminal_command(host: str, port: int) -> str:
    command = _console_script_path("fls-pilot-daemon")
    if host == DEFAULT_TCP_HOST and port == DEFAULT_TCP_PORT:
        return command
    return _prefixed_command(
        {
            "FLS_PILOT_TCP_HOST": host,
            "FLS_PILOT_TCP_PORT": str(port),
        },
        command,
    )


def _sse_terminal_command(state: ControlCenterState, command: str) -> str:
    daemon_host, daemon_port = _selected_daemon_endpoint(state)
    return _prefixed_command(
        {
            "FLS_PILOT_TRANSPORT": "tcp",
            "FLS_PILOT_TCP_HOST": daemon_host,
            "FLS_PILOT_TCP_PORT": str(daemon_port),
            "FLS_PILOT_SSE_PORT": str(state.sse_port),
        },
        f"{command} --sse --port {state.sse_port}",
    )


def _prefixed_command(env: dict[str, str], command: str) -> str:
    if os.name == "nt":
        prefix = " && ".join(f'set "{key}={value}"' for key, value in env.items())
        return f"{prefix} && {command}"
    prefix = " ".join(f"{key}={value}" for key, value in env.items())
    return f"{prefix} {command}"


def _process_state_text(proc: dict[str, Any]) -> str:
    if "state" in proc:
        return str(proc["state"])
    if proc.get("running"):
        return "running"
    if proc.get("returncode") is not None:
        return f"exited ({proc['returncode']})"
    return "stopped"


def _redact_args(args: list[str]) -> list[str]:
    return [_redact_path(arg) for arg in args]


def _redact_path(value: Any) -> str:
    text = str(value)
    home = str(Path.home())
    if home and home in text:
        return text.replace(home, "~")
    return text


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


if __name__ == "__main__":
    main()
