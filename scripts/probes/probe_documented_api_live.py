#!/usr/bin/env python3
"""LIVE: false-positive probe for documented FL APIs that failed a sweep.

Use this before demoting a documented Image-Line API to api-limited. The probe:

- confirms the API names are present through api_probe/dir,
- tries the smallest rollback-safe write,
- retries documented mixer writes with the target track selected, and
- reports INCONCLUSIVE instead of treating one failed live readback as final.

Pre-req:
- FL Studio open with the fixture project copy loaded.
- fls-pilot daemon running (TCP).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("FLS_PILOT_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fls_pilot import protocol, safety  # noqa: E402
from fls_pilot.connection import FLCommandFailed, get_bridge  # noqa: E402


@dataclass
class ProbeResult:
    label: str
    status: str
    detail: str


def _report(status: str, label: str, detail: str) -> ProbeResult:
    print(f"[{status}] {label}: {detail}")
    return ProbeResult(label=label, status=status, detail=detail)


def _dir_names(bridge, module: str) -> set[str]:
    names: list[str] = []
    start = 0
    while True:
        row = bridge.call(protocol.CMD_API_PROBE, {"op": "dir", "module": module, "start": start})
        names.extend(str(n) for n in row.get("names", []) or [])
        next_start = row.get("next_start")
        if next_start is None:
            break
        start = int(next_start)
    return set(names)


def _require_api(available: set[str], module: str, names: tuple[str, ...]) -> ProbeResult:
    missing = [name for name in names if name not in available]
    if missing:
        return _report(
            "INCONCLUSIVE",
            f"{module} API presence",
            f"documented names not exposed on this build: {missing}",
        )
    return _report("PASS", f"{module} API presence", f"found {', '.join(names)}")


def _rollback_latest(bridge, label: str) -> bool:
    rb = safety.rollback_last_change(bridge)
    if not rb.get("ok"):
        _report("FAIL", label, f"rollback failed: {rb}")
        return False
    return True


def _probe_pattern_length(bridge) -> ProbeResult:
    selected = int(bridge.call(protocol.CMD_PATTERN_SELECTED, {}).get("selected", 1))
    before = bridge.call(protocol.CMD_PATTERN_GET, {"index": selected})
    before_len = float(before.get("length", 16))
    wanted = before_len + 1.0 if before_len < 63 else max(1.0, before_len - 1.0)
    label = f"patterns.setPatternLength pattern={selected}"

    try:
        result = safety.safe_write(
            bridge,
            tool="documented_api_probe_pattern_length",
            scope=f"pattern:{selected}",
            command=protocol.CMD_PATTERN_SET_LENGTH,
            params={"index": selected, "beats": wanted},
            build_restore=lambda snap: {
                "command": protocol.CMD_PATTERN_SET_LENGTH,
                "params": {"index": selected, "beats": float(snap.get("length", before_len))},
            },
        )
    except FLCommandFailed as exc:
        return _report("INCONCLUSIVE", label, f"write command failed despite documented API: {exc}")

    after_len = float(result.get("after", {}).get("length", before_len))
    ok = abs(after_len - wanted) <= 0.01
    rolled_back = _rollback_latest(bridge, label)
    restored = bridge.call(protocol.CMD_PATTERN_GET, {"index": selected})
    restored_ok = abs(float(restored.get("length", before_len)) - before_len) <= 0.01

    if ok and rolled_back and restored_ok:
        return _report("PASS", label, f"{before_len:g} -> {after_len:g} -> restored")
    if rolled_back and restored_ok:
        return _report(
            "INCONCLUSIVE",
            label,
            f"write/readback did not stick: wanted={wanted:g}, got={after_len:g}; restored",
        )
    return _report("FAIL", label, f"restore mismatch after probe: {restored}")


def _valid_slots(bridge) -> list[tuple[int, int, str]]:
    selected = int(bridge.call(protocol.CMD_MIXER_SELECTED, {}).get("track", 0))
    scan_tracks = list(dict.fromkeys([selected, 49, 50] + list(range(1, 61))))
    out: list[tuple[int, int, str]] = []
    for track in scan_tracks:
        for slot in range(10):
            try:
                row = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
            except Exception:
                continue
            if row.get("valid"):
                out.append((track, slot, str(row.get("name") or "")))
                if len(out) >= 6:
                    return out
    return out


def _select_track_with_rollback(bridge, track: int) -> bool:
    try:
        result = safety.safe_write(
            bridge,
            tool="documented_api_probe_select_track",
            scope="mixer_selection",
            command=protocol.CMD_MIXER_SELECT_TRACK,
            params={"track": track},
            verify=("track", track),
            build_restore=lambda snap: {
                "command": protocol.CMD_MIXER_SELECT_TRACK,
                "params": {"track": int(snap.get("track", 0))},
            },
        )
    except FLCommandFailed as exc:
        _report("INCONCLUSIVE", f"select track {track}", f"selection command failed: {exc}")
        return False
    selected = bool(result.get("ok")) and int(result.get("after", {}).get("track", -1)) == track
    if not selected:
        _rollback_latest(bridge, f"select track {track}")
    return selected


def _probe_slot_mix_one(
    bridge, track: int, slot: int, name: str, *, select_first: bool
) -> ProbeResult:
    label = f"mixer.setPluginMixLevel track={track} slot={slot} {name!r}"
    if select_first and not _select_track_with_rollback(bridge, track):
        return _report("INCONCLUSIVE", label, "could not select target track before write")

    before = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    before_mix = float(before.get("mix", 0.8))
    wanted = 0.2 if before_mix > 0.4 else 0.8
    try:
        result = safety.safe_write(
            bridge,
            tool="documented_api_probe_slot_mix",
            scope=f"effect_slot:{track}:{slot}",
            command=protocol.CMD_MIXER_SET_SLOT_MIX,
            params={"track": track, "slot": slot, "mix": wanted},
            build_restore=lambda snap: {
                "command": protocol.CMD_MIXER_SET_SLOT_MIX,
                "params": {"track": track, "slot": slot, "mix": float(snap.get("mix", before_mix))},
            },
        )
    except FLCommandFailed as exc:
        if select_first:
            _rollback_latest(bridge, f"{label} selection")
        return _report("INCONCLUSIVE", label, f"write command failed: {exc}")

    after_mix = float(result.get("after", {}).get("mix", before_mix))
    ok = abs(after_mix - wanted) <= 0.03
    rolled_back = _rollback_latest(bridge, label)
    restored = bridge.call(protocol.CMD_MIXER_GET_SLOT, {"track": track, "slot": slot})
    restored_ok = abs(float(restored.get("mix", before_mix)) - before_mix) <= 0.03
    if select_first:
        _rollback_latest(bridge, f"{label} selection")

    suffix = "selected target variant" if select_first else "direct variant"
    if ok and rolled_back and restored_ok:
        return _report("PASS", label, f"{suffix}: {before_mix:.3f} -> {after_mix:.3f} -> restored")
    if rolled_back and restored_ok:
        return _report(
            "INCONCLUSIVE",
            label,
            f"{suffix}: wanted={wanted:.3f}, got={after_mix:.3f}; restored",
        )
    return _report("FAIL", label, f"{suffix}: restore mismatch after probe")


def _probe_slot_mix(bridge) -> ProbeResult:
    slots = _valid_slots(bridge)
    if not slots:
        return _report("SKIP", "mixer.setPluginMixLevel", "no loaded effect slots found")

    direct_results = []
    selected_results = []
    for track, slot, name in slots[:3]:
        direct_results.append(_probe_slot_mix_one(bridge, track, slot, name, select_first=False))
        time.sleep(0.05)
        selected_results.append(_probe_slot_mix_one(bridge, track, slot, name, select_first=True))
        if direct_results[-1].status == "PASS" or selected_results[-1].status == "PASS":
            return _report(
                "PASS", "mixer.setPluginMixLevel", f"verified on track={track} slot={slot}"
            )
    if any(row.status == "FAIL" for row in direct_results + selected_results):
        return _report("FAIL", "mixer.setPluginMixLevel", "restore failed in one variant")
    return _report(
        "INCONCLUSIVE", "mixer.setPluginMixLevel", "documented API present but no variant stuck"
    )


def _probe_native_eq(bridge) -> ProbeResult:
    selected = int(bridge.call(protocol.CMD_MIXER_SELECTED, {}).get("track", 0))
    tracks = list(dict.fromkeys([selected, 1, 49, 50]))
    inconclusive: list[str] = []
    for track in tracks:
        try:
            before = bridge.call(protocol.CMD_MIXER_GET_EQ, {"track": track})
        except Exception:
            continue
        band = next((b for b in before.get("bands", []) if int(b.get("band", -1)) == 1), None)
        if band is None:
            continue
        before_gain = float(band.get("gain", 0.0))
        wanted = max(-1.0, min(1.0, before_gain + (0.1 if before_gain <= 0 else -0.1)))
        try:
            result = safety.safe_write(
                bridge,
                tool="documented_api_probe_native_eq",
                scope=f"mixer_eq:{track}",
                command=protocol.CMD_MIXER_SET_EQ,
                params={"track": track, "band": 1, "gain": wanted},
                build_restore=lambda snap, t=track, g=before_gain: {
                    "command": protocol.CMD_MIXER_SET_EQ,
                    "params": {"track": t, "band": 1, "gain": g},
                },
            )
        except FLCommandFailed as exc:
            return _report("INCONCLUSIVE", "mixer native EQ", f"write command failed: {exc}")

        after_band = next(
            (b for b in result.get("after", {}).get("bands", []) if int(b.get("band", -1)) == 1),
            None,
        )
        after_gain = float((after_band or {}).get("gain", before_gain))
        ok = abs(after_gain - wanted) <= 0.02
        rolled_back = _rollback_latest(bridge, f"mixer native EQ track={track}")
        restored = bridge.call(protocol.CMD_MIXER_GET_EQ, {"track": track})
        restored_band = next(
            (b for b in restored.get("bands", []) if int(b.get("band", -1)) == 1),
            None,
        )
        restored_ok = (
            restored_band
            and abs(float(restored_band.get("gain", before_gain)) - before_gain) <= 0.02
        )
        if ok and rolled_back and restored_ok:
            return _report("PASS", "mixer native EQ", f"verified gain write on track={track}")
        if rolled_back and restored_ok:
            inconclusive.append(f"track={track} wanted={wanted:.3f} got={after_gain:.3f}; restored")
            continue
        return _report("FAIL", "mixer native EQ", f"track={track}: restore mismatch")
    if inconclusive:
        return _report("INCONCLUSIVE", "mixer native EQ", "; ".join(inconclusive))
    return _report("SKIP", "mixer native EQ", "no readable EQ target found")


def main() -> int:
    bridge = get_bridge()
    pong = bridge.call(protocol.CMD_PING, {})
    print(f"FL: {pong.get('fl_version')} | build={pong.get('build')}")
    print("Running documented API false-positive probes with immediate rollback...")

    pattern_names = _dir_names(bridge, "patterns")
    mixer_names = _dir_names(bridge, "mixer")
    results = [
        _require_api(pattern_names, "patterns", ("getPatternLength", "setPatternLength")),
        _require_api(mixer_names, "mixer", ("getPluginMixLevel", "setPluginMixLevel")),
        _require_api(
            mixer_names, "mixer", ("getEqGain", "setEqGain", "getEqFrequency", "setEqFrequency")
        ),
    ]
    if "setEqBandwidth" in mixer_names or "getEqBandwidth" in mixer_names:
        results.append(_require_api(mixer_names, "mixer", ("getEqBandwidth", "setEqBandwidth")))
    else:
        results.append(
            _report("SKIP", "mixer EQ bandwidth API", "bandwidth API absent on this build")
        )

    results.extend(
        [
            _probe_pattern_length(bridge),
            _probe_slot_mix(bridge),
            _probe_native_eq(bridge),
        ]
    )

    bad = [row for row in results if row.status == "FAIL"]
    inconclusive = [row for row in results if row.status == "INCONCLUSIVE"]

    print("\n=== Documented API probe summary ===")
    print(f"pass={sum(r.status == 'PASS' for r in results)}")
    print(f"skip={sum(r.status == 'SKIP' for r in results)}")
    print(f"inconclusive={len(inconclusive)}")
    print(f"fail={len(bad)}")
    if inconclusive:
        print("Inconclusive documented APIs must stay probe-gated, not api-limited.")
    if bad:
        print("At least one probe failed to restore cleanly; inspect before further writes.")
        return 1
    return 1 if inconclusive else 0


if __name__ == "__main__":
    raise SystemExit(main())
