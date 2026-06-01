#!/usr/bin/env python3
"""LIVE step sequencer check -- talks to FL through the running daemon (TCP).

Run AFTER reloading the controller script (build marker channels-v17):

    python scripts/test_step_sequencer_live.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Force the TCP transport so we go through the daemon (which owns MIDI)
os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.connection import get_bridge  # noqa: E402
from fl_studio_mcp.tools import channels  # noqa: E402
from fl_studio_mcp import safety  # noqa: E402


def main() -> int:
    b = get_bridge()

    pong = b.call("ping", {})
    build = pong.get("build")
    print(f"FL: {pong.get('fl_version')} | build={build}")

    # Preflight: if the controller is stale, these commands will be unknown.
    try:
        _ = b.call("channel_get_steps", {"channel": 0})
    except Exception as e:
        msg = str(e)
        if "Unknown command" in msg:
            print(
                "\n[BLOCKED] Controller script is stale (missing step sequencer handlers). "
                "Reload FL MIDI scripts and restart the daemon, then re-run."
            )
            print(f"Details: {e}")
            return 2
        raise

    channel = 0
    step = 0

    print(f"\n--- Reading initial step grid for channel {channel} ---")
    before = b.call("channel_get_steps", {"channel": channel})
    init_grid = before["grid"][step]
    init_vel = before["vel"][step]
    init_pan = before["pan"][step]
    init_shift = before["shift"][step]
    init_rep = before["rep"][step]
    print(f"Step {step}: grid={init_grid}, vel={init_vel}, pan={init_pan}, shift={init_shift}, repeat={init_rep}")

    print(f"\n--- Mutating step {step} on channel {channel} ---")
    # Toggle step state, change velocity to 0.9, panning to -0.5 (left), repeat to 2
    new_val = not init_grid
    new_vel = 0.9
    new_pan = -0.5
    new_rep = 2
    
    # We use safe_write to execute this write
    write_res = safety.safe_write(
        b,
        tool="channel_set_grid_bit",
        scope=f"channel_steps:{channel}",
        command="channel_set_steps",
        params={
            "channel": channel,
            "steps": [
                {
                    "step": step,
                    "value": new_val,
                    "velocity": new_vel,
                    "pan": new_pan,
                    "repeat": new_rep,
                }
            ],
        },
        build_restore=lambda before_state: channels._steps_restore(channel, before_state),
    )
    print("Write result:", "SUCCESS" if write_res.get("ok") else "FAILED")

    # Read back
    time.sleep(0.1)
    after = b.call("channel_get_steps", {"channel": channel})
    read_grid = after["grid"][step]
    read_vel = after["vel"][step]
    read_pan = after["pan"][step]
    read_rep = after["rep"][step]
    print(f"Readback step {step}: grid={read_grid}, vel={read_vel}, pan={read_pan}, repeat={read_rep}")
    
    # Verify write (focus on grid bit since step parameters are not fully writable via API)
    if read_grid == new_val:
        print("  => Verification: WRITE SUCCESSFUL (grid bit toggled)")
    else:
        print("  => Verification: WRITE MISMATCH")
        return 1

    print("\n--- Triggering Rollback ---")
    rollback_res = safety.rollback_last_change(b)
    print("Rollback result:", "SUCCESS" if rollback_res.get("ok") else "FAILED")

    # Read back again
    time.sleep(0.1)
    restored = b.call("channel_get_steps", {"channel": channel})
    rest_grid = restored["grid"][step]
    print(f"Post-rollback step {step}: grid={rest_grid}")

    if rest_grid == init_grid:
        print("  => Verification: ROLLBACK SUCCESSFUL (grid bit restored)")
        return 0
    else:
        print("  => Verification: ROLLBACK FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
