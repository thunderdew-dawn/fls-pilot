from __future__ import annotations

import io
import json
import subprocess
from unittest import mock

from fls_pilot import control_center, doctor, runtime_config


def _finding(component: str, severity: str = "blocker", status: str = "ok") -> doctor.Finding:
    return doctor.Finding(component, severity, status, "evidence", "fix", "source")


def _state(*, port: int = 8766, sse_port: int = 8080) -> control_center.ControlCenterState:
    return control_center.ControlCenterState(
        host="127.0.0.1",
        port=port,
        sse_host="127.0.0.1",
        sse_port=sse_port,
    )


def test_state_uses_configured_daemon_endpoint(monkeypatch):
    monkeypatch.setenv("FLS_PILOT_TCP_HOST", "127.0.0.2")
    monkeypatch.setenv("FLS_PILOT_TCP_PORT", "9791")

    state = _state()

    assert state.daemon_host == "127.0.0.2"
    assert state.daemon_port == 9791


def test_status_groups_doctor_findings(monkeypatch):
    findings = [
        _finding("Python Environment"),
        _finding("MIDI/IAC/loopMIDI Ports"),
        _finding("FL Studio Controller Script"),
        _finding("Piano Roll MCP_Apply Script", "advisory", "manual_check"),
    ]
    monkeypatch.setattr(control_center.doctor, "run_all_checks", lambda **_: findings)
    state = _state()

    status = control_center.collect_status(state)

    assert status["control_center"]["port"] == 8766
    assert status["groups"]["midi"][0]["component"] == "MIDI/IAC/loopMIDI Ports"
    assert status["groups"]["mcp_apply"][0]["status"] == "manual_check"
    assert status["readiness"]["read_only_review_ready"] is True


def test_manual_checkpoint_is_user_confirmed(monkeypatch):
    monkeypatch.setattr(control_center.doctor, "run_all_checks", lambda **_: [])
    state = _state()

    result = control_center._confirm_step(state, "ran_mcp_apply")

    assert result["checkpoints"]["ran_mcp_apply"]["status"] == "user_confirmed"
    assert result["readiness"]["write_tools_ready"] is True


def test_client_snippets_use_selected_sse_port():
    state = _state(sse_port=8091)

    snippets = control_center.client_snippets(state)

    assert snippets["chatgpt"]["url"] == "http://localhost:8091/sse"
    assert snippets["claude"]["mcpServers"]["fls-pilot"]["env"]["FLS_PILOT_TRANSPORT"] == "tcp"


def test_client_snippets_use_daemon_fallback_port():
    state = _state()
    state.daemon_fallback_port = 9788

    snippets = control_center.client_snippets(state)

    assert snippets["claude"]["mcpServers"]["fls-pilot"]["env"]["FLS_PILOT_TCP_PORT"] == "9788"
    assert "9788" in snippets["terminal"]["daemon"]
    assert "FLS_PILOT_TCP_PORT=9788" in snippets["terminal"]["sse"]


def test_start_daemon_reports_non_daemon_port_conflict(monkeypatch):
    state = _state()
    monkeypatch.setattr(control_center, "_daemon_health", lambda host, port: {"reachable": False})
    monkeypatch.setattr(
        control_center,
        "tcp_port_status",
        lambda host, port: {"available": False, "fallback_port": 9788},
    )
    monkeypatch.setattr(control_center, "find_available_tcp_port", lambda host, port: 9788)

    result = control_center._start_daemon(state)

    assert result["ok"] is False
    assert result["state"] == "port_conflict"
    assert result["fallback_port"] == 9788
    assert state.daemon_fallback_port == 9788


def test_start_sse_uses_fallback_port_and_safe_args(monkeypatch):
    state = _state()
    state.daemon_fallback_port = 9788
    monkeypatch.setattr(control_center, "find_available_tcp_port", lambda host, port: 8081)
    spawned: dict = {}

    def fake_spawn(name, args, env):  # noqa: ANN001, ANN202
        spawned["name"] = name
        spawned["args"] = args
        spawned["env"] = env
        process = mock.Mock(spec=subprocess.Popen)
        process.pid = 123
        process.poll.return_value = None
        return control_center.ManagedProcess(
            name=name,
            args=args,
            env=env,
            process=process,
            started_at="now",
        )

    monkeypatch.setattr(control_center, "_spawn", fake_spawn)

    result = control_center._start_sse(state)

    assert result["url"] == "http://localhost:8081/sse"
    assert state.sse_port == 8081
    assert spawned["args"][-2:] == ["--port", "8081"]
    assert spawned["env"]["FLS_PILOT_TRANSPORT"] == "tcp"
    assert spawned["env"]["FLS_PILOT_TCP_HOST"] == "127.0.0.1"
    assert spawned["env"]["FLS_PILOT_TCP_PORT"] == "9788"


