#!/usr/bin/env python3
"""Slice 2 test: routing WRITE (fl_set_route) + rollback, via the real MCP tools.

Adds a send between two UNUSED Insert tracks (9 -> 1) so nothing audible
changes, asserts the write lands and the default ->Master send is untouched,
then rolls back and confirms the project returns to its exact prior routing.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_route_write.py [src] [dst]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.server import build_server  # noqa: E402

SRC = int(sys.argv[1]) if len(sys.argv) > 1 else 9
DST = int(sys.argv[2]) if len(sys.argv) > 2 else 1
_P = _F = 0


def check(label, cond, detail=""):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def unwrap(result):
    for attr in ("data", "structured_content", "structuredContent"):
        v = getattr(result, attr, None)
        if v is not None:
            return v
    return result


def routes_of(bridge, t):
    info = bridge.call(protocol.CMD_MIXER_GET_ROUTING, {"track": t})
    return {d.get("dst") for d in info.get("routes_to", [])}


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller (slice2-route-v5) loaded? daemon up?")
        return 1

    m = build_server()

    def call(name, args):
        return unwrap(asyncio.run(m.call_tool(name, args)))

    pre = routes_of(bridge, SRC)
    print("pre  routes of track %d: %s" % (SRC, sorted(x for x in pre if x is not None)))
    check("default %d -> Master(0) present" % SRC, 0 in pre)
    check("%d -> %d initially OFF" % (SRC, DST), DST not in pre)

    r = call("fl_set_route", {"src": SRC, "dst": DST, "enabled": True})
    print("set_route(%d->%d, on) -> after=%s" % (SRC, DST, r.get("after")))
    check(
        "set_route readback enabled=True",
        (r.get("after") or {}).get("enabled") is True,
        str(r.get("after")),
    )
    mid = routes_of(bridge, SRC)
    check(
        "%d -> %d now ON" % (SRC, DST),
        DST in mid,
        f"routes={sorted(x for x in mid if x is not None)}",
    )
    check("default %d -> Master still present" % SRC, 0 in mid)

    rb = call("fl_rollback_last_change", {})
    print(f"rollback -> {rb.get('rolled_back')}  restored={rb.get('restored')}")
    post = routes_of(bridge, SRC)
    print("post routes of track %d: %s" % (SRC, sorted(x for x in post if x is not None)))
    check(
        "rollback removed %d -> %d" % (SRC, DST),
        DST not in post,
        f"routes={sorted(x for x in post if x is not None)}",
    )
    check("post routing == pre routing", post == pre)

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
