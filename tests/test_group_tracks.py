#!/usr/bin/env python3
"""Slice 2 test: fl_group_tracks (exclusive bus) + one-shot rollback.

Groups two UNUSED Insert tracks (9, 10) into an unused bus (11) and renames the
bus -- audio-safe + fully reversible. Verifies exclusive routing (source -> bus
ON, source -> Master OFF, bus -> Master ON, bus renamed), then rolls the WHOLE
grouping back with a single fl_rollback_last_change and confirms pre == post.

    set FLSTUDIO_MCP_TRANSPORT=tcp
    python scripts/test_group_tracks.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.server import build_server  # noqa: E402

SOURCES = [9, 10]
BUS = 11
NEW_NAME = "TEST BUS"
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
    return sorted(d.get("dst") for d in info.get("routes_to", []))


def name_of(bridge, t):
    return bridge.call(protocol.CMD_MIXER_GET_TRACK, {"index": t}).get("name")


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller (slice2-route-v5) loaded? daemon up?")
        return 1

    m = build_server()

    def call(name, args):
        return unwrap(asyncio.run(m.call_tool(name, args)))

    pre = {t: routes_of(bridge, t) for t in SOURCES + [BUS]}
    pre_busname = name_of(bridge, BUS)
    print("pre routes:", pre, "| bus name:", repr(pre_busname))

    r = call("fl_group_tracks", {"sources": SOURCES, "bus": BUS, "name": NEW_NAME})
    print("group_tracks ->", {k: r.get(k) for k in ("ok", "sources", "bus", "name")})

    for s in SOURCES:
        rt = routes_of(bridge, s)
        check("source %d -> bus %d ONLY (exclusive)" % (s, BUS), rt == [BUS], f"routes={rt}")
    check(
        "bus %d -> Master(0) ON" % BUS,
        0 in routes_of(bridge, BUS),
        f"routes={routes_of(bridge, BUS)}",
    )
    check(
        "bus %d renamed to %r" % (BUS, NEW_NAME),
        name_of(bridge, BUS) == NEW_NAME,
        f"name={name_of(bridge, BUS)!r}",
    )

    rb = call("fl_rollback_last_change", {})
    print("rollback ->", rb.get("rolled_back"))
    check("rollback reverted group_tracks", rb.get("rolled_back") == "group_tracks")

    post = {t: routes_of(bridge, t) for t in SOURCES + [BUS]}
    post_busname = name_of(bridge, BUS)
    print("post routes:", post, "| bus name:", repr(post_busname))
    check("routes restored (pre == post)", post == pre, f"pre={pre} post={post}")
    check("bus name restored", post_busname == pre_busname, f"{post_busname!r} vs {pre_busname!r}")

    print("\n%d passed, %d failed" % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
