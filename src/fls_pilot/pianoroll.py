"""Piano-roll note authoring -- the generate-script bridge.

FL's pyscript sandbox blocks file I/O (read AND write), so we can't pass note
data via a job file. Instead we GENERATE a .pyscript with the notes baked in
(pyscript_gen), write it into FL's Piano roll scripts folder, then force-focus
FL and fire Ctrl+Alt+Y "Run last script again" (pyscript_trigger). FL re-reads
the file on that hotkey, so the fresh notes apply with no manual click.

This runs in a process that can write files + send keystrokes (the daemon, or
a normally-launched MCP server). Under the Store/MSIX MCP Client the MCP
server can't, so it delegates here via the daemon's "apply_notes" op.

One-time setup the user must do: run MCP_Apply once from the piano-roll
Scripting menu so it becomes FL's "last script" (then Ctrl+Alt+Y targets it).
"""

from __future__ import annotations

from .pyscript_gen import (
    write_apply_script,
    write_duplicate_script,
    write_marker_add_script,
    write_marker_clear_script,
    write_quantize_script,
    write_transpose_script,
    write_velocity_ramp_script,
)


def apply_notes(
    notes,
    mode="replace",
    trigger=True,
    quantize=None,
    snap_ends=False,
    transpose=None,
    duplicate_bars=None,
    velocity_ramp=None,
    marker_add=None,
    marker_clear=False,
):
    """Write a pyscript into MCP_Apply.pyscript and (optionally) trigger FL.

    Normally writes the given notes. If ``quantize`` (grid in bars) is set, writes
    a script that instead reads the score and snaps existing notes to that grid.
    If ``transpose`` (semitones) is set, writes a script that shifts pitch.
    Returns {ok, ..., script, triggered, focused, hint?}.
    """
    if marker_clear:
        path = write_marker_clear_script()
        result = {
            "ok": True,
            "action": "marker_clear",
            "script": path,
        }
    elif marker_add is not None:
        path = write_marker_add_script(
            marker_add.get("time_bars", 0.0),
            marker_add.get("name", "Marker"),
            mode=marker_add.get("mode", 0),
            ts_num=marker_add.get("ts_num"),
            ts_den=marker_add.get("ts_den"),
        )
        result = {
            "ok": True,
            "action": "marker_add",
            "marker": marker_add,
            "script": path,
        }
    elif duplicate_bars is not None:
        path = write_duplicate_script(float(duplicate_bars))
        result = {
            "ok": True,
            "action": "duplicate",
            "offset_bars": float(duplicate_bars),
            "script": path,
        }
    elif velocity_ramp is not None:
        start, end = velocity_ramp
        path = write_velocity_ramp_script(float(start), float(end))
        result = {
            "ok": True,
            "action": "velocity_ramp",
            "start": float(start),
            "end": float(end),
            "script": path,
        }
    elif transpose is not None:
        path = write_transpose_script(int(transpose))
        result = {
            "ok": True,
            "action": "transpose",
            "semitones": int(transpose),
            "script": path,
        }
    elif quantize is not None:
        path = write_quantize_script(float(quantize), snap_ends)
        result = {
            "ok": True,
            "action": "quantize",
            "grid_bars": float(quantize),
            "snap_ends": bool(snap_ends),
            "script": path,
        }
    else:
        path = write_apply_script(notes, mode)
        result = {"ok": True, "count": len(notes), "script": path, "mode": mode}

    if not trigger:
        result["triggered"] = False
        return result

    try:
        from .pyscript_trigger import trigger_run_last_script

        trig = trigger_run_last_script()
        result["triggered"] = True
        result["focused"] = trig.get("focused", False)
        # The trigger can't confirm the script actually ran. The Piano roll is
        # auto-opened by the caller, but Ctrl+Alt+Y only fires OUR script if
        # MCP_Apply was run once this FL session (no API to arm it). So if notes
        # don't appear, that one-time arm is the cause.
        result["setup"] = (
            "If notes did not appear: run 'MCP Apply' ONCE from the "
            "Piano roll Scripting menu this FL session (the only "
            "manual step -- arms Ctrl+Alt+Y; no FL API to automate it)."
        )
        if not trig.get("focused"):
            result["hint"] = (
                "Could not focus FL automatically -- click the FL Piano roll and press Ctrl+Alt+Y."
            )
    except Exception as e:
        # Script is written regardless; trigger is best-effort.
        result["triggered"] = False
        result["error"] = f"{type(e).__name__}: {e}"
        result["hint"] = (
            f"Notes written but auto-trigger failed ({e}). Click the "
            "FL Piano roll and press Ctrl+Alt+Y to apply."
        )
    return result
