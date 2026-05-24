#!/usr/bin/env python3
"""Micro-benchmark the controller commands to find the slow API.

Times existing commands so we can see per-call cost without guessing.
    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_timings.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402


def t(label, fn):
    t0 = time.perf_counter()
    try:
        r = fn()
        dt = (time.perf_counter() - t0) * 1000
        print("  %-42s %7.0f ms" % (label, dt))
        return r, dt
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        print("  %-42s %7.0f ms  FAIL %s" % (label, dt, e))
        return None, dt


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("bridge not alive")
        return 1

    print("timings (each is one full round trip):")
    t("ping", lambda: b.call(protocol.CMD_PING))
    t("mixer_get_routing(track=1)  [~16 getRouteSendActive]",
      lambda: b.call(protocol.CMD_MIXER_GET_ROUTING, {"track": 1}))
    t("mixer_get_routing_all       [~16x16 sends]",
      lambda: b.call(protocol.CMD_MIXER_GET_ROUTING_ALL, {"start": 0}, timeout=20.0))
    t("plugin_list(track=1 empty)  [10 isValid]",
      lambda: b.call(protocol.CMD_PLUGIN_LIST, {"track": 1}))
    t("plugin_list(track=2 EQ/rev/dly) [isValid+names]",
      lambda: b.call(protocol.CMD_PLUGIN_LIST, {"track": 2}))
    t("channel_routing_summary",
      lambda: b.call(protocol.CMD_CHANNEL_ROUTING_SUMMARY, {"start": 0}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
