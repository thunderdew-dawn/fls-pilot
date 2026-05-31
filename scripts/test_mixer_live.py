#!/usr/bin/env python3
"""LIVE Mixer check -- talks to FL through the running daemon (TCP).

Run AFTER reloading the controller script (build marker channels-v28):

    python scripts/test_mixer_live.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Force the TCP transport so we go through the daemon
os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp import safety  # noqa: E402

def main() -> int:
    b = get_bridge()

    pong = b.call("ping", {})
    build = pong.get("build")
    print(f"FL: {pong.get('fl_version')} | build={build} (want channels-v28)")
    if build != "channels-v28":
        print("\n[WARNING] Controller not reloaded yet. Please in FL Studio:")
        print("  1. Open Options > MIDI Settings (F10).")
        print("  2. Click 'Refresh device list' at the bottom.")
        print("  Or open View > Script output and click 'Reload script'.")
        print("  Then re-run this test script.")
        return 1

    # 1. Test get_track details & dock_side
    print("\n--- Getting mixer track 5 details ---")
    track_details = b.call("mixer_get_track", {"index": 5})
    print("Track 5 details:", track_details)
    if "dock_side" in track_details and "stereo_sep" in track_details:
        print(f"  => Verification: SUCCESS (dock_side={track_details['dock_side']}, stereo_sep={track_details['stereo_sep']})")
    else:
        print("  => Verification: FAILED (no dock_side or stereo_sep)")
        return 1

    # 2. Test select track write + rollback
    print("\n--- Testing track selection & rollback ---")
    init_sel = b.call("mixer_selected", {})
    init_track = init_sel["track"]
    print(f"Initial selected track: {init_track}")

    target_track = 6 if init_track != 6 else 5
    print(f"Selecting track {target_track}...")
    
    write_res = safety.safe_write(
        b,
        tool="mixer_select_track",
        scope="mixer_selection",
        command="mixer_select_track",
        params={"track": target_track},
        verify=("track", target_track),
        build_restore=lambda before_state: {
            "command": "mixer_select_track",
            "params": {"track": before_state["track"]},
        },
    )
    print("Write result:", "SUCCESS" if write_res.get("ok") else "FAILED")

    # Read back selection
    time.sleep(0.1)
    after_sel = b.call("mixer_selected", {})
    print(f"Readback selected track: {after_sel['track']}")

    if after_sel["track"] == target_track:
        print("  => Verification: SELECT TRACK SUCCESSFUL")
    else:
        print("  => Verification: SELECT TRACK FAILED")
        return 1

    # Rollback selection
    print("Triggering rollback...")
    rollback_res = safety.rollback_last_change(b)
    print("Rollback result:", "SUCCESS" if rollback_res.get("ok") else "FAILED")

    time.sleep(0.1)
    restored_sel = b.call("mixer_selected", {})
    print(f"Post-rollback selected track: {restored_sel['track']}")

    if restored_sel["track"] == init_track:
        print("  => Verification: ROLLBACK SUCCESSFUL")
    else:
        print("  => Verification: ROLLBACK FAILED")
        return 1

    # 3. Test routing write + rollback
    print("\n--- Testing track routing & rollback ---")
    routing_before = b.call("mixer_get_routing", {"track": 5})
    init_enabled = any(r.get("dst") == 10 for r in routing_before.get("routes_to", []))
    print(f"Initial routing from track 5 to track 10: {init_enabled}")

    new_routing = not init_enabled
    print(f"Setting routing from 5 to 10 to {new_routing}...")
    
    write_route_res = safety.safe_write(
        b,
        tool="mixer_set_route",
        scope="route:5:10",
        command="mixer_set_route",
        params={"src": 5, "dst": 10, "enabled": new_routing},
        verify=("enabled", new_routing),
        build_restore=lambda before_state: {
            "command": "mixer_set_route",
            "params": {"src": 5, "dst": 10, "enabled": before_state["enabled"]},
        },
    )
    print("Write route result:", "SUCCESS" if write_route_res.get("ok") else "FAILED")

    # Read back routing
    time.sleep(0.1)
    routing_after = b.call("mixer_get_routing", {"track": 5})
    after_enabled = any(r.get("dst") == 10 for r in routing_after.get("routes_to", []))
    print(f"Readback routing: {after_enabled}")

    if after_enabled == new_routing:
        print("  => Verification: ROUTING WRITE SUCCESSFUL")
    else:
        print("  => Verification: ROUTING WRITE FAILED")
        return 1

    # Rollback routing
    print("Triggering rollback...")
    rollback_route_res = safety.rollback_last_change(b)
    print("Rollback route result:", "SUCCESS" if rollback_route_res.get("ok") else "FAILED")

    time.sleep(0.1)
    routing_restored = b.call("mixer_get_routing", {"track": 5})
    restored_enabled = any(r.get("dst") == 10 for r in routing_restored.get("routes_to", []))
    print(f"Post-rollback routing: {restored_enabled}")

    if restored_enabled == init_enabled:
        print("  => Verification: ROUTING ROLLBACK SUCCESSFUL")
    else:
        print("  => Verification: ROUTING ROLLBACK FAILED")
        return 1

    # 3.5 Test stereo separation write + rollback
    print("\n--- Testing stereo separation & rollback ---")
    track_details_init = b.call("mixer_get_track", {"index": 5})
    init_sep = track_details_init["stereo_sep"]
    print(f"Initial stereo separation: {init_sep}")

    target_sep = 0.5 if init_sep != 0.5 else -0.5
    print(f"Setting stereo separation to {target_sep}...")

    write_sep_res = safety.safe_write(
        b,
        tool="mixer_set_stereo_separation",
        scope="mixer_track:5",
        command="mixer_set_stereo_sep",
        params={"track": 5, "value": target_sep},
        build_restore=lambda before_state: {
            "command": "mixer_set_stereo_sep",
            "params": {"track": 5, "value": before_state["stereo_sep"]},
        },
    )
    print("Write separation result:", "SUCCESS" if write_sep_res.get("ok") else "FAILED")

    # Read back separation
    time.sleep(0.1)
    track_details_after = b.call("mixer_get_track", {"index": 5})
    after_sep = track_details_after["stereo_sep"]
    print(f"Readback stereo separation: {after_sep}")

    if abs(after_sep - target_sep) < 0.01:
        print("  => Verification: STEREO SEPARATION WRITE SUCCESSFUL")
    else:
        print("  => Verification: STEREO SEPARATION WRITE FAILED")
        return 1

    # Rollback separation
    print("Triggering rollback...")
    rollback_sep_res = safety.rollback_last_change(b)
    print("Rollback separation result:", "SUCCESS" if rollback_sep_res.get("ok") else "FAILED")

    time.sleep(0.1)
    track_details_restored = b.call("mixer_get_track", {"index": 5})
    restored_sep = track_details_restored["stereo_sep"]
    print(f"Post-rollback stereo separation: {restored_sep}")

    if abs(restored_sep - init_sep) < 0.01:
        print("  => Verification: STEREO SEPARATION ROLLBACK SUCCESSFUL")
    else:
        print("  => Verification: STEREO SEPARATION ROLLBACK FAILED")
        return 1

    # 4. Test peak levels
    print("\n--- Testing peak levels measurement ---")
    peaks = b.call("mixer_get_peaks", {"track": 0})
    print("Master peaks raw:", peaks)
    
    from fl_studio_mcp.music import levels
    res_levels = levels.measure_track_level(b, 0, samples=5, interval_ms=50)
    print("Master measured level info:", res_levels)

    print("\nALL LIVE MIXER CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
