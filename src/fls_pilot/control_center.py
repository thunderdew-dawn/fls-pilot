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
            state.last_findings = doctor.run_all_checks(
                server_transport="stdio",
                sse_host=state.sse_host,
                sse_port=state.sse_port,
                bridge_transport="tcp",
                tcp_host=daemon_host,
                tcp_port=daemon_port,
                smoke_timeout_seconds=1.5,
            )
        findings = [finding.to_dict() for finding in state.last_findings]
        groups = _group_findings(state.last_findings)
        readiness = _readiness(state.last_findings, state.checkpoints)
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
            "snippets": client_snippets(state),
            "dashboard": dashboard_data,
        }


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
            return {
                "ok": True,
                "process": existing.to_dict(),
                "message": "SSE server already running",
            }

        selected = find_available_tcp_port(state.sse_host, DEFAULT_SSE_PORT)
        state.sse_port = selected
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
        return {"ok": True, "process": proc.to_dict(), "url": f"http://localhost:{selected}/sse"}


def _stop_process(state: ControlCenterState, name: str) -> dict[str, Any]:
    with state.lock:
        proc = state.processes.get(name)
        if proc is None:
            return {"ok": True, "state": "stopped", "message": f"{name} is not managed here"}
        _stop_managed_process(proc)
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
    daemon_host, daemon_port = _selected_daemon_endpoint(state)
    daemon_health = _daemon_health(daemon_host, daemon_port)
    if daemon_health.get("reachable") and not state.processes.get("daemon"):
        managed["daemon"] = {"state": "external", "health": daemon_health, "logs": []}
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
