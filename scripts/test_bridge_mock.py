#!/usr/bin/env python3
"""Mock TCP bridge smoke test.

This test does not require FL Studio, MIDI ports, or a running daemon. It starts
a tiny local TCP server that speaks the daemon's newline-delimited JSON protocol
and verifies the TCPBridge health path, command path, error mapping, and
apply_notes proxy shape.
"""

from __future__ import annotations

import json
import socketserver
import sys
import threading
from pathlib import Path

# Allow running from a checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import (  # noqa: E402
    FLCommandFailed,
    FLNotRunning,
    TCPBridge,
)


class _State:
    bpm = 120.0
    calls: list[dict] = []


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        req = json.loads(raw.decode("utf-8"))
        op = req.get("op")

        if op == "health":
            resp = {"alive": True, "heartbeat_age": 0.01}
        elif op == "call":
            resp = _handle_call(req)
        elif op == "apply_notes":
            notes = req.get("notes") or []
            resp = {
                "ok": True,
                "mode": req.get("mode"),
                "triggered": bool(req.get("trigger")),
                "notes_written": len(notes),
            }
        else:
            resp = {"ok": False, "exc": "Error", "error": f"unknown op: {op}"}

        self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))


def _handle_call(req: dict) -> dict:
    command = req.get("cmd")
    params = req.get("params") or {}
    _State.calls.append({"cmd": command, "params": params})

    if command == protocol.CMD_PING:
        return {"ok": True, "data": {"protocol_version": protocol.PROTOCOL_VERSION}}
    if command == protocol.CMD_GET_TEMPO:
        return {"ok": True, "data": {"bpm": _State.bpm}}
    if command == protocol.CMD_SET_TEMPO:
        _State.bpm = float(params["bpm"])
        return {"ok": True, "data": {"bpm": _State.bpm}}
    if command == "simulate_not_running":
        return {"ok": False, "exc": "FLNotRunning", "error": "controller offline"}
    return {
        "ok": False,
        "exc": "FLCommandFailed",
        "code": "client",
        "error": f"unknown command: {command}",
    }


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def check(label: str, condition: bool) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    return condition


def main() -> int:
    server = _Server(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bridge = TCPBridge(host="127.0.0.1", port=server.server_address[1], default_timeout=2.0)

    passed = True
    try:
        passed &= check("bridge reports alive", bridge.is_alive() is True)
        passed &= check("heartbeat age is recent", bridge.heartbeat_age() == 0.01)

        ping = bridge.call(protocol.CMD_PING)
        passed &= check(
            "ping protocol version",
            ping["protocol_version"] == protocol.PROTOCOL_VERSION,
        )

        tempo = bridge.call(protocol.CMD_GET_TEMPO)
        passed &= check("initial tempo", tempo["bpm"] == 120.0)

        changed = bridge.call(protocol.CMD_SET_TEMPO, {"bpm": 128.0})
        passed &= check("set tempo", changed["bpm"] == 128.0)

        notes = [{"pitch": 60, "time_bars": 0.0, "length_bars": 0.25}]
        applied = bridge.apply_notes(notes, mode="append", trigger=True)
        passed &= check(
            "apply_notes proxied",
            applied["notes_written"] == 1 and applied["mode"] == "append",
        )

        try:
            bridge.call("simulate_not_running")
        except FLNotRunning:
            passed &= check("FLNotRunning mapped", True)
        else:
            passed &= check("FLNotRunning mapped", False)

        try:
            bridge.call("not_a_command")
        except FLCommandFailed as exc:
            passed &= check("command failure mapped", exc.code == "client")
        else:
            passed &= check("command failure mapped", False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
