"""Piano-roll note authoring -- the generate-script bridge.

FL's pyscript sandbox blocks file I/O (read AND write), so we can't pass note
data via a job file. Instead we GENERATE a .pyscript with the notes baked in
(pyscript_gen), write it into FL's Piano roll scripts folder, then force-focus
FL and fire Ctrl+Alt+Y "Run last script again" (pyscript_trigger). FL re-reads
the file on that hotkey, so the fresh notes apply with no manual click.

This runs in a process that can write files + send keystrokes (the daemon, or
a normally-launched MCP server). Under the Store/MSIX Claude Desktop the MCP
server can't, so it delegates here via the daemon's "apply_notes" op.

One-time setup the user must do: run MCP_Apply once from the piano-roll
Scripting menu so it becomes FL's "last script" (then Ctrl+Alt+Y targets it).
"""

from __future__ import annotations

from .pyscript_gen import write_apply_script


def apply_notes(notes, mode="replace", trigger=True):
    """Write the notes into MCP_Apply.pyscript and (optionally) trigger FL.

    notes: list of {pitch, time_bars, length_bars, velocity}.
    Returns {ok, count, script, triggered, focused, hint?}.
    """
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
        result["setup"] = ("If notes did not appear: run 'MCP Apply' ONCE from the "
                           "Piano roll Scripting menu this FL session (the only "
                           "manual step -- arms Ctrl+Alt+Y; no FL API to automate it).")
        if not trig.get("focused"):
            result["hint"] = ("Could not focus FL automatically -- click the FL "
                              "Piano roll and press Ctrl+Alt+Y.")
    except Exception as e:
        # Script is written regardless; trigger is best-effort.
        result["triggered"] = False
        result["error"] = "%s: %s" % (type(e).__name__, e)
        result["hint"] = ("Notes written but auto-trigger failed (%s). Click the "
                          "FL Piano roll and press Ctrl+Alt+Y to apply." % e)
    return result
