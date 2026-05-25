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
from ..connection import get_bridge
from ..music import mix_doctor as md


def register(mcp: FastMCP) -> None:
    _RO = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}
    _WR = {"readOnlyHint": False, "destructiveHint": False,
           "idempotentHint": False, "openWorldHint": True}

    @mcp.tool(annotations={"title": "Diagnose the mix (Mix Doctor)", **_RO})
    def fl_diagnose_mix() -> dict:
        """Scan the WHOLE mix and report problems + proposed fixes. READ-ONLY.

        Gathers a thin, paginated snapshot (all-track levels/plugins/routing),
        then runs transparent threshold rules: clipping, headroom, level
        imbalance, missing high-pass (heuristic), ungrouped related tracks, and
        EQ-band clashes. Each finding has a severity + the exact evidence; each
        proposal is a concrete, approvable change.

        Level rules (clipping/headroom/imbalance) need PLAYBACK: if the project
        is STOPPED, `needs_playback` is true -- ask the user to press play and
        call this again. Applies NOTHING. To apply a proposal, get the user's
        ok, then call fl_apply_mix_fix (volume) / fl_group_tracks (grouping) /
        fl_apply_eq_intent (EQ).
        """
        try:
            bridge = get_bridge()
            snap = md.gather_snapshot(bridge)            # sustained peaks while playing
            diag = md.diagnose(snap)
            plan = md.plan_fixes(snap)
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}

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
            "ok": True,
            "playing": snap["playing"],
            "needs_playback": not snap["playing"],
            "track_count": snap["track_count"],
            "summary": plan["summary"],
            "guidance": ("Project is STOPPED -- press PLAY in FL and call fl_diagnose_mix "
                         "again for level diagnosis (clipping/headroom/imbalance)."
                         if not snap["playing"] else
                         "Levels sampled over a sustained window; findings are trustworthy."),
            "findings": [{k: f[k] for k in ("rule", "severity", "track", "evidence", "message")}
                         for f in diag["findings"]],
            "proposals": proposals,
            "notes": plan["notes"],
        }

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