def test_start_daemon_uses_configured_endpoint_and_child_env(monkeypatch):
    state = _state()
    state.daemon_host = "127.0.0.2"
    state.daemon_port = 9791
    health_calls = []
    spawned: dict = {}

    monkeypatch.setattr(
        control_center,
        "_daemon_health",
        lambda host, port: health_calls.append((host, port)) or {"reachable": False},
    )
    monkeypatch.setattr(
        control_center,
        "tcp_port_status",
        lambda host, port: {
            "host": host,
            "preferred_port": port,
            "available": True,
            "selected_port": port,
            "fallback_port": None,
        },
    )

    def fake_spawn(name, args, env):  # noqa: ANN001, ANN202
        spawned["name"] = name
        spawned["args"] = args
        spawned["env"] = env
        process = mock.Mock(spec=subprocess.Popen)
        process.pid = 123
        process.poll.return_value = None
        return control_center.ManagedProcess(
            name=name,
            args=args,
            env=env,
            process=process,
            started_at="now",
        )

    monkeypatch.setattr(control_center, "_spawn", fake_spawn)

    result = control_center._start_daemon(state)

    assert result["ok"] is True
    assert health_calls == [("127.0.0.2", 9791)]
    assert spawned["env"]["FLS_PILOT_TCP_HOST"] == "127.0.0.2"
    assert spawned["env"]["FLS_PILOT_TCP_PORT"] == "9791"


def test_process_status_checks_selected_daemon_fallback(monkeypatch):
    state = _state()
    state.daemon_fallback_port = 9788
    calls = []

    monkeypatch.setattr(
        control_center,
        "_daemon_health",
        lambda host, port: calls.append((host, port)) or {"reachable": True},
    )

    status = control_center._process_status(state)

    assert calls == [("127.0.0.1", 9788)]
    assert status["daemon"]["state"] == "external"


def test_setup_report_redacts_home(monkeypatch):
    home_text = str(control_center.Path.home())
    findings = [doctor.Finding("Python Environment", "blocker", "ok", home_text, "", "source")]
    monkeypatch.setattr(control_center.doctor, "run_all_checks", lambda **_: findings)
    state = _state()

    report = control_center.setup_report(state)

    assert home_text not in report
    assert "~" in report


def test_setup_report_handles_running_managed_process(monkeypatch):
    monkeypatch.setattr(control_center.doctor, "run_all_checks", lambda **_: [])
    monkeypatch.setattr(control_center, "_daemon_health", lambda host, port: {"reachable": False})
    monkeypatch.setattr(control_center, "can_bind_tcp", lambda host, port: True)
    state = _state()
    process = mock.Mock(spec=subprocess.Popen)
    process.pid = 123
    process.poll.return_value = None
    state.processes["sse"] = control_center.ManagedProcess(
        name="sse",
        args=["fls-pilot", "--sse"],
        env={},
        process=process,
        started_at="now",
    )

    report = control_center.setup_report(state)

    assert "- sse: running" in report


def test_port_state_uses_selected_sse_port(monkeypatch):
    monkeypatch.setattr(control_center, "can_bind_tcp", lambda host, port: False)
    monkeypatch.setattr(
        control_center,
        "tcp_port_status",
        lambda host, port: {
            "host": host,
            "preferred_port": port,
            "available": True,
            "selected_port": port,
            "fallback_port": None,
        },
    )
    state = _state(sse_port=8081)

    ports = control_center._port_state(state)

    assert ports["sse"]["selected_port"] == 8081
    assert ports["sse"]["fallback_port"] == 8081


def test_port_state_reports_configured_daemon_port(monkeypatch):
    monkeypatch.setattr(control_center, "can_bind_tcp", lambda host, port: port == 9791)
    monkeypatch.setattr(
        control_center,
        "tcp_port_status",
        lambda host, port: {
            "host": host,
            "preferred_port": port,
            "available": True,
            "selected_port": port,
            "fallback_port": None,
        },
    )
    state = _state()
    state.daemon_host = "127.0.0.2"
    state.daemon_port = 9791

    ports = control_center._port_state(state)

    assert ports["daemon"]["host"] == "127.0.0.2"
    assert ports["daemon"]["preferred_port"] == 9791
    assert ports["daemon"]["available"] is True
    assert ports["daemon"]["selected_port"] == 9791


def test_runtime_port_status_finds_fallback(monkeypatch):
    calls = []

    def fake_can_bind(host, port):  # noqa: ANN001, ANN202
        calls.append((host, port))
        return port == 9002

    monkeypatch.setattr(runtime_config, "can_bind_tcp", fake_can_bind)

    status = runtime_config.tcp_port_status("127.0.0.1", 9000)

    assert status["available"] is False
    assert status["selected_port"] == 9002
    assert status["fallback_port"] == 9002
    assert calls[:3] == [("127.0.0.1", 9000), ("127.0.0.1", 9001), ("127.0.0.1", 9002)]


def test_http_status_endpoint(monkeypatch):
    monkeypatch.setattr(control_center.doctor, "run_all_checks", lambda **_: [])
    state = _state(port=0)
    handler_cls = control_center._handler_factory(state)
    request = b"GET /api/status HTTP/1.1\r\nHost: localhost\r\n\r\n"

    class OneShotHandler(handler_cls):
        def setup(self):  # noqa: ANN001
            self.rfile = io.BytesIO(request)
            self.wfile = io.BytesIO()

        def finish(self):  # noqa: ANN001
            pass

    server = mock.Mock()
    server.server_version = "test"
    server.sys_version = ""
    server.timeout = 1
    server._BaseServer__is_shut_down = mock.Mock()
    server._BaseServer__shutdown_request = False

    handler = OneShotHandler(request=None, client_address=("127.0.0.1", 1234), server=server)
    response = handler.wfile.getvalue().decode("utf-8")
    payload = json.loads(response.split("\r\n\r\n", 1)[1])
    assert payload["version"]


def test_main_rejects_non_loopback_host():
    with mock.patch("fls_pilot.control_center.serve_control_center") as serve:
        try:
            control_center.main(["--host", "0.0.0.0"])
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover - defensive
            raise AssertionError("main accepted a non-loopback host")
    serve.assert_not_called()
