#!/usr/bin/env python3
"""LIVE: Plugin parameter write/readback/rollback probe.

Looks for an already-loaded plugin on mixer tracks 49 or 50, changes one
parameter (by index) via the safety layer, reads it back, then immediately
rolls it back and verifies restoration.

This does NOT load plugins and will skip/exit if no plugin is present.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402


def _pass(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def _pick_slot(b, track: int) -> int | None:
    info = b.call(protocol.CMD_PLUGIN_LIST, {"track": track})
    for row in info.get("slots", []) or []:
        # plugin_list returns only filled slots; treat any row with a slot index
        # (and typically a name) as a valid candidate.
        try:
            slot = int(row.get("slot", 0))
        except Exception:
            continue
        name = str(row.get("name") or "").strip()
        if name:
            return slot
    return None


def main() -> int:
    b = get_bridge()
    pong = b.call(protocol.CMD_PING, {})
    print(f"FL: {pong.get('fl_version')} | build={pong.get('build')}")

    ok = True

    track = None
    slot = None
    for t in (49, 50):
        try:
            s = _pick_slot(b, t)
        except Exception:
            continue
        if s is not None:
            track, slot = t, s
            break

    if track is None or slot is None:
        print("[SKIP] No loaded plugin found on mixer tracks 49/50.")
        print("       Load any plugin on one of those tracks (manual), then re-run.")
        return 0

    print(f"Target plugin: track={track} slot={slot}")

    # Read preset name (read-only)
    try:
        preset = b.call(protocol.CMD_PLUGIN_GET_PRESET_NAME, {"track": track, "slot": slot})
        _pass(f"preset name read: {preset.get('plugin_name')!r} / {preset.get('name_f3') or preset.get('name_f6')}")
    except Exception as e:
        _fail(f"preset name read failed: {type(e).__name__}: {e}")
        ok = False

    # Param write / rollback probe
    param = 0
    before = b.call(protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": param})
    before_v = float(before.get("v", 0.0))
    want = 0.75 if before_v < 0.5 else 0.25

    res = safety.safe_write(
        b,
        tool="plugin_param_live_probe",
        scope=f"plugin_param:{track}:{slot}:{param}",
        command=protocol.CMD_PLUGIN_SET_PARAM,
        params={"track": track, "slot": slot, "param": param, "value": want},
        build_restore=lambda snap: {
            "command": protocol.CMD_PLUGIN_SET_PARAM,
            "params": {"track": track, "slot": slot, "param": param, "value": float(snap.get("v", before_v))},
        },
    )
    if not res.get("ok"):
        _fail(f"param write failed: {res}")
        return 1

    time.sleep(0.05)
    after = b.call(protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": param})
    after_v = float(after.get("v", 0.0))
    if abs(after_v - want) <= 0.02:
        _pass("plugin_set_param write/readback")
    else:
        _fail(f"plugin_set_param mismatch: wanted {want:.3f} got {after_v:.3f}")
        ok = False

    rb = safety.rollback_last_change(b)
    if rb.get("ok"):
        _pass("rollback ok")
    else:
        _fail(f"rollback failed: {rb}")
        return 1

    time.sleep(0.05)
    restored = b.call(protocol.CMD_PLUGIN_GET_PARAM, {"track": track, "slot": slot, "param": param})
    restored_v = float(restored.get("v", 0.0))
    if abs(restored_v - before_v) <= 0.02:
        _pass("plugin_set_param restore verified")
    else:
        _fail(f"restore mismatch: before {before_v:.3f} got {restored_v:.3f}")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
