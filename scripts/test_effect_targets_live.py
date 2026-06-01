#!/usr/bin/env python3
"""LIVE: targeted rollback-safe probe for known effect tracks.

Default fixture:
- track 49: Fruity Limiter, sidechained from kick track 1
- track 50: Fruity Parametric EQ 2

The script does not load plugins or create routing. It only verifies the
existing state, performs smallest-practical temporary writes, rolls each write
back immediately, and verifies restoration.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp import protocol, safety  # noqa: E402
from fl_studio_mcp.connection import FLCommandFailed, fetch_all_pages, get_bridge  # noqa: E402

KICK_TRACK = 1
LIMITER_TRACK = 49
EQ2_TRACK = 50


def _pass(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _is_api_limited_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "api unavailable" in text or "unknown command" in text


def _plugin_slots(bridge, track: int) -> list[dict]:
    info = bridge.call(protocol.CMD_PLUGIN_LIST, {"track": track})
    return list(info.get("slots", []) or [])


def _find_slot(bridge, track: int, needle: str) -> dict | None:
    needle_l = needle.lower()
    for row in _plugin_slots(bridge, track):
        if needle_l in str(row.get("name") or "").lower():
            return row
    return None


def _route_active(bridge, src: int, dst: int) -> dict | None:
    routing = bridge.call(protocol.CMD_MIXER_GET_ROUTING, {"track": src})
    for row in routing.get("routes_to", []) or []:
        if int(row.get("dst", -1)) == dst:
            return row
    return None


def _plugin_params(bridge, track: int, slot: int) -> list[dict]:
    data = fetch_all_pages(
        bridge, protocol.CMD_PLUGIN_GET_PARAMS, "params", {"track": track, "slot": slot}
    )
    return list(data.get("params", []) or [])


def _preferred_param_indices(params: list[dict], names: tuple[str, ...]) -> list[int]:
    by_name = {str(row.get("name") or "").lower(): int(row["i"]) for row in params}
    preferred = []
    for name in names:
        idx = by_name.get(name.lower())
        if idx is not None:
            preferred.append(idx)
    for row in params:
        idx = int(row["i"])
        if idx not in preferred:
            preferred.append(idx)
    return preferred


def _safe_plugin_param_probe(
    bridge, *, track: int, slot: int, label: str, preferred_names: tuple[str, ...]
) -> bool:
    params = _plugin_params(bridge, track, slot)
    for param in _preferred_param_indices(params, preferred_names):
        if _try_plugin_param_probe(bridge, track=track, slot=slot, param=param, label=label):
            return True
    _fail(f"{label}: no writable plugin parameter found")
    return False


def _try_plugin_param_probe(bridge, *, track: int, slot: int, param: int, label: str) -> bool:
    param_payload = {"track": track, "slot": slot, "param": param}
    before = bridge.call(protocol.CMD_PLUGIN_GET_PARAM, param_payload)
    before_v = float(before.get("v", 0.0))
    wanted = 0.75 if before_v < 0.5 else 0.25
    param_name = str(before.get("name") or f"param {param}")

    result = safety.safe_write(
        bridge,
        tool=f"{label}_plugin_param_probe",
        scope=f"plugin_param:{track}:{slot}:{param}",
        command=protocol.CMD_PLUGIN_SET_PARAM,
        params={"track": track, "slot": slot, "param": param, "value": wanted},
        build_restore=lambda snap: {
            "command": protocol.CMD_PLUGIN_SET_PARAM,
            "params": {
                "track": track,
                "slot": slot,
                "param": param,
                "value": float(snap.get("v", before_v)),
            },
        },
    )
    if not result.get("ok"):
        _fail(f"{label}: param write failed: {result}")
        return False

    time.sleep(0.05)
    after = bridge.call(protocol.CMD_PLUGIN_GET_PARAM, param_payload)
    after_v = float(after.get("v", 0.0))
    ok = abs(after_v - wanted) <= 0.02
    if ok:
        _pass(f"{label}: plugin param write/readback ({param}: {param_name})")
    else:
        _warn(
            f"{label}: param {param} ({param_name}) did not stick "
            f"wanted={wanted:.3f} got={after_v:.3f}"
        )

    rollback = safety.rollback_last_change(bridge)
    if not rollback.get("ok"):
        _fail(f"{label}: rollback failed: {rollback}")
        return False

    time.sleep(0.05)
    restored = bridge.call(protocol.CMD_PLUGIN_GET_PARAM, param_payload)
    restored_v = float(restored.get("v", 0.0))
    if abs(restored_v - before_v) <= 0.02:
        if ok:
            _pass(f"{label}: plugin param restore verified")
        return ok

    _fail(f"{label}: restore mismatch before={before_v:.3f} got={restored_v:.3f}")
    return False


def _safe_slot_mix_probe(bridge, *, track: int, slot: int, label: str) -> bool:
    before = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    before_mix = float(before.get("mix", 0.8))
    wanted = 0.2 if before_mix > 0.4 else 0.8

    result = safety.safe_write(
        bridge,
        tool=f"{label}_slot_mix_probe",
        scope=f"effect_slot:{track}:{slot}",
        command=protocol.CMD_MIXER_SET_SLOT_MIX,
        params={"track": track, "slot": slot, "mix": wanted},
        build_restore=lambda snap: {
            "command": protocol.CMD_MIXER_SET_SLOT_MIX,
            "params": {"track": track, "slot": slot, "mix": float(snap.get("mix", before_mix))},
        },
    )
    after_mix = float(result.get("after", {}).get("mix", before_mix))
    ok = bool(result.get("ok")) and abs(after_mix - wanted) <= 0.03
    if ok:
        _pass(f"{label}: slot mix write/readback")
    else:
        _fail(f"{label}: slot mix mismatch: {result}")

    rollback = safety.rollback_last_change(bridge)
    if not rollback.get("ok"):
        _fail(f"{label}: slot mix rollback failed: {rollback}")
        return False

    restored = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    restored_mix = float(restored.get("mix", before_mix))
    if abs(restored_mix - before_mix) <= 0.03:
        _pass(f"{label}: slot mix restore verified")
        return ok

    _fail(f"{label}: slot mix restore mismatch before={before_mix:.3f} got={restored_mix:.3f}")
    return False


def _safe_slot_enabled_probe(bridge, *, track: int, slot: int, label: str) -> bool:
    before = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    before_enabled = bool(before.get("enabled", True))
    wanted = not before_enabled

    try:
        result = safety.safe_write(
            bridge,
            tool=f"{label}_slot_enabled_probe",
            scope=f"effect_slot:{track}:{slot}",
            command=protocol.CMD_MIXER_SET_SLOT_ENABLED,
            params={"track": track, "slot": slot, "enabled": wanted},
            verify=("enabled", wanted),
            build_restore=lambda snap: {
                "command": protocol.CMD_MIXER_SET_SLOT_ENABLED,
                "params": {
                    "track": track,
                    "slot": slot,
                    "enabled": bool(snap.get("enabled", before_enabled)),
                },
            },
        )
    except FLCommandFailed as exc:
        if _is_api_limited_error(exc):
            _warn(f"{label}: slot enabled write unavailable: {exc}")
            return True
        raise
    after_enabled = bool(result.get("after", {}).get("enabled", before_enabled))
    ok = bool(result.get("ok")) and after_enabled == wanted
    if ok:
        _pass(f"{label}: slot enabled write/readback")
    else:
        _fail(f"{label}: slot enabled mismatch: {result}")

    rollback = safety.rollback_last_change(bridge)
    if not rollback.get("ok"):
        _fail(f"{label}: slot enabled rollback failed: {rollback}")
        return False

    restored = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    restored_enabled = bool(restored.get("enabled", before_enabled))
    if restored_enabled == before_enabled:
        _pass(f"{label}: slot enabled restore verified")
        return ok

    _fail(f"{label}: slot enabled restore mismatch")
    return False


def main() -> int:
    bridge = get_bridge()
    pong = bridge.call(protocol.CMD_PING, {})
    print(f"FL: {pong.get('fl_version')} | build={pong.get('build')}")

    ok = True

    limiter = _find_slot(bridge, LIMITER_TRACK, "limiter")
    eq2 = _find_slot(bridge, EQ2_TRACK, "parametric eq 2")

    print(f"Track {LIMITER_TRACK} slots: {_plugin_slots(bridge, LIMITER_TRACK)}")
    print(f"Track {EQ2_TRACK} slots: {_plugin_slots(bridge, EQ2_TRACK)}")

    if limiter is None:
        _fail(f"track {LIMITER_TRACK}: Fruity Limiter not found")
        ok = False
    else:
        limiter_slot = int(limiter["slot"])
        _pass(f"track {LIMITER_TRACK}: found {limiter.get('name')!r} in slot {limiter_slot}")

        route = _route_active(bridge, KICK_TRACK, LIMITER_TRACK)
        if route is None:
            _warn(
                f"route {KICK_TRACK}->{LIMITER_TRACK} is not active; "
                "sidechain state not verified"
            )
        else:
            _pass(f"route {KICK_TRACK}->{LIMITER_TRACK} active: {route}")

        ok = _safe_slot_mix_probe(
            bridge, track=LIMITER_TRACK, slot=limiter_slot, label="fruity_limiter"
        ) and ok
        ok = _safe_slot_enabled_probe(
            bridge, track=LIMITER_TRACK, slot=limiter_slot, label="fruity_limiter"
        ) and ok
        ok = _safe_plugin_param_probe(
            bridge,
            track=LIMITER_TRACK,
            slot=limiter_slot,
            label="fruity_limiter",
            preferred_names=("Comp threshold", "Comp ratio", "Gain", "Limiter ceiling"),
        ) and ok

    if eq2 is None:
        _fail(f"track {EQ2_TRACK}: Fruity Parametric EQ 2 not found")
        ok = False
    else:
        eq2_slot = int(eq2["slot"])
        _pass(f"track {EQ2_TRACK}: found {eq2.get('name')!r} in slot {eq2_slot}")
        ok = _safe_slot_mix_probe(bridge, track=EQ2_TRACK, slot=eq2_slot, label="fruity_eq2") and ok
        ok = (
            _safe_slot_enabled_probe(bridge, track=EQ2_TRACK, slot=eq2_slot, label="fruity_eq2")
            and ok
        )
        ok = (
            _safe_plugin_param_probe(
                bridge,
                track=EQ2_TRACK,
                slot=eq2_slot,
                label="fruity_eq2",
                preferred_names=("Band 4 level", "Band 1 level", "Band 2 level"),
            )
            and ok
        )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
