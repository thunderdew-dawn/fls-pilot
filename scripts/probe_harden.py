#!/usr/bin/env python3
"""Note-bridge hardening probe: ui/midi API for auto-open + arm assessment.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/probe_harden.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol                       # noqa: E402
from fl_studio_mcp.connection import get_bridge           # noqa: E402


def dir_of(b, module, filt=None):
    names, start = [], 0
    while True:
        r = b.call(protocol.CMD_API_PROBE, {"op": "dir", "module": module, "start": start}, timeout=15.0)
        names.extend(r.get("names", []))
        nxt = r.get("next_start")
        if nxt is None or int(nxt) <= start:
            break
        start = int(nxt)
    if filt:
        names = [n for n in names if any(f in n.lower() for f in filt)]
    return names


def main() -> int:
    b = get_bridge()
    b.open()
    if not b.is_alive():
        print("Bridge not alive -- reloaded to harden-v12? daemon up?")
        return 1

    print("=== ui (window / script / menu related) ===")
    print(dir_of(b, "ui", ["window", "script", "show", "visible", "piano", "menu", "run", "focus"]))

    print("\n=== midi wid* (window constants) ===")
    print(dir_of(b, "midi", ["wid"]))

    print("\n=== ensure_piano_roll ===")
    print(b.call(protocol.CMD_ENSURE_PIANO_ROLL, {}, timeout=15.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
