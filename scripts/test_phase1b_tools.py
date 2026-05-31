#!/usr/bin/env python3
"""Phase 1B tool-layer test: name resolution + safe_write + rollback.

Exercises the server-side tool logic WITHOUT needing Claude Desktop to reload
the MCP server: it calls the real module-level resolve_param_index() helper and
drives safety.safe_write / rollback_last_change exactly the way the
fl_plugin_set_param tool does internally.

    set FLSTUDIO_MCP_TRANSPORT=tcp        # route through the running daemon
    python scripts/test_phase1b_tools.py

Prereqs: FL open, controller reloaded WITH the plugin_get_param handler,
daemon running (if tcp). Targets mixer track 2 (Fruity Parametric EQ 2 in
slot 0, Fruity Reeverb 2 in slot 1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.tools.plugin import (  # noqa: E402
    ParamNotFound,
    resolve_param_index,
)

TRACK = 2
EQ_SLOT = 0
REV_SLOT = 1

_passed = 0
_failed = 0


def check(label, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")


def main() -> int:
    bridge = get_bridge()
    bridge.open()
    if not bridge.is_alive():
        print("Bridge not alive -- FL open? controller reloaded? daemon up?")
        return 1
    print("Heartbeat age:", bridge.heartbeat_age())

    # 1. name resolution ------------------------------------------------------
    print("\n[1] resolve_param_index")
    idx, name = resolve_param_index(bridge, TRACK, REV_SLOT, "Decay time")
    check("Reeverb 'Decay time' -> idx 5", idx == 5, "got idx=%d name=%r" % (idx, name))

    idx2, name2 = resolve_param_index(
        bridge, TRACK, EQ_SLOT, "band 3 freq"
    )  # case/space-insensitive
    check("EQ 'band 3 freq' (fuzzy) -> idx 9", idx2 == 9, "got idx=%d name=%r" % (idx2, name2))

    idx3, name3 = resolve_param_index(bridge, TRACK, EQ_SLOT, 35)  # integer passthrough
    check(
        "EQ int 35 -> 'Main level'",
        idx3 == 35 and "main" in name3.lower(),
        "got idx=%d name=%r" % (idx3, name3),
    )

    try:
        resolve_param_index(bridge, TRACK, EQ_SLOT, "no such knob")
        check("bogus name raises ParamNotFound", False, "did NOT raise")
    except ParamNotFound as e:
        check("bogus name raises ParamNotFound", True, (str(e)[:55] + "..."))

    # 2. name-based safe_write + rollback ------------------------------------
    print("\n[2] safe_write set (by name) + rollback")
    tgt_idx, tgt_name = resolve_param_index(bridge, TRACK, EQ_SLOT, "Band 1 level")
    before = bridge.call(
        protocol.CMD_PLUGIN_GET_PARAM, {"track": TRACK, "slot": EQ_SLOT, "param": tgt_idx}
    )
    orig = before["v"]
    print("  original %r [idx %d] = %s [%s]" % (tgt_name, tgt_idx, orig, before.get("s")))

    new_val = round(orig + 0.15, 4) if orig <= 0.5 else round(orig - 0.15, 4)
    scope = "plugin_param:%d:%d:%d" % (TRACK, EQ_SLOT, tgt_idx)
    res = safety.safe_write(
        bridge,
        tool="plugin_set_param",
        scope=scope,
        command=protocol.CMD_PLUGIN_SET_PARAM,
        params={"track": TRACK, "slot": EQ_SLOT, "param": tgt_idx, "value": new_val},
        build_restore=lambda b: {
            "command": protocol.CMD_PLUGIN_SET_PARAM,
            "params": {"track": TRACK, "slot": EQ_SLOT, "param": tgt_idx, "value": b["v"]},
        },
    )
    after_v = res["after"]["v"]
    print(f"  after set({new_val}) = {after_v} [{res['after'].get('s')}]")
    check("set landed on target", abs(after_v - new_val) < 0.02, f"want {new_val} got {after_v}")

    last = safety.get_changelog().recent(1)
    check("changelog recorded the write", bool(last) and last[0].get("tool") == "plugin_set_param")

    rb = safety.rollback_last_change(bridge)
    rb_v = (rb.get("restored") or {}).get("v")
    print(f"  rollback -> {rb_v} [{(rb.get('restored') or {}).get('s')}]")
    check(
        "rolled back to original",
        rb_v is not None and abs(rb_v - orig) < 0.02,
        f"want {orig} got {rb_v}",
    )

    print("\n%d passed, %d failed" % (_passed, _failed))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
