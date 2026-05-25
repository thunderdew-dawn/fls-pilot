"""MCP tools for Mix Doctor: diagnose the whole mix + apply gated fixes.

fl_diagnose_mix is READ-ONLY (thin paginated snapshot + transparent threshold
diagnosis). fl_apply_mix_fix applies ONE proposed fix through the safety layer
(snapshot -> write -> FRESH readback -> rollback-able). Diagnosis never writes;
apply is a separate explicit call so the human approves each fix in conversation.

Grouping and EQ moves are surfaced as proposals but applied via the existing
fl_group_tracks / fl_apply_eq_intent tools (reuse, not re-implement).
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

from .. import protocol, safety
from ..connection import fetch_all_pages, get_bridge
from ..music import mix_doctor as md


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}
    _WR = {"readOnlyHint": False, "destructiveHint": False,
           "idempotentHint": False, "openWorldHint": True}

    def _result(snap):
        """Diagnose + plan a gathered snapshot -> the common tool payload."""
        diag = md.diagnose(snap)
        plan = md.plan_fixes(snap)
        proposals = []
        for p in plan["plans"]:
            prop = {"id": p["id"], "kind": p["kind"], "severity": p["severity"],
                    "actionable": bool(p.get("actionable")),
                    "human": p["human"], "reason": p.get("reason", "")}
            if p["kind"] == "trim_volume":
                prop["track"] = p["track"]
                prop["target_db"] = p["target_fader_db"]
            elif p["kind"] == "group":
                prop["tracks"] = p.get("args")
            proposals.append(prop)
        return {
            "track_count": snap["track_count"],
            "levels_valid": snap.get("levels_valid"),
            "summary": plan["summary"],
            "findings": [{k: f[k] for k in ("rule", "severity", "track", "evidence", "message")}
                         for f in diag["findings"]],
            "proposals": proposals,
            "notes": plan["notes"],
        }

    @mcp.tool(annotations={"title": "Diagnose the mix (Mix Doctor)", **_RO})
    def fl_diagnose_mix() -> dict:
        """Scan the WHOLE mix and report problems + proposed fixes. READ-ONLY.

        Transparent threshold rules (clipping, headroom, level imbalance, missing
        high-pass, ungrouped tracks, EQ clashes) on a thin paginated snapshot;
        returns findings (severity + exact evidence) + concrete proposals.

        IMPORTANT: this samples peaks over only ~1.2s -- one MOMENT of the song,
        so it can MISS clipping in a drop/chorus that isn't playing right now. For
        full-song-accurate levels use WATCH mode: fl_mix_watch_start -> play the
        whole song -> fl_mix_watch_stop. If stopped, level rules are skipped
        (needs_playback). Applies nothing.
        """
        try:
            snap = md.gather_snapshot(get_bridge())
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        playing = snap["playing"]
        guidance = ("Project STOPPED -- press PLAY and call again, or use watch mode "
                    "(fl_mix_watch_start -> play full song -> fl_mix_watch_stop)."
                    if not playing else
                    "NOTE: ~1.2s sample (one moment). For full-song peaks (catch the "
                    "drop/chorus) use fl_mix_watch_start -> play -> fl_mix_watch_stop.")
        return {"ok": True, "playing": playing, "needs_playback": not playing,
                "peak_source": snap.get("peak_window", {}).get("source"),
                "guidance": guidance, **_result(snap)}

    @mcp.tool(annotations={"title": "Apply a Mix Doctor fix (gated)", **_WR})
    def fl_apply_mix_fix(
        kind: Annotated[str, Field(description="Fix kind. Currently 'trim_volume' (the proven, safe one).")],
        track: Annotated[Optional[int], Field(ge=0, description="Mixer track index (for trim_volume).")] = None,
        target_db: Annotated[Optional[float], Field(description="Absolute target fader level in dB, e.g. -3.0.")] = None,
    ) -> dict:
        """Apply ONE Mix Doctor fix via the safety layer: snapshot -> write ->
        FRESH readback -> rollback-able with fl_rollback_last_change.

        Call this ONLY after the user approves the exact change in conversation
        (Mix Doctor never auto-applies). 'trim_volume' sets a mixer track's fader
        to target_db. For grouping use fl_group_tracks; for EQ use
        fl_apply_eq_intent.
        """
        if kind != "trim_volume":
            return {"ok": False, "error": "only 'trim_volume' is wired here; use "
                    "fl_group_tracks (grouping) or fl_apply_eq_intent (EQ moves)."}
        if track is None or target_db is None:
            return {"ok": False, "error": "trim_volume needs both track and target_db."}
        try:
            bridge = get_bridge()
            res = safety.safe_write(
                bridge, tool="mixer_set_volume", scope="mixer_track:%d" % track,
                command=protocol.CMD_MIXER_SET_VOLUME,
                params={"track": track, "value": target_db, "unit": "db"},
                build_restore=lambda b: {"command": protocol.CMD_MIXER_SET_VOLUME,
                                         "params": {"track": track, "value": b["vol_norm"],
                                                    "unit": "normalized"}})
            if res.get("dry_run"):
                return {"ok": True, "dry_run": True, "planned": res.get("planned")}
            before, after = res.get("before") or {}, res.get("after") or {}
            applied = (after.get("vol_db") is not None
                       and abs(after["vol_db"] - target_db) <= 0.6)
            return {"ok": True, "kind": kind, "track": track,
                    "name": after.get("name") or before.get("name"),
                    "before_db": before.get("vol_db"), "after_db": after.get("vol_db"),
                    "target_db": target_db, "applied": applied,
                    "undo": "call fl_rollback_last_change to revert this"}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    @mcp.tool(annotations={"title": "Start full-song peak watch (Mix Doctor)", **_RO})
    def fl_mix_watch_start(
        interval_ms: Annotated[int, Field(ge=50, le=1000,
                     description="Poll interval per round in ms (default 150).")] = 150,
    ) -> dict:
        """Begin a peak-HOLD watch: continuously sample every mixer track's peak,
        keeping a RUNNING MAX per track, until fl_mix_watch_stop. Tell the user to
        PLAY the whole song (or at least the loudest section / the drop) while this
        runs -- then stop for full-song-accurate level diagnosis. Read-only."""
        try:
            bridge = get_bridge()
            tracks = fetch_all_pages(bridge, protocol.CMD_MIXER_LIST_TRACKS, "tracks").get("tracks", [])
            indices = [t.get("i", t.get("index")) for t in tracks]
            r = md.get_watcher().start(bridge, indices, interval_ms=interval_ms)
            if not r.get("ok"):
                return {"ok": False, "error": r.get("error"),
                        "hint": "a watch is already running -- call fl_mix_watch_stop to finish it"}
            return {"ok": True, "watching_tracks": r["watching"], "interval_ms": r["interval_ms"],
                    "message": "Watching peaks (running max). PLAY the full song / the drop, "
                               "then call fl_mix_watch_stop for full-song diagnosis."}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    @mcp.tool(annotations={"title": "Peak watch status (Mix Doctor)", **_RO})
    def fl_mix_watch_status() -> dict:
        """Is a peak watch running, and for how long / how many polls so far?"""
        return {"ok": True, **md.get_watcher().status()}

    @mcp.tool(annotations={"title": "Stop peak watch + diagnose (Mix Doctor)", **_RO})
    def fl_mix_watch_stop() -> dict:
        """Stop the peak watch and diagnose on the FULL-SONG running-max peaks
        captured across the whole watch (accurate clipping/headroom/imbalance vs
        the ~1.2s snapshot). Read-only -- proposes fixes, applies nothing."""
        try:
            peaks_lin, reads, elapsed = md.get_watcher().stop()
            if not peaks_lin or reads == 0 or max(peaks_lin.values(), default=0.0) <= 0.0:
                return {"ok": False, "reads": reads, "elapsed_s": round(elapsed, 1),
                        "error": "no peaks captured -- was the song playing during the watch?"}
            snap = md.gather_snapshot(get_bridge(), peaks_override=peaks_lin)
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        return {"ok": True, "peak_source": "watch (full-song running max)",
                "watch": {"reads": reads, "elapsed_s": round(elapsed, 1)},
                "guidance": "Levels are full-song maxima -- trustworthy for clipping/headroom.",
                **_result(snap)}
